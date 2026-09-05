"""Build the per-container metrics implementation from environment config."""

from __future__ import annotations

import logging
import os
from typing import cast

from openchronicle.core.application.observability.exporter import MetricsExporter
from openchronicle.core.application.observability.null_recorder import NullMetricsRecorder
from openchronicle.core.domain.exceptions import ConfigError
from openchronicle.core.domain.ports.metrics_port import MetricsRecorder

logger = logging.getLogger(__name__)


def metrics_enabled_from_env() -> bool:
    """Parse OC_METRICS_ENABLED, defaulting safely to disabled."""
    raw = os.getenv("OC_METRICS_ENABLED", "").strip().lower()
    if not raw:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    logger.warning("Invalid OC_METRICS_ENABLED=%r; using default false", raw)
    return False


def create_metrics() -> tuple[MetricsRecorder, MetricsExporter | None]:
    """Return one recorder/exporter pair for one application lifecycle."""
    if not metrics_enabled_from_env():
        return NullMetricsRecorder(), None
    try:
        from openchronicle.core.infrastructure.observability.prometheus_recorder import PrometheusMetricsRecorder

        recorder = PrometheusMetricsRecorder()
    except ImportError as exc:
        raise ConfigError(
            "OC_METRICS_ENABLED is true but prometheus-client is not installed; "
            "install openchronicle-mcp[metrics] or use the standard image",
        ) from exc
    return cast(MetricsRecorder, recorder), cast(MetricsExporter, recorder)
