#!/usr/bin/env bash
# v3.8.0's added per-request work, timed directly (design 0010 follow-up to
# v380-write-path.sh, whose NAS run was inconclusive on host noise).
# Uses the v3.8.0 image that v380_write_path.sh built and the newest catalogued
# snapshot, read-only, no network. Production is touched once: `docker inspect`.
#   sudo bash tools/perf/v380-microbench.sh 2>&1 | tee v380-micro.log
set -euo pipefail
IMG="${IMG:-openchronicle-mcp:v380p-707cadb6}"
EXPORTS=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/exports"}}{{.Source}}{{end}}{{end}}' openchronicle-mcp)
SNAP=$(ls -1t "$EXPORTS"/backups/auto/openchronicle-*.db | head -n 1)
echo "image: $IMG ($(docker run --rm --pull never --network none --entrypoint cat "$IMG" /app/build-revision))"
echo "snapshot: $SNAP"
docker run --rm --pull never --network none --read-only --user 1000:1000 \
  --mount "type=bind,source=$SNAP,target=/s.db,readonly" \
  --entrypoint python "$IMG" - <<'PY'
import sqlite3, statistics, timeit
from datetime import datetime
from openchronicle.core.domain.time_utils import require_utc

def us(stmt, setup="pass", n=2000, g=None):
    runs = timeit.repeat(stmt, setup, number=n, repeat=7, globals=g)
    return statistics.median(runs) / n * 1e6

aware = datetime.fromisoformat("2026-10-03T10:15:30.123456-05:00")
g = {"require_utc": require_utc, "aware": aware}
conv = us("require_utc(aware, field='created_at').isoformat()", g=g, n=100000)
base = us("aware.isoformat()", g=g, n=100000)
print(f"require_utc + isoformat: {conv:.2f} us (plain isoformat {base:.2f} us); "
      f"memory_save calls it twice: +{2 * (conv - base):.2f} us per request")

c = sqlite3.connect("file:/s.db?mode=ro&immutable=1", uri=True)
g = {"c": c}
for label, old, new in [
    ("project_list", "SELECT * FROM projects ORDER BY created_at DESC",
                     "SELECT * FROM projects ORDER BY created_at DESC, id DESC"),
    ("list_memory_by_source (git-onboard)",
     "SELECT * FROM memory_items WHERE source = 'git-onboard' ORDER BY created_at DESC",
     "SELECT * FROM memory_items WHERE source = 'git-onboard' ORDER BY created_at DESC, id DESC"),
]:
    t_old = us(f"c.execute({old!r}).fetchall()", g=g, n=500)
    t_new = us(f"c.execute({new!r}).fetchall()", g=g, n=500)
    rows = len(c.execute(new).fetchall())
    print(f"{label}: {t_old:.1f} us -> {t_new:.1f} us ({t_new - t_old:+.1f} us, {rows} rows)")
print("budget for comparison: 1 ms = 1000 us added p95 per operation")
PY
