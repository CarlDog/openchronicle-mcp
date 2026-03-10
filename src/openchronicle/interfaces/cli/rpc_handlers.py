"""RPC command handlers for the stdio JSON-line protocol.

Each handler has the signature:
    def handle_xxx(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]

Returns a json_envelope(...) dict.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Callable
from typing import cast

from openchronicle.core.application.config.settings import PrivacyOutboundSettings
from openchronicle.core.application.policies.provider_policy import is_external_provider
from openchronicle.core.application.routing.pool_config import load_pool_config
from openchronicle.core.application.use_cases import (
    convo_mode,
    explain_turn,
    export_convo,
    show_conversation,
    task_once,
)
from openchronicle.core.application.use_cases.ask_conversation import (
    TelemetryRecorder,
    is_enqueueable_provider_failure,
)
from openchronicle.core.application.use_cases.ask_conversation import (
    enqueue as enqueue_conversation,
)
from openchronicle.core.application.use_cases.ask_conversation import (
    execute as ask_conversation_execute,
)
from openchronicle.core.domain.errors.error_codes import (
    INTERNAL_ERROR,
    INVALID_ARGUMENT,
    INVALID_TASK_TYPE,
    PROJECT_NOT_FOUND,
    TASK_NOT_FOUND,
    UNKNOWN_HANDLER,
    UNKNOWN_TASK_TYPE,
)
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.project import Event, Task, TaskStatus
from openchronicle.core.domain.ports.llm_port import LLMProviderError
from openchronicle.core.domain.ports.privacy_gate_port import PrivacyGatePort
from openchronicle.core.domain.services.verification import VerificationResult, VerificationService
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.cli.stdio import (
    METRICS,
    RUNNABLE_TASK_TYPES,
    STDIO_RPC_PROTOCOL_VERSION,
    _execute_plugin_invoke_task,
    _parse_run_many_limit,
    _resolve_privacy_settings,
    _task_summary,
    coerce_int,
    json_envelope,
    json_error_payload,
)

# ---------------------------------------------------------------------------
# System handlers
# ---------------------------------------------------------------------------


def handle_system_info(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
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


def handle_system_commands(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
    from openchronicle.interfaces.cli.stdio import SUPPORTED_COMMANDS

    return json_envelope(
        command=command,
        ok=True,
        result={"commands": sorted(SUPPORTED_COMMANDS)},
        error=None,
    )


def handle_system_metrics(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
    return json_envelope(
        command=command,
        ok=True,
        result=METRICS.snapshot(),
        error=None,
    )


def handle_system_health(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
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


def handle_system_ping(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
    return json_envelope(
        command=command,
        ok=True,
        result={"pong": True},
        error=None,
    )


def handle_system_shutdown(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
    return json_envelope(
        command=command,
        ok=True,
        result={"shutdown": True, "reason": "requested"},
        error=None,
    )


# ---------------------------------------------------------------------------
# Conversation handlers
# ---------------------------------------------------------------------------


def handle_convo_export(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
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


def handle_convo_verify(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
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


def handle_convo_mode(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
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


def handle_convo_show(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
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
            except (ValueError, NotFoundError, DomainValidationError):
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


def handle_convo_ask(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
    cs = container.conversation_settings
    conversation_id = str(args.get("conversation_id", ""))
    prompt_text = str(args.get("prompt", ""))
    last_n = coerce_int(args.get("last_n"), cs.last_n)
    top_k_memory = coerce_int(args.get("top_k_memory"), cs.top_k_memory)
    include_pinned_memory = bool(args.get("include_pinned_memory", cs.include_pinned_memory))
    include_explain = bool(args.get("explain", False))
    allow_pii = bool(args.get("allow_pii", False))
    enqueue_if_unavailable = bool(args.get("enqueue_if_unavailable", False))

    async def _run() -> dict[str, object]:
        turn = await ask_conversation_execute(
            convo_store=container.storage,
            storage=container.storage,
            memory_store=container.storage,
            llm=container.llm,
            interaction_router=container.interaction_router,
            emit_event=container.emit_event,
            conversation_id=conversation_id,
            prompt_text=prompt_text,
            router_policy=container.router_policy,
            last_n=last_n,
            top_k_memory=top_k_memory,
            include_pinned_memory=include_pinned_memory,
            allow_pii=allow_pii,
            privacy_gate=getattr(container, "privacy_gate", None),
            privacy_settings=getattr(container, "privacy_settings", None),
            telemetry=cast(TelemetryRecorder, METRICS),
        )

        explain_payload: dict[str, object] | None = None
        if include_explain:
            try:
                explain_payload = explain_turn.execute(
                    storage=container.storage,
                    conversation_id=conversation_id,
                    turn_id=turn.id,
                )
            except (ValueError, NotFoundError, DomainValidationError):
                explain_payload = None
        return {
            "conversation_id": turn.conversation_id,
            "turn_id": turn.id,
            "turn_index": turn.turn_index,
            "assistant_text": turn.assistant_text,
            "explain": explain_payload if include_explain else None,
        }

    try:
        result = asyncio.run(_run())
        return json_envelope(
            command=command,
            ok=True,
            result=result,
            error=None,
        )
    except LLMProviderError as exc:
        if enqueue_if_unavailable and is_enqueueable_provider_failure(exc.error_code):
            task = enqueue_conversation(
                orchestrator=container.orchestrator,
                convo_store=container.storage,
                conversation_id=conversation_id,
                prompt_text=prompt_text,
                include_explain=include_explain,
                allow_pii=allow_pii,
                metadata=None,
                interaction_router=container.interaction_router,
                emit_event=container.emit_event,
                router_policy=container.router_policy,
            )
            return json_envelope(
                command=command,
                ok=True,
                result={
                    "conversation_id": conversation_id,
                    "task_id": task.id,
                    "status": "queued",
                    "reason_code": exc.error_code,
                },
                error=None,
            )
        raise
    except (NotFoundError, DomainValidationError) as exc:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(error_code=getattr(exc, "code", INVALID_ARGUMENT), message=str(exc), hint=None),
        )


def handle_convo_ask_async(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
    conversation_id = str(args.get("conversation_id", ""))
    prompt_text = str(args.get("prompt", ""))
    include_explain = bool(args.get("explain", False))
    allow_pii = bool(args.get("allow_pii", False))
    metadata_value = args.get("metadata")
    metadata = metadata_value if isinstance(metadata_value, dict) else None
    task = enqueue_conversation(
        orchestrator=container.orchestrator,
        convo_store=container.storage,
        conversation_id=conversation_id,
        prompt_text=prompt_text,
        include_explain=include_explain,
        allow_pii=allow_pii,
        metadata=metadata,
        interaction_router=container.interaction_router,
        emit_event=container.emit_event,
        router_policy=container.router_policy,
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


# ---------------------------------------------------------------------------
# Privacy handler
# ---------------------------------------------------------------------------


def handle_privacy_preview(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
    text_value = args.get("text")
    if not isinstance(text_value, str):
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=INVALID_ARGUMENT,
                message="Request 'text' must be a string",
                hint=None,
            ),
        )

    provider_value = args.get("provider")
    provider = provider_value if isinstance(provider_value, str) else None

    privacy_gate = getattr(container, "privacy_gate", None)
    privacy_settings = getattr(container, "privacy_settings", None)
    if not isinstance(privacy_gate, PrivacyGatePort) or not isinstance(privacy_settings, PrivacyOutboundSettings):
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=INTERNAL_ERROR,
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
                error_code=INVALID_ARGUMENT,
                message=error_message,
                hint=None,
            ),
        )

    effective_mode = resolved_settings.mode
    applies = effective_mode != "off"
    if applies and resolved_settings.external_only and provider is not None and not is_external_provider(provider):
        applies = False
    if provider is None and resolved_settings.external_only:
        applies = True

    # Determine analysis mode for the preview:
    # - "off" if privacy is disabled
    # - effective_mode if privacy applies (respects block/warn/redact)
    # - "warn" if configured but doesn't apply to this provider
    #   (informational: shows detected PII without blocking)
    if effective_mode == "off":
        analysis_mode = "off"
    elif applies:
        analysis_mode = effective_mode
    else:
        analysis_mode = "warn"

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


# ---------------------------------------------------------------------------
# Task handlers
# ---------------------------------------------------------------------------


def handle_task_submit(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
    from openchronicle.core.application.use_cases import task_submit

    project_id = str(args.get("project_id", ""))
    task_type = str(args.get("task_type", ""))
    payload = args.get("payload")

    if not project_id:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=INVALID_ARGUMENT,
                message="Missing required argument: project_id",
                hint=None,
            ),
        )

    if not task_type:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=INVALID_ARGUMENT,
                message="Missing required argument: task_type",
                hint=None,
            ),
        )

    if payload is None or not isinstance(payload, dict):
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=INVALID_ARGUMENT,
                message="Missing or invalid required argument: payload (must be a JSON object)",
                hint=None,
            ),
        )

    project = container.storage.get_project(project_id)
    if project is None:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=PROJECT_NOT_FOUND,
                message=f"Project not found: {project_id}",
                hint="Use 'oc init-project' to create a project first",
            ),
        )

    try:
        task = task_submit.execute(
            orchestrator=container.orchestrator,
            project_id=project_id,
            task_type=task_type,
            payload=payload,
        )
    except task_submit.InvalidTaskTypeError as exc:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(error_code=INVALID_TASK_TYPE, message=str(exc), hint=None),
        )
    except task_submit.InvalidPluginPayloadError as exc:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(error_code=INVALID_ARGUMENT, message=str(exc), hint=None),
        )
    except task_submit.UnknownHandlerError as exc:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(error_code=UNKNOWN_HANDLER, message=str(exc), hint=None),
        )
    except (ValueError, NotFoundError, DomainValidationError) as exc:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(error_code=UNKNOWN_TASK_TYPE, message=str(exc), hint=None),
        )

    return json_envelope(
        command=command,
        ok=True,
        result={
            "task_id": task.id,
            "status": task.status.value,
        },
        error=None,
    )


def handle_task_get(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
    task_id = str(args.get("task_id", ""))
    task_maybe = container.storage.get_task(task_id)
    if task_maybe is None:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=TASK_NOT_FOUND,
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


def handle_task_list(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
    status_value = args.get("status")
    status_filter = str(status_value).lower() if isinstance(status_value, str) else None
    if status_filter is not None and status_filter not in {status.value for status in TaskStatus}:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=INVALID_ARGUMENT,
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
                error_code=INVALID_ARGUMENT,
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
                error_code=INVALID_ARGUMENT,
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


def handle_task_run_one(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
    task_type_value = args.get("type", "convo.ask")
    if not isinstance(task_type_value, str):
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=INVALID_ARGUMENT,
                message="Task type must be a string",
                hint=None,
            ),
        )

    max_scan = 10
    scanned = 0
    skipped_unrunnable = 0
    invalid_type_count = 0
    run_one_result: dict[str, object] = {
        "ran": False,
        "task_id": None,
        "status": "none",
        "error": None,
    }

    run_one_pending: list[Task] = []
    for project in container.storage.list_projects():
        run_one_pending.extend(container.storage.list_tasks_by_project(project.id))
    run_one_pending = [task for task in run_one_pending if task.status == TaskStatus.PENDING]
    run_one_pending.sort(key=lambda task: (task.created_at, task.id))

    for task in run_one_pending:
        if scanned >= max_scan:
            break
        scanned += 1

        if "." in task.type and task.type not in RUNNABLE_TASK_TYPES:
            invalid_type_count += 1
            error_payload = {
                "error_code": INVALID_TASK_TYPE,
                "message": f"Invalid task type: {task.type}",
            }
            container.storage.update_task_error(task.id, json.dumps(error_payload), TaskStatus.FAILED.value)
            container.emit_event(
                Event(
                    project_id=task.project_id,
                    task_id=task.id,
                    type="task.failed",
                    payload={"task_id": task.id, "error_code": INVALID_TASK_TYPE},
                )
            )
            continue

        if task.type not in RUNNABLE_TASK_TYPES:
            skipped_unrunnable += 1
            continue
        if task.type != task_type_value:
            continue

        if task.type == "convo.ask":
            run_one_result = asyncio.run(
                task_once.execute_task_by_id(
                    storage=container.storage,
                    convo_store=container.storage,
                    memory_store=container.storage,
                    llm=container.llm,
                    interaction_router=container.interaction_router,
                    emit_event=container.emit_event,
                    privacy_gate=getattr(container, "privacy_gate", None),
                    privacy_settings=getattr(container, "privacy_settings", None),
                    task_id=task.id,
                    task_type=task_type_value,
                    router_policy=container.router_policy,
                )
            )
        else:
            run_one_result = _execute_plugin_invoke_task(container, task)
            run_one_result["ran"] = True

        break

    run_one_result["scanned"] = scanned
    run_one_result["skipped_unrunnable"] = skipped_unrunnable
    run_one_result["invalid_type_count"] = invalid_type_count

    if run_one_result.get("ran") is True:
        status_value = str(run_one_result.get("status"))
        if status_value == "completed":
            METRICS.record_task_run("run_one", completed=1, failed=0)
        elif status_value == "failed":
            METRICS.record_task_run("run_one", completed=0, failed=1)

    return json_envelope(
        command=command,
        ok=True,
        result=run_one_result,
        error=None,
    )


def handle_task_run_many(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
    task_type_value = args.get("type", "convo.ask")
    if not isinstance(task_type_value, str):
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=INVALID_ARGUMENT,
                message="Task type must be a string",
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
                error_code=INVALID_ARGUMENT,
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
                error_code=INVALID_ARGUMENT,
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
                error_code=INVALID_ARGUMENT,
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
                error_code=INVALID_ARGUMENT,
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
                error_code=INVALID_ARGUMENT,
                message="max_seconds must be non-negative",
                hint=None,
            ),
        )

    start_time = time.monotonic()
    max_scan = run_many_limit * 10
    scanned = 0
    skipped_unrunnable = 0
    invalid_type_count = 0
    executed = 0
    completed_count = 0
    failed_count = 0
    results: list[dict[str, object]] = []

    run_many_pending: list[Task] = []
    for project in container.storage.list_projects():
        run_many_pending.extend(container.storage.list_tasks_by_project(project.id))
    run_many_pending = [task for task in run_many_pending if task.status == TaskStatus.PENDING]
    run_many_pending.sort(key=lambda task: (task.created_at, task.id))

    for task in run_many_pending:
        if executed >= run_many_limit:
            break
        if scanned >= max_scan:
            break
        if max_seconds > 0 and time.monotonic() - start_time >= max_seconds:
            break

        scanned += 1

        if "." in task.type and task.type not in RUNNABLE_TASK_TYPES:
            invalid_type_count += 1
            error_payload = {
                "error_code": INVALID_TASK_TYPE,
                "message": f"Invalid task type: {task.type}",
            }
            container.storage.update_task_error(task.id, json.dumps(error_payload), TaskStatus.FAILED.value)
            container.emit_event(
                Event(
                    project_id=task.project_id,
                    task_id=task.id,
                    type="task.failed",
                    payload={"task_id": task.id, "error_code": INVALID_TASK_TYPE},
                )
            )
            continue

        if task.type not in RUNNABLE_TASK_TYPES:
            skipped_unrunnable += 1
            continue
        if task.type != task_type_value:
            continue

        if task.type == "convo.ask":
            run_many_task_result = asyncio.run(
                task_once.execute_task_by_id(
                    storage=container.storage,
                    convo_store=container.storage,
                    memory_store=container.storage,
                    llm=container.llm,
                    interaction_router=container.interaction_router,
                    emit_event=container.emit_event,
                    privacy_gate=getattr(container, "privacy_gate", None),
                    privacy_settings=getattr(container, "privacy_settings", None),
                    task_id=task.id,
                    task_type=task_type_value,
                    router_policy=container.router_policy,
                )
            )
            status = str(run_many_task_result.get("status"))
            results.append(run_many_task_result)
        else:
            run_many_task_result = _execute_plugin_invoke_task(container, task)
            status = str(run_many_task_result.get("status"))
            results.append(run_many_task_result)

        executed += 1
        if status == "completed":
            completed_count += 1
        elif status == "failed":
            failed_count += 1

    remaining_queued = 0
    refreshed_pending: list[Task] = []
    for project in container.storage.list_projects():
        refreshed_pending.extend(container.storage.list_tasks_by_project(project.id))
    for task in refreshed_pending:
        if task.status != TaskStatus.PENDING:
            continue
        if task.type in RUNNABLE_TASK_TYPES and task.type == task_type_value:
            remaining_queued += 1

    run_many_result = {
        "ran": executed,
        "executed": executed,
        "completed": completed_count,
        "failed": failed_count,
        "scanned": scanned,
        "skipped_unrunnable": skipped_unrunnable,
        "invalid_type_count": invalid_type_count,
        "has_more": remaining_queued > 0,
        "remaining_queued": remaining_queued,
        "tasks": results,
    }

    completed = run_many_result.get("completed") if isinstance(run_many_result, dict) else 0
    failed = run_many_result.get("failed") if isinstance(run_many_result, dict) else 0
    completed_count = completed if isinstance(completed, int) and completed >= 0 else 0
    failed_count = failed if isinstance(failed, int) and failed >= 0 else 0
    METRICS.record_task_run("run_many", completed=completed_count, failed=failed_count)

    return json_envelope(
        command=command,
        ok=True,
        result=run_many_result,
        error=None,
    )


# ---------------------------------------------------------------------------
# Scheduler handlers
# ---------------------------------------------------------------------------


def handle_scheduler_add(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
    from openchronicle.core.domain.errors.error_codes import INVALID_ARGUMENT

    project_id = str(args.get("project_id", ""))
    name = str(args.get("name", ""))
    task_type = str(args.get("task_type", ""))
    payload = args.get("payload")

    if not project_id or not name or not task_type:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=INVALID_ARGUMENT,
                message="Missing required: project_id, name, task_type",
                hint=None,
            ),
        )
    if payload is None or not isinstance(payload, dict):
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=INVALID_ARGUMENT,
                message="payload must be a JSON object",
                hint=None,
            ),
        )

    from datetime import datetime

    due_at_raw = args.get("due_at")
    due_at = datetime.fromisoformat(str(due_at_raw)) if due_at_raw else None
    interval_raw = args.get("interval_seconds")
    interval = coerce_int(interval_raw, 0) if interval_raw is not None else None
    max_failures = coerce_int(args.get("max_failures"), 0) or 0

    job = container.scheduler.add_job(
        project_id=project_id,
        name=name,
        task_type=task_type,
        task_payload=payload,
        due_at=due_at,
        interval_seconds=interval,
        max_failures=max_failures,
    )
    return json_envelope(command=command, ok=True, result=_job_summary(job), error=None)


def handle_scheduler_list(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
    project_id = args.get("project_id")
    status = args.get("status")
    jobs = container.scheduler.list_jobs(
        project_id=str(project_id) if project_id else None,
        status=str(status) if status else None,
    )
    return json_envelope(
        command=command,
        ok=True,
        result={"jobs": [_job_summary(j) for j in jobs]},
        error=None,
    )


def handle_scheduler_pause(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
    return _scheduler_transition(container, command, args, "pause")


def handle_scheduler_resume(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
    return _scheduler_transition(container, command, args, "resume")


def handle_scheduler_cancel(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
    return _scheduler_transition(container, command, args, "cancel")


def handle_scheduler_tick(container: CoreContainer, command: str, args: dict[str, object]) -> dict[str, object]:
    max_jobs = coerce_int(args.get("max_jobs"), 10) or 10
    results = container.scheduler.tick(max_jobs=max_jobs)
    return json_envelope(
        command=command,
        ok=True,
        result={
            "jobs_fired": len(results),
            "tasks": [{"job_id": job.id, "job_name": job.name, "task_id": task.id} for job, task in results],
        },
        error=None,
    )


def _scheduler_transition(
    container: CoreContainer, command: str, args: dict[str, object], action: str
) -> dict[str, object]:
    from openchronicle.core.application.services.scheduler import InvalidTransitionError, JobNotFoundError
    from openchronicle.core.domain.errors.error_codes import INVALID_STATE_TRANSITION, JOB_NOT_FOUND

    job_id = str(args.get("job_id", ""))
    if not job_id:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(error_code=INVALID_ARGUMENT, message="Missing job_id", hint=None),
        )

    method = getattr(container.scheduler, f"{action}_job")
    try:
        job = method(job_id)
    except JobNotFoundError:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(error_code=JOB_NOT_FOUND, message=f"Job not found: {job_id}", hint=None),
        )
    except InvalidTransitionError as exc:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(error_code=INVALID_STATE_TRANSITION, message=str(exc), hint=None),
        )

    return json_envelope(command=command, ok=True, result=_job_summary(job), error=None)


def _job_summary(job: object) -> dict[str, object]:
    from openchronicle.core.domain.models.scheduled_job import ScheduledJob

    assert isinstance(job, ScheduledJob)
    return {
        "id": job.id,
        "project_id": job.project_id,
        "name": job.name,
        "task_type": job.task_type,
        "status": job.status.value,
        "next_due_at": job.next_due_at.isoformat(),
        "interval_seconds": job.interval_seconds,
        "fire_count": job.fire_count,
        "last_task_id": job.last_task_id,
    }


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_RpcHandler = Callable[[CoreContainer, str, dict[str, object]], dict[str, object]]

RPC_DISPATCH: dict[str, _RpcHandler] = {
    "system.info": handle_system_info,
    "system.commands": handle_system_commands,
    "system.metrics": handle_system_metrics,
    "system.health": handle_system_health,
    "system.ping": handle_system_ping,
    "system.shutdown": handle_system_shutdown,
    "convo.ask": handle_convo_ask,
    "convo.ask_async": handle_convo_ask_async,
    "convo.export": handle_convo_export,
    "convo.verify": handle_convo_verify,
    "convo.mode": handle_convo_mode,
    "convo.show": handle_convo_show,
    "privacy.preview": handle_privacy_preview,
    "task.submit": handle_task_submit,
    "task.get": handle_task_get,
    "task.list": handle_task_list,
    "task.run_one": handle_task_run_one,
    "task.run_many": handle_task_run_many,
    "scheduler.add": handle_scheduler_add,
    "scheduler.list": handle_scheduler_list,
    "scheduler.pause": handle_scheduler_pause,
    "scheduler.resume": handle_scheduler_resume,
    "scheduler.cancel": handle_scheduler_cancel,
    "scheduler.tick": handle_scheduler_tick,
}
