"""Cached exporter parity, lifecycle, fallback and bounded-retention contracts."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any, SupportsIndex

import pytest
from prometheus_client import generate_latest
from prometheus_client.metrics_core import Metric
from prometheus_client.openmetrics import exposition as om
from prometheus_client.samples import Exemplar, Sample, Timestamp

from openchronicle.core.application.observability.exporter import MetricsScrapeBusyError, MetricsScrapeError
from openchronicle.core.infrastructure.observability.cached_exporter import CachedPrefixExporter
from openchronicle.core.infrastructure.observability.prometheus_recorder import PrometheusMetricsRecorder
from tests.helpers.metrics import FrozenCollector, make_recorder


def family(
    *, name: str = "example", kind: str = "gauge", value: Any = 1.0, labels: Any = None, timestamp: Any = None
) -> Metric:
    metric = Metric(name, 'help with \\ and\nnewline and "quote"', kind)
    metric.samples.append(Sample(name, {} if labels is None else labels, value, timestamp=timestamp))
    return metric


@pytest.mark.parametrize("full", [False, True])
def test_complete_recorder_matrix_and_updated_values_are_byte_identical(
    full: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder, process = make_recorder(full=full)
    snapshot = FrozenCollector(tuple(recorder.registry.collect()))
    exporter = CachedPrefixExporter()
    expected = generate_latest(snapshot)
    assert exporter(snapshot) == expected
    assert b"__unknown__" in expected or not full
    assert b"test_process_cpu_seconds_total" in expected
    assert len(exporter._prefixes) < 4096
    if full:
        # 3,642 when Patch 2 was promoted (design 0010-4c), plus 27 for the
        # `reconcile_backfill` job name added with ADR 0005 §7 (2026-09-23).
        assert sum(line.startswith(b"oc_") for line in expected.splitlines()) == 3669
        assert sum(line.startswith(b"test_process_") for line in expected.splitlines()) == 6

    def unexpected_prefix(key: Any) -> str:
        raise AssertionError("warm scrape must not repeat name/label formatting")

    with monkeypatch.context() as patch:
        patch.setattr(exporter, "_make_prefix", unexpected_prefix)
        assert exporter(snapshot) == expected
    recorder.observe_http(path="/api/v1/memory", method="GET", status_code=200, duration_seconds=0.25)
    recorder.observe_embedding(provider="stub", operation="single", outcome="other_error", duration_seconds=0.05)
    recorder.inflight_inc("rest")
    process.value = 77.0
    updated = FrozenCollector(tuple(recorder.registry.collect()))
    actual = exporter(updated)
    assert actual == generate_latest(updated)
    assert actual != expected
    assert b"test_process_cpu_seconds_total 77.0" in actual


def test_each_scrape_collects_fresh_live_values_once() -> None:
    recorder, process = make_recorder(full=False)
    exporter = CachedPrefixExporter()
    before = process.calls
    for value in (7.0, 13.0, 2.0):
        process.value = value
        body = exporter(recorder.registry)
        before += 1
        assert process.calls == before
        assert f"test_process_cpu_seconds_total {value}".encode() in body
        assert f"test_process_resident_memory_bytes {value}".encode() in body


@pytest.mark.parametrize("value", [0.0, -0.0, 1e-9, 1e8, -9.5, float("inf"), -float("inf"), float("nan")])
@pytest.mark.parametrize("timestamp", [None, 1234.567, Timestamp(-2, 123456789)])
def test_numeric_timestamp_and_escaping_parity(value: float, timestamp: Any) -> None:
    metric = family(
        value=value, timestamp=timestamp, labels={"z": 'slash\\line\n"quote"', "a": "東京🙂\r\t", "empty": ""}
    )
    snapshot = FrozenCollector((metric,))
    exporter = CachedPrefixExporter()
    for _ in range(2):
        assert exporter(snapshot) == generate_latest(snapshot)


def test_created_and_gauge_histogram_tail_ordering_with_exemplars() -> None:
    metric = family(kind="counter")
    metric.samples = [
        Sample("example_created", {"id": "b"}, 1.0),
        Sample("example_total", {"id": "a"}, 2.0, exemplar=Exemplar({"trace": "fresh"}, 3.0)),
        Sample("example_gsum", {}, 4.0),
        Sample("example_gcount", {}, 5.0),
        Sample("example_created", {"id": "a"}, 6.0),
    ]
    snapshot = FrozenCollector((metric,))
    assert CachedPrefixExporter()(snapshot) == generate_latest(snapshot)


@pytest.mark.parametrize("kind", ["summary", "info", "stateset", "gaugehistogram", "unknown"])
def test_unsupported_families_delegate_to_standard(kind: str) -> None:
    snapshot = FrozenCollector((family(kind=kind),))
    exporter = CachedPrefixExporter()
    assert exporter(snapshot) == generate_latest(snapshot)
    assert exporter._prefixes == {}


@pytest.mark.parametrize("escaping", [om.UNDERSCORES, om.ALLOWUTF8, om.DOTS, om.VALUES, "unknown-scheme"])
def test_nonlegacy_names_and_other_escaping_delegate(escaping: str) -> None:
    snapshot = FrozenCollector((family(name="metric.東京", labels={"label.dot": '"line\n', "正常": "value"}),))
    exporter = CachedPrefixExporter()
    assert exporter(snapshot, escaping=escaping) == generate_latest(snapshot, escaping=escaping)
    assert not exporter._prefixes


@pytest.mark.parametrize(
    "metric",
    [
        family(value="not-a-number"),
        family(value=None),
        family(timestamp="not-a-time"),
        family(labels={"x": []}),
        family(labels={"x": 4}),
        family(labels={0: "x", "a": "y"}),
        family(labels={"x": "\ud800"}),
    ],
)
def test_error_type_and_context_match_standard(metric: Metric) -> None:
    snapshot = FrozenCollector((metric,))
    with pytest.raises(Exception) as standard:
        generate_latest(snapshot)
    with pytest.raises(type(standard.value)) as integrated:
        CachedPrefixExporter()(snapshot)
    assert integrated.value.args == standard.value.args


@pytest.mark.parametrize("entries,byte_limit", [(0, 0), (1, 1_048_576), (4096, 64), (4096, 1024)])
def test_entry_and_retained_text_limits_do_not_drop_samples(entries: int, byte_limit: int) -> None:
    exporter = CachedPrefixExporter(max_entries=entries, max_payload_bytes=byte_limit)
    for index in range(20):
        snapshot = FrozenCollector((family(labels={"label": str(index)}, value=index),))
        assert exporter(snapshot) == generate_latest(snapshot)
        assert len(exporter._prefixes) <= entries
        assert exporter._payload_bytes <= byte_limit
    large = FrozenCollector((family(labels={"label": "🙂" * 10_000}),))
    before = dict(exporter._prefixes)
    assert exporter(large) == generate_latest(large)
    assert exporter._prefixes == before
    recomputed = 0
    for (name, labels), prefix in exporter._prefixes.items():
        assert all(type(part) is str for pair in labels for part in pair)
        recomputed += sum(len(text.encode()) for text in (name, prefix, *(part for pair in labels for part in pair)))
    assert recomputed == exporter._payload_bytes


def test_cache_instances_are_isolated() -> None:
    first, second = CachedPrefixExporter(), CachedPrefixExporter()
    first(FrozenCollector((family(),)))
    assert first._prefixes
    assert second._prefixes == {} and second._payload_bytes == 0


def test_collection_errors_are_not_swallowed_or_augmented() -> None:
    class FailingCollector:
        def collect(self) -> Iterator[Metric]:
            yield family()
            raise RuntimeError("synthetic collection failure")

    for exporter in (generate_latest, CachedPrefixExporter()):
        with pytest.raises(RuntimeError) as error:
            exporter(FailingCollector())
        assert error.value.args == ("synthetic collection failure",)


@pytest.mark.asyncio
async def test_integrated_failure_and_scrape_health_recovery_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = PrometheusMetricsRecorder()
    exporter = recorder._generate_latest
    assert isinstance(exporter, CachedPrefixExporter)

    def failed_prefix(sample: Sample) -> str:
        raise RuntimeError("synthetic formatting failure")

    with monkeypatch.context() as patch:
        patch.setattr(exporter, "_prefix", failed_prefix)
        with pytest.raises(MetricsScrapeError):
            await recorder.render()
    assert recorder.registry.get_sample_value("oc_metrics_recorder_healthy") == 0
    assert recorder.registry.get_sample_value("oc_metrics_recorder_errors_total", {"operation": "scrape"}) == 1
    assert b"oc_metrics_recorder_healthy 0.0" in await recorder.render()
    recorder.observe_http(path="/api/v1/memory", method="GET", status_code=200, duration_seconds=0.01)
    assert b"oc_metrics_recorder_healthy 1.0" in await recorder.render()


@pytest.mark.asyncio
async def test_integrated_exporter_retains_single_worker_ownership_through_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder, _ = make_recorder(full=True)
    exporter = recorder._generate_latest
    assert isinstance(exporter, CachedPrefixExporter)
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    loop_thread = threading.get_ident()
    calls = 0

    def blocked_export(registry: Any) -> bytes:
        nonlocal calls
        calls += 1
        assert threading.get_ident() != loop_thread
        started.set()
        assert release.wait(timeout=5)
        return exporter(registry)

    owned = recorder._render_owned

    def owned_finished() -> bytes:
        try:
            return owned()
        finally:
            finished.set()

    recorder._generate_latest = blocked_export
    monkeypatch.setattr(recorder, "_render_owned", owned_finished)
    first = asyncio.create_task(recorder.render())
    try:
        assert await asyncio.to_thread(started.wait, 5)
        with pytest.raises(MetricsScrapeBusyError):
            await recorder.render()
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        with pytest.raises(MetricsScrapeBusyError):
            await recorder.render()
        assert calls == 1
        recorder.inflight_inc("rest")
    finally:
        release.set()
    assert await asyncio.to_thread(finished.wait, 5)
    recorder._generate_latest = exporter
    assert b'oc_requests_inflight{surface="rest"} 1.0' in await recorder.render()


@pytest.mark.parametrize("position", ["name", "label", "value"])
def test_warm_cache_does_not_bypass_unusual_string_fallback(position: str) -> None:
    class UnusualString(str):
        def replace(self, old: str, new: str, count: SupportsIndex = -1) -> str:
            return "different"

    original = family(labels={"label": "value"})
    exporter = CachedPrefixExporter()
    exporter(FrozenCollector((original,)))
    sample = original.samples[0]
    if position == "name":
        changed = sample._replace(name=UnusualString(sample.name))
    elif position == "label":
        changed = sample._replace(labels={UnusualString("label"): "value"})
    else:
        changed = sample._replace(labels={"label": UnusualString("value")})
    original.samples = [changed]
    snapshot = FrozenCollector((original,))
    before = dict(exporter._prefixes)
    assert exporter(snapshot) == generate_latest(snapshot)
    assert exporter._prefixes == before


@pytest.mark.parametrize("kind", ["gauge", "summary", "info", "unknown"])
def test_encoding_errors_include_the_whole_scrape(kind: str) -> None:
    snapshot = FrozenCollector((family(name="before"), family(kind=kind, labels={"x": "\ud800"}), family(name="after")))
    with pytest.raises(UnicodeEncodeError) as standard:
        generate_latest(snapshot)
    with pytest.raises(UnicodeEncodeError) as integrated:
        CachedPrefixExporter()(snapshot)
    assert integrated.value.args == standard.value.args
    assert "before" in integrated.value.object and "after" in integrated.value.object


@pytest.mark.parametrize("later_failure", ["collection", "formatting"])
def test_fallback_encoding_does_not_hide_later_failures(later_failure: str) -> None:
    bad_value = family(name="bad", value="not-a-number")

    class FailingCollector:
        def collect(self) -> Iterator[Metric]:
            yield family(kind="summary", labels={"x": "\ud800"})
            if later_failure == "collection":
                raise RuntimeError("later collection failure")
            yield bad_value

    with pytest.raises(Exception) as standard:
        generate_latest(FailingCollector())
    with pytest.raises(type(standard.value)) as integrated:
        CachedPrefixExporter()(FailingCollector())
    assert integrated.value.args == standard.value.args


@pytest.mark.parametrize("kind", ["gauge", "summary"])
def test_value_encoding_errors_are_not_mistaken_for_body_encoding(kind: str) -> None:
    class EncodingFailure:
        def __float__(self) -> float:
            raise UnicodeEncodeError("utf-8", "\ud800", 0, 1, "synthetic value conversion failure")

    snapshot = FrozenCollector((family(kind=kind, value=EncodingFailure()),))
    with pytest.raises(UnicodeEncodeError) as standard:
        generate_latest(snapshot)
    with pytest.raises(UnicodeEncodeError) as integrated:
        CachedPrefixExporter()(snapshot)
    assert integrated.value.args == standard.value.args
    assert integrated.value.args[-1] is snapshot.metrics[0]


@pytest.mark.parametrize("limits", [{"max_entries": -1}, {"max_payload_bytes": -1}])
def test_negative_cache_limits_are_rejected(limits: dict[str, int]) -> None:
    with pytest.raises(ValueError, match="nonnegative"):
        CachedPrefixExporter(**limits)


def test_enabled_recorders_own_distinct_cached_exporters() -> None:
    first, second = PrometheusMetricsRecorder(), PrometheusMetricsRecorder()
    assert isinstance(first._generate_latest, CachedPrefixExporter)
    assert isinstance(second._generate_latest, CachedPrefixExporter)
    assert first._generate_latest is not second._generate_latest
    first._generate_latest(first.registry)
    assert first._generate_latest._prefixes
    assert second._generate_latest._prefixes == {}


@pytest.mark.skipif(sys.platform != "linux", reason="native ProcessCollector requires Linux /proc")
def test_native_process_collector_is_called_on_every_scrape(monkeypatch: pytest.MonkeyPatch) -> None:
    from prometheus_client.process_collector import ProcessCollector

    collect = ProcessCollector.collect
    calls = 0

    def counted_collect(self: ProcessCollector) -> Any:
        nonlocal calls
        calls += 1
        return collect(self)

    monkeypatch.setattr(ProcessCollector, "collect", counted_collect)
    recorder = PrometheusMetricsRecorder()
    for _ in range(3):
        before = calls
        body = recorder._generate_latest(recorder.registry)
        assert calls == before + 1
        samples = {
            name.decode(): float(value)
            for line in body.splitlines()
            if line.startswith(b"process_")
            for name, value in [line.split()]
        }
        assert samples["process_cpu_seconds_total"] >= 0
        assert samples["process_resident_memory_bytes"] > 0
        assert samples["process_virtual_memory_bytes"] > 0
        assert samples["process_start_time_seconds"] > 0
        assert samples["process_open_fds"] >= 0
        assert samples["process_max_fds"] > 0


@pytest.mark.parametrize("setting", [None, "false"])
def test_disabled_factory_never_imports_prometheus_or_cached_exporter(setting: str | None) -> None:
    environment = os.environ.copy()
    environment.pop("OC_METRICS_ENABLED", None)
    if setting is not None:
        environment["OC_METRICS_ENABLED"] = setting
    source = Path(__file__).resolve().parents[1] / "src"
    script = f"""
import sys
sys.path.insert(0, {str(source)!r})
class RejectMetricsImport:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith('prometheus_client') or fullname.endswith('.cached_exporter'):
            raise AssertionError('disabled metrics imported ' + fullname)
sys.meta_path.insert(0, RejectMetricsImport())
from openchronicle.core.infrastructure.observability.factory import create_metrics
from openchronicle.core.infrastructure.observability.prometheus_recorder import PrometheusMetricsRecorder
recorder, exporter = create_metrics()
assert not recorder.enabled and exporter is None
assert not any(name.startswith('prometheus_client') or name.endswith('.cached_exporter') for name in sys.modules)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script], env=environment, capture_output=True, text=True, timeout=15
    )
    assert completed.returncode == 0, completed.stderr
