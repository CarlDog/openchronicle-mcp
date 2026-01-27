from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PrivacyOutboundSettings:
    mode: str = "off"
    external_only: bool = True
    categories: list[str] = field(default_factory=lambda: ["email", "phone", "ip", "ssn", "cc", "api_key"])
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


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_categories(value: str | None) -> list[str]:
    if value is None:
        return ["email", "phone", "ip", "ssn", "cc", "api_key"]
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_int(value: str | None, *, default: int) -> int:
    if value is None:
        return default
    raw = value.strip()
    if not raw.isdigit():
        return default
    return int(raw)


def load_privacy_outbound_settings() -> PrivacyOutboundSettings:
    return PrivacyOutboundSettings(
        mode=os.getenv("OC_PRIVACY_OUTBOUND_MODE", "off"),
        external_only=_parse_bool(os.getenv("OC_PRIVACY_OUTBOUND_EXTERNAL_ONLY"), default=True),
        categories=_parse_categories(os.getenv("OC_PRIVACY_OUTBOUND_CATEGORIES")),
        redact_style=os.getenv("OC_PRIVACY_OUTBOUND_REDACT_STYLE", "mask"),
        log_events=_parse_bool(os.getenv("OC_PRIVACY_OUTBOUND_LOG"), default=True),
    )


def load_telemetry_settings() -> TelemetrySettings:
    return TelemetrySettings(
        enabled=_parse_bool(os.getenv("OC_TELEMETRY_ENABLED"), default=True),
        perf_enabled=_parse_bool(os.getenv("OC_TELEMETRY_PERF_ENABLED"), default=True),
        usage_enabled=_parse_bool(os.getenv("OC_TELEMETRY_USAGE_ENABLED"), default=True),
        context_enabled=_parse_bool(os.getenv("OC_TELEMETRY_CONTEXT_ENABLED"), default=True),
        memory_enabled=_parse_bool(os.getenv("OC_TELEMETRY_MEMORY_ENABLED"), default=True),
        memory_self_report_enabled=_parse_bool(
            os.getenv("OC_TELEMETRY_MEMORY_SELF_REPORT_ENABLED"),
            default=False,
        ),
        memory_self_report_max_ids=_parse_int(
            os.getenv("OC_TELEMETRY_MEMORY_SELF_REPORT_MAX_IDS"),
            default=20,
        ),
        memory_self_report_strict=_parse_bool(
            os.getenv("OC_TELEMETRY_MEMORY_SELF_REPORT_STRICT"),
            default=False,
        ),
    )
