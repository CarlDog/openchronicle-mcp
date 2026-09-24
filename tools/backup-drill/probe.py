"""Latency probe for the backup drill; runs inside the drill container.

Budget (operator, 2026-09-24): zero failed requests, and the p95 of /health
plus one keyword search during a snapshot is at most 2x the idle p95 and
under 500 ms. Prints one JSON line; exit status 0 only when the budget holds.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"
PATHS = ("/health", "/memory/search?query=backup&mode=keyword&top_k=5")
IDLE_SAMPLES = 60
BACKUPS = 10
# The API allows 600 requests/min per client (OC_API_RATE_LIMIT_RPM); an
# unpaced loop measures the rate limiter's 429s, not the service.
INTERVAL = 0.125
statuses: dict[str, int] = {}


def request(path: str) -> tuple[float, float, bool]:
    start = time.monotonic()
    try:
        with urllib.request.urlopen(BASE + path, timeout=10) as response:
            response.read()
            status = str(response.status)
    except urllib.error.HTTPError as exc:
        status = str(exc.code)
    except Exception as exc:  # noqa: BLE001 - any failure counts against the budget
        status = type(exc).__name__
    statuses[status] = statuses.get(status, 0) + 1
    end = time.monotonic()
    time.sleep(max(0.0, INTERVAL - (end - start)))
    return start, end, status == "200"


def p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, int(round(0.95 * len(ordered))) - 1)] if ordered else float("nan")


idle = [request(PATHS[i % 2]) for i in range(IDLE_SAMPLES)]

samples: list[tuple[float, float, bool]] = []
stop = threading.Event()


def load() -> None:
    i = 0
    while not stop.is_set():
        samples.append(request(PATHS[i % 2]))
        i += 1


worker = threading.Thread(target=load)
worker.start()
windows = []
backup_seconds = []
for n in range(BACKUPS):
    time.sleep(0.3)
    started = time.monotonic()
    subprocess.run(["oc", "db", "backup", "--force", f"/tmp/probe-{n}.db"], check=True, capture_output=True)
    ended = time.monotonic()
    windows.append((started, ended))
    backup_seconds.append(ended - started)
time.sleep(0.3)
stop.set()
worker.join()
subprocess.run(["sh", "-c", "rm -f /tmp/probe-*.db*"], check=False)

during = [s for s in samples if any(s[0] < end and s[1] > start for start, end in windows)]
idle_ms = [(e - s) * 1000 for s, e, ok in idle if ok]
during_ms = [(e - s) * 1000 for s, e, ok in during if ok]
failures = sum(not ok for _, _, ok in idle + samples)
idle_p95, during_p95 = p95(idle_ms), p95(during_ms)
checks = {
    "zero_failures": failures == 0,
    "enough_samples_during_backup": len(during) >= 10,
    "during_p95_within_2x_idle": during_p95 <= 2 * idle_p95,
    "during_p95_under_500ms": during_p95 < 500,
}
result = {
    "idle_samples": len(idle),
    "during_samples": len(during),
    "total_load_samples": len(samples),
    "failures": failures,
    "statuses": statuses,
    "idle_p95_ms": round(idle_p95, 2),
    "during_p95_ms": round(during_p95, 2),
    "backup_seconds": [round(x, 3) for x in backup_seconds],
    "checks": checks,
    "budget_pass": all(checks.values()),
}
print("PROBE " + json.dumps(result, sort_keys=True))
sys.exit(0 if result["budget_pass"] else 1)
