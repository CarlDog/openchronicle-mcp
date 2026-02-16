from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openchronicle.core.infrastructure.config.env_helpers import (
    env_override,
    parse_bool,
    parse_int,
    parse_str,
    parse_str_list,
)

_DEFAULT_CATEGORIES = ["email", "phone", "ip", "ssn", "cc", "api_key"]


@dataclass(frozen=True)
class PrivacyOutboundSettings:
    mode: str = "off"
    external_only: bool = True
    categories: list[str] = field(default_factory=lambda: list(_DEFAULT_CATEGORIES))
    redact_style: str = "mask"
    log_events: bool = True


@dataclass(frozen=True)
class TelemetrySettings:
    enabled: bool = True
    perf_enabled: bool = True
    usage_enabled: bool = True
    context_enabled: bool = True
    memory_enabled: bool = True
    memory_self_report_enabled: bool = False
    memory_self_report_max_ids: int = 20
    memory_self_report_strict: bool = False


@dataclass(frozen=True)
class RouterAssistSettings:
    enabled: bool = False
    backend: str = "linear"
    model_path: str | None = None
    timeout_ms: int = 50


def load_privacy_outbound_settings(
    file_config: dict[str, Any] | None = None,
) -> PrivacyOutboundSettings:
    fc = file_config or {}
    return PrivacyOutboundSettings(
        mode=parse_str(
            env_override("OC_PRIVACY_OUTBOUND_MODE", fc.get("mode")),
            default="off",
        ),
        external_only=parse_bool(
            env_override("OC_PRIVACY_OUTBOUND_EXTERNAL_ONLY", fc.get("external_only")),
            default=True,
        ),
        categories=parse_str_list(
            env_override("OC_PRIVACY_OUTBOUND_CATEGORIES", fc.get("categories")),
            default=_DEFAULT_CATEGORIES,
        ),
        redact_style=parse_str(
            env_override("OC_PRIVACY_OUTBOUND_REDACT_STYLE", fc.get("redact_style")),
            default="mask",
        ),
        log_events=parse_bool(
            env_override("OC_PRIVACY_OUTBOUND_LOG", fc.get("log_events")),
            default=True,
        ),
    )


def load_telemetry_settings(
    file_config: dict[str, Any] | None = None,
) -> TelemetrySettings:
    fc = file_config or {}
    return TelemetrySettings(
        enabled=parse_bool(
            env_override("OC_TELEMETRY_ENABLED", fc.get("enabled")),
            default=True,
        ),
        perf_enabled=parse_bool(
            env_override("OC_TELEMETRY_PERF_ENABLED", fc.get("perf_enabled")),
            default=True,
        ),
        usage_enabled=parse_bool(
            env_override("OC_TELEMETRY_USAGE_ENABLED", fc.get("usage_enabled")),
            default=True,
        ),
        context_enabled=parse_bool(
            env_override("OC_TELEMETRY_CONTEXT_ENABLED", fc.get("context_enabled")),
            default=True,
        ),
        memory_enabled=parse_bool(
            env_override("OC_TELEMETRY_MEMORY_ENABLED", fc.get("memory_enabled")),
            default=True,
        ),
        memory_self_report_enabled=parse_bool(
            env_override("OC_TELEMETRY_MEMORY_SELF_REPORT_ENABLED", fc.get("memory_self_report_enabled")),
            default=False,
        ),
        memory_self_report_max_ids=parse_int(
            env_override("OC_TELEMETRY_MEMORY_SELF_REPORT_MAX_IDS", fc.get("memory_self_report_max_ids")),
            default=20,
        ),
        memory_self_report_strict=parse_bool(
            env_override("OC_TELEMETRY_MEMORY_SELF_REPORT_STRICT", fc.get("memory_self_report_strict")),
            default=False,
        ),
    )


def load_router_assist_settings(
    file_config: dict[str, Any] | None = None,
) -> RouterAssistSettings:
    fc = file_config or {}
    return RouterAssistSettings(
        enabled=parse_bool(
            env_override("OC_ROUTER_ASSIST_ENABLED", fc.get("enabled")),
            default=False,
        ),
        backend=parse_str(
            env_override("OC_ROUTER_ASSIST_BACKEND", fc.get("backend")),
            default="linear",
        ),
        model_path=parse_str(
            env_override("OC_ROUTER_ASSIST_MODEL_PATH", fc.get("model_path")),
            default="",
        )
        or None,
        timeout_ms=parse_int(
            env_override("OC_ROUTER_ASSIST_TIMEOUT_MS", fc.get("timeout_ms")),
            default=50,
        ),
    )
