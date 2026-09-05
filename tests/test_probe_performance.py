"""Contract tests for the bounded Phase 1 performance probe."""

from __future__ import annotations

from argparse import ArgumentTypeError
from pathlib import Path

import pytest

from scripts.probe_performance import (
    OperationResult,
    OperationSummary,
    ProbeConfig,
    ProbeError,
    ScrapeSummary,
    _memory_payload,
    _same_run_affinity_masks,
    _sanitized_child_environment,
    _validate_args,
    _vector_count_from_health,
    build_parser,
    operation_for,
    parse_affinity_mask,
    parse_clients,
)


def test_parse_clients_deduplicates_and_sorts() -> None:
    assert parse_clients("16, 1, 8, 8,4") == (1, 4, 8, 16)


def test_parse_clients_rejects_out_of_range() -> None:
    with pytest.raises(ArgumentTypeError):
        parse_clients("0,4")
    with pytest.raises(ArgumentTypeError):
        parse_clients("257")


def test_parse_affinity_mask_accepts_hex_and_rejects_invalid_values() -> None:
    assert parse_affinity_mask("0xff") == 255
    assert parse_affinity_mask("256") == 256
    with pytest.raises(ArgumentTypeError):
        parse_affinity_mask("0")
    with pytest.raises(ArgumentTypeError):
        parse_affinity_mask(str(1 << 64))


def test_same_run_affinity_masks_rotate_equal_partitions() -> None:
    assert _same_run_affinity_masks(("A", "B", "C"), logical_cpu_count=32) == {
        "A": 0xFF,
        "B": 0xFF00,
        "C": 0xFF0000,
    }
    assert _same_run_affinity_masks(("B", "C", "A"), logical_cpu_count=32) == {
        "B": 0xFF,
        "C": 0xFF00,
        "A": 0xFF0000,
    }
    with pytest.raises(ProbeError, match="at least 24"):
        _same_run_affinity_masks(("A", "B", "C"), logical_cpu_count=23)


def test_workload_lanes_have_distinct_contracts() -> None:
    assert {operation_for("fixed", value) for value in (0.0, 0.89, 0.90, 0.99)} == {"search", "list"}
    assert operation_for("growth", 0.0) == "search"
    assert operation_for("growth", 0.70) == "save"
    assert operation_for("growth", 0.90) == "list"


def test_summary_suppresses_percentiles_until_sample_threshold() -> None:
    summary = OperationSummary()
    for index in range(99):
        summary.add(OperationResult("search", float(index), 0.01, True, False))
    payload = summary.as_dict()
    assert payload["p95_seconds"] is None
    assert payload["p99_seconds"] is None
    assert payload["p95_sample_sufficient"] is False
    assert payload["p99_sample_sufficient"] is False


def test_summary_keeps_timeout_durations_outside_success_percentiles() -> None:
    summary = OperationSummary()
    summary.add(OperationResult("search", 0.0, 0.01, True, False))
    summary.add(OperationResult("search", 0.0, 0.4, False, True, "timeout"))
    payload = summary.as_dict()
    assert payload["sample_count"] == 1
    assert payload["p50_seconds"] == 0.01
    assert payload["timed_out"] == 1
    assert payload["timeout_duration_sample_count"] == 1
    assert payload["timeout_duration_p50_seconds"] == 0.4
    assert payload["timeout_duration_max_seconds"] == 0.4


def test_scrape_summary_retains_every_attempt_duration() -> None:
    summary = ScrapeSummary()
    summary.record(0.01, True)
    summary.record(0.25, False)
    payload = summary.as_dict()
    assert payload["all_durations_seconds"] == [0.01, 0.25]
    assert payload["max_attempt_seconds"] == 0.25
    assert payload["completed"] == 1
    assert payload["failed"] == 1


def test_fixed_seed_payload_is_deterministic_and_bounded() -> None:
    first = _memory_payload(4, "probe-project", 123)
    second = _memory_payload(4, "probe-project", 123)
    assert first == second
    assert len(first["content"]) <= 5000
    assert first["project_id"] == "probe-project"


def test_child_environment_overrides_paths_and_removes_provider_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OC_DB_PATH", "should-not-leak")
    monkeypatch.setenv("OPENAI_API_KEY", "should-not-leak")
    env = _sanitized_child_environment(tmp_path, 8123, "stub")
    assert env["OC_DB_PATH"] == str(tmp_path / "openchronicle.db")
    assert env["OC_CONFIG_DIR"] == str(tmp_path / "config")
    assert env["OC_API_RATE_LIMIT_RPM"] == "0"
    assert "OPENAI_API_KEY" not in env
    assert env["OC_EMBEDDING_PROVIDER"] == "stub"
    assert env["OC_METRICS_ENABLED"] == "false"


def test_child_environment_enables_metrics_only_for_enabled_state(tmp_path: Path) -> None:
    disabled = _sanitized_child_environment(tmp_path / "disabled", 8123, "none")
    enabled = _sanitized_child_environment(tmp_path / "enabled", 8124, "none", metrics_enabled=True)
    assert disabled["OC_METRICS_ENABLED"] == "false"
    assert enabled["OC_METRICS_ENABLED"] == "true"


def test_probe_accepts_a_local_source_root(tmp_path: Path) -> None:
    source_root = tmp_path / "checkout"
    (source_root / "src" / "openchronicle").mkdir(parents=True)
    args = build_parser().parse_args(["--source-root", str(source_root)])
    _validate_args(args)


def test_same_run_matrix_requires_one_fixed_rest_client_count(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    (baseline / "src" / "openchronicle").mkdir(parents=True)
    args = build_parser().parse_args(
        [
            "--same-run-baseline-root",
            str(baseline),
            "--clients",
            "8,16",
            "--scrape-interval-seconds",
            "30",
        ]
    )
    with pytest.raises(ProbeError, match="exactly one client count"):
        _validate_args(args)


def test_vector_count_snapshot_accepts_disabled_and_active_health() -> None:
    assert _vector_count_from_health({"embedding_status": {"provider": "none", "status": "disabled"}}) == 0
    assert _vector_count_from_health({"embedding_status": {"provider": "stub", "status": "active", "embedded": 3}}) == 3
    with pytest.raises(ProbeError):
        _vector_count_from_health({"embedding_status": {"provider": "stub", "status": "active"}})


def test_rate_limit_check_is_explicitly_opt_in() -> None:
    args = build_parser().parse_args(["--check-rate-limit"])
    assert args.check_rate_limit is True


def test_probe_defaults_match_phase_one_contract() -> None:
    config = ProbeConfig()
    assert config.corpus_size == 1000
    assert config.clients == (1, 4, 8, 16)
    assert config.warmup_seconds == 5.0
    assert config.duration_seconds == 60.0
    assert config.max_runtime_seconds == 600.0


def test_probe_rejects_unbounded_scrape_frequency() -> None:
    from scripts.probe_performance import _validate_args

    args = build_parser().parse_args(["--scrape-interval-seconds", "0.009"])
    with pytest.raises(ProbeError, match="at least 0.01"):
        _validate_args(args)
