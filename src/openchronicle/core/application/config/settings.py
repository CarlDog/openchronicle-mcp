from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openchronicle.core.application.config.env_helpers import (
    env_override,
    parse_bool,
    parse_float,
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
    mcp_tracking_enabled: bool = True
    moe_tracking_enabled: bool = True

    def __post_init__(self) -> None:
        if self.memory_self_report_max_ids < 1:
            raise ValueError(f"memory_self_report_max_ids must be >= 1, got {self.memory_self_report_max_ids}")


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
        mcp_tracking_enabled=parse_bool(
            env_override("OC_TELEMETRY_MCP_TRACKING_ENABLED", fc.get("mcp_tracking_enabled")),
            default=True,
        ),
        moe_tracking_enabled=parse_bool(
            env_override("OC_TELEMETRY_MOE_TRACKING_ENABLED", fc.get("moe_tracking_enabled")),
            default=True,
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


@dataclass(frozen=True)
class ConversationSettings:
    temperature: float = 0.2
    max_output_tokens: int = 512
    top_k_memory: int = 8
    last_n: int = 10
    include_pinned_memory: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(f"temperature must be in [0.0, 2.0], got {self.temperature}")
        if self.max_output_tokens <= 0:
            raise ValueError(f"max_output_tokens must be > 0, got {self.max_output_tokens}")
        if self.top_k_memory < 0:
            raise ValueError(f"top_k_memory must be >= 0, got {self.top_k_memory}")
        if self.last_n < 1:
            raise ValueError(f"last_n must be >= 1, got {self.last_n}")


def load_conversation_settings(
    file_config: dict[str, Any] | None = None,
) -> ConversationSettings:
    fc = file_config or {}
    return ConversationSettings(
        temperature=parse_float(
            env_override("OC_CONVO_TEMPERATURE", fc.get("temperature")),
            default=0.2,
        ),
        max_output_tokens=parse_int(
            env_override("OC_CONVO_MAX_OUTPUT_TOKENS", fc.get("max_output_tokens")),
            default=512,
        ),
        top_k_memory=parse_int(
            env_override("OC_CONVO_TOP_K_MEMORY", fc.get("top_k_memory")),
            default=8,
        ),
        last_n=parse_int(
            env_override("OC_CONVO_LAST_N", fc.get("last_n")),
            default=10,
        ),
        include_pinned_memory=parse_bool(
            env_override("OC_CONVO_INCLUDE_PINNED_MEMORY", fc.get("include_pinned_memory")),
            default=True,
        ),
    )


def _parse_optional_float(value: object) -> float | None:
    """Parse a float, returning None if unset or empty string."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            return None
    return None


@dataclass(frozen=True)
class MoESettings:
    """Mixture-of-Experts execution configuration."""

    enabled: bool = False
    min_experts: int = 2
    temperature: float | None = None

    def __post_init__(self) -> None:
        if self.min_experts < 2:
            raise ValueError(f"min_experts must be >= 2, got {self.min_experts}")


def load_moe_settings(
    file_config: dict[str, Any] | None = None,
) -> MoESettings:
    fc = file_config or {}
    return MoESettings(
        enabled=parse_bool(
            env_override("OC_MOE_ENABLED", fc.get("enabled")),
            default=False,
        ),
        min_experts=parse_int(
            env_override("OC_MOE_MIN_EXPERTS", fc.get("min_experts")),
            default=2,
        ),
        temperature=_parse_optional_float(
            env_override("OC_MOE_TEMPERATURE", fc.get("temperature")),
        ),
    )
