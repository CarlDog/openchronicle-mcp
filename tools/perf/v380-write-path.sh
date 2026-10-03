#!/usr/bin/env bash
# Design 0010 check for v3.8.0 (operator, 2026-10-03: "Measure first").
#
# Compares v3.7.0 (A) with v3.8.0 (B, PR #38, migration 005) on the request
# paths #38 changed: memory_save (two require_utc conversions) and
# project_list (an id DESC tie-break), plus keyword search as a control.
# R is A again, a repeat baseline that measures run-to-run noise.
#
# Run on the NAS as a user who can run docker:
#   sudo bash v380-write-path.sh 2>&1 | tee v380.log
# Everything runs on new volumes seeded from the newest catalogued snapshot,
# with no network. Production is touched once: one `docker inspect` to find
# the exports path. Both images are built here from source the same way, so
# the comparison is not confounded by build tooling.
#
# Budgets (0010 step 3): added p95 per operation at most max(1 ms, 5% of A),
# throughput loss at most 5%. Rules (0010 "R/A" lane): a metric is
# inconclusive if any |R-A| exceeds its budget, if B's blocks straddle the
# budget, or if B's median delta is within the largest |R-A| of the budget.
set -euo pipefail

A_SHA="${A_SHA:-7feac57901b302d0b5a76dc4499dddd48186104d}"   # v3.7.0
B_SHA="${B_SHA:-707cadb6b1a3d3fab477b4af58a8c032658f65ac}"   # main with PR #38
CLIENTS="${CLIENTS:-8}"
ITERS="${ITERS:-150}"      # per client; each iteration is save + list + search
PROD=openchronicle-mcp
RUN="v380p-$(date -u +%Y%m%dT%H%M%SZ)"
WORK=$(mktemp -d "${TMPDIR:-/tmp}/oc-v380p.XXXXXXXXXX")
CREATED_CONTAINERS=()
CREATED_VOLUMES=()

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
cleanup() {
  for c in "${CREATED_CONTAINERS[@]:-}"; do [ -n "$c" ] && docker rm -f "$c" >/dev/null 2>&1 || true; done
  for v in "${CREATED_VOLUMES[@]:-}"; do [ -n "$v" ] && docker volume rm "$v" >/dev/null 2>&1 || true; done
  rm -rf "$WORK"
}
trap cleanup EXIT

build() {  # build SHA -> prints image id
  local sha=$1 tag="openchronicle-mcp:v380p-${1:0:8}"
  mkdir -p "$WORK/$sha"
  curl -fsSL "https://codeload.github.com/CarlDog/openchronicle-mcp/tar.gz/$sha" | tar -xz -C "$WORK/$sha"
  docker build -q --build-arg "OC_BUILD_REVISION=$sha" -t "$tag" "$WORK/$sha/openchronicle-mcp-$sha" >/dev/null
  local rev
  rev=$(docker run --rm --pull never --network none --read-only --entrypoint cat "$tag" /app/build-revision)
  [ "$rev" = "$sha" ] || fail "built $tag reports revision $rev"
  docker image inspect -f '{{.Id}}' "$tag"
}

# Load generator, run inside the container under test against loopback.
LOAD_PY='
import json, sys, threading, time, urllib.request, uuid
clients, iters = int(sys.argv[1]), int(sys.argv[2])
B = "http://127.0.0.1:8000/api/v1"
def req(method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(B + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=30) as resp:
        resp.read()
        return resp.status
proj = json.loads(urllib.request.urlopen(urllib.request.Request(
    B + "/project", data=json.dumps({"name": "perf-" + uuid.uuid4().hex[:8]}).encode(),
    method="POST", headers={"Content-Type": "application/json"}), timeout=30).read())["id"]
ops = {
    "save": lambda i: req("POST", "/memory", {"content": f"perf sample {uuid.uuid4().hex} release timestamp",
                                              "project_id": proj, "tags": ["perf"],
                                              "created_at": "2026-10-03T10:15:30.123456-05:00"}),
    "list": lambda i: req("GET", "/project"),
    "search": lambda i: req("GET", "/memory/search?query=release&mode=keyword&top_k=8"),
}
for i in range(10):  # warm-up, not measured
    for f in ops.values():
        f(i)
lat = {k: [] for k in ops}
errors = []
lock = threading.Lock()
def worker():
    mine = {k: [] for k in ops}
    for i in range(iters):
        for k, f in ops.items():
            t = time.perf_counter()
            try:
                status = f(i)
                if status != 200:
                    errors.append(f"{k}:{status}")
            except Exception as exc:
                errors.append(f"{k}:{type(exc).__name__}")
            mine[k].append((time.perf_counter() - t) * 1000)
    with lock:
        for k in ops:
            lat[k].extend(mine[k])
t0 = time.perf_counter()
ts = [threading.Thread(target=worker) for _ in range(clients)]
for t in ts: t.start()
for t in ts: t.join()
wall = time.perf_counter() - t0
def pct(xs, p):
    s = sorted(xs); return s[max(0, round(p * len(s)) - 1)]
print(json.dumps({"throughput": sum(len(v) for v in lat.values()) / wall,
                  "errors": len(errors), "error_kinds": sorted(set(errors))[:5],
                  **{f"{k}_p50": pct(v, .5) for k, v in lat.items()},
                  **{f"{k}_p95": pct(v, .95) for k, v in lat.items()},
                  "samples": {k: len(v) for k, v in lat.items()}}))
'

run_case() {  # run_case LABEL IMAGE_ID -> prints one JSON line
  local label=$1 image=$2 vol="oc-$RUN-$1-$RANDOM" name="oc-$RUN-$1-$RANDOM"
  docker volume create "$vol" >/dev/null; CREATED_VOLUMES+=("$vol")
  docker run --rm --pull never --network none --read-only \
    --mount "type=volume,source=$vol,target=/data" \
    --mount "type=bind,source=$SNAP,target=/snapshot.db,readonly" \
    --entrypoint sh "$image" -c 'cp /snapshot.db /data/openchronicle.db && chown -R 1000:1000 /data'
  docker run -d --pull never --name "$name" --network none \
    --mount "type=volume,source=$vol,target=/data" \
    --env OC_DB_PATH=/data/openchronicle.db --env OC_EMBEDDING_PROVIDER=none \
    --env OC_MAINTENANCE_DISABLED=1 --env OC_API_KEY= --env OC_API_RATE_LIMIT_RPM=10000000 \
    "$image" >/dev/null
  CREATED_CONTAINERS+=("$name")
  for _ in $(seq 1 45); do
    docker exec "$name" python -c 'import urllib.request as u; u.urlopen("http://127.0.0.1:8000/health", timeout=3)' 2>/dev/null && break
    sleep 2
  done
  local out
  out=$(docker exec "$name" python -c "$LOAD_PY" "$CLIENTS" "$ITERS") || { docker logs --tail 30 "$name" >&2; fail "$label load run"; }
  docker rm -f "$name" >/dev/null; docker volume rm "$vol" >/dev/null
  echo "{\"case\": \"$label\", \"result\": $out}"
}

echo "===== Snapshot ====="
EXPORTS=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/exports"}}{{.Source}}{{end}}{{end}}' "$PROD")
[ -n "$EXPORTS" ] || fail "could not find the production /exports bind"
SNAP=$(ls -1t "$EXPORTS"/backups/auto/openchronicle-*.db | head -n 1)
echo "snapshot: $SNAP"

echo "===== Build A (v3.7.0, $A_SHA) and B ($B_SHA) from source ====="
A_IMG=$(build "$A_SHA"); echo "A: $A_IMG"
B_IMG=$(build "$B_SHA"); echo "B: $B_IMG"

echo "===== Three blocks, rotating order; $CLIENTS clients x $ITERS iterations ====="
RESULTS="$WORK/results.jsonl"
: >"$RESULTS"
block=0
for order in "A B R" "B R A" "R A B"; do
  block=$((block + 1))
  for c in $order; do
    img=$A_IMG; [ "$c" = B ] && img=$B_IMG
    line=$(run_case "$c" "$img")
    echo "{\"block\": $block, ${line:1}" | tee -a "$RESULTS"
  done
done

echo "===== Verdict ====="
docker run --rm -i --pull never --network none --entrypoint python "$A_IMG" -c '
import json, statistics, sys
rows = [json.loads(l) for l in sys.stdin if l.strip()]
by = {}
for r in rows:
    by.setdefault(r["block"], {})[r["case"]] = r["result"]
errors = sum(r["result"]["errors"] for r in rows)
verdicts = []
print(f"requests with errors: {errors}")
for op in ("save", "list", "search"):
    k = f"{op}_p95"
    budgets = [max(1.0, 0.05 * b["A"][k]) for b in by.values()]
    db = [b["B"][k] - b["A"][k] for b in by.values()]
    dr = [b["R"][k] - b["A"][k] for b in by.values()]
    budget, med, noise = statistics.median(budgets), statistics.median(db), max(abs(x) for x in dr)
    if any(abs(x) > bud for x, bud in zip(dr, budgets)) or (min(db) <= budget < max(db)) or (budget - med) < noise:
        v = "INCONCLUSIVE"
    else:
        v = "PASS" if med <= budget else "FAIL"
    if op != "search":
        verdicts.append(v)
    a = statistics.median(b["A"][k] for b in by.values())
    print(f"{op:6s} p95: A median {a:.2f} ms; B-A {[round(x, 2) for x in db]} (median {med:+.2f}); "
          f"R-A {[round(x, 2) for x in dr]}; budget {budget:.2f} ms -> {v}" + (" (control, not gated)" if op == "search" else ""))
tb = [(b["B"]["throughput"] - b["A"]["throughput"]) / b["A"]["throughput"] * 100 for b in by.values()]
tr = [(b["R"]["throughput"] - b["A"]["throughput"]) / b["A"]["throughput"] * 100 for b in by.values()]
med, noise = statistics.median(tb), max(abs(x) for x in tr)
if any(abs(x) > 5 for x in tr) or (min(tb) < -5 <= max(tb)) or (med + 5) < noise:
    v = "INCONCLUSIVE"
else:
    v = "PASS" if med >= -5 else "FAIL"
verdicts.append(v)
print(f"throughput: B vs A {[round(x, 1) for x in tb]}% (median {med:+.1f}%); R vs A {[round(x, 1) for x in tr]}%; budget -5% -> {v}")
if "FAIL" in verdicts:
    overall = "FAIL"
elif "INCONCLUSIVE" in verdicts or errors:
    overall = "INCONCLUSIVE"
else:
    overall = "PASS"
print(f"OVERALL: {overall}")
' <"$RESULTS"
echo "Paste everything above into the thread."
