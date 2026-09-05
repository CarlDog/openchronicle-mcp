"""Bounded Prometheus recorder and guarded scrape exporter."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable
from typing import Final

from openchronicle.core.application.observability.exporter import (
    MetricsScrapeBusyError,
    MetricsScrapeError,
)
from openchronicle.core.domain.ports.metrics_port import LockKind, MetricsSurface
from openchronicle.version import build_revision, package_version

logger = logging.getLogger(__name__)

REQUEST_BUCKETS: Final[tuple[float, ...]] = (
    0.001,
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
    60.0,
)
LOCK_BUCKETS: Final[tuple[float, ...]] = (0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 30.0)
JOB_BUCKETS: Final[tuple[float, ...]] = (0.01, 0.1, 0.5, 1.0, 5.0, 30.0, 60.0, 300.0, 900.0, 3600.0)

_UNKNOWN = "__unknown__"
_HTTP_METHODS: Final[frozenset[str]] = frozenset({"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"})
_MCP_TOOLS: Final[frozenset[str]] = frozenset(
    {
        "health",
        "project_create",
        "project_get",
        "project_list",
        "project_update",
        "project_delete",
        "project_delete_bulk",
        "onboard_git",
        "memory_search",
        "memory_save",
        "memory_list",
        "memory_pin",
        "memory_update",
        "memory_get",
        "memory_delete",
        "memory_stats",
        "memory_embed",
        "context_recent",
    }
)
_PROVIDERS: Final[frozenset[str]] = frozenset({"none", "stub", "openai", "ollama"})
_EMBEDDING_OPERATIONS: Final[frozenset[str]] = frozenset({"single", "batch"})
_EMBEDDING_OUTCOMES: Final[frozenset[str]] = frozenset(
    {"success", "transient_failure", "permanent_rejection", "other_error"}
)
_MCP_OUTCOMES: Final[frozenset[str]] = frozenset({"ok", "started", "partial", "rejected", "error", "cancelled"})
_SEARCH_STAGES: Final[frozenset[str]] = frozenset(
    {"keyword_lookup", "vector_loading", "candidate_prep_scoring", "fusion_materialization"}
)
_FALLBACK_REASONS: Final[frozenset[str]] = frozenset({"provider_failure", "over_length_query"})
_JOB_NAMES: Final[frozenset[str]] = frozenset(
    {"db_vacuum", "db_integrity_check", "embedding_backfill", "db_backup", "git_onboard_resync", "operator_backfill"}
)
_JOB_OUTCOMES: Final[frozenset[str]] = frozenset({"success", "partial", "failure", "cancel", "overlap"})
_BACKFILL_OUTCOMES: Final[frozenset[str]] = frozenset({"generated", "failed", "tombstoned"})


def _bounded(value: str, allowed: frozenset[str]) -> str:
    return value if value in allowed else _UNKNOWN


def _duration(value: float) -> float:
    try:
        return max(0.0, float(value))
    except TypeError, ValueError:
        return 0.0


def normalize_http_route(path: str) -> str | None:
    """Map an ASGI path to a fixed route label, or exclude it."""
    if path in {
        "/health",
        "/api/v1/health",
        "/docs",
        "/docs/",
        "/docs/oauth2-redirect",
        "/redoc",
        "/redoc/",
        "/openapi.json",
        "/metrics",
        "/metrics/",
    }:
        return None
    fixed = {
        "/api/v1/memory",
        "/api/v1/memory/search",
        "/api/v1/memory/stats",
        "/api/v1/memory/embed",
        "/api/v1/project",
    }
    if path in fixed:
        return path
    if path.startswith("/api/v1/memory/"):
        return "/api/v1/memory/{memory_id}"
    if path.startswith("/api/v1/project/"):
        return "/api/v1/project/{project_id}"
    if path == "/mcp":
        return "/mcp"
    return _UNKNOWN


def _status_class(status_code: int) -> str:
    if 100 <= status_code <= 599:
        return f"{status_code // 100}xx"
    return "other"


class PrometheusMetricsRecorder:
    """Per-container recorder with only fixed-cardinality label values."""

    enabled = True

    def __init__(self) -> None:
        # Imports stay in the enabled-only factory path. A normal install with
        # metrics disabled never imports prometheus-client.
        from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
        from prometheus_client.process_collector import ProcessCollector

        self._generate_latest: Callable[..., bytes] = generate_latest
        self.registry = CollectorRegistry(auto_describe=True)
        # Register only the standard process collector explicitly. On
        # platforms without /proc it simply contributes no process samples.
        ProcessCollector(registry=self.registry)

        self._http_requests = Counter(
            "oc_http_requests_total",
            "Completed REST HTTP requests.",
            ["route", "method", "status_class"],
            registry=self.registry,
        )
        self._http_duration = Histogram(
            "oc_http_request_duration_seconds",
            "REST HTTP request duration in seconds.",
            ["route", "method"],
            buckets=REQUEST_BUCKETS,
            registry=self.registry,
        )
        self._mcp_executions = Counter(
            "oc_mcp_executions_total",
            "MCP tool executions.",
            ["tool", "outcome"],
            registry=self.registry,
        )
        self._mcp_duration = Histogram(
            "oc_mcp_execution_duration_seconds",
            "MCP tool execution duration in seconds.",
            ["tool"],
            buckets=REQUEST_BUCKETS,
            registry=self.registry,
        )
        self._inflight = Gauge(
            "oc_requests_inflight",
            "Currently admitted REST requests and MCP tool handlers.",
            ["surface"],
            registry=self.registry,
        )
        self._lock_wait = Histogram(
            "oc_store_lock_wait_seconds",
            "Time waiting for the shared SQLite store lock.",
            ["kind"],
            buckets=LOCK_BUCKETS,
            registry=self.registry,
        )
        self._lock_hold = Histogram(
            "oc_store_lock_hold_seconds",
            "Time holding the shared SQLite store lock.",
            ["kind"],
            buckets=REQUEST_BUCKETS,
            registry=self.registry,
        )
        self._embedding_operations = Counter(
            "oc_embedding_operations_total",
            "Embedding provider operations.",
            ["provider", "operation", "outcome"],
            registry=self.registry,
        )
        self._embedding_duration = Histogram(
            "oc_embedding_operation_duration_seconds",
            "Embedding provider operation duration in seconds.",
            ["provider", "operation"],
            buckets=REQUEST_BUCKETS,
            registry=self.registry,
        )
        self._search_stage_duration = Histogram(
            "oc_search_stage_duration_seconds",
            "Search pipeline stage duration in seconds.",
            ["stage"],
            buckets=REQUEST_BUCKETS,
            registry=self.registry,
        )
        self._search_fallbacks = Counter(
            "oc_search_fallbacks_total",
            "Search degradation fallbacks.",
            ["reason"],
            registry=self.registry,
        )
        self._job_runs = Counter(
            "oc_job_runs_total",
            "Maintenance and operator job runs.",
            ["job", "outcome"],
            registry=self.registry,
        )
        self._job_duration = Histogram(
            "oc_job_duration_seconds",
            "Maintenance and operator job duration in seconds.",
            ["job"],
            buckets=JOB_BUCKETS,
            registry=self.registry,
        )
        self._job_last_success = Gauge(
            "oc_job_last_success_timestamp_seconds",
            "Unix timestamp of the last successful job completion.",
            ["job"],
            registry=self.registry,
        )
        self._backfill_items = Counter(
            "oc_backfill_items_total",
            "Backfill item outcomes.",
            ["outcome"],
            registry=self.registry,
        )
        self._recorder_healthy = Gauge(
            "oc_metrics_recorder_healthy",
            "Whether the metrics recorder has completed its last operation successfully.",
            registry=self.registry,
        )
        self._recorder_errors = Counter(
            "oc_metrics_recorder_errors_total",
            "Metrics recorder failures by bounded operation name.",
            ["operation"],
            registry=self.registry,
        )
        self._build_info = Gauge(
            "oc_build_info",
            "OpenChronicle build identity.",
            ["version", "revision"],
            registry=self.registry,
        )
        self._build_info.labels(version=package_version(), revision=build_revision()).set(1)
        self._recorder_healthy.set(1)

        # The event loop acquires this slot before dispatching serialization
        # to a worker. Therefore a second scrape returns 503 instead of
        # waiting in an executor queue. The worker owns the release, even if
        # the awaiting request is cancelled.
        self._scrape_slot = threading.Lock()
        self._warning_lock = threading.Lock()
        self._warning_emitted = False

    @property
    def content_type(self) -> str:
        from prometheus_client import CONTENT_TYPE_LATEST

        return CONTENT_TYPE_LATEST

    def _mark_error(self, operation: str) -> None:
        try:
            self._recorder_healthy.set(0)
            self._recorder_errors.labels(operation=operation).inc()
        except Exception:  # pragma: no cover - defensive against exporter failure
            pass
        with self._warning_lock:
            if not self._warning_emitted:
                logger.warning("metrics recorder failure; metric samples may be incomplete")
                self._warning_emitted = True

    def _safe(self, operation: str, callback: Callable[[], None]) -> None:
        try:
            callback()
            self._recorder_healthy.set(1)
        except Exception:  # pragma: no cover - prometheus-client is defensive, but metrics must never break OC
            self._mark_error(operation)

    def inflight_inc(self, surface: MetricsSurface) -> None:
        self._safe(
            "inflight_inc", lambda: self._inflight.labels(surface=_bounded(surface, frozenset({"rest", "mcp"}))).inc()
        )

    def inflight_dec(self, surface: MetricsSurface) -> None:
        self._safe(
            "inflight_dec", lambda: self._inflight.labels(surface=_bounded(surface, frozenset({"rest", "mcp"}))).dec()
        )

    def observe_http(
        self,
        *,
        path: str,
        method: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        route = normalize_http_route(path)
        if route is None:
            return
        bounded_method = method if method in _HTTP_METHODS else _UNKNOWN
        duration = _duration(duration_seconds)

        def record() -> None:
            self._http_requests.labels(
                route=route,
                method=bounded_method,
                status_class=_status_class(status_code),
            ).inc()
            self._http_duration.labels(route=route, method=bounded_method).observe(duration)

        self._safe("http", record)

    def observe_mcp(self, *, tool: str, outcome: str, duration_seconds: float) -> None:
        bounded_tool = _bounded(tool, _MCP_TOOLS)
        bounded_outcome = _bounded(outcome, _MCP_OUTCOMES)
        duration = _duration(duration_seconds)

        def record() -> None:
            self._mcp_executions.labels(tool=bounded_tool, outcome=bounded_outcome).inc()
            self._mcp_duration.labels(tool=bounded_tool).observe(duration)

        self._safe("mcp", record)

    def observe_store_lock(self, *, kind: LockKind, wait_seconds: float, hold_seconds: float) -> None:
        bounded_kind = _bounded(kind, frozenset({"read", "write", "maintenance"}))
        wait = _duration(wait_seconds)
        hold = _duration(hold_seconds)

        def record() -> None:
            self._lock_wait.labels(kind=bounded_kind).observe(wait)
            self._lock_hold.labels(kind=bounded_kind).observe(hold)

        self._safe("store_lock", record)

    def observe_embedding(
        self,
        *,
        provider: str,
        operation: str,
        outcome: str,
        duration_seconds: float,
    ) -> None:
        bounded_provider = _bounded(provider, _PROVIDERS)
        bounded_operation = _bounded(operation, _EMBEDDING_OPERATIONS)
        bounded_outcome = _bounded(outcome, _EMBEDDING_OUTCOMES)
        duration = _duration(duration_seconds)

        def record() -> None:
            self._embedding_operations.labels(
                provider=bounded_provider,
                operation=bounded_operation,
                outcome=bounded_outcome,
            ).inc()
            self._embedding_duration.labels(provider=bounded_provider, operation=bounded_operation).observe(duration)

        self._safe("embedding", record)

    def observe_search_stage(self, *, stage: str, duration_seconds: float) -> None:
        self._safe(
            "search_stage",
            lambda: self._search_stage_duration.labels(stage=_bounded(stage, _SEARCH_STAGES)).observe(
                _duration(duration_seconds)
            ),
        )

    def observe_search_fallback(self, *, reason: str) -> None:
        self._safe(
            "search_fallback",
            lambda: self._search_fallbacks.labels(reason=_bounded(reason, _FALLBACK_REASONS)).inc(),
        )

    def observe_job(self, *, name: str, outcome: str, duration_seconds: float | None = None) -> None:
        bounded_name = _bounded(name, _JOB_NAMES)
        bounded_outcome = _bounded(outcome, _JOB_OUTCOMES)

        def record() -> None:
            self._job_runs.labels(job=bounded_name, outcome=bounded_outcome).inc()
            if duration_seconds is not None:
                self._job_duration.labels(job=bounded_name).observe(_duration(duration_seconds))

        self._safe("job", record)

    def set_job_last_success(self, *, name: str, timestamp_seconds: float) -> None:
        self._safe(
            "job_last_success",
            lambda: self._job_last_success.labels(job=_bounded(name, _JOB_NAMES)).set(
                max(0.0, float(timestamp_seconds))
            ),
        )

    def observe_backfill_item(self, *, outcome: str) -> None:
        self._safe(
            "backfill_item",
            lambda: self._backfill_items.labels(outcome=_bounded(outcome, _BACKFILL_OUTCOMES)).inc(),
        )

    def _render_owned(self) -> bytes:
        try:
            return self._generate_latest(self.registry)
        except Exception as exc:
            self._mark_error("scrape")
            raise MetricsScrapeError("metrics scrape serialization failed") from exc
        finally:
            self._scrape_slot.release()

    async def render(self) -> bytes:
        if not self._scrape_slot.acquire(blocking=False):
            raise MetricsScrapeBusyError("metrics scrape already in progress")
        try:
            # The worker owns the slot and releases it after serialization.
            # shield keeps request cancellation from cancelling the worker,
            # which prevents a stale active-slot leak or premature reuse.
            worker = asyncio.create_task(asyncio.to_thread(self._render_owned))
        except BaseException:
            self._scrape_slot.release()
            raise
        return await asyncio.shield(worker)
