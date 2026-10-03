"""MEAS-01 direct-cost run (design 0010, scope chosen by the operator 2026-10-03).

Runs inside the production image with no network, against copies of one
catalogued snapshot. Nothing here touches the live container or its volumes.

Part 1, paired end-to-end. Three `oc serve` processes on loopback, each on
its own copy of the snapshot: B (metrics off), C (metrics on, scraped) and
B2 (metrics off again, the repeated-baseline control). One client sends
each request to all three in a rotating order, so host noise lands on every
condition at the same moment instead of on whole runs. C-B is the enabled
cost; B2-B is the noise floor, and a metric whose B2-B already exceeds its
budget is inconclusive, never a pass. Phase "prod" scrapes C every 30 s
(production); phase "stress" scrapes it every 1 s for the responsiveness
gate. Operations: REST and MCP search (keyword) and list, equal quotas.

Part 2, direct recorder and exporter cost, single thread: the recorder calls
one request makes, timed on the Prometheus and the null recorder, and one
full-cardinality scrape render.

Budgets are design 0010's, unchanged: per-operation p95 +max(1 ms, 5% of B),
throughput (1/mean latency at one client) loss <= 5%, RSS +10 MiB; for the
responsiveness gate p99 +max(5 ms, 10% of B) with >= 1,000 samples per
operation, every scrape under 1 s and at least 30 scrapes.

Prints progress to stderr and one JSON report to stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import os
import random
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import timeit
import urllib.error
import urllib.request
from contextlib import AsyncExitStack
from datetime import timedelta
from itertools import product
from pathlib import Path
from typing import Any

KEY = "meas01-test-key"
CONDITIONS = ("B", "C", "B2")
PORTS = {"B": 18101, "C": 18102, "B2": 18103}
OPS = ("rest_search", "rest_list", "mcp_search", "mcp_list")
QUERIES = ("backup", "metrics", "release", "deploy", "search", "portainer", "schema", "test", "snapshot", "latency")
ORDERS = [list(p) for p in ((0, 1, 2), (1, 2, 0), (2, 0, 1), (0, 2, 1), (2, 1, 0), (1, 0, 2))]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def rss_mib(pid: int) -> float | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except OSError:
        return None
    return None


def host_snapshot() -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        out["loadavg"] = Path("/proc/loadavg").read_text().split()[:3]
        fields = Path("/proc/stat").read_text().splitlines()[0].split()[1:9]
        out["cpu_jiffies"] = [int(x) for x in fields]
    except OSError:
        pass
    return out


def busy_share(a: dict[str, Any], b: dict[str, Any]) -> float | None:
    if "cpu_jiffies" not in a or "cpu_jiffies" not in b:
        return None
    d = [y - x for x, y in zip(a["cpu_jiffies"], b["cpu_jiffies"], strict=True)]
    total = sum(d)
    idle = d[3] + d[4]  # idle + iowait
    return round(100 * (total - idle) / total, 2) if total else None


# ---------------------------------------------------------------- servers


def start_server(name: str, db: Path, work: Path) -> subprocess.Popen[bytes]:
    root = work / name
    for sub in ("config", "output", "backups"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("OC_", "OLLAMA", "OPENAI"))}
    env.update(
        {
            "OC_DB_PATH": str(db),
            "OC_CONFIG_DIR": str(root / "config"),
            "OC_OUTPUT_DIR": str(root / "output"),
            "OC_BACKUP_DIR": str(root / "backups"),
            "OC_API_HOST": "127.0.0.1",
            "OC_API_PORT": str(PORTS[name]),
            "OC_API_KEY": KEY,
            "OC_MCP_ALLOWED_HOSTS": "127.0.0.1:*",
            "OC_API_RATE_LIMIT_RPM": "1000000",
            "OC_EMBEDDING_PROVIDER": "none",
            "OC_MAINTENANCE_DISABLED": "1",
            "OC_METRICS_ENABLED": "true" if name == "C" else "false",
            "OC_LOG_LEVEL": "WARNING",
            "OC_LOG_FILE": "",
        }
    )
    oc = shutil.which("oc") or "oc"
    return subprocess.Popen(  # noqa: S603 - fixed argv, loopback only
        [oc, "serve"], env=env, stdout=subprocess.DEVNULL, stderr=open(root / "stderr.log", "wb")
    )


def get(port: int, path: str, timeout: float = 10.0) -> tuple[int, bytes]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers={"X-API-Key": KEY})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - loopback
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, b""


def wait_healthy(procs: dict[str, subprocess.Popen[bytes]], work: Path, deadline: float) -> None:
    pending = set(procs)
    while pending and time.monotonic() < deadline:
        for name in list(pending):
            if procs[name].poll() is not None:
                err = (work / name / "stderr.log").read_text(errors="replace")[-2000:]
                raise SystemExit(f"server {name} exited: {err}")
            try:
                if get(PORTS[name], "/health", 2)[0] == 200:
                    pending.discard(name)
            except OSError:
                pass
        time.sleep(0.5)
    if pending:
        raise SystemExit(f"servers not healthy: {sorted(pending)}")


class Scraper(threading.Thread):
    def __init__(self, interval: float) -> None:
        super().__init__(daemon=True)
        self.interval = interval
        self.durations: list[float] = []
        self.failures = 0
        self.stop_event = threading.Event()

    def run(self) -> None:
        nxt = time.monotonic()
        while not self.stop_event.is_set():
            t0 = time.monotonic()
            try:
                status, body = get(PORTS["C"], "/metrics", 10)
                ok = status == 200 and b"oc_" in body
            except OSError:
                ok = False
            if ok:
                self.durations.append(time.monotonic() - t0)
            else:
                self.failures += 1
            nxt += self.interval
            self.stop_event.wait(max(0.0, nxt - time.monotonic()))


# ---------------------------------------------------------------- workload


class Clients:
    def __init__(self, project_id: str | None) -> None:
        import httpx

        self.project_id = project_id
        self.http = {
            n: httpx.AsyncClient(base_url=f"http://127.0.0.1:{PORTS[n]}", headers={"X-API-Key": KEY}, timeout=30)
            for n in CONDITIONS
        }
        self.mcp: dict[str, Any] = {}
        self.stack = AsyncExitStack()

    async def open(self) -> None:
        from mcp.client.session import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        for n in CONDITIONS:
            read, write, _ = await self.stack.enter_async_context(
                streamablehttp_client(
                    f"http://127.0.0.1:{PORTS[n]}/mcp/", headers={"X-API-Key": KEY}, timeout=30, sse_read_timeout=30
                )
            )
            session = await self.stack.enter_async_context(
                ClientSession(read, write, read_timeout_seconds=timedelta(seconds=30))
            )
            await session.initialize()
            self.mcp[n] = session

    async def close(self) -> None:
        await self.stack.aclose()
        for c in self.http.values():
            await c.aclose()

    def _scope(self) -> dict[str, Any]:
        return {"project_id": self.project_id} if self.project_id else {}

    async def run(self, cond: str, op: str, seq: int) -> tuple[bool, float]:
        query = QUERIES[seq % len(QUERIES)]
        t0 = time.perf_counter()
        try:
            if op == "rest_search":
                r = await self.http[cond].get(
                    "/api/v1/memory/search",
                    params={"query": query, "mode": "keyword", "top_k": 8, "compact": "true", **self._scope()},
                )
                ok = r.status_code == 200
            elif op == "rest_list":
                r = await self.http[cond].get(
                    "/api/v1/memory",
                    params={"limit": 20, "compact": "true", "order_by": "created_at", **self._scope()},
                )
                ok = r.status_code == 200
            elif op == "mcp_search":
                res = await self.mcp[cond].call_tool(
                    "memory_search", {"query": query, "mode": "keyword", "top_k": 8, "compact": True, **self._scope()}
                )
                ok = not getattr(res, "isError", False)
            else:
                res = await self.mcp[cond].call_tool(
                    "memory_list", {"limit": 20, "compact": True, "order_by": "created_at", **self._scope()}
                )
                ok = not getattr(res, "isError", False)
        except Exception:  # noqa: BLE001 - any failure is counted, never retried
            ok = False
        return ok, (time.perf_counter() - t0) * 1000


async def run_phase(
    clients: Clients, per_op: int, warmup: int, scrape_interval: float, rng: random.Random
) -> dict[str, Any]:
    plan = [op for op in OPS for _ in range(per_op)]
    rng.shuffle(plan)
    for i in range(warmup):
        for cond in CONDITIONS:
            await clients.run(cond, OPS[i % len(OPS)], i)
    gc.collect()
    scraper = Scraper(scrape_interval)
    lat: dict[str, dict[str, list[float]]] = {c: {op: [] for op in OPS} for c in CONDITIONS}
    errors: dict[str, int] = dict.fromkeys(CONDITIONS, 0)
    host0, t0 = host_snapshot(), time.monotonic()
    scraper.start()
    for seq, op in enumerate(plan):
        for idx in ORDERS[seq % len(ORDERS)]:
            cond = CONDITIONS[idx]
            ok, ms = await clients.run(cond, op, seq)
            if ok:
                lat[cond][op].append(ms)
            else:
                errors[cond] += 1
    scraper.stop_event.set()
    scraper.join(15)
    elapsed, host1 = time.monotonic() - t0, host_snapshot()
    return {
        "lat": lat,
        "errors": errors,
        "elapsed_s": round(elapsed, 1),
        "host_busy_pct": busy_share(host0, host1),
        "load_before_after": [host0.get("loadavg"), host1.get("loadavg")],
        "scrapes": {
            "interval_s": scrape_interval,
            "ok": len(scraper.durations),
            "failed": scraper.failures,
            "max_ms": round(max(scraper.durations) * 1000, 2) if scraper.durations else None,
            "p50_ms": round(statistics.median(scraper.durations) * 1000, 2) if scraper.durations else None,
        },
    }


# ---------------------------------------------------------------- verdicts


def compare(lat: dict[str, dict[str, list[float]]], q: float, floor_ms: float, frac: float, min_n: int) -> dict:
    out: dict[str, Any] = {}
    for op in OPS:
        b, c, b2 = lat["B"][op], lat["C"][op], lat["B2"][op]
        n = min(len(b), len(c), len(b2))
        pb, pc, pb2 = pct(b, q), pct(c, q), pct(b2, q)
        row: dict[str, Any] = {"n": n}
        if n < min_n or pb is None or pc is None or pb2 is None:
            row["verdict"] = "insufficient"
            out[op] = row
            continue
        budget = max(floor_ms, frac * pb)
        delta, noise = pc - pb, pb2 - pb
        row.update(
            {
                f"B_p{int(q * 100)}_ms": round(pb, 3),
                f"C_p{int(q * 100)}_ms": round(pc, 3),
                f"B2_p{int(q * 100)}_ms": round(pb2, 3),
                "C_minus_B_ms": round(delta, 3),
                "B2_minus_B_ms": round(noise, 3),
                "budget_ms": round(budget, 3),
            }
        )
        if abs(noise) > budget:
            row["verdict"] = "inconclusive (control moved more than the budget)"
        else:
            row["verdict"] = "pass" if delta <= budget else "fail"
        out[op] = row
    return out


def throughput(lat: dict[str, dict[str, list[float]]]) -> dict[str, Any]:
    # One closed-loop client: throughput is 1/mean latency over the same mix.
    mean = {c: statistics.fmean([x for op in OPS for x in lat[c][op]]) for c in CONDITIONS}
    loss = (mean["C"] - mean["B"]) / mean["C"] * 100
    noise = (mean["B2"] - mean["B"]) / mean["B2"] * 100
    verdict = "inconclusive (control moved more than 5%)" if abs(noise) > 5 else ("pass" if loss <= 5 else "fail")
    return {
        "mean_ms": {k: round(v, 3) for k, v in mean.items()},
        "C_loss_pct": round(loss, 2),
        "B2_loss_pct": round(noise, 2),
        "verdict": verdict,
    }


# ---------------------------------------------------------------- part 2


def full_matrix(recorder: Any, m: Any) -> None:
    """Every reachable label combination (mirrors tests/helpers/metrics.py)."""
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
    for route, method, status in product(routes, sorted(m._HTTP_METHODS) + ["unknown"], [100, 200, 300, 400, 500, 600]):
        recorder.observe_http(path=route, method=method, status_code=status, duration_seconds=0.01)
    for tool, outcome in product(sorted(m._MCP_TOOLS) + ["unknown"], sorted(m._MCP_OUTCOMES) + ["unknown"]):
        recorder.observe_mcp(tool=tool, outcome=outcome, duration_seconds=0.01)
    for provider, operation, outcome in product(
        sorted(m._PROVIDERS) + ["unknown"],
        sorted(m._EMBEDDING_OPERATIONS) + ["unknown"],
        sorted(m._EMBEDDING_OUTCOMES) + ["unknown"],
    ):
        recorder.observe_embedding(provider=provider, operation=operation, outcome=outcome, duration_seconds=0.01)
    for kind in sorted(m._LOCK_KINDS) + ["unknown"]:
        recorder.observe_store_lock(kind=kind, wait_seconds=0.001, hold_seconds=0.01)
    for surface in sorted(m._SURFACES) + ["unknown"]:
        recorder.inflight_inc(surface)
        recorder.inflight_dec(surface)
    for stage in sorted(m._SEARCH_STAGES) + ["unknown"]:
        recorder.observe_search_stage(stage=stage, duration_seconds=0.01)
    for reason in sorted(m._FALLBACK_REASONS) + ["unknown"]:
        recorder.observe_search_fallback(reason=reason)
    for job, outcome in product(sorted(m._JOB_NAMES) + ["unknown"], sorted(m._JOB_OUTCOMES) + ["unknown"]):
        recorder.observe_job(name=job, outcome=outcome, duration_seconds=0.01)
        recorder.set_job_last_success(name=job, timestamp_seconds=0)
    for outcome in sorted(m._BACKFILL_OUTCOMES) + ["unknown"]:
        recorder.observe_backfill_item(outcome=outcome)


def direct_cost() -> dict[str, Any]:
    import openchronicle.core.infrastructure.observability.prometheus_recorder as m
    from openchronicle.core.application.observability.null_recorder import NullMetricsRecorder

    # A keyword search request: middleware in/out and HTTP observation, the
    # MCP tool observation when it came over MCP, the search stages and the
    # store lock around the read. Upper bound: both surfaces on one request.
    stages = sorted(m._SEARCH_STAGES)[:4]
    lock_kind = "read"

    def request(r: Any) -> None:
        r.inflight_inc("rest")
        for s in stages:
            r.observe_search_stage(stage=s, duration_seconds=0.001)
        r.observe_store_lock(kind=lock_kind, wait_seconds=0.0001, hold_seconds=0.001)
        r.observe_mcp(tool="memory_search", outcome="ok", duration_seconds=0.004)
        r.inflight_dec("rest")
        r.observe_http(path="/api/v1/memory/search", method="GET", status_code=200, duration_seconds=0.005)

    def us(fn: Any, n: int) -> float:
        runs = timeit.repeat(fn, number=n, repeat=9)
        return statistics.median(runs) / n * 1e6

    prom, null = m.PrometheusMetricsRecorder(), NullMetricsRecorder()
    per_request_prom = us(lambda: request(prom), 20000)
    per_request_null = us(lambda: request(null), 20000)

    full = m.PrometheusMetricsRecorder()
    full_matrix(full, m)

    async def render_times(rec: Any, n: int) -> list[float]:
        out = []
        for _ in range(n):
            c0 = time.process_time()
            body = await rec.render()
            out.append((time.process_time() - c0) * 1000)
        out.append(len(body))
        return out

    times = asyncio.run(render_times(full, 60))
    size = int(times.pop())
    series = sum(1 for line in (asyncio.run(full.render())).decode().splitlines() if line and not line.startswith("#"))
    render_ms = statistics.median(times)
    return {
        "per_request_recorder_us": {
            "prometheus": round(per_request_prom, 2),
            "null": round(per_request_null, 3),
            "added_us": round(per_request_prom - per_request_null, 2),
            "budget_us": 1000,
            "calls": "inflight in/out, 4 search stages, 1 store lock, MCP and HTTP observations",
        },
        "full_cardinality_scrape": {
            "series": series,
            "bytes": size,
            "render_cpu_ms_median": round(render_ms, 3),
            "render_cpu_ms_max": round(max(times), 3),
            "share_of_one_core_at_30s_pct": round(render_ms / 30000 * 100, 4),
        },
    }


# ---------------------------------------------------------------- main


def pick_project(db: Path) -> str | None:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = con.execute(
            "SELECT project_id, COUNT(*) n FROM memory_items GROUP BY project_id ORDER BY n DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None
    finally:
        con.close()


async def amain(args: argparse.Namespace) -> dict[str, Any]:
    work = Path(tempfile.mkdtemp(prefix="meas01-", dir=args.workdir))
    src = Path(args.snapshot)
    dbs = {}
    for n in CONDITIONS:
        dbs[n] = work / f"{n}.db"
        shutil.copyfile(src, dbs[n])
    project = pick_project(dbs["B"])
    procs = {n: start_server(n, dbs[n], work) for n in CONDITIONS}
    report: dict[str, Any] = {"snapshot_bytes": src.stat().st_size, "scoped_to_largest_project": bool(project)}
    try:
        wait_healthy(procs, work, time.monotonic() + 120)
        log("servers healthy")
        clients = Clients(project)
        await clients.open()
        rng = random.Random(20261003)
        try:
            for phase, per_op, interval in (("prod", args.per_op, 30.0), ("stress", args.stress_per_op, 1.0)):
                log(f"phase {phase}: {per_op} per operation x {len(OPS)} operations x 3 conditions")
                res = await run_phase(clients, per_op, args.warmup, interval, rng)
                lat = res.pop("lat")
                res["counts"] = {c: {op: len(lat[c][op]) for op in OPS} for c in CONDITIONS}
                res["p50_ms"] = {c: {op: round(pct(lat[c][op], 0.5) or 0, 3) for op in OPS} for c in CONDITIONS}
                if phase == "prod":
                    res["p95_gate"] = compare(lat, 0.95, 1.0, 0.05, 100)
                    res["throughput_gate"] = throughput(lat)
                else:
                    res["p99_gate"] = compare(lat, 0.99, 5.0, 0.10, 1000)
                    s = res["scrapes"]
                    res["scrape_gate"] = (
                        "pass"
                        if s["ok"] >= 30 and not s["failed"] and (s["max_ms"] or 0) < 1000
                        else "fail or insufficient"
                    )
                report[phase] = res
                log(f"phase {phase} done in {res['elapsed_s']} s")
        finally:
            await clients.close()
        rss = {n: rss_mib(p.pid) for n, p in procs.items()}
        report["rss_mib"] = {k: round(v, 1) if v else None for k, v in rss.items()}
        if rss["B"] and rss["C"] and rss["B2"]:
            delta, noise = rss["C"] - rss["B"], rss["B2"] - rss["B"]
            report["rss_gate"] = {
                "C_minus_B_mib": round(delta, 1),
                "B2_minus_B_mib": round(noise, 1),
                "verdict": "inconclusive" if abs(noise) > 10 else ("pass" if delta <= 10 else "fail"),
            }
    finally:
        for p in procs.values():
            p.terminate()
        for p in procs.values():
            try:
                p.wait(15)
            except subprocess.TimeoutExpired:
                p.kill()
        shutil.rmtree(work, ignore_errors=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--workdir", default="/tmp")
    parser.add_argument("--per-op", type=int, default=1500)
    parser.add_argument("--stress-per-op", type=int, default=1200)
    parser.add_argument("--warmup", type=int, default=50)
    args = parser.parse_args()
    from openchronicle.version import package_version

    started = time.time()
    report = {"tool": "meas01.py", "package_version": package_version(), "build_revision": None}
    rev = Path("/app/build-revision")
    if rev.exists():
        report["build_revision"] = rev.read_text().strip()
    report.update(asyncio.run(amain(args)))
    log("part 2: direct recorder and exporter cost")
    report["direct_cost"] = direct_cost()
    report["total_s"] = round(time.time() - started, 1)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
