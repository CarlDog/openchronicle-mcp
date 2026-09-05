"""Bounded Linux A/B/C benchmark with repeated, freshly seeded A/A controls.

Runs only the disposable loopback probe, never a supplied server URL. Each
case has a fresh process and database. The full suite has a ten-minute cap;
partial results are retained, never silently dropped or rerun. Host-variance
rules are conservative empirical checks, not statistical confidence intervals.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ORDERS = (("A", "B", "C", "R"), ("B", "C", "A", "R"), ("C", "A", "B", "R"))
STATES = {"A": "uninstrumented", "R": "uninstrumented", "B": "disabled", "C": "enabled"}
OPERATIONS = ("search", "list")


def source_digest(root: Path) -> str:
    """Hash application source/resources, excluding generated interpreter caches."""
    digest = hashlib.sha256()
    files = sorted(path for path in (root / "src" / "openchronicle").rglob("*") if path.is_file())
    for path in files:
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def case_result(report: dict[str, Any]) -> dict[str, Any]:
    return dict(report["result"]["client_counts"][0])


def eligibility(report: dict[str, Any], corpus_size: int) -> list[str]:
    """Fail closed on errors, missing percentiles/RSS, or a changed corpus."""
    try:
        case = case_result(report)
        reasons = list(case["eligibility"]["reasons"])
        if not case["eligibility"]["fixed_overhead_comparison"] or case["failed"] or case["timed_out"]:
            reasons.append("workload is ineligible")
        throughput = case["throughput_completed_per_second"]
        if case["completed"] <= 0 or not math.isfinite(throughput) or throughput <= 0:
            reasons.append("no completed workload")
        corpus = case["corpus"]
        if not corpus["state_unchanged"] or not corpus["starting"] == corpus["post_warmup"] == corpus["final"]:
            reasons.append("corpus changed")
        if any(corpus["final"][key] != corpus_size for key in ("memory_rows", "vector_rows")):
            reasons.append("unexpected corpus size")
        for operation in OPERATIONS:
            values = case["operations"][operation]
            if not values["p95_sample_sufficient"] or values["sample_count"] < 100:
                reasons.append(f"insufficient {operation} p95 samples")
            if values["p95_seconds"] is None or not math.isfinite(values["p95_seconds"]):
                reasons.append(f"unavailable {operation} p95")
        memory = case["process_memory"]
        if (
            not memory["supported"]
            or not memory["sample_count"]
            or memory["peak_rss_bytes"] is None
            or not math.isfinite(memory["peak_rss_bytes"])
            or memory["peak_rss_bytes"] <= 0
        ):
            reasons.append("unavailable OC RSS")
        if report["instrumentation_state"] == "enabled":
            scrapes = case.get("scrapes", {})
            if not scrapes.get("completed") or scrapes.get("failed", 0):
                reasons.append("missing or failed enabled scrape")
        return reasons
    except KeyError, IndexError, TypeError, ValueError:
        return ["missing or malformed case evidence"]


def deltas(reference: dict[str, Any], candidate: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Positive values mean regression; budgets stay in their original units."""
    values = {
        "throughput_loss_percent": {
            "delta": 100
            * (1 - candidate["throughput_completed_per_second"] / reference["throughput_completed_per_second"]),
            "budget": 5.0,
        },
        "rss_delta_mib": {
            "delta": (candidate["process_memory"]["peak_rss_bytes"] - reference["process_memory"]["peak_rss_bytes"])
            / 2**20,
            "budget": 10.0,
        },
    }
    for operation in OPERATIONS:
        baseline = reference["operations"][operation]["p95_seconds"]
        values[f"{operation}_p95_delta_ms"] = {
            "delta": 1000 * (candidate["operations"][operation]["p95_seconds"] - baseline),
            "budget": max(1.0, 50 * baseline),
        }
    return values


def assess(runs: list[dict[str, Any]], corpus_size: int = 1000) -> dict[str, Any]:
    """Assess all three complete blocks; do not cherry-pick successful cases."""
    reasons: list[str] = []
    expected = [(block, label) for block, order in enumerate(ORDERS, 1) for label in order]
    if [(run["block"], run["label"]) for run in runs] != expected:
        reasons.append("all twelve scheduled runs are required")
    fingerprints = set()
    metadata = set()
    for run in runs:
        report = run.get("report")
        if report is None:
            reasons.append(f"{run['block']}/{run['label']}: {run.get('error', 'missing report')}")
            continue
        reasons.extend(f"{run['block']}/{run['label']}: {reason}" for reason in eligibility(report, corpus_size))
        try:
            fingerprints.add(case_result(report)["corpus"]["final"]["fingerprint"])
            metadata.add(
                json.dumps(
                    {
                        key: report[key]
                        for key in (
                            "python_version",
                            "dependency_versions",
                            "clients",
                            "lane",
                            "transport",
                            "mode",
                            "provider_profile",
                            "corpus_size",
                            "seed",
                            "warmup_seconds",
                            "duration_seconds",
                            "cpu_affinity_mask",
                        )
                    },
                    sort_keys=True,
                )
            )
            if report["instrumentation_state"] != STATES[run["label"]]:
                reasons.append("condition state mismatch")
        except KeyError:
            reasons.append("missing comparability metadata")
    if len(fingerprints) != 1 or len(metadata) != 1:
        reasons.append("corpus or common launch/runtime metadata differ")
    if reasons:
        return {"status": "inconclusive", "reasons": reasons, "comparisons": {}}

    blocks: list[dict[str, Any]] = []
    for block in range(1, 4):
        cases = {run["label"]: case_result(run["report"]) for run in runs if run["block"] == block}
        blocks.append({"block": block, **{label: deltas(cases["A"], cases[label]) for label in ("R", "B", "C")}})
    comparisons = {}
    for label in ("B", "C"):
        metrics = {}
        for metric in blocks[0][label]:
            values = [block[label][metric] for block in blocks]
            fractions = [round(value["delta"] / value["budget"], 12) for value in values]
            noise = max(abs(block["R"][metric]["delta"] / block["R"][metric]["budget"]) for block in blocks)
            median_fraction = statistics.median(fractions)
            if noise > 1 or min(fractions) <= 1 < max(fractions) or (noise > 0 and abs(median_fraction - 1) <= noise):
                status = "inconclusive"
            else:
                status = "fail" if median_fraction > 1 else "pass"
            metrics[metric] = {
                "median_delta": statistics.median(value["delta"] for value in values),
                "median_budget": statistics.median(value["budget"] for value in values),
                "within_block": values,
                "max_control_noise_budget_fraction": noise,
                "status": status,
            }
        statuses = [value["status"] for value in metrics.values()]
        status = "inconclusive" if "inconclusive" in statuses else "fail" if "fail" in statuses else "pass"
        comparisons[f"{label}/A"] = {"status": status, "metrics": metrics}
    statuses = [comparison["status"] for comparison in comparisons.values()]
    return {
        "status": "inconclusive" if "inconclusive" in statuses else "fail" if "fail" in statuses else "pass",
        "blocks": blocks,
        "comparisons": comparisons,
        "noise_rule": "Inconclusive when repeated-A variation exceeds a budget, blocks cross a budget, or the median is within observed A/A variation of the budget. Empirical veto, not a confidence interval.",
    }


def run_probe(command: list[str], timeout: float) -> tuple[int, bool]:
    """A process-group timeout also stops the disposable OC grandchild."""
    kill_group = getattr(os, "killpg", None)
    sigkill = getattr(signal, "SIGKILL", None)
    if kill_group is None or sigkill is None:
        raise RuntimeError("Linux process-group cleanup is required")
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        return process.wait(timeout=timeout), False
    except subprocess.TimeoutExpired:
        with suppress(ProcessLookupError):
            kill_group(process.pid, signal.SIGTERM)
        with suppress(subprocess.TimeoutExpired):
            process.wait(timeout=5)
        # The parent can exit before its server; kill the entire group even
        # when wait() already returned, so a timed-out case cannot overlap.
        with suppress(ProcessLookupError):
            kill_group(process.pid, sigkill)
        process.wait(timeout=2)
        return process.returncode, True
    except BaseException:
        with suppress(ProcessLookupError):
            kill_group(process.pid, sigkill)
        process.wait(timeout=2)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    get_affinity = getattr(os, "sched_getaffinity", None)
    if os.name != "posix" or get_affinity is None:
        parser.error("run this bounded process-group harness inside the Linux test image")
    for root in (args.baseline_root, args.candidate_root):
        if not (root / "src" / "openchronicle").is_dir():
            parser.error("both source roots must contain src/openchronicle")
    sources = {"A": source_digest(args.baseline_root), "B_C": source_digest(args.candidate_root)}
    if sources["A"] == sources["B_C"]:
        parser.error("baseline and candidate must not be the same source tree")
    report: dict[str, Any] = {
        "method": "sequential-ABC-repeated-A-v1",
        "started_utc": datetime.now(UTC).isoformat(),
        "baseline_revision": os.environ.get("BENCHMARK_BASE_REVISION", "unknown"),
        "candidate_state": "uncommitted source snapshot",
        "source_sha256": sources,
        "python_version": platform.python_version(),
        "dependency_versions": {item.metadata["Name"]: item.version for item in importlib.metadata.distributions()},
        "cpu_affinity": sorted(get_affinity(0)),
        "cpu_count": os.cpu_count(),
        "maximum_runtime_seconds": 600,
        "runs": [],
    }
    deadline = time.perf_counter() + 600
    aborted = False
    with tempfile.TemporaryDirectory(prefix="oc-sequential-") as temp:
        for block, order in enumerate(ORDERS, 1):
            for label in order:
                run: dict[str, Any] = {"block": block, "label": label}
                remaining = deadline - time.perf_counter()
                if aborted:
                    run["error"] = "not started after an earlier probe failure"
                elif remaining < 45:
                    run["error"] = "suite runtime cap: insufficient time to start another case"
                else:
                    out = Path(temp) / f"{block}-{label}.json"
                    root = args.baseline_root if label in ("A", "R") else args.candidate_root
                    command = [
                        sys.executable,
                        str(ROOT / "scripts" / "probe_performance.py"),
                        "--source-root",
                        str(root),
                        "--instrumentation-state",
                        STATES[label],
                        "--transport",
                        "rest",
                        "--lane",
                        "fixed",
                        "--mode",
                        "hybrid",
                        "--provider-profile",
                        "stub",
                        "--corpus-size",
                        "1000",
                        "--clients",
                        "8",
                        "--warmup-seconds",
                        "5",
                        "--duration-seconds",
                        "30",
                        "--seed",
                        "20260904",
                        "--max-runtime-seconds",
                        str(min(120, remaining - 7)),
                        "--out",
                        str(out),
                    ]
                    if label == "C":
                        command.extend(["--scrape-interval-seconds", "30"])
                    print(f"OC_BENCHMARK_PROGRESS starting {block}/{label}", flush=True)
                    started = time.perf_counter()
                    code, timed_out = run_probe(command, min(127, remaining))
                    run["wall_seconds"] = round(time.perf_counter() - started, 3)
                    if code == 0 and out.exists():
                        run["report"] = json.loads(out.read_text(encoding="utf-8"))
                    else:
                        run["error"] = "process timeout" if timed_out else f"probe exit {code}"
                        aborted = True
                report["runs"].append(run)
                print(f"OC_BENCHMARK_CASE={json.dumps(run, separators=(',', ':'))}", flush=True)
                # Checkpoint every attempted run, including failed or skipped ones.
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["assessment"] = assess(report["runs"])
    report["finished_utc"] = datetime.now(UTC).isoformat()
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"OC_BENCHMARK_REPORT={json.dumps(report, separators=(',', ':'))}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
