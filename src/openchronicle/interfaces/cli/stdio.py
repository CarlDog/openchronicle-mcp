from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
from collections import OrderedDict
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from io import TextIOBase
from queue import Empty, Queue
from typing import TextIO

from openchronicle.core.application.config.settings import (
    PrivacyOutboundSettings,
    TelemetrySettings,
    load_telemetry_settings,
)
from openchronicle.core.domain.errors.error_codes import (
    HANDLER_ERROR,
    INTERNAL_ERROR,
    INVALID_ARGUMENT,
    INVALID_JSON,
    INVALID_REQUEST,
    UNKNOWN_COMMAND,
    UNKNOWN_HANDLER,
    UNSUPPORTED_PROTOCOL_VERSION,
)
from openchronicle.core.domain.models.project import Event, Task, TaskStatus
from openchronicle.core.domain.ports.llm_port import LLMUsage
from openchronicle.core.infrastructure.wiring.container import CoreContainer

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
    "task.submit",
    "system.commands",
    "system.health",
    "system.info",
    "system.metrics",
    "system.ping",
    "system.shutdown",
    "scheduler.add",
    "scheduler.list",
    "scheduler.pause",
    "scheduler.resume",
    "scheduler.cancel",
    "scheduler.tick",
)

RUNNABLE_TASK_TYPES = frozenset(
    {
        "convo.ask",
        "plugin.invoke",
    }
)


class MetricsTracker:
    def __init__(self, telemetry: TelemetrySettings) -> None:
        self._telemetry = telemetry
        self._started_at = datetime.now(UTC)
        self._started_monotonic = time.monotonic()
        self._requests_total = 0
        self._requests_ok = 0
        self._requests_error = 0
        self._by_command: dict[str, int] = {}
        self._by_error_code: dict[str, int] = {}
        self._tasks_run_one = 0
        self._tasks_run_many = 0
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._llm_calls_total = 0
        self._calls_by_provider: dict[str, int] = {}
        self._calls_by_model: dict[str, int] = {}
        self._tokens_prompt_total = 0
        self._tokens_completion_total = 0
        self._tokens_total = 0
        self._usage_unknown_calls = 0
        self._rate_limit_hits = 0
        self._quota_hits = 0
        self._ask_total_ms_sum = 0.0
        self._ask_total_ms_count = 0
        self._provider_call_ms_sum = 0.0
        self._provider_call_ms_count = 0
        self._context_assemble_ms_sum = 0.0
        self._context_assemble_ms_count = 0
        self._context_max_tokens_known_calls = 0
        self._context_prompt_tokens_sum = 0
        self._context_max_tokens_sum = 0
        self._context_utilization_sum = 0.0
        self._memory_retrieved_total = 0
        self._memory_pinned_total = 0
        self._memory_retrieved_chars_total = 0
        self._memory_duplicate_retrieval_total = 0
        self._memory_unique_ids_seen: set[str] = set()
        self._memory_retrieval_reason_counts: dict[str, int] = {}
        self._memory_self_report_valid_total = 0
        self._memory_self_report_invalid_total = 0
        self._memory_used_ids_total = 0

    def telemetry_enabled(self) -> bool:
        return self._telemetry.enabled

    def usage_enabled(self) -> bool:
        return self._telemetry.enabled and self._telemetry.usage_enabled

    def perf_enabled(self) -> bool:
        return self._telemetry.enabled and self._telemetry.perf_enabled

    def context_enabled(self) -> bool:
        return self._telemetry.enabled and self._telemetry.context_enabled

    def memory_enabled(self) -> bool:
        return self._telemetry.enabled and self._telemetry.memory_enabled

    def memory_self_report_enabled(self) -> bool:
        return self._telemetry.enabled and self._telemetry.memory_self_report_enabled

    def memory_self_report_max_ids(self) -> int:
        return self._telemetry.memory_self_report_max_ids

    def memory_self_report_strict(self) -> bool:
        return self._telemetry.memory_self_report_strict

    def record_request(self, command: str, *, ok: bool, error_code: str | None) -> None:
        self._requests_total += 1
        if ok:
            self._requests_ok += 1
        else:
            self._requests_error += 1
        self._by_command[command] = self._by_command.get(command, 0) + 1
        if error_code:
            self._by_error_code[error_code] = self._by_error_code.get(error_code, 0) + 1

    def record_task_run(self, kind: str, *, completed: int, failed: int) -> None:
        if kind == "run_one":
            self._tasks_run_one += 1
        elif kind == "run_many":
            self._tasks_run_many += 1

        if completed > 0:
            self._tasks_completed += completed
        if failed > 0:
            self._tasks_failed += failed

    def record_llm_usage(self, *, provider: str, model: str, usage: LLMUsage | None) -> None:
        if not self.usage_enabled():
            return
        self._llm_calls_total += 1
        self._calls_by_provider[provider] = self._calls_by_provider.get(provider, 0) + 1
        self._calls_by_model[model] = self._calls_by_model.get(model, 0) + 1

        if usage is None:
            self._usage_unknown_calls += 1
            return

        prompt_tokens = usage.input_tokens
        completion_tokens = usage.output_tokens
        total_tokens = usage.total_tokens

        if prompt_tokens is None and completion_tokens is None and total_tokens is None:
            self._usage_unknown_calls += 1
            return

        if isinstance(prompt_tokens, int):
            self._tokens_prompt_total += prompt_tokens
        if isinstance(completion_tokens, int):
            self._tokens_completion_total += completion_tokens

        if isinstance(total_tokens, int):
            self._tokens_total += total_tokens
        elif isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
            self._tokens_total += prompt_tokens + completion_tokens

    def record_llm_error(self, *, error_code: str | None) -> None:
        if not self.usage_enabled() or not error_code:
            return
        code = error_code.lower()
        if code in {"rate_limit", "rate_limit_exceeded", "too_many_requests", "http_429", "429"}:
            self._rate_limit_hits += 1
            return
        if code in {"insufficient_quota", "quota_exceeded", "billing_hard_limit_reached"}:
            self._quota_hits += 1
            return

    def record_perf(
        self,
        *,
        ask_total_ms: float | None = None,
        provider_call_ms: float | None = None,
        context_assemble_ms: float | None = None,
    ) -> None:
        if not self.perf_enabled():
            return
        if isinstance(ask_total_ms, float):
            self._ask_total_ms_sum += ask_total_ms
            self._ask_total_ms_count += 1
        if isinstance(provider_call_ms, float):
            self._provider_call_ms_sum += provider_call_ms
            self._provider_call_ms_count += 1
        if isinstance(context_assemble_ms, float):
            self._context_assemble_ms_sum += context_assemble_ms
            self._context_assemble_ms_count += 1

    def record_context(self, *, prompt_tokens: int | None, max_context_tokens: int | None) -> None:
        if not self.context_enabled():
            return
        if isinstance(prompt_tokens, int):
            self._context_prompt_tokens_sum += prompt_tokens
        if isinstance(max_context_tokens, int):
            self._context_max_tokens_sum += max_context_tokens
            self._context_max_tokens_known_calls += 1
            if isinstance(prompt_tokens, int) and max_context_tokens > 0:
                self._context_utilization_sum += prompt_tokens / max_context_tokens

    def record_memory_retrieval(
        self,
        *,
        retrieved_ids: Iterable[str],
        pinned_ids: Iterable[str],
        retrieved_chars_total: int,
    ) -> None:
        if not self.memory_enabled():
            return
        retrieved_list = [value for value in retrieved_ids if isinstance(value, str) and value]
        pinned_list = [value for value in pinned_ids if isinstance(value, str) and value]
        self._memory_retrieved_total += len(retrieved_list)
        self._memory_pinned_total += len(pinned_list)
        if retrieved_chars_total > 0:
            self._memory_retrieved_chars_total += retrieved_chars_total

        for memory_id in retrieved_list:
            if memory_id in self._memory_unique_ids_seen:
                self._memory_duplicate_retrieval_total += 1
            else:
                self._memory_unique_ids_seen.add(memory_id)

        if retrieved_list:
            reason = "heuristic_v0"
            self._memory_retrieval_reason_counts[reason] = self._memory_retrieval_reason_counts.get(reason, 0) + len(
                retrieved_list
            )

    def record_memory_self_report(self, *, used_ids: Iterable[str], valid: bool) -> None:
        if not self.memory_enabled() or not self.memory_self_report_enabled():
            return
        if valid:
            self._memory_self_report_valid_total += 1
            self._memory_used_ids_total += len([value for value in used_ids if isinstance(value, str) and value])
        else:
            self._memory_self_report_invalid_total += 1

    def snapshot(self) -> dict[str, object]:
        by_command = dict(sorted(self._by_command.items()))
        by_error_code = dict(sorted(self._by_error_code.items()))
        snapshot: dict[str, object] = {
            "started_at": self._started_at.isoformat(),
            "uptime_seconds": time.monotonic() - self._started_monotonic,
            "requests": {
                "total": self._requests_total,
                "ok": self._requests_ok,
                "error": self._requests_error,
                "by_command": by_command,
                "by_error_code": by_error_code,
            },
            "tasks": {
                "run_one": self._tasks_run_one,
                "run_many": self._tasks_run_many,
                "completed": self._tasks_completed,
                "failed": self._tasks_failed,
            },
        }
        if not self.telemetry_enabled():
            snapshot["telemetry_enabled"] = False
            return snapshot

        snapshot["telemetry_enabled"] = True
        snapshot["llm"] = {
            "calls_total": self._llm_calls_total,
            "calls_by_provider": dict(sorted(self._calls_by_provider.items())),
            "calls_by_model": dict(sorted(self._calls_by_model.items())),
            "tokens_prompt_total": self._tokens_prompt_total,
            "tokens_completion_total": self._tokens_completion_total,
            "tokens_total": self._tokens_total,
            "usage_unknown_calls": self._usage_unknown_calls,
            "rate_limit_hits": self._rate_limit_hits,
            "quota_hits": self._quota_hits,
        }
        snapshot["perf"] = {
            "ask_total_ms_sum": self._ask_total_ms_sum,
            "ask_total_ms_count": self._ask_total_ms_count,
            "provider_call_ms_sum": self._provider_call_ms_sum,
            "provider_call_ms_count": self._provider_call_ms_count,
            "context_assemble_ms_sum": self._context_assemble_ms_sum,
            "context_assemble_ms_count": self._context_assemble_ms_count,
        }
        snapshot["context"] = {
            "max_tokens_known_calls": self._context_max_tokens_known_calls,
            "prompt_tokens_sum": self._context_prompt_tokens_sum,
            "max_context_tokens_sum": self._context_max_tokens_sum,
            "utilization_sum": self._context_utilization_sum,
        }
        used_rate_avg = 0.0
        if self._memory_retrieved_total > 0:
            used_rate_avg = self._memory_used_ids_total / self._memory_retrieved_total
        snapshot["memory"] = {
            "retrieved_total": self._memory_retrieved_total,
            "pinned_total": self._memory_pinned_total,
            "retrieved_chars_total": self._memory_retrieved_chars_total,
            "duplicate_retrieval_total": self._memory_duplicate_retrieval_total,
            "unique_memory_ids_seen_total": len(self._memory_unique_ids_seen),
            "retrieval_reason_counts": dict(sorted(self._memory_retrieval_reason_counts.items())),
            "self_report_enabled": self._telemetry.memory_self_report_enabled,
            "self_report_valid_total": self._memory_self_report_valid_total,
            "self_report_invalid_total": self._memory_self_report_invalid_total,
            "used_ids_total": self._memory_used_ids_total,
            "used_rate_avg": used_rate_avg,
        }
        return snapshot


TELEMETRY_SETTINGS = load_telemetry_settings()
METRICS = MetricsTracker(telemetry=TELEMETRY_SETTINGS)


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


def _record_response(command: str, payload: dict[str, object]) -> None:
    ok_value = payload.get("ok")
    ok = ok_value is True
    error_code = None
    error = payload.get("error")
    if isinstance(error, dict):
        code_value = error.get("error_code")
        if isinstance(code_value, str):
            error_code = code_value
    METRICS.record_request(command, ok=ok, error_code=error_code)


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
            error_code=INVALID_ARGUMENT,
            message=str(exc),
            hint=None,
            details=None,
        )

    return json_error_payload(
        error_code=INTERNAL_ERROR,
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


def _execute_plugin_invoke_task(container: CoreContainer, task: Task) -> dict[str, object]:
    payload = task.payload if isinstance(task.payload, dict) else {}
    handler_name = payload.get("handler")
    input_payload = payload.get("input")

    if not isinstance(handler_name, str) or not handler_name:
        error_payload = {
            "error_code": INVALID_ARGUMENT,
            "message": "Missing or invalid payload.handler for plugin.invoke",
        }
        container.storage.update_task_error(task.id, json.dumps(error_payload), TaskStatus.FAILED.value)
        return {
            "task_id": task.id,
            "status": "failed",
            "error": error_payload,
        }

    if not isinstance(input_payload, dict):
        error_payload = {
            "error_code": INVALID_ARGUMENT,
            "message": "Missing or invalid payload.input for plugin.invoke (must be JSON object)",
        }
        container.storage.update_task_error(task.id, json.dumps(error_payload), TaskStatus.FAILED.value)
        return {
            "task_id": task.id,
            "status": "failed",
            "error": error_payload,
        }

    handler = container.orchestrator.handler_registry.get(handler_name)
    if handler is None:
        error_payload = {
            "error_code": UNKNOWN_HANDLER,
            "message": f"Unknown handler: {handler_name}",
        }
        container.storage.update_task_error(task.id, json.dumps(error_payload), TaskStatus.FAILED.value)
        return {
            "task_id": task.id,
            "status": "failed",
            "error": error_payload,
        }

    container.storage.update_task_status(task.id, TaskStatus.RUNNING.value)
    container.event_logger.append(
        Event(
            project_id=task.project_id,
            task_id=task.id,
            type="task.started",
            payload={"task_id": task.id, "task_type": task.type, "handler": handler_name},
        )
    )

    async def _run_handler() -> object:
        invoke_task = Task(
            id=task.id,
            project_id=task.project_id,
            agent_id=task.agent_id,
            parent_task_id=task.parent_task_id,
            type=task.type,
            payload=input_payload,
            status=TaskStatus.RUNNING,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
        return await handler(invoke_task, {"agent_id": None, "emit_event": container.event_logger.append})

    try:
        result = asyncio.run(_run_handler())
    except Exception as exc:  # noqa: BLE001
        error_payload = {
            "error_code": HANDLER_ERROR,
            "message": str(exc)[:500],
        }
        container.storage.update_task_error(task.id, json.dumps(error_payload), TaskStatus.FAILED.value)
        container.event_logger.append(
            Event(
                project_id=task.project_id,
                task_id=task.id,
                type="task.failed",
                payload={"task_id": task.id, "error_code": HANDLER_ERROR},
            )
        )
        return {
            "task_id": task.id,
            "status": "failed",
            "error": error_payload,
        }

    result_json = json.dumps(result if isinstance(result, dict) else {"value": result})
    container.storage.update_task_result(task.id, result_json, TaskStatus.COMPLETED.value)
    container.event_logger.append(
        Event(
            project_id=task.project_id,
            task_id=task.id,
            type="task.completed",
            payload={"task_id": task.id, "handler": handler_name},
        )
    )
    return {
        "task_id": task.id,
        "status": "completed",
        "error": None,
    }


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
                error_code=UNKNOWN_COMMAND,
                message=f"Unsupported command: {command}",
                hint=None,
            ),
        )

    from openchronicle.interfaces.cli.rpc_handlers import RPC_DISPATCH

    handler = RPC_DISPATCH.get(command)
    if handler is None:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=UNKNOWN_COMMAND,
                message=f"Unsupported command: {command}",
                hint=None,
            ),
        )

    try:
        return handler(container, command, args)
    except Exception as exc:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=_normalize_error(exc),
        )


def dispatch_request(container: CoreContainer, request: dict[str, object]) -> dict[str, object]:
    command_value = request.get("command")
    args_value = request.get("args")
    protocol_value = request.get("protocol_version")
    request_id_value = request.get("request_id")
    command_name = command_value if isinstance(command_value, str) else "unknown"
    if request_id_value is not None and not isinstance(request_id_value, str):
        payload = json_envelope(
            command=str(command_value) if isinstance(command_value, str) else "unknown",
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=INVALID_REQUEST,
                message="Request 'request_id' must be a string",
                hint=None,
            ),
        )
        payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
        _record_response(command_name, payload)
        return payload

    request_id = request_id_value if isinstance(request_id_value, str) else None

    if protocol_value is not None and not isinstance(protocol_value, str):
        payload = json_envelope(
            command=str(command_value) if isinstance(command_value, str) else "unknown",
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=INVALID_REQUEST,
                message="Request 'protocol_version' must be a string",
                hint=None,
            ),
        )
        payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
        _attach_request_id(payload, request_id)
        _record_response(command_name, payload)
        return payload

    if protocol_value is not None and protocol_value != STDIO_RPC_PROTOCOL_VERSION:
        payload = json_envelope(
            command=str(command_value) if isinstance(command_value, str) else "unknown",
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=UNSUPPORTED_PROTOCOL_VERSION,
                message=f"Unsupported protocol_version: {protocol_value}",
                hint='Use protocol_version "1".',
            ),
        )
        payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
        _attach_request_id(payload, request_id)
        _record_response(command_name, payload)
        return payload

    if not isinstance(command_value, str):
        payload = json_envelope(
            command=str(command_value) if command_value is not None else "unknown",
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=INVALID_REQUEST,
                message="Request must include 'command' string",
                hint=None,
            ),
        )
        payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
        _attach_request_id(payload, request_id)
        _record_response(command_name, payload)
        return payload

    if args_value is None:
        args_value = {}
    if not isinstance(args_value, dict):
        payload = json_envelope(
            command=command_value,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=INVALID_REQUEST,
                message="Request 'args' must be an object",
                hint=None,
            ),
        )
        payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
        _attach_request_id(payload, request_id)
        _record_response(command_name, payload)
        return payload

    if command_value == "system.metrics":
        METRICS.record_request("system.metrics", ok=True, error_code=None)
        response = dispatch_json_command(container, command_value, args_value)
        response["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
        _attach_request_id(response, request_id)
        return response

    response = dispatch_json_command(container, command_value, args_value)
    response["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
    _attach_request_id(response, request_id)
    _record_response(command_name, response)
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
                    error_code=INVALID_JSON,
                    message=str(exc),
                    hint=None,
                ),
            )
            payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
            METRICS.record_request("unknown", ok=False, error_code=INVALID_JSON)
            output_stream.write(json_dumps_line(payload) + "\n")
            output_stream.flush()
            continue

        if not isinstance(request, dict):
            payload = json_envelope(
                command="unknown",
                ok=False,
                result=None,
                error=json_error_payload(
                    error_code=INVALID_REQUEST,
                    message="Request must be a JSON object",
                    hint=None,
                ),
            )
            payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
            METRICS.record_request("unknown", ok=False, error_code=INVALID_REQUEST)
            output_stream.write(json_dumps_line(payload) + "\n")
            output_stream.flush()
            continue

        request_id = request.get("request_id") if isinstance(request.get("request_id"), str) else None
        if request_id is not None and request_id in cache:
            cached = cache[request_id]
            cached_command = request.get("command")
            command_name = cached_command if isinstance(cached_command, str) else "unknown"
            _record_response(command_name, cached)
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
