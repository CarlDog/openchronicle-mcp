"""Application-facing port for bounded runtime metrics observations."""

from __future__ import annotations

from typing import Literal, Protocol

MetricsSurface = Literal["rest", "mcp"]
LockKind = Literal["read", "write", "maintenance"]


class MetricsRecorder(Protocol):
    """Record fixed-cardinality observations without owning their export."""

    enabled: bool

    def inflight_inc(self, surface: MetricsSurface) -> None: ...

    def inflight_dec(self, surface: MetricsSurface) -> None: ...

    def observe_http(
        self,
        *,
        path: str,
        method: str,
        status_code: int,
        duration_seconds: float,
    ) -> None: ...

    def observe_mcp(
        self,
        *,
        tool: str,
        outcome: str,
        duration_seconds: float,
    ) -> None: ...

    def observe_store_lock(self, *, kind: LockKind, wait_seconds: float, hold_seconds: float) -> None: ...

    def observe_embedding(
        self,
        *,
        provider: str,
        operation: str,
        outcome: str,
        duration_seconds: float,
    ) -> None: ...

    def observe_search_stage(self, *, stage: str, duration_seconds: float) -> None: ...

    def observe_search_fallback(self, *, reason: str) -> None: ...

    def observe_job(self, *, name: str, outcome: str, duration_seconds: float | None = None) -> None: ...

    def set_job_last_success(self, *, name: str, timestamp_seconds: float) -> None: ...

    def observe_backfill_item(self, *, outcome: str) -> None: ...
