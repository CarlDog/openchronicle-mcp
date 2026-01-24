from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from collections import OrderedDict
from collections.abc import Sequence
from io import TextIOBase
from queue import Empty, Queue
from typing import TextIO

from openchronicle.core.application.routing.pool_config import load_pool_config
from openchronicle.core.application.routing.router_policy import RouterPolicy
from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.use_cases import (
    ask_conversation,
    convo_mode,
    explain_turn,
    export_convo,
    run_task,
    show_conversation,
    task_once,
)
from openchronicle.core.domain.models.project import Event, Task, TaskStatus
from openchronicle.core.domain.ports.llm_port import LLMProviderError
from openchronicle.core.domain.ports.privacy_gate_port import PrivacyGatePort
from openchronicle.core.domain.services.verification import VerificationResult, VerificationService
from openchronicle.core.infrastructure.config.settings import PrivacyOutboundSettings
from openchronicle.core.infrastructure.privacy.rule_privacy import is_external_provider
from openchronicle.core.infrastructure.routing.rule_router import RuleInteractionRouter

STDIO_RPC_PROTOCOL_VERSION = "1"
MAX_REQUEST_CACHE_ENTRIES = 256
SUPPORTED_COMMANDS: tuple[str, ...] = (
    "convo.ask",
    "convo.ask_async",
    "convo.export",
    "convo.mode",
    "convo.show",
    "convo.verify",
    "privacy.preview",
    "task.get",
    "task.list",
    "task.run_one",
    "task.run_many",
    "system.commands",
    "system.health",
    "system.info",
    "system.ping",
    "system.shutdown",
)


def json_error_payload(
    *,
    error_code: str | None,
    message: str,
    hint: str | None,
    details: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "error_code": error_code,
        "message": message,
        "hint": hint,
        "details": details,
    }


def json_envelope(
    *,
    command: str,
    ok: bool,
    result: dict[str, object] | None,
    error: dict[str, object] | None,
) -> dict[str, object]:
    return {
        "command": command,
        "ok": ok,
        "result": result,
        "error": error,
    }


def _attach_request_id(payload: dict[str, object], request_id: str | None) -> None:
    if request_id is not None:
        payload["request_id"] = request_id


def json_dumps_line(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True)


def coerce_int(value: object, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return default


def _parse_run_many_limit(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("Limit must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    raise ValueError("Limit must be an integer")


def _sanitize_details(details: dict[str, object]) -> dict[str, object]:
    sanitized: dict[str, object] = {}
    for key, value in details.items():
        key_lower = key.lower()
        if "prompt" in key_lower or "user_text" in key_lower or "assistant_text" in key_lower:
            continue
        sanitized[key] = value
    return sanitized


def _normalize_error(exc: Exception) -> dict[str, object]:
    if hasattr(exc, "error_code") or hasattr(exc, "hint"):
        error_code = getattr(exc, "error_code", None)
        hint = getattr(exc, "hint", None)
        details: dict[str, object] = {}

        configured_providers = getattr(exc, "configured_providers", None)
        if configured_providers:
            details["configured_providers"] = configured_providers

        configured_pools = getattr(exc, "configured_pools", None)
        if configured_pools:
            details["configured_pools"] = configured_pools

        config_dir = getattr(exc, "config_dir", None)
        if config_dir:
            details["config_dir"] = config_dir

        extra_details = getattr(exc, "details", None)
        if isinstance(extra_details, dict):
            details.update(extra_details)

        if details:
            details = _sanitize_details(details)
            try:
                json.dumps(details)
            except TypeError:
                details = {}

        return json_error_payload(
            error_code=error_code,
            message=str(exc),
            hint=hint,
            details=details or None,
        )

    if isinstance(exc, ValueError):
        return json_error_payload(
            error_code="INVALID_ARGUMENT",
            message=str(exc),
            hint=None,
            details=None,
        )

    return json_error_payload(
        error_code="INTERNAL_ERROR",
        message="Internal error",
        hint="See stderr logs for details.",
        details=None,
    )


def _configured_providers(pool_config: object) -> list[str]:
    providers: set[str] = set()
    for pool_name in ("fast_pool", "quality_pool", "nsfw_pool"):
        pool = getattr(pool_config, pool_name, [])
        for candidate in pool:
            provider = getattr(candidate, "provider", None)
            if isinstance(provider, str) and provider:
                providers.add(provider)
    return sorted(providers)


def _pool_candidates(pool: Sequence[object]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for candidate in pool:
        provider = getattr(candidate, "provider", None)
        model = getattr(candidate, "model", None)
        weight = getattr(candidate, "weight", None)
        if isinstance(provider, str) and isinstance(model, str):
            results.append({"provider": provider, "model": model, "weight": weight})
    return results


def _task_summary(task: Task) -> dict[str, object]:
    summary: dict[str, object] = {
        "task_id": task.id,
        "type": task.type,
        "status": task.status.value,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }
    if task.parent_task_id:
        summary["parent_task_id"] = task.parent_task_id
    return summary


def _resolve_privacy_settings(
    settings: PrivacyOutboundSettings,
    overrides: dict[str, object],
) -> tuple[PrivacyOutboundSettings, str | None]:
    mode_override = overrides.get("mode_override")
    if mode_override is not None and (
        not isinstance(mode_override, str) or mode_override not in {"off", "warn", "redact", "block"}
    ):
        return settings, "Invalid mode_override"

    external_only_override = overrides.get("external_only_override")
    if external_only_override is not None and not isinstance(external_only_override, bool):
        return settings, "Invalid external_only_override"

    categories_override = overrides.get("categories_override")
    if categories_override is not None and (
        not isinstance(categories_override, list) or not all(isinstance(item, str) for item in categories_override)
    ):
        return settings, "Invalid categories_override"

    redact_style_override = overrides.get("redact_style_override")
    if redact_style_override is not None and (
        not isinstance(redact_style_override, str) or redact_style_override != "mask"
    ):
        return settings, "Invalid redact_style_override"

    resolved = PrivacyOutboundSettings(
        mode=mode_override if isinstance(mode_override, str) else settings.mode,
        external_only=external_only_override if isinstance(external_only_override, bool) else settings.external_only,
        categories=categories_override if isinstance(categories_override, list) else list(settings.categories),
        redact_style=redact_style_override if isinstance(redact_style_override, str) else settings.redact_style,
        log_events=settings.log_events,
    )
    return resolved, None


def dispatch_json_command(
    container: CoreContainer,
    command: str,
    args: dict[str, object],
) -> dict[str, object]:
    if command not in SUPPORTED_COMMANDS:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code="UNKNOWN_COMMAND",
                message=f"Unsupported command: {command}",
                hint=None,
            ),
        )

    if command == "system.info":
        return json_envelope(
            command=command,
            ok=True,
            result={
                "name": "openchronicle",
                "protocol_version": STDIO_RPC_PROTOCOL_VERSION,
                "capabilities": {
                    "rpc": True,
                    "serve": True,
                },
            },
            error=None,
        )

    if command == "system.commands":
        return json_envelope(
            command=command,
            ok=True,
            result={"commands": sorted(SUPPORTED_COMMANDS)},
            error=None,
        )

    if command == "system.health":
        config_dir = os.getenv("OC_CONFIG_DIR", "config")
        config_ok = os.path.isdir(config_dir) and os.access(config_dir, os.R_OK)

        pool_config = load_pool_config() if config_ok else None
        pools: list[str] = []
        if pool_config is not None:
            if pool_config.fast_pool:
                pools.append("FAST")
            if pool_config.nsfw_pool:
                pools.append("NSFW")
            if pool_config.quality_pool:
                pools.append("QUALITY")
        pools.sort()

        nsfw_pool_configured = bool(pool_config.nsfw_pool) if pool_config is not None else False

        storage_ok = False
        try:
            conn = getattr(container.storage, "_conn", None)
            if conn is not None:
                conn.execute("SELECT 1").fetchone()
                storage_ok = True
        except Exception:
            storage_ok = False

        overall_ok = storage_ok and config_ok

        return json_envelope(
            command=command,
            ok=True,
            result={
                "ok": overall_ok,
                "storage": {
                    "type": "sqlite",
                    "reachable": storage_ok,
                },
                "config": {
                    "config_dir": config_dir,
                    "pools": pools,
                    "nsfw_pool_configured": nsfw_pool_configured,
                },
            },
            error=None,
        )

    if command == "system.ping":
        return json_envelope(
            command=command,
            ok=True,
            result={"pong": True},
            error=None,
        )

    if command == "system.shutdown":
        return json_envelope(
            command=command,
            ok=True,
            result={"shutdown": True, "reason": "requested"},
            error=None,
        )

    try:
        if command == "convo.export":
            conversation_id = str(args.get("conversation_id", ""))
            include_explain = bool(args.get("explain", False))
            include_verify = bool(args.get("verify", False))

            export = export_convo.execute(
                storage=container.storage,
                convo_store=container.storage,
                conversation_id=conversation_id,
                include_explain=include_explain,
                include_verify=include_verify,
            )

            ok = True
            if include_verify:
                verification = export.get("verification") if isinstance(export, dict) else None
                verification_dict = verification if isinstance(verification, dict) else {}
                ok = verification_dict.get("ok") is True

            return json_envelope(
                command=command,
                ok=ok,
                result=export,
                error=None
                if ok
                else json_error_payload(
                    error_code=None,
                    message="verification failed",
                    hint=None,
                ),
            )

        if command == "convo.verify":
            conversation_id = str(args.get("conversation_id", ""))
            verification_service = VerificationService(container.storage)
            convo_verify_result: VerificationResult = verification_service.verify_task_chain(conversation_id)

            first_mismatch = convo_verify_result.first_mismatch or {}
            expected_hash = first_mismatch.get("expected_hash")
            actual_hash = first_mismatch.get("computed_hash")
            if expected_hash is None and actual_hash is None:
                expected_hash = first_mismatch.get("expected_prev_hash")
                actual_hash = first_mismatch.get("actual_prev_hash")
            verification_payload = {
                "ok": convo_verify_result.success,
                "failure_event_id": first_mismatch.get("event_id"),
                "expected_hash": expected_hash,
                "actual_hash": actual_hash,
            }

            return json_envelope(
                command=command,
                ok=convo_verify_result.success,
                result={
                    "conversation_id": conversation_id,
                    "verification": verification_payload,
                },
                error=None
                if convo_verify_result.success
                else json_error_payload(
                    error_code=None,
                    message=convo_verify_result.error_message or "verification failed",
                    hint=None,
                ),
            )

        if command == "convo.mode":
            conversation_id = str(args.get("conversation_id", ""))
            mode_value = args.get("mode")
            if isinstance(mode_value, str) and mode_value:
                conversation_mode = convo_mode.set_mode(
                    convo_store=container.storage,
                    conversation_id=conversation_id,
                    mode=mode_value,
                )
            else:
                conversation_mode = convo_mode.get_mode(
                    convo_store=container.storage,
                    conversation_id=conversation_id,
                )

            return json_envelope(
                command=command,
                ok=True,
                result={
                    "conversation_id": conversation_id,
                    "mode": conversation_mode,
                },
                error=None,
            )

        if command == "convo.show":
            conversation_id = str(args.get("conversation_id", ""))
            limit_raw = args.get("limit")
            limit_value = coerce_int(limit_raw, 0)
            limit: int | None = limit_value if limit_value > 0 else None
            include_explain = bool(args.get("explain", False))

            conversation, turns = show_conversation.execute(
                convo_store=container.storage,
                conversation_id=conversation_id,
                limit=limit,
            )

            turns_payload: list[dict[str, object]] = []
            for turn in turns:
                explain_payload: dict[str, object] | None = None
                if include_explain:
                    try:
                        explain_payload = explain_turn.execute(
                            storage=container.storage,
                            conversation_id=conversation_id,
                            turn_id=turn.id,
                        )
                    except ValueError:
                        explain_payload = None
                turns_payload.append(
                    {
                        "turn_id": turn.id,
                        "turn_index": turn.turn_index,
                        "user_text": turn.user_text,
                        "assistant_text": turn.assistant_text,
                        "explain": explain_payload if include_explain else None,
                    }
                )

            return json_envelope(
                command=command,
                ok=True,
                result={
                    "conversation_id": conversation.id,
                    "mode": conversation.mode,
                    "turns": turns_payload,
                },
                error=None,
            )

        if command == "convo.ask":
            conversation_id = str(args.get("conversation_id", ""))
            prompt_text = str(args.get("prompt", ""))
            last_n = coerce_int(args.get("last_n"), 10)
            top_k_memory = coerce_int(args.get("top_k_memory"), 8)
            include_pinned_memory = bool(args.get("include_pinned_memory", True))
            include_explain = bool(args.get("explain", False))
            allow_pii = bool(args.get("allow_pii", False))

            async def _run() -> dict[str, object]:
                turn = await ask_conversation.execute(
                    convo_store=container.storage,
                    storage=container.storage,
                    memory_store=container.storage,
                    llm=container.llm,
                    interaction_router=container.interaction_router,
                    emit_event=container.event_logger.append,
                    conversation_id=conversation_id,
                    prompt_text=prompt_text,
                    last_n=last_n,
                    top_k_memory=top_k_memory,
                    include_pinned_memory=include_pinned_memory,
                    allow_pii=allow_pii,
                    privacy_gate=getattr(container, "privacy_gate", None),
                    privacy_settings=getattr(container, "privacy_settings", None),
                )

                explain_payload: dict[str, object] | None = None
                if include_explain:
                    try:
                        explain_payload = explain_turn.execute(
                            storage=container.storage,
                            conversation_id=conversation_id,
                            turn_id=turn.id,
                        )
                    except ValueError:
                        explain_payload = None
                return {
                    "conversation_id": turn.conversation_id,
                    "turn_id": turn.id,
                    "turn_index": turn.turn_index,
                    "assistant_text": turn.assistant_text,
                    "explain": explain_payload if include_explain else None,
                }

            result = asyncio.run(_run())
            return json_envelope(
                command=command,
                ok=True,
                result=result,
                error=None,
            )

        if command == "convo.ask_async":
            conversation_id = str(args.get("conversation_id", ""))
            prompt_text = str(args.get("prompt", ""))
            include_explain = bool(args.get("explain", False))
            allow_pii = bool(args.get("allow_pii", False))
            metadata_value = args.get("metadata")
            metadata = metadata_value if isinstance(metadata_value, dict) else None

            conversation, recent_turns = show_conversation.execute(
                convo_store=container.storage,
                conversation_id=conversation_id,
                limit=10,
            )

            effective_mode = (conversation.mode or "general").strip().lower()
            if effective_mode not in {"general", "persona", "story"}:
                effective_mode = "general"

            router_hint = RuleInteractionRouter().analyze(user_text=prompt_text, recent_turns=recent_turns)
            if router_hint.requires_nsfw_capable_model and effective_mode in {"persona", "story"}:
                router = RouterPolicy()
                nsfw_pool = router.pool_config.nsfw_pool
                if not nsfw_pool:
                    config_dir = os.getenv("OC_CONFIG_DIR", "config")
                    configured_providers = _configured_providers(router.pool_config)
                    providers_str = ", ".join(configured_providers) if configured_providers else "none"
                    raise LLMProviderError(
                        "NSFW pool not configured",
                        error_code="NSFW_POOL_NOT_CONFIGURED",
                        hint=(
                            "Set OC_LLM_POOL_NSFW in your environment or config under OC_CONFIG_DIR="
                            f"{config_dir} to a pool that supports NSFW-capable persona/story mode. "
                            f"Configured providers: {providers_str}."
                        ),
                        configured_providers=configured_providers,
                        details={
                            "config_dir": config_dir,
                            "configured_providers": configured_providers,
                            "fast_pool": _pool_candidates(router.pool_config.fast_pool),
                            "quality_pool": _pool_candidates(router.pool_config.quality_pool),
                            "nsfw_pool": _pool_candidates(router.pool_config.nsfw_pool),
                        },
                    )

            task_payload: dict[str, object] = {
                "conversation_id": conversation_id,
                "prompt": prompt_text,
                "explain": include_explain,
                "allow_pii": allow_pii,
            }
            if metadata is not None:
                task_payload["metadata"] = metadata

            task = run_task.submit(
                container.orchestrator,
                project_id=conversation.project_id,
                task_type="convo.ask",
                payload=task_payload,
            )

            container.event_logger.append(
                Event(
                    project_id=conversation.project_id,
                    task_id=task.id,
                    type="convo.ask_queued",
                    payload={
                        "conversation_id": conversation_id,
                        "explain": include_explain,
                        "allow_pii": allow_pii,
                    },
                )
            )

            return json_envelope(
                command=command,
                ok=True,
                result={
                    "conversation_id": conversation_id,
                    "task_id": task.id,
                    "status": "queued",
                },
                error=None,
            )

        if command == "privacy.preview":
            text_value = args.get("text")
            if not isinstance(text_value, str):
                return json_envelope(
                    command=command,
                    ok=False,
                    result=None,
                    error=json_error_payload(
                        error_code="INVALID_ARGUMENT",
                        message="Request 'text' must be a string",
                        hint=None,
                    ),
                )

            provider_value = args.get("provider")
            provider = provider_value if isinstance(provider_value, str) else None

            privacy_gate = getattr(container, "privacy_gate", None)
            privacy_settings = getattr(container, "privacy_settings", None)
            if not isinstance(privacy_gate, PrivacyGatePort) or not isinstance(
                privacy_settings, PrivacyOutboundSettings
            ):
                return json_envelope(
                    command=command,
                    ok=False,
                    result=None,
                    error=json_error_payload(
                        error_code="INTERNAL_ERROR",
                        message="Privacy gate not configured",
                        hint=None,
                    ),
                )

            resolved_settings, error_message = _resolve_privacy_settings(privacy_settings, args)
            if error_message is not None:
                return json_envelope(
                    command=command,
                    ok=False,
                    result=None,
                    error=json_error_payload(
                        error_code="INVALID_ARGUMENT",
                        message=error_message,
                        hint=None,
                    ),
                )

            effective_mode = resolved_settings.mode
            applies = effective_mode != "off"
            if (
                applies
                and resolved_settings.external_only
                and provider is not None
                and not is_external_provider(provider)
            ):
                applies = False
            if provider is None and resolved_settings.external_only:
                applies = True

            analysis_mode = "warn" if applies and effective_mode != "off" else "warn"
            if effective_mode == "off":
                analysis_mode = "off"
            if applies:
                analysis_mode = effective_mode

            redacted_text, report = privacy_gate.analyze_and_apply(
                text=text_value,
                mode=analysis_mode,
                redact_style=resolved_settings.redact_style,
                categories=resolved_settings.categories,
            )

            categories = sorted(report.categories)
            counts = {key: report.counts[key] for key in categories}
            result_payload: dict[str, object] = {
                "effective_policy": {
                    "mode": effective_mode,
                    "external_only": resolved_settings.external_only,
                    "applies": applies,
                },
                "report": {
                    "categories": categories,
                    "counts": counts,
                    "redactions_applied": report.redactions_applied if applies else False,
                    "summary": report.summary,
                },
            }
            if applies and effective_mode == "redact":
                result_payload["redacted_text"] = redacted_text

            return json_envelope(
                command=command,
                ok=True,
                result=result_payload,
                error=None,
            )

        if command == "task.get":
            task_id = str(args.get("task_id", ""))
            task_maybe = container.storage.get_task(task_id)
            if task_maybe is None:
                return json_envelope(
                    command=command,
                    ok=False,
                    result=None,
                    error=json_error_payload(
                        error_code="TASK_NOT_FOUND",
                        message=f"Task not found: {task_id}",
                        hint=None,
                    ),
                )

            return json_envelope(
                command=command,
                ok=True,
                result={"task": _task_summary(task_maybe)},
                error=None,
            )

        if command == "task.list":
            status_value = args.get("status")
            status_filter = str(status_value).lower() if isinstance(status_value, str) else None
            if status_filter is not None and status_filter not in {status.value for status in TaskStatus}:
                return json_envelope(
                    command=command,
                    ok=False,
                    result=None,
                    error=json_error_payload(
                        error_code="INVALID_ARGUMENT",
                        message=f"Unsupported status filter: {status_value}",
                        hint=None,
                    ),
                )

            limit = coerce_int(args.get("limit"), 50)
            if limit <= 0:
                limit = 50
            limit = min(limit, 200)
            offset = coerce_int(args.get("offset"), 0)
            if offset < 0:
                offset = 0

            sort_key = args.get("sort", "created_at")
            if sort_key != "created_at":
                return json_envelope(
                    command=command,
                    ok=False,
                    result=None,
                    error=json_error_payload(
                        error_code="INVALID_ARGUMENT",
                        message=f"Unsupported sort key: {sort_key}",
                        hint=None,
                    ),
                )

            order = args.get("order", "desc")
            if order not in {"asc", "desc"}:
                return json_envelope(
                    command=command,
                    ok=False,
                    result=None,
                    error=json_error_payload(
                        error_code="INVALID_ARGUMENT",
                        message=f"Unsupported sort order: {order}",
                        hint=None,
                    ),
                )

            tasks: list[Task] = []
            for project in container.storage.list_projects():
                tasks.extend(container.storage.list_tasks_by_project(project.id))

            if status_filter is not None:
                tasks = [task for task in tasks if task.status.value == status_filter]

            tasks.sort(key=lambda task: (task.created_at, task.id), reverse=order == "desc")
            total = len(tasks)
            sliced = tasks[offset : offset + limit]

            return json_envelope(
                command=command,
                ok=True,
                result={
                    "tasks": [_task_summary(task) for task in sliced],
                    "total": total,
                },
                error=None,
            )

        if command == "task.run_one":
            task_type_value = args.get("type", "convo.ask")
            if not isinstance(task_type_value, str) or task_type_value != "convo.ask":
                return json_envelope(
                    command=command,
                    ok=False,
                    result=None,
                    error=json_error_payload(
                        error_code="INVALID_ARGUMENT",
                        message="Only task type 'convo.ask' is supported",
                        hint=None,
                    ),
                )

            result = asyncio.run(
                task_once.execute(
                    storage=container.storage,
                    convo_store=container.storage,
                    memory_store=container.storage,
                    llm=container.llm,
                    interaction_router=container.interaction_router,
                    emit_event=container.event_logger.append,
                    privacy_gate=getattr(container, "privacy_gate", None),
                    privacy_settings=getattr(container, "privacy_settings", None),
                    task_type=task_type_value,
                )
            )

            return json_envelope(
                command=command,
                ok=True,
                result=result,
                error=None,
            )

        if command == "task.run_many":
            task_type_value = args.get("type", "convo.ask")
            if not isinstance(task_type_value, str) or task_type_value != "convo.ask":
                return json_envelope(
                    command=command,
                    ok=False,
                    result=None,
                    error=json_error_payload(
                        error_code="INVALID_ARGUMENT",
                        message="Only task type 'convo.ask' is supported",
                        hint=None,
                    ),
                )

            try:
                run_many_limit = _parse_run_many_limit(args.get("limit", 10))
            except ValueError:
                return json_envelope(
                    command=command,
                    ok=False,
                    result=None,
                    error=json_error_payload(
                        error_code="INVALID_ARGUMENT",
                        message="Limit must be an integer",
                        hint=None,
                    ),
                )

            if run_many_limit < 1:
                return json_envelope(
                    command=command,
                    ok=False,
                    result=None,
                    error=json_error_payload(
                        error_code="INVALID_ARGUMENT",
                        message="Limit must be at least 1",
                        hint=None,
                    ),
                )
            if run_many_limit > 200:
                run_many_limit = 200

            max_seconds_value = args.get("max_seconds", 0)
            if isinstance(max_seconds_value, bool):
                return json_envelope(
                    command=command,
                    ok=False,
                    result=None,
                    error=json_error_payload(
                        error_code="INVALID_ARGUMENT",
                        message="max_seconds must be a number",
                        hint=None,
                    ),
                )
            if isinstance(max_seconds_value, int | float):
                max_seconds = float(max_seconds_value)
            else:
                return json_envelope(
                    command=command,
                    ok=False,
                    result=None,
                    error=json_error_payload(
                        error_code="INVALID_ARGUMENT",
                        message="max_seconds must be a number",
                        hint=None,
                    ),
                )

            if max_seconds < 0:
                return json_envelope(
                    command=command,
                    ok=False,
                    result=None,
                    error=json_error_payload(
                        error_code="INVALID_ARGUMENT",
                        message="max_seconds must be non-negative",
                        hint=None,
                    ),
                )

            result = asyncio.run(
                task_once.execute_many(
                    storage=container.storage,
                    convo_store=container.storage,
                    memory_store=container.storage,
                    llm=container.llm,
                    interaction_router=container.interaction_router,
                    emit_event=container.event_logger.append,
                    privacy_gate=getattr(container, "privacy_gate", None),
                    privacy_settings=getattr(container, "privacy_settings", None),
                    task_type=task_type_value,
                    limit=run_many_limit,
                    max_seconds=max_seconds,
                )
            )

            return json_envelope(
                command=command,
                ok=True,
                result=result,
                error=None,
            )

    except Exception as exc:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=_normalize_error(exc),
        )

    return json_envelope(
        command=command,
        ok=False,
        result=None,
        error=json_error_payload(
            error_code="UNKNOWN_COMMAND",
            message=f"Unsupported command: {command}",
            hint=None,
        ),
    )


def dispatch_request(container: CoreContainer, request: dict[str, object]) -> dict[str, object]:
    command_value = request.get("command")
    args_value = request.get("args")
    protocol_value = request.get("protocol_version")
    request_id_value = request.get("request_id")
    if request_id_value is not None and not isinstance(request_id_value, str):
        payload = json_envelope(
            command=str(command_value) if isinstance(command_value, str) else "unknown",
            ok=False,
            result=None,
            error=json_error_payload(
                error_code="INVALID_REQUEST",
                message="Request 'request_id' must be a string",
                hint=None,
            ),
        )
        payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
        return payload

    request_id = request_id_value if isinstance(request_id_value, str) else None

    if protocol_value is not None and not isinstance(protocol_value, str):
        payload = json_envelope(
            command=str(command_value) if isinstance(command_value, str) else "unknown",
            ok=False,
            result=None,
            error=json_error_payload(
                error_code="INVALID_REQUEST",
                message="Request 'protocol_version' must be a string",
                hint=None,
            ),
        )
        payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
        _attach_request_id(payload, request_id)
        return payload

    if protocol_value is not None and protocol_value != STDIO_RPC_PROTOCOL_VERSION:
        payload = json_envelope(
            command=str(command_value) if isinstance(command_value, str) else "unknown",
            ok=False,
            result=None,
            error=json_error_payload(
                error_code="UNSUPPORTED_PROTOCOL_VERSION",
                message=f"Unsupported protocol_version: {protocol_value}",
                hint='Use protocol_version "1".',
            ),
        )
        payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
        _attach_request_id(payload, request_id)
        return payload

    if not isinstance(command_value, str):
        payload = json_envelope(
            command=str(command_value) if command_value is not None else "unknown",
            ok=False,
            result=None,
            error=json_error_payload(
                error_code="INVALID_REQUEST",
                message="Request must include 'command' string",
                hint=None,
            ),
        )
        payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
        _attach_request_id(payload, request_id)
        return payload

    if args_value is None:
        args_value = {}
    if not isinstance(args_value, dict):
        payload = json_envelope(
            command=command_value,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code="INVALID_REQUEST",
                message="Request 'args' must be an object",
                hint=None,
            ),
        )
        payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
        _attach_request_id(payload, request_id)
        return payload

    response = dispatch_json_command(container, command_value, args_value)
    response["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
    _attach_request_id(response, request_id)
    return response


def serve_stdio(
    container: CoreContainer,
    *,
    input_stream: TextIO | TextIOBase | None = None,
    output_stream: TextIO | TextIOBase | None = None,
    idle_timeout_seconds: int = 0,
) -> int:
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout
    assert input_stream is not None
    assert output_stream is not None

    cache: OrderedDict[str, dict[str, object]] = OrderedDict()
    queue: Queue[str | None] = Queue()
    stop_event = threading.Event()

    def _reader() -> None:
        while not stop_event.is_set():
            line = input_stream.readline()
            if line == "":
                queue.put(None)
                break
            queue.put(line)

    reader_thread = threading.Thread(target=_reader, daemon=True)
    reader_thread.start()

    while True:
        try:
            line = queue.get(timeout=idle_timeout_seconds) if idle_timeout_seconds > 0 else queue.get()
        except Empty:
            break

        if line is None:
            break
        raw = line.strip()
        if not raw:
            continue
        try:
            request = json.loads(raw)
        except json.JSONDecodeError as exc:
            payload = json_envelope(
                command="unknown",
                ok=False,
                result=None,
                error=json_error_payload(
                    error_code="INVALID_JSON",
                    message=str(exc),
                    hint=None,
                ),
            )
            payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
            output_stream.write(json_dumps_line(payload) + "\n")
            output_stream.flush()
            continue

        if not isinstance(request, dict):
            payload = json_envelope(
                command="unknown",
                ok=False,
                result=None,
                error=json_error_payload(
                    error_code="INVALID_REQUEST",
                    message="Request must be a JSON object",
                    hint=None,
                ),
            )
            payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
            output_stream.write(json_dumps_line(payload) + "\n")
            output_stream.flush()
            continue

        request_id = request.get("request_id") if isinstance(request.get("request_id"), str) else None
        if request_id is not None and request_id in cache:
            cached = cache[request_id]
            output_stream.write(json_dumps_line(cached) + "\n")
            output_stream.flush()
            continue

        response = dispatch_request(container, request)
        if request_id is not None:
            cache[request_id] = response
            if len(cache) > MAX_REQUEST_CACHE_ENTRIES:
                cache.popitem(last=False)

        output_stream.write(json_dumps_line(response) + "\n")
        output_stream.flush()
        if isinstance(request.get("command"), str) and request.get("command") == "system.shutdown":
            break
    stop_event.set()
    return 0
