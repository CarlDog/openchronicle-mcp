"""Decision-contract tests: noisy, partial, or incorrect runs cannot pass."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from scripts.probe_sequential import (
    ORDERS,
    PROTOCOL,
    STATES,
    assess,
    assess_calibration,
    case_result,
    deltas,
    source_digest,
    validate_report,
)


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


def _report(*, calibration: bool = False) -> dict[str, Any]:
    runs = [run for run in _runs() if not calibration or run["label"] in ("A", "R")]
    for run in runs:
        metadata = run["report"]
        metadata.update(warmup_seconds=15, duration_seconds=90, cpu_affinity_mask="0x3")
        case = case_result(metadata)
        case.update(attempted=9000, completed=9000)
        for name, count in (("search", 8100), ("list", 900)):
            case["operations"][name].update(
                sample_count=count, completed=count, throughput_completed_per_second=count / 90
            )
        if run["label"] == "C":
            case["scrapes"] = {
                "attempted": 3,
                "completed": 3,
                "failed": 0,
                "scheduled_offsets_seconds": [0, 30, 60],
                "attempts": [
                    {"offset_seconds": offset, "duration_seconds": 0.01, "completed": True} for offset in (0, 30, 60)
                ],
            }
        metadata["result"]["client_counts"][0] = case
        run["source_sha256"] = ("a" if run["label"] in ("A", "R") else "b") * 64
    return {
        "method": "sequential-ABC-repeated-A-v2",
        "suite_mode": "calibration" if calibration else "acceptance",
        "protocol": deepcopy(PROTOCOL),
        "source_sha256": {"A": "a" * 64, "B_C": "b" * 64},
        "probe_sha256": dict.fromkeys(("probe_artifact.py", "probe_sequential.py", "probe_performance.py"), "c" * 64),
        "python_version": "test",
        "dependency_versions": {"fastapi": "same"},
        "cpu_affinity": [0, 1],
        "maximum_runtime_seconds": 900 if calibration else 1800,
        "started_utc": "2026-09-05T00:00:00+00:00",
        "finished_utc": "2026-09-05T00:15:00+00:00",
        "runs": runs,
        "assessment": assess_calibration(runs) if calibration else assess(runs),
    }


@pytest.mark.parametrize("calibration", [False, True])
def test_valid_report_recalculates(calibration: bool) -> None:
    report = _report(calibration=calibration)
    validate_report(report)
    assert report["assessment"]["status"] == "pass"


def test_validator_accepts_the_real_probe_cpu_mask_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import probe_performance as probe

    monkeypatch.setattr(probe.subprocess, "check_output", lambda *args, **kwargs: "")
    mask = probe._metadata(probe.ProbeConfig(cpu_affinity_mask=3))["cpu_affinity_mask"]
    assert mask == "0x3"
    report = _report(calibration=True)
    for run in report["runs"]:
        run["report"]["cpu_affinity_mask"] = mask
    validate_report(report)


@pytest.mark.parametrize(
    "problem",
    ["state", "key", "assessment", "counts", "source", "harness", "cpu", "protocol", "scrapes", "nan", "order"],
)
def test_report_validation_rejects_malformed_evidence(problem: str) -> None:
    report = _report()
    case = report["runs"][2]["report"]["result"]["client_counts"][0]
    if problem == "state":
        report["runs"][4]["report"]["instrumentation_state"] = "2026-09-05T16:28:37.791171084Z disabled"
    elif problem == "key":
        values = case["operations"]["search"]
        values["throughput_comp2026-09-05T16:28:37.791171084Z leted_per_second"] = values.pop(
            "throughput_completed_per_second"
        )
    elif problem == "assessment":
        report["assessment"]["comparisons"]["C/A"]["metrics"]["search_p95_delta_ms"]["median_delta"] = 999
    elif problem == "counts":
        case["attempted"] += 1
    elif problem == "source":
        report["runs"][0]["source_sha256"] = "b" * 64
    elif problem == "harness":
        report["probe_sha256"].pop("probe_artifact.py")
    elif problem == "cpu":
        report["runs"][0]["report"]["cpu_affinity_mask"] = 7
    elif problem == "protocol":
        report["protocol"]["duration_seconds"] = 30
    elif problem == "scrapes":
        case["scrapes"]["attempted"] = 1
    elif problem == "nan":
        case["operations"]["search"]["p95_seconds"] = float("nan")
    else:
        report["runs"].reverse()
    with pytest.raises(ValueError):
        validate_report(report)


def test_baseline_calibration_requires_every_pair_within_budget() -> None:
    report = _report(calibration=True)
    runs = report["runs"]
    assert assess_calibration(runs)["status"] == "pass"
    case = runs[3]["report"]["result"]["client_counts"][0]
    case["throughput_completed_per_second"] = 106
    result = assess_calibration(runs)
    assert result["status"] == "inconclusive"
    assert result["max_control_noise_budget_fraction"]["throughput_loss_percent"] == pytest.approx(1.2)
    assert assess_calibration(runs[:-1])["status"] == "inconclusive"


def test_measured_scrape_missing_or_finishing_late_vetoes_eligibility() -> None:
    report = _report()
    case = report["runs"][2]["report"]["result"]["client_counts"][0]
    case["scrapes"]["attempts"][2]["duration_seconds"] = 31
    assert assess(report["runs"])["status"] == "inconclusive"
    case["scrapes"]["attempts"].pop()
    assert assess(report["runs"])["status"] == "inconclusive"


def test_failed_metric_remains_visible_when_aggregate_is_inconclusive() -> None:
    runs = _runs()
    for run in runs:
        case = run["report"]["result"]["client_counts"][0]
        if run["label"] == "C":
            case["throughput_completed_per_second"] = 90
        elif run["label"] == "R":
            case["operations"]["list"]["p95_seconds"] = 0.12
    comparison = assess(runs)["comparisons"]["C/A"]
    assert comparison["status"] == "inconclusive"
    assert comparison["metrics"]["throughput_loss_percent"]["status"] == "fail"
