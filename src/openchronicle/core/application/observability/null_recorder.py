"""No-op implementation used when metrics collection is disabled."""

from __future__ import annotations

from openchronicle.core.domain.ports.metrics_port import LockKind, MetricsSurface


class NullMetricsRecorder:
    """Keep instrumentation call sites cheap and dependency-free by default."""

    enabled = False

    def inflight_inc(self, surface: MetricsSurface) -> None:
        del surface

    def inflight_dec(self, surface: MetricsSurface) -> None:
        del surface

    def observe_http(
        self,
        *,
        path: str,
        method: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        del path, method, status_code, duration_seconds

    def observe_mcp(self, *, tool: str, outcome: str, duration_seconds: float) -> None:
        del tool, outcome, duration_seconds

    def observe_store_lock(self, *, kind: LockKind, wait_seconds: float, hold_seconds: float) -> None:
        del kind, wait_seconds, hold_seconds

    def observe_embedding(
        self,
        *,
        provider: str,
        operation: str,
        outcome: str,
        duration_seconds: float,
    ) -> None:
        del provider, operation, outcome, duration_seconds

    def observe_search_stage(self, *, stage: str, duration_seconds: float) -> None:
        del stage, duration_seconds

    def observe_search_fallback(self, *, reason: str) -> None:
        del reason

    def observe_job(self, *, name: str, outcome: str, duration_seconds: float | None = None) -> None:
        del name, outcome, duration_seconds

    def set_job_last_success(self, *, name: str, timestamp_seconds: float) -> None:
        del name, timestamp_seconds

    def observe_backfill_item(self, *, outcome: str) -> None:
        del outcome
