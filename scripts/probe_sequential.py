"""Bounded Linux A/B/C benchmark with repeated, freshly seeded A/A controls.

Runs only the disposable loopback probe, never a supplied server URL. Each
case has a fresh process and database. Every suite has an explicit time cap;
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
import re
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
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scripts.probe_artifact import encode, load_json  # noqa: E402

ORDERS = (("A", "B", "C", "R"), ("B", "C", "A", "R"), ("C", "A", "B", "R"))
CALIBRATION_ORDERS = (("A", "R"),) * 3
STATES = {"A": "uninstrumented", "R": "uninstrumented", "B": "disabled", "C": "enabled"}
OPERATIONS = ("search", "list")
PROTOCOL: dict[str, Any] = {
    "id": "nas-sequential-recovery-v2",
    "warmup_seconds": 15,
    "duration_seconds": 90,
    "case_cap_seconds": 180,
    "calibration_cap_seconds": 900,
    "acceptance_cap_seconds": 1800,
    "scrape_interval_seconds": 30,
    "scrape_offsets_seconds": [0, 30, 60],
    "corpus_size": 1000,
    "clients": [8],
    "seed": 20260904,
}


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
            if "scheduled_offsets_seconds" in scrapes:
                attempts = scrapes.get("attempts", [])
                if len(attempts) != len(scrapes["scheduled_offsets_seconds"]) or any(
                    not item["completed"]
                    or item["offset_seconds"] + item["duration_seconds"] > report["duration_seconds"]
                    for item in attempts
                ):
                    reasons.append("missing or late measured scrape")
        return reasons
    except (KeyError, IndexError, TypeError, ValueError):
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


def _case_checks(runs: list[dict[str, Any]], orders: tuple[tuple[str, ...], ...], corpus_size: int) -> list[str]:
    reasons: list[str] = []
    expected = [(block, label) for block, order in enumerate(orders, 1) for label in order]
    if [(run.get("block"), run.get("label")) for run in runs] != expected:
        return ["all scheduled runs are required in order"]
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
    return reasons


def assess(runs: list[dict[str, Any]], corpus_size: int = 1000) -> dict[str, Any]:
    """Assess all three complete blocks; do not cherry-pick successful cases."""
    reasons = _case_checks(runs, ORDERS, corpus_size)
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


def assess_calibration(runs: list[dict[str, Any]]) -> dict[str, Any]:
    reasons = _case_checks(runs, CALIBRATION_ORDERS, 1000)
    if reasons:
        return {"status": "inconclusive", "reasons": reasons, "pairs": []}
    pairs: list[dict[str, Any]] = [
        {
            "block": index // 2 + 1,
            "metrics": deltas(case_result(runs[index]["report"]), case_result(runs[index + 1]["report"])),
        }
        for index in range(0, len(runs), 2)
    ]
    noise = {
        metric: max(abs(pair["metrics"][metric]["delta"] / pair["metrics"][metric]["budget"]) for pair in pairs)
        for metric in pairs[0]["metrics"]
    }
    return {
        "status": "pass" if max(noise.values()) <= 1 else "inconclusive",
        "pairs": pairs,
        "max_control_noise_budget_fraction": noise,
        "reasons": [name for name, value in noise.items() if value > 1],
    }


def validate_report(report: dict[str, Any]) -> None:
    """Validate evidence before trusting the producer's saved assessment.

    Failed/skipped runs remain valid artifacts but cannot pass the assessor.
    Malformed evidence is an integrity failure, not merely a noisy comparison.
    """
    try:
        json.dumps(report, allow_nan=False)
        version2 = report["method"] == "sequential-ABC-repeated-A-v2"
        if not version2 and report["method"] != "sequential-ABC-repeated-A-v1":
            raise ValueError("unknown benchmark method")
        mode = report["suite_mode"] if version2 else "acceptance"
        if mode not in ("calibration", "acceptance"):
            raise ValueError("unknown suite mode")
        orders = CALIBRATION_ORDERS if mode == "calibration" else ORDERS
        expected = [(block, label) for block, order in enumerate(orders, 1) for label in order]
        runs = report["runs"]
        if [(run["block"], run["label"]) for run in runs] != expected:
            raise ValueError("incorrect case count/order")
        for value in report["source_sha256"].values():
            if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise ValueError("invalid source hash")
        if set(report["source_sha256"]) != {"A", "B_C"}:
            raise ValueError("missing source identity")
        if version2:
            if report["protocol"] != PROTOCOL:
                raise ValueError("protocol differs from frozen v2")
            if set(report["probe_sha256"]) != {"probe_performance.py", "probe_sequential.py", "probe_artifact.py"}:
                raise ValueError("missing harness identity")
            if any(re.fullmatch(r"[0-9a-f]{64}", value) is None for value in report["probe_sha256"].values()):
                raise ValueError("invalid harness hash")
            if report["maximum_runtime_seconds"] != PROTOCOL[f"{mode}_cap_seconds"]:
                raise ValueError("suite deadline mismatch")
        if not report["python_version"] or not report["dependency_versions"] or not report["cpu_affinity"]:
            raise ValueError("missing runtime identity")
        for timestamp in (report["started_utc"], report["finished_utc"]):
            if datetime.fromisoformat(timestamp).tzinfo is None:
                raise ValueError("missing timestamp timezone")
        for run in runs:
            if "error" in run:
                if not isinstance(run["error"], str) or not run["error"] or "report" in run:
                    raise ValueError("malformed failed case")
                continue
            case_report = run["report"]
            if case_report["instrumentation_state"] != STATES[run["label"]]:
                raise ValueError("condition state mismatch")
            if len(case_report["result"]["client_counts"]) != 1:
                raise ValueError("one client-count result is required")
            case = case_result(case_report)
            for key in ("attempted", "completed", "failed", "timed_out"):
                if type(case[key]) is not int or case[key] < 0:
                    raise ValueError("invalid operation count")
            if case["attempted"] != case["completed"] + case["failed"] or case["timed_out"] > case["failed"]:
                raise ValueError("inconsistent operation counts")
            duration = case_report["duration_seconds"]
            if not isinstance(duration, (int, float)) or duration <= 0:
                raise ValueError("invalid measurement duration")
            total = 0
            for operation in OPERATIONS:
                values = case["operations"][operation]
                if type(values["sample_count"]) is not int or values["sample_count"] < 0:
                    raise ValueError("invalid sample count")
                if values["sample_count"] != values["completed"]:
                    raise ValueError("sample/count mismatch")
                total += values["completed"]
                throughput = values["throughput_completed_per_second"]
                if abs(throughput - values["completed"] / duration) > 0.00011:
                    raise ValueError("operation throughput disagrees with counts")
            if total != case["completed"] or abs(case["throughput_completed_per_second"] - total / duration) > 0.00011:
                raise ValueError("total throughput disagrees with counts")
            if version2:
                for key in ("warmup_seconds", "duration_seconds", "clients", "corpus_size", "seed"):
                    if case_report[key] != PROTOCOL[key]:
                        raise ValueError(f"case {key} differs from protocol")
                source = "A" if run["label"] in ("A", "R") else "B_C"
                if run["source_sha256"] != report["source_sha256"][source]:
                    raise ValueError("case source identity mismatch")
                if case_report["cpu_affinity_mask"] != hex(sum(1 << cpu for cpu in report["cpu_affinity"])):
                    raise ValueError("case CPU placement mismatch")
                if case_report["python_version"] != report["python_version"] or any(
                    report["dependency_versions"].get(key) != value
                    for key, value in case_report["dependency_versions"].items()
                ):
                    raise ValueError("case runtime identity mismatch")
                if run["label"] == "C":
                    scrapes = case["scrapes"]
                    attempts = scrapes["attempts"]
                    if scrapes["scheduled_offsets_seconds"] != PROTOCOL["scrape_offsets_seconds"]:
                        raise ValueError("scrape schedule mismatch")
                    if scrapes["attempted"] != len(attempts) or len(attempts) > 3:
                        raise ValueError("scrape attempt count mismatch")
                    for attempt in attempts:
                        if not 0 <= attempt["offset_seconds"] < duration or attempt["duration_seconds"] < 0:
                            raise ValueError("scrape lies outside measured interval")
                    if scrapes["completed"] != sum(item["completed"] is True for item in attempts):
                        raise ValueError("scrape completion count mismatch")
        assessment = assess_calibration(runs) if mode == "calibration" else assess(runs)
        if report["assessment"] != assessment:
            raise ValueError("saved assessment disagrees with cases")
    except (KeyError, TypeError, IndexError, OverflowError) as exc:
        raise ValueError("missing or malformed report evidence") from exc


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


def host_observation() -> dict[str, Any]:
    """Read-only snapshots, outside measurement; missing host data is explicit."""
    result: dict[str, Any] = {"observed_utc": datetime.now(UTC).isoformat()}
    for name in ("loadavg", "stat", "diskstats", "pressure/cpu", "pressure/io"):
        try:
            lines = (Path("/proc") / name).read_text().splitlines()
            if name == "stat":
                lines = [line for line in lines if line.startswith(("cpu ", "ctxt "))]
            result[name] = lines
        except OSError:
            result[name] = "unsupported"
    result["cpus"] = {}
    get_affinity = getattr(os, "sched_getaffinity", None)
    for cpu in sorted(get_affinity(0) if get_affinity is not None else []):
        values = {}
        for name in ("topology/core_id", "topology/thread_siblings_list", "cpufreq/scaling_cur_freq"):
            try:
                values[name] = (Path(f"/sys/devices/system/cpu/cpu{cpu}") / name).read_text().strip()
            except OSError:
                values[name] = "unsupported"
        result["cpus"][str(cpu)] = values
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--suite-mode", choices=("calibration", "acceptance"), default="acceptance")
    parser.add_argument(
        "--artifact-smoke", action="store_true", help="emit an explicitly unmeasured report to test retrieval"
    )
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
    orders = CALIBRATION_ORDERS if args.suite_mode == "calibration" else ORDERS
    suite_cap = PROTOCOL[f"{args.suite_mode}_cap_seconds"]
    report: dict[str, Any] = {
        "method": "sequential-ABC-repeated-A-v2",
        "suite_mode": args.suite_mode,
        "protocol": PROTOCOL,
        "started_utc": datetime.now(UTC).isoformat(),
        "baseline_revision": os.environ.get("BENCHMARK_BASE_REVISION", "unknown"),
        "candidate_state": "uncommitted source snapshot",
        "source_sha256": sources,
        "probe_sha256": {
            name: hashlib.sha256((ROOT / "scripts" / name).read_bytes()).hexdigest()
            for name in ("probe_performance.py", "probe_sequential.py", "probe_artifact.py")
        },
        "python_version": platform.python_version(),
        "dependency_versions": {item.metadata["Name"]: item.version for item in importlib.metadata.distributions()},
        "cpu_affinity": sorted(get_affinity(0)),
        "cpu_count": os.cpu_count(),
        "maximum_runtime_seconds": suite_cap,
        "runs": [],
    }
    deadline = time.perf_counter() + suite_cap
    aborted = False
    with tempfile.TemporaryDirectory(prefix="oc-sequential-") as temp:
        for block, order in enumerate(orders, 1):
            for label in order:
                run: dict[str, Any] = {"block": block, "label": label}
                remaining = deadline - time.perf_counter()
                if args.artifact_smoke:
                    run["error"] = "artifact transport smoke: no workload attempted"
                elif aborted:
                    run["error"] = "not started after an earlier probe failure"
                elif remaining < PROTOCOL["case_cap_seconds"]:
                    run["error"] = "suite runtime cap: insufficient time to start another case"
                else:
                    out = Path(temp) / f"{block}-{label}.json"
                    root = args.baseline_root if label in ("A", "R") else args.candidate_root
                    run["source_sha256"] = sources["A" if label in ("A", "R") else "B_C"]
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
                        str(PROTOCOL["warmup_seconds"]),
                        "--duration-seconds",
                        str(PROTOCOL["duration_seconds"]),
                        "--seed",
                        "20260904",
                        "--max-runtime-seconds",
                        str(PROTOCOL["case_cap_seconds"] - 14),
                        "--cpu-affinity-mask",
                        str(sum(1 << cpu for cpu in report["cpu_affinity"])),
                        "--out",
                        str(out),
                    ]
                    if label == "C":
                        command.extend(["--scrape-interval-seconds", str(PROTOCOL["scrape_interval_seconds"])])
                    print(f"OC_BENCHMARK_PROGRESS starting {block}/{label}", flush=True)
                    run["host_before"] = host_observation()
                    started = time.perf_counter()
                    code, timed_out = run_probe(command, PROTOCOL["case_cap_seconds"] - 7)
                    run["wall_seconds"] = round(time.perf_counter() - started, 3)
                    run["host_after"] = host_observation()
                    if code == 0 and out.exists():
                        try:
                            run["report"] = load_json(out.read_bytes())
                        except (OSError, ValueError):
                            run["error"] = "invalid child report"
                            aborted = True
                    else:
                        run["error"] = "process timeout" if timed_out else f"probe exit {code}"
                        aborted = True
                report["runs"].append(run)
                print(f"OC_BENCHMARK_PROGRESS finished {block}/{label} report={'report' in run}", flush=True)
                # Checkpoint every attempted run, including failed or skipped ones.
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["assessment"] = (
        assess_calibration(report["runs"]) if args.suite_mode == "calibration" else assess(report["runs"])
    )
    report["finished_utc"] = datetime.now(UTC).isoformat()
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for record in encode(args.out.read_bytes()):
        print(record, flush=True)
    validate_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
