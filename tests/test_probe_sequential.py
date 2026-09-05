"""Decision-contract tests: noisy, partial, or incorrect runs cannot pass."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from scripts.probe_sequential import ORDERS, STATES, assess, case_result, deltas, source_digest


def _runs() -> list[dict[str, Any]]:
    snapshot = {"memory_rows": 1000, "vector_rows": 1000, "fingerprint": "same-corpus"}
    case = {
        "eligibility": {"fixed_overhead_comparison": True, "reasons": []},
        "failed": 0,
        "timed_out": 0,
        "completed": 3000,
        "throughput_completed_per_second": 100.0,
        "corpus": {"state_unchanged": True, "starting": snapshot, "post_warmup": snapshot, "final": snapshot},
        "process_memory": {"supported": True, "sample_count": 300, "peak_rss_bytes": 100 * 2**20},
        "operations": {
            name: {"sample_count": 300, "p95_sample_sufficient": True, "p95_seconds": 0.1}
            for name in ("search", "list")
        },
        "scrapes": {"completed": 1, "failed": 0},
    }
    metadata = {
        "python_version": "test",
        "dependency_versions": {"fastapi": "same"},
        "clients": [8],
        "lane": "fixed",
        "transport": "rest",
        "mode": "hybrid",
        "provider_profile": "stub",
        "corpus_size": 1000,
        "seed": 20260904,
        "warmup_seconds": 5,
        "duration_seconds": 30,
        "cpu_affinity_mask": None,
    }
    return [
        {
            "block": block,
            "label": label,
            "report": {
                **deepcopy(metadata),
                "instrumentation_state": STATES[label],
                "result": {"client_counts": [deepcopy(case)]},
            },
        }
        for block, order in enumerate(ORDERS, 1)
        for label in order
    ]


def test_zero_overhead_stable_controls_pass() -> None:
    assert assess(_runs())["status"] == "pass"


def test_exact_budget_with_zero_control_noise_passes() -> None:
    runs = _runs()
    for run in runs:
        if run["label"] == "B":
            run["report"]["result"]["client_counts"][0]["throughput_completed_per_second"] = 95
    assert assess(runs)["status"] == "pass"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1.0])
def test_invalid_throughput_never_passes(value: float) -> None:
    runs = _runs()
    runs[0]["report"]["result"]["client_counts"][0]["throughput_completed_per_second"] = value
    assert assess(runs)["status"] == "inconclusive"


def test_repeatable_throughput_regression_fails_independent_gate() -> None:
    runs = _runs()
    for run in runs:
        if run["label"] == "C":
            run["report"]["result"]["client_counts"][0]["throughput_completed_per_second"] = 90
    assessment = assess(runs)
    assert assessment["status"] == "fail"
    assert assessment["comparisons"]["B/A"]["status"] == "pass"
    assert assessment["comparisons"]["C/A"]["status"] == "fail"


def test_baseline_noise_vetoes_apparent_pass() -> None:
    runs = _runs()
    runs[3]["report"]["result"]["client_counts"][0]["throughput_completed_per_second"] = 90
    assert runs[3]["label"] == "R"
    assert assess(runs)["status"] == "inconclusive"


def test_budget_crossing_and_borderline_median_are_inconclusive() -> None:
    runs = _runs()
    for run in runs:
        if run["label"] == "B":
            run["report"]["result"]["client_counts"][0]["throughput_completed_per_second"] = (
                94 if run["block"] == 1 else 99
            )
    assert assess(runs)["comparisons"]["B/A"]["status"] == "inconclusive"
    for run in runs:
        if run["label"] == "B":
            run["report"]["result"]["client_counts"][0]["throughput_completed_per_second"] = 95.2
        if run["label"] == "R":
            run["report"]["result"]["client_counts"][0]["throughput_completed_per_second"] = 99.5
    assert assess(runs)["comparisons"]["B/A"]["status"] == "inconclusive"


@pytest.mark.parametrize("problem", ["missing", "failure", "samples", "rss", "scrapes", "corpus", "runtime", "state"])
def test_missing_or_incomparable_evidence_never_passes(problem: str) -> None:
    runs = _runs()
    report = runs[2]["report"]
    case = report["result"]["client_counts"][0]
    if problem == "missing":
        runs.pop()
    elif problem == "failure":
        case["failed"] = 1
    elif problem == "samples":
        case["operations"]["list"]["sample_count"] = 99
    elif problem == "rss":
        case["process_memory"]["peak_rss_bytes"] = None
    elif problem == "scrapes":
        case["scrapes"]["failed"] = 1
    elif problem == "corpus":
        case["corpus"]["final"]["fingerprint"] = "different"
    elif problem == "runtime":
        report["dependency_versions"] = {"fastapi": "different"}
    elif problem == "state":
        report["instrumentation_state"] = "disabled"
    assert assess(runs)["status"] == "inconclusive"
    assert assess(runs)["reasons"]


def test_aggregation_uses_median_not_last_or_maximum_block() -> None:
    runs = _runs()
    for run in runs:
        if run["label"] == "B":
            run["report"]["result"]["client_counts"][0]["throughput_completed_per_second"] = {1: 99, 2: 80, 3: 110}[
                run["block"]
            ]
    metric = assess(runs)["comparisons"]["B/A"]["metrics"]["throughput_loss_percent"]
    assert metric["median_delta"] == pytest.approx(1)
    assert metric["status"] == "inconclusive"


def test_latency_budget_and_rss_units() -> None:
    baseline = case_result(_runs()[0]["report"])
    candidate = deepcopy(baseline)
    candidate["process_memory"]["peak_rss_bytes"] += 2**20
    candidate["operations"]["search"]["p95_seconds"] += 0.001
    result = deltas(baseline, candidate)
    assert result["rss_delta_mib"] == {"delta": 1.0, "budget": 10.0}
    assert result["search_p95_delta_ms"]["delta"] == pytest.approx(1)
    assert result["search_p95_delta_ms"]["budget"] == pytest.approx(5)


def test_source_digest_includes_resources_not_generated_caches(tmp_path: Path) -> None:
    source = tmp_path / "src" / "openchronicle"
    source.mkdir(parents=True)
    (source / "module.py").write_text("pass\n")
    original = source_digest(tmp_path)
    cache = source / "__pycache__"
    cache.mkdir()
    (cache / "module.pyc").write_bytes(b"compiled")
    assert source_digest(tmp_path) == original
    (source / "migration.sql").write_text("SELECT 1;\n")
    assert source_digest(tmp_path) != original
