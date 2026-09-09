"""Contract tests for the opt-in, bounded runtime metrics surface."""

from __future__ import annotations

import asyncio
import builtins
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from prometheus_client import generate_latest

from openchronicle.core.application.observability.exporter import MetricsScrapeBusyError, MetricsScrapeError
from openchronicle.core.application.observability.null_recorder import NullMetricsRecorder
from openchronicle.core.application.services.embedding_service import EmbeddingService
from openchronicle.core.application.services.maintenance_loop import JobState, MaintenanceLoop
from openchronicle.core.domain.exceptions import ConfigError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.infrastructure.embedding.stub_adapter import StubEmbeddingAdapter
from openchronicle.core.infrastructure.observability.factory import create_metrics
from openchronicle.core.infrastructure.observability.prometheus_recorder import (
    REQUEST_BUCKETS,
    PrometheusMetricsRecorder,
)
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.interfaces.api.app import create_app
from openchronicle.interfaces.api.config import HTTPConfig
from openchronicle.interfaces.api.middleware.metrics import MetricsMiddleware
from openchronicle.interfaces.mcp.server import MetricsFastMCP


def _text(recorder: PrometheusMetricsRecorder) -> str:
    return generate_latest(recorder.registry).decode("utf-8")


def _mock_container(*, recorder: object, exporter: object | None) -> MagicMock:
    container = MagicMock()
    container.file_configs = {}
    container.metrics = recorder
    container.metrics_exporter = exporter
    container.storage = MagicMock()
    container.storage.list_projects.return_value = []
    container.storage.list_memory.return_value = []
    container.storage.search_memory.return_value = []
    container.storage.search_pinned.return_value = []
    container.embedding_service = None
    container.embedding_status_dict.return_value = {"status": "disabled", "provider": "none"}
    container.maintenance_degraded = False
    return container


def test_metrics_are_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OC_METRICS_ENABLED", raising=False)
    recorder, exporter = create_metrics()
    assert isinstance(recorder, NullMetricsRecorder)
    assert exporter is None


def test_enabled_metrics_require_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OC_METRICS_ENABLED", "true")
    real_import = builtins.__import__

    def blocked_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "prometheus_client" or name.startswith("prometheus_client."):
            raise ImportError("simulated missing optional dependency")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    with pytest.raises(ConfigError, match="prometheus-client.*not installed"):
        create_metrics()


def test_prometheus_labels_are_bounded_and_sensitive_paths_are_not_exported() -> None:
    recorder = PrometheusMetricsRecorder()
    recorder.observe_http(path="/api/v1/memory/user-secret-123", method="TRACE", status_code=799, duration_seconds=1)
    recorder.observe_http(path="/health", method="GET", status_code=200, duration_seconds=1)
    recorder.observe_http(path="/metrics/", method="GET", status_code=200, duration_seconds=1)
    recorder.observe_mcp(tool="tool-with-user-secret", outcome="secret-outcome", duration_seconds=1)
    recorder.observe_embedding(
        provider="https://provider.example/secret",
        operation="secret-operation",
        outcome="secret-outcome",
        duration_seconds=1,
    )
    recorder.observe_search_stage(stage="secret-stage", duration_seconds=1)
    recorder.observe_search_fallback(reason="secret-reason")
    recorder.observe_job(name="secret-job", outcome="secret-outcome", duration_seconds=1)
    recorder.observe_backfill_item(outcome="secret-outcome")

    text = _text(recorder)
    assert "user-secret-123" not in text
    assert "provider.example" not in text
    assert "secret-outcome" not in text
    assert 'route="/health"' not in text
    assert 'route="/metrics/"' not in text
    assert "__unknown__" in text


def test_metric_cardinality_stays_bounded_under_untrusted_values() -> None:
    recorder = PrometheusMetricsRecorder()
    for index in range(500):
        recorder.observe_http(
            path=f"/api/v1/memory/{index}",
            method=f"METHOD-{index}",
            status_code=600 + index,
            duration_seconds=index,
        )
        recorder.observe_mcp(tool=f"tool-{index}", outcome=f"outcome-{index}", duration_seconds=index)
        recorder.observe_embedding(
            provider=f"provider-{index}",
            operation=f"operation-{index}",
            outcome=f"outcome-{index}",
            duration_seconds=index,
        )
        recorder.observe_search_stage(stage=f"stage-{index}", duration_seconds=index)
        recorder.observe_search_fallback(reason=f"reason-{index}")
        recorder.observe_job(name=f"job-{index}", outcome=f"outcome-{index}", duration_seconds=index)
        recorder.observe_backfill_item(outcome=f"outcome-{index}")

    text = _text(recorder)
    series = sum(1 for line in text.splitlines() if line and not line.startswith("#"))
    assert series < 5_000
    assert len(text) < 1_048_576


def test_each_recorder_owns_an_independent_registry() -> None:
    first = PrometheusMetricsRecorder()
    second = PrometheusMetricsRecorder()
    first.observe_http(path="/api/v1/project", method="GET", status_code=200, duration_seconds=0.01)

    assert 'route="/api/v1/project"' in _text(first)
    assert "oc_http_requests_total{" not in _text(second)


def test_hot_metric_children_are_reused_after_first_observation(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = PrometheusMetricsRecorder()
    recorder.observe_http(path="/api/v1/memory", method="GET", status_code=200, duration_seconds=0.01)
    recorder.observe_embedding(provider="stub", operation="single", outcome="success", duration_seconds=0.01)
    recorder.observe_store_lock(kind="read", wait_seconds=0.001, hold_seconds=0.01)
    recorder.observe_search_stage(stage="keyword_lookup", duration_seconds=0.01)
    recorder.inflight_inc("rest")

    def unexpected_labels(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("cached observation must not repeat labels()")

    for metric in (
        recorder._lock_wait,
        recorder._lock_hold,
        recorder._search_stage_duration,
        recorder._inflight,
        recorder._http_requests,
        recorder._http_duration,
        recorder._embedding_operations,
        recorder._embedding_duration,
    ):
        monkeypatch.setattr(metric, "labels", unexpected_labels)
    recorder.observe_http(path="/api/v1/memory", method="GET", status_code=201, duration_seconds=0.01)
    recorder.observe_embedding(provider="stub", operation="single", outcome="success", duration_seconds=0.01)
    recorder.observe_store_lock(kind="read", wait_seconds=0.001, hold_seconds=0.01)
    recorder.observe_search_stage(stage="keyword_lookup", duration_seconds=0.01)
    recorder.inflight_dec("rest")
    assert recorder.registry.get_sample_value("oc_metrics_recorder_healthy") == 1
    assert recorder.registry.get_sample_value("oc_store_lock_wait_seconds_count", {"kind": "read"}) == 2
    assert (
        recorder.registry.get_sample_value("oc_search_stage_duration_seconds_count", {"stage": "keyword_lookup"}) == 2
    )
    assert recorder.registry.get_sample_value("oc_requests_inflight", {"surface": "rest"}) == 0
    assert (
        recorder.registry.get_sample_value(
            "oc_http_requests_total", {"route": "/api/v1/memory", "method": "GET", "status_class": "2xx"}
        )
        == 2
    )
    assert (
        recorder.registry.get_sample_value(
            "oc_embedding_operations_total", {"provider": "stub", "operation": "single", "outcome": "success"}
        )
        == 2
    )
    assert (
        recorder.registry.get_sample_value(
            "oc_http_request_duration_seconds_count", {"route": "/api/v1/memory", "method": "GET"}
        )
        == 2
    )
    assert (
        recorder.registry.get_sample_value(
            "oc_embedding_operation_duration_seconds_count", {"provider": "stub", "operation": "single"}
        )
        == 2
    )


def test_child_caches_are_bounded_normalized_and_recorder_local() -> None:
    first = PrometheusMetricsRecorder()
    second = PrometheusMetricsRecorder()
    for index in range(100):
        first.observe_http(
            path=f"/unknown-{index}", method=f"unknown-{index}", status_code=600 + index, duration_seconds=0
        )
        first.observe_embedding(
            provider=f"unknown-{index}", operation=f"unknown-{index}", outcome=f"unknown-{index}", duration_seconds=0
        )
        first.observe_store_lock(kind=cast(Any, f"unknown-{index}"), wait_seconds=0, hold_seconds=0)
        first.observe_search_stage(stage=f"unknown-{index}", duration_seconds=0)
        first.inflight_inc(cast(Any, f"unknown-{index}"))
        first.inflight_dec(cast(Any, f"unknown-{index}"))
    assert set(first._lock_children) == set(first._stage_children) == set(first._inflight_children) == {"__unknown__"}
    assert not second._lock_children and not second._stage_children and not second._inflight_children
    assert set(first._http_request_children) == {("__unknown__", "__unknown__", "other")}
    assert set(first._embedding_operation_children) == {("__unknown__", "__unknown__", "__unknown__")}
    assert (
        set(first._http_duration_children)
        == set(first._embedding_duration_children)
        == {("__unknown__", "__unknown__")}
    )
    assert not second._http_request_children and not second._http_duration_children
    assert not second._embedding_operation_children and not second._embedding_duration_children
    assert second.registry.get_sample_value("oc_store_lock_wait_seconds_count", {"kind": "__unknown__"}) is None
    assert "unknown-99" not in _text(first)


def test_http_and_embedding_cache_full_label_bounds() -> None:
    recorder = PrometheusMetricsRecorder()
    paths = (
        "/api/v1/memory",
        "/api/v1/memory/search",
        "/api/v1/memory/stats",
        "/api/v1/memory/embed",
        "/api/v1/project",
        "/api/v1/memory/secret-id",
        "/api/v1/project/secret-id",
        "/mcp",
        "/unknown-path",
    )
    for path, method, status in product(
        paths, ("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD", "TRACE"), (100, 200, 300, 400, 500, 799)
    ):
        recorder.observe_http(path=path, method=method, status_code=status, duration_seconds=0.01)
    for provider, operation, outcome in product(
        ("none", "stub", "openai", "ollama", "unknown-provider"),
        ("single", "batch", "unknown-operation"),
        ("success", "transient_failure", "permanent_rejection", "other_error", "unknown-outcome"),
    ):
        recorder.observe_embedding(provider=provider, operation=operation, outcome=outcome, duration_seconds=0.01)
    assert len(recorder._http_request_children) == 432
    assert len(recorder._http_duration_children) == 72
    assert len(recorder._embedding_operation_children) == 75
    assert len(recorder._embedding_duration_children) == 15
    assert recorder.registry.get_sample_value("oc_metrics_recorder_healthy") == 1
    for histogram, count in (
        *((child, 6) for child in recorder._http_duration_children.values()),
        *((child, 5) for child in recorder._embedding_duration_children.values()),
    ):
        samples = list(histogram.collect())[0].samples
        assert next(s.value for s in samples if s.name.endswith("_count")) == count
        assert next(s.value for s in samples if s.name.endswith("_sum")) == pytest.approx(count * 0.01)
        for sample in samples:
            if sample.name.endswith("_bucket"):
                assert sample.value == (count if float(sample.labels["le"]) >= 0.01 else 0)


def test_histogram_children_are_shared_across_new_status_and_outcome_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = PrometheusMetricsRecorder()
    recorder.observe_http(path="/api/v1/memory", method="GET", status_code=200, duration_seconds=0.01)
    recorder.observe_embedding(provider="stub", operation="single", outcome="success", duration_seconds=0.01)

    def unexpected_labels(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("new counter labels must reuse the duration child")

    monkeypatch.setattr(recorder._http_duration, "labels", unexpected_labels)
    monkeypatch.setattr(recorder._embedding_duration, "labels", unexpected_labels)
    recorder.observe_http(path="/api/v1/memory", method="GET", status_code=503, duration_seconds=0.01)
    recorder.observe_embedding(provider="stub", operation="single", outcome="other_error", duration_seconds=0.01)
    assert len(recorder._http_request_children) == len(recorder._embedding_operation_children) == 2
    assert len(recorder._http_duration_children) == len(recorder._embedding_duration_children) == 1
    assert recorder.registry.get_sample_value("oc_metrics_recorder_healthy") == 1


def test_concurrent_first_use_keeps_exact_counts_and_gauges(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = PrometheusMetricsRecorder()
    barrier = threading.Barrier(8)

    def concurrent_labels(parent: Any) -> Any:
        original = parent.labels
        first_use = threading.Barrier(8)

        def labels(*args: Any, **kwargs: Any) -> Any:
            # All eight workers must miss this cache before any can publish
            # its child. Rely on the library to return the same child to each.
            first_use.wait(timeout=5)
            return original(*args, **kwargs)

        return labels

    for parent in (
        recorder._http_requests,
        recorder._http_duration,
        recorder._embedding_operations,
        recorder._embedding_duration,
    ):
        monkeypatch.setattr(parent, "labels", concurrent_labels(parent))

    def work(_: int) -> None:
        barrier.wait(timeout=5)
        for _ in range(100):
            recorder.inflight_inc("rest")
            recorder.observe_store_lock(kind="read", wait_seconds=0.001, hold_seconds=0.01)
            recorder.observe_search_stage(stage="keyword_lookup", duration_seconds=0.01)
            recorder.observe_http(path="/api/v1/memory", method="GET", status_code=200, duration_seconds=0.01)
            recorder.observe_embedding(provider="stub", operation="single", outcome="success", duration_seconds=0.01)
            recorder.inflight_dec("rest")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(work, range(8)))
    registry = recorder.registry
    assert registry.get_sample_value("oc_store_lock_wait_seconds_count", {"kind": "read"}) == 800
    assert registry.get_sample_value("oc_store_lock_wait_seconds_sum", {"kind": "read"}) == pytest.approx(0.8)
    assert registry.get_sample_value("oc_store_lock_hold_seconds_count", {"kind": "read"}) == 800
    assert registry.get_sample_value("oc_store_lock_hold_seconds_sum", {"kind": "read"}) == pytest.approx(8)
    assert registry.get_sample_value("oc_search_stage_duration_seconds_count", {"stage": "keyword_lookup"}) == 800
    assert registry.get_sample_value("oc_requests_inflight", {"surface": "rest"}) == 0
    assert registry.get_sample_value("oc_metrics_recorder_healthy") == 1
    for metric, labels in (
        ("oc_http_requests_total", {"route": "/api/v1/memory", "method": "GET", "status_class": "2xx"}),
        ("oc_embedding_operations_total", {"provider": "stub", "operation": "single", "outcome": "success"}),
    ):
        assert registry.get_sample_value(metric, labels) == 800
    for metric, labels in (
        ("oc_http_request_duration_seconds", {"route": "/api/v1/memory", "method": "GET"}),
        ("oc_embedding_operation_duration_seconds", {"provider": "stub", "operation": "single"}),
    ):
        assert registry.get_sample_value(f"{metric}_count", labels) == 800
        assert registry.get_sample_value(f"{metric}_sum", labels) == pytest.approx(8)
        for bound in (*REQUEST_BUCKETS, float("inf")):
            assert registry.get_sample_value(
                f"{metric}_bucket", {**labels, "le": "+Inf" if bound == float("inf") else str(bound)}
            ) == (800 if bound >= 0.01 else 0)


@pytest.mark.parametrize("kind", ["http", "embedding"])
@pytest.mark.parametrize("failure", ["counter_labels", "counter_inc", "histogram_labels", "histogram_observe"])
def test_request_cache_failures_preserve_partial_observations_and_recover(
    kind: str,
    failure: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = PrometheusMetricsRecorder()
    if kind == "http":

        def observe(duration: float) -> None:
            recorder.observe_http(path="/api/v1/memory", method="GET", status_code=200, duration_seconds=duration)

        counter_parent, histogram_parent = recorder._http_requests, recorder._http_duration
        counters, histograms = recorder._http_request_children, recorder._http_duration_children
        counter_name, histogram_name = "oc_http_requests_total", "oc_http_request_duration_seconds"
        labels = {"route": "/api/v1/memory", "method": "GET"}
        counter_labels = {**labels, "status_class": "2xx"}
    else:

        def observe(duration: float) -> None:
            recorder.observe_embedding(
                provider="stub", operation="single", outcome="success", duration_seconds=duration
            )

        counter_parent, histogram_parent = recorder._embedding_operations, recorder._embedding_duration
        counters, histograms = recorder._embedding_operation_children, recorder._embedding_duration_children
        counter_name, histogram_name = "oc_embedding_operations_total", "oc_embedding_operation_duration_seconds"
        labels = {"provider": "stub", "operation": "single"}
        counter_labels = {**labels, "outcome": "success"}

    primed = not failure.endswith("labels")
    if primed:
        observe(0.01)
    target: Any
    if failure.startswith("counter"):
        target = next(iter(counters.values())) if primed else counter_parent
    else:
        target = next(iter(histograms.values())) if primed else histogram_parent
    method = failure.split("_", 1)[1]
    original = getattr(target, method)

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("synthetic recorder failure")

    monkeypatch.setattr(target, method, fail)
    observe(0.25)
    registry = recorder.registry
    assert registry.get_sample_value("oc_metrics_recorder_healthy") == 0
    assert registry.get_sample_value("oc_metrics_recorder_errors_total", {"operation": kind}) == 1
    counter_count = int(primed) + int(failure.startswith("histogram"))
    assert registry.get_sample_value(counter_name, counter_labels) == (counter_count or None)
    assert registry.get_sample_value(f"{histogram_name}_count", labels) == (1 if primed else None)
    if failure == "counter_labels":
        assert not counters and not histograms
    elif failure == "histogram_labels":
        assert len(counters) == 1 and not histograms
    monkeypatch.setattr(target, method, original)
    observe(0.5)
    assert registry.get_sample_value("oc_metrics_recorder_healthy") == 1
    assert registry.get_sample_value(counter_name, counter_labels) == counter_count + 1
    assert registry.get_sample_value(f"{histogram_name}_count", labels) == int(primed) + 1
    assert registry.get_sample_value(f"{histogram_name}_sum", labels) == pytest.approx(0.51 if primed else 0.5)
    assert registry.get_sample_value("oc_metrics_recorder_errors_total", {"operation": kind}) == 1


def test_cached_observation_failure_is_visible_and_recovers(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = PrometheusMetricsRecorder()
    recorder.observe_store_lock(kind="read", wait_seconds=0, hold_seconds=0)
    child = recorder._lock_children["read"][0]
    observe = child.observe

    def fail(value: float) -> None:
        raise RuntimeError("synthetic recorder failure")

    monkeypatch.setattr(child, "observe", fail)
    recorder.observe_store_lock(kind="read", wait_seconds=0, hold_seconds=0)
    assert recorder.registry.get_sample_value("oc_metrics_recorder_healthy") == 0
    assert recorder.registry.get_sample_value("oc_metrics_recorder_errors_total", {"operation": "store_lock"}) == 1
    monkeypatch.setattr(child, "observe", observe)
    recorder.observe_store_lock(kind="read", wait_seconds=0, hold_seconds=0)
    assert recorder.registry.get_sample_value("oc_metrics_recorder_healthy") == 1
    assert recorder.registry.get_sample_value("oc_store_lock_wait_seconds_count", {"kind": "read"}) == 2


def _fail_recording() -> None:
    raise RuntimeError("synthetic recording failure")


def test_healthy_recordings_skip_gauge_writes_but_failures_and_recovery_remain_visible(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    recorder = PrometheusMetricsRecorder()
    publish = MagicMock(wraps=recorder._recorder_healthy.set)
    monkeypatch.setattr(recorder._recorder_healthy, "set", publish)
    callback = MagicMock()
    for _ in range(100):
        recorder._safe("http", callback)
    assert callback.call_count == 100
    publish.assert_not_called()
    for _ in range(2):
        recorder._safe("http", _fail_recording)
        assert recorder.registry.get_sample_value("oc_metrics_recorder_healthy") == 0
    assert recorder.registry.get_sample_value("oc_metrics_recorder_errors_total", {"operation": "http"}) == 2
    assert len(caplog.records) == 1
    for _ in range(100):
        recorder._safe("http", callback)
    assert callback.call_count == 200
    assert [call.args for call in publish.call_args_list] == [(0,), (0,), (1,)]
    assert recorder.registry.get_sample_value("oc_metrics_recorder_healthy") == 1


@pytest.mark.parametrize("failed_value", [0, 1])
def test_failed_health_publication_is_counted_and_retried(
    failed_value: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = PrometheusMetricsRecorder()
    if failed_value == 1:
        recorder._safe("http", _fail_recording)
    original_set = recorder._recorder_healthy.set

    def fail_set(value: float) -> None:
        if value == failed_value:
            raise RuntimeError("synthetic gauge failure")
        original_set(value)

    monkeypatch.setattr(recorder._recorder_healthy, "set", fail_set)
    recorder._safe("http", _fail_recording if failed_value == 0 else lambda: None)
    assert not recorder._healthy
    assert (
        recorder.registry.get_sample_value("oc_metrics_recorder_errors_total", {"operation": "http"})
        == failed_value + 1
    )
    publish = MagicMock(wraps=original_set)
    monkeypatch.setattr(recorder._recorder_healthy, "set", publish)
    recorder._safe("http", lambda: None)
    publish.assert_called_once_with(1)
    assert recorder._healthy
    assert recorder.registry.get_sample_value("oc_metrics_recorder_healthy") == 1


@pytest.mark.parametrize("first_value", [0, 1])
def test_concurrent_health_publications_keep_gauge_and_state_ordered(
    first_value: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = PrometheusMetricsRecorder()
    if first_value == 1:
        recorder._safe("http", _fail_recording)
    publishing = threading.Event()
    release = threading.Event()
    second_callback_ran = threading.Event()
    original_set = recorder._recorder_healthy.set
    published: list[float] = []

    def controlled_set(value: float) -> None:
        if value == first_value:
            publishing.set()
            assert release.wait(timeout=5)
        original_set(value)
        published.append(value)

    def second_callback() -> None:
        second_callback_ran.set()
        if first_value == 1:
            _fail_recording()

    monkeypatch.setattr(recorder._recorder_healthy, "set", controlled_set)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(recorder._safe, "http", _fail_recording if first_value == 0 else lambda: None)
        try:
            assert publishing.wait(timeout=5)
            second = pool.submit(recorder._safe, "http", second_callback)
            # Callbacks remain runnable while another health publication owns
            # the lock, but the second publication cannot overtake it.
            assert second_callback_ran.wait(timeout=5)
            assert not second.done()
        finally:
            release.set()
        first.result(timeout=5)
        second.result(timeout=5)
    assert published == [first_value, 1 - first_value]
    assert recorder._healthy == (first_value == 0)
    assert recorder.registry.get_sample_value("oc_metrics_recorder_healthy") == 1 - first_value
    assert (
        recorder.registry.get_sample_value("oc_metrics_recorder_errors_total", {"operation": "http"}) == first_value + 1
    )


@pytest.mark.parametrize("slow_failure", [False, True])
def test_overlapping_callbacks_publish_health_when_they_finish(slow_failure: bool) -> None:
    recorder = PrometheusMetricsRecorder()
    started = threading.Event()
    release = threading.Event()

    def slow_callback() -> None:
        started.set()
        assert release.wait(timeout=5)
        if slow_failure:
            _fail_recording()

    with ThreadPoolExecutor(max_workers=2) as pool:
        slow = pool.submit(recorder._safe, "http", slow_callback)
        try:
            assert started.wait(timeout=5)
            fast = pool.submit(recorder._safe, "http", (lambda: None) if slow_failure else _fail_recording)
            fast.result(timeout=5)
            assert recorder.registry.get_sample_value("oc_metrics_recorder_healthy") == int(slow_failure)
        finally:
            release.set()
        slow.result(timeout=5)
    assert recorder.registry.get_sample_value("oc_metrics_recorder_healthy") == int(not slow_failure)
    assert recorder._healthy == (not slow_failure)
    assert recorder.registry.get_sample_value("oc_metrics_recorder_errors_total", {"operation": "http"}) == 1


@pytest.mark.asyncio
async def test_successful_scrape_does_not_recover_recording_health(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = PrometheusMetricsRecorder()
    original_generate = recorder._generate_latest

    def fail_generate(registry: object) -> bytes:
        raise RuntimeError("synthetic exporter failure")

    monkeypatch.setattr(recorder, "_generate_latest", fail_generate)
    with pytest.raises(MetricsScrapeError):
        await recorder.render()
    assert recorder.registry.get_sample_value("oc_metrics_recorder_healthy") == 0
    assert recorder.registry.get_sample_value("oc_metrics_recorder_errors_total", {"operation": "scrape"}) == 1
    monkeypatch.setattr(recorder, "_generate_latest", original_generate)
    body = await recorder.render()
    assert b"oc_metrics_recorder_healthy 0.0" in body
    recorder.observe_http(path="/metrics", method="GET", status_code=200, duration_seconds=0.01)
    assert recorder.registry.get_sample_value("oc_metrics_recorder_healthy") == 0
    recorder.observe_http(path="/api/v1/memory", method="GET", status_code=200, duration_seconds=0.01)
    assert recorder.registry.get_sample_value("oc_metrics_recorder_healthy") == 1


def test_sqlite_lock_observation_is_reentrant_aware() -> None:
    recorder = PrometheusMetricsRecorder()
    store = SqliteStore(":memory:", metrics=recorder)
    try:
        store.init_schema()
        store.add_project(Project(id="p", name="before"))
        store.update_project("p", name="after")
        store.list_projects()
        text = _text(recorder)
        write_count = re.search(r'oc_store_lock_hold_seconds_count\{kind="write"\} ([0-9.]+)', text)
        read_count = re.search(r'oc_store_lock_hold_seconds_count\{kind="read"\} ([0-9.]+)', text)
        maintenance_count = re.search(r'oc_store_lock_hold_seconds_count\{kind="maintenance"\} ([0-9.]+)', text)
        assert write_count is not None and float(write_count.group(1)) == 2
        assert read_count is not None and float(read_count.group(1)) == 1
        assert maintenance_count is not None and float(maintenance_count.group(1)) >= 1
    finally:
        store.close()


def test_disabled_sqlite_metrics_bypass_observation_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    import openchronicle.core.infrastructure.persistence.sqlite_store as sqlite_store_module

    store = SqliteStore(":memory:", metrics=NullMetricsRecorder())
    try:

        def unexpected_observation(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("disabled metrics must not enter the observation wrapper")

        monkeypatch.setattr(sqlite_store_module, "_observed_lock", unexpected_observation)
        store.init_schema()
        store.list_projects()
    finally:
        store.close()


def test_http_metrics_route_is_opt_in_and_guarded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OC_MAINTENANCE_DISABLED", "1")
    disabled_container = _mock_container(recorder=NullMetricsRecorder(), exporter=None)
    disabled_app = create_app(disabled_container, HTTPConfig(), mount_mcp=False)
    assert not any(cast(Any, middleware.cls) is MetricsMiddleware for middleware in disabled_app.user_middleware)
    with TestClient(disabled_app) as client:
        assert client.get("/metrics").status_code == 404

    recorder = PrometheusMetricsRecorder()
    enabled_container = _mock_container(recorder=recorder, exporter=recorder)
    with TestClient(create_app(enabled_container, HTTPConfig(), mount_mcp=False)) as client:
        assert client.get("/api/v1/project").status_code == 200
        assert client.get("/health").status_code == 200
        metrics_response = client.get("/metrics")
        assert metrics_response.status_code == 200
        assert metrics_response.headers["content-type"].startswith("text/plain; version=")
        assert 'route="/api/v1/project"' in metrics_response.text
        assert 'route="/health"' not in metrics_response.text
        assert client.get("/metrics/", follow_redirects=False).status_code == 307

    guarded_config = HTTPConfig(api_key="test-key")
    with TestClient(create_app(enabled_container, guarded_config, mount_mcp=False)) as client:
        assert client.get("/metrics").status_code in {401, 403}
        assert client.get("/metrics", headers={"Authorization": "Bearer test-key"}).status_code == 200


def test_disabled_mcp_metrics_keep_original_handler() -> None:
    recorder = NullMetricsRecorder()
    server = MetricsFastMCP("test", metrics=recorder)

    async def probe() -> dict[str, str]:
        return {"status": "ok"}

    assert server._wrap_handler(probe, "probe") is probe


@pytest.mark.asyncio
async def test_mcp_handler_metrics_preserve_tool_schema() -> None:
    recorder = PrometheusMetricsRecorder()
    server = MetricsFastMCP("test", metrics=recorder)

    @server.tool(name="health")
    async def probe(value: int) -> dict[str, object]:
        return {"status": "started", "value": value}

    tools = await server.list_tools()
    assert tools[0].name == "health"
    assert tools[0].inputSchema["properties"]["value"]["type"] == "integer"
    result = await server.call_tool("health", {"value": 7})
    assert '"value": 7' in repr(result)

    text = _text(recorder)
    assert 'outcome="started",tool="health"' in text


@pytest.mark.asyncio
async def test_scrape_overlap_and_cancellation_do_not_queue_serialization() -> None:
    recorder = PrometheusMetricsRecorder()
    worker_started = threading.Event()
    worker_release = threading.Event()
    worker_finished = threading.Event()
    original_generate = recorder._generate_latest

    def slow_generate(registry: object) -> bytes:
        worker_started.set()
        worker_release.wait(timeout=5)
        try:
            return original_generate(registry)
        finally:
            worker_finished.set()

    recorder._generate_latest = slow_generate
    first = asyncio.create_task(recorder.render())
    assert await asyncio.to_thread(worker_started.wait, 2)
    with pytest.raises(MetricsScrapeBusyError):
        await recorder.render()

    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    with pytest.raises(MetricsScrapeBusyError):
        await recorder.render()

    worker_release.set()
    assert await asyncio.to_thread(worker_finished.wait, 2)
    body = await recorder.render()
    assert b"oc_build_info" in body


def test_embedding_and_backfill_stages_use_the_same_recorder() -> None:
    recorder = PrometheusMetricsRecorder()
    store = SqliteStore(":memory:", metrics=recorder)
    try:
        store.init_schema()
        store.add_memory(MemoryItem(id="m", content="metrics search content"))
        service = EmbeddingService(StubEmbeddingAdapter(dims=8), store, metrics=recorder)
        service.generate_for_memory("m", "metrics search content")
        assert service.search_hybrid("metrics", top_k=1)
        text = _text(recorder)
        assert 'operation="single",outcome="success",provider="stub"' in text
        assert 'stage="keyword_lookup"' in text
        assert 'stage="vector_loading"' in text
        assert 'stage="candidate_prep_scoring"' in text
        assert 'stage="fusion_materialization"' in text
    finally:
        store.close()


def test_backfill_persistence_failure_is_not_mislabeled_as_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = PrometheusMetricsRecorder()
    store = SqliteStore(":memory:", metrics=recorder)
    try:
        store.init_schema()
        store.add_memory(MemoryItem(id="m", content="persist failure"))
        service = EmbeddingService(StubEmbeddingAdapter(dims=8), store, metrics=recorder)

        def fail_save(*args: Any, **kwargs: Any) -> bool:
            raise RuntimeError("simulated persistence failure")

        monkeypatch.setattr(store, "save_embedding", fail_save)
        result = service.generate_missing()

        assert result.generated == 0
        assert result.failed == 1
        text = _text(recorder)
        assert 'oc_backfill_items_total{outcome="failed"} 1.0' in text
        assert 'outcome="transient_failure"' not in text
    finally:
        store.close()


@pytest.mark.asyncio
async def test_maintenance_metrics_include_success_and_persisted_seed() -> None:
    recorder = PrometheusMetricsRecorder()
    container = SimpleNamespace(metrics=recorder)
    ran = asyncio.Event()

    async def handler(_container: object) -> None:
        ran.set()

    job = JobState(name="probe", interval_seconds=60, enabled=True)
    loop = MaintenanceLoop(cast(Any, container), [job], {"probe": handler})
    await loop.run_once("probe")
    assert ran.is_set()
    text = _text(recorder)
    assert 'job="__unknown__",outcome="success"' in text
