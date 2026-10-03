"""Deterministic OC cardinality matrix and isolated process-shaped test data."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product
from typing import Any, cast

from prometheus_client.metrics_core import CounterMetricFamily, GaugeMetricFamily, Metric

import openchronicle.core.infrastructure.observability.prometheus_recorder as metrics


@dataclass
class FrozenCollector:
    """Share one collected snapshot when comparing two serializers."""

    metrics: tuple[Metric, ...]

    def collect(self) -> Iterator[Metric]:
        return iter(self.metrics)


class ProcessShapedCollector:
    """Controlled Linux-shaped data; not evidence of native /proc behavior."""

    def __init__(self) -> None:
        self.calls = 0
        self.value = 1.0

    def collect(self) -> Iterator[Metric]:
        self.calls += 1
        yield CounterMetricFamily(
            "test_process_cpu_seconds", "Total user and system CPU time spent in seconds.", value=self.value
        )
        for name in (
            "resident_memory_bytes",
            "virtual_memory_bytes",
            "start_time_seconds",
            "open_fds",
            "max_fds",
        ):
            yield GaugeMetricFamily(
                "test_process_" + name, "Controlled process-shaped diagnostic sample.", value=self.value
            )


def make_recorder(*, full: bool) -> tuple[metrics.PrometheusMetricsRecorder, ProcessShapedCollector]:
    recorder = metrics.PrometheusMetricsRecorder()
    process = ProcessShapedCollector()
    # The test namespace coexists with Linux native process samples. This
    # controlled collector does not replace or verify native /proc behavior.
    recorder.registry.register(process)
    if not full:
        recorder.observe_http(path="/api/v1/memory", method="GET", status_code=200, duration_seconds=0.01)
        return recorder, process
    routes = [
        "/api/v1/memory",
        "/api/v1/memory/search",
        "/api/v1/memory/stats",
        "/api/v1/memory/embed",
        "/api/v1/project",
        "/api/v1/memory/example",
        "/api/v1/project/example",
        "/mcp",
        "/unknown",
    ]
    for route, method, status in product(
        routes, sorted(metrics._HTTP_METHODS) + ["unknown"], [100, 200, 300, 400, 500, 600]
    ):
        recorder.observe_http(path=route, method=method, status_code=status, duration_seconds=0.01)
    for tool, outcome in product(sorted(metrics._MCP_TOOLS) + ["unknown"], sorted(metrics._MCP_OUTCOMES) + ["unknown"]):
        recorder.observe_mcp(tool=tool, outcome=outcome, duration_seconds=0.01)
    for provider, operation, outcome in product(
        sorted(metrics._PROVIDERS) + ["unknown"],
        sorted(metrics._EMBEDDING_OPERATIONS) + ["unknown"],
        sorted(metrics._EMBEDDING_OUTCOMES) + ["unknown"],
    ):
        recorder.observe_embedding(provider=provider, operation=operation, outcome=outcome, duration_seconds=0.01)
    for kind in sorted(metrics._LOCK_KINDS) + ["unknown"]:
        recorder.observe_store_lock(kind=cast(Any, kind), wait_seconds=0.001, hold_seconds=0.01)
    for surface in sorted(metrics._SURFACES) + ["unknown"]:
        recorder.inflight_inc(cast(Any, surface))
        recorder.inflight_dec(cast(Any, surface))
    for stage in sorted(metrics._SEARCH_STAGES) + ["unknown"]:
        recorder.observe_search_stage(stage=stage, duration_seconds=0.01)
    for reason in sorted(metrics._FALLBACK_REASONS) + ["unknown"]:
        recorder.observe_search_fallback(reason=reason)
    for job, outcome in product(sorted(metrics._JOB_NAMES) + ["unknown"], sorted(metrics._JOB_OUTCOMES) + ["unknown"]):
        recorder.observe_job(name=job, outcome=outcome, duration_seconds=0.01)
        recorder.set_job_last_success(name=job, timestamp_seconds=0)
    for outcome in sorted(metrics._BACKFILL_OUTCOMES) + ["unknown"]:
        recorder.observe_backfill_item(outcome=outcome)
    for operation in [
        "http",
        "mcp",
        "inflight_inc",
        "inflight_dec",
        "store_lock",
        "embedding",
        "search_stage",
        "search_fallback",
        "job",
        "job_last_success",
        "backfill_item",
        "scrape",
    ]:
        recorder._recorder_errors.labels(operation=operation).inc(0)
    return recorder, process
