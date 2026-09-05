"""Contract tests for the opt-in, bounded runtime metrics surface."""

from __future__ import annotations

import asyncio
import builtins
import re
import threading
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from prometheus_client import generate_latest

from openchronicle.core.application.observability.exporter import MetricsScrapeBusyError
from openchronicle.core.application.observability.null_recorder import NullMetricsRecorder
from openchronicle.core.application.services.embedding_service import EmbeddingService
from openchronicle.core.application.services.maintenance_loop import JobState, MaintenanceLoop
from openchronicle.core.domain.exceptions import ConfigError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.infrastructure.embedding.stub_adapter import StubEmbeddingAdapter
from openchronicle.core.infrastructure.observability.factory import create_metrics
from openchronicle.core.infrastructure.observability.prometheus_recorder import PrometheusMetricsRecorder
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.interfaces.api.app import create_app
from openchronicle.interfaces.api.config import HTTPConfig
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


def test_http_metrics_route_is_opt_in_and_guarded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OC_MAINTENANCE_DISABLED", "1")
    disabled_container = _mock_container(recorder=NullMetricsRecorder(), exporter=None)
    with TestClient(create_app(disabled_container, HTTPConfig(), mount_mcp=False)) as client:
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
