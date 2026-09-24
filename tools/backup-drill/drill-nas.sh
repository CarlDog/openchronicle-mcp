#!/usr/bin/env bash
# NAS restore drill driver for OpenChronicle design 0017 (PR #39).
#
# Runs the runbook's drill blocks verbatim, each as its own `bash <file>`,
# filling only `VAR='<...>'` placeholder lines with values printed by earlier
# blocks, exactly as an operator would. Everything it creates is named
# oc-restore-drill-*; it never touches the production stack.
#
# Usage: copy this script, probe.py, the runbook (local_backup_restore.md)
# and a verified seed snapshot into one NAS folder, then run from it:
#   sudo bash drill-nas.sh
# Override IMAGE_REF, EXPECTED_REVISION, SEED_NAME, SEED_SHA and
# PROD_CONTAINER for a later drill; the defaults are the 2026-09-24 run.
set -euo pipefail
cd "$(dirname "$0")"
HERE=$(pwd -W 2>/dev/null || pwd)  # pwd -W: Git Bash test runs

RUNBOOK="$HERE/local_backup_restore.md"
PROBE="$HERE/probe.py"
IMAGE_REF="${IMAGE_REF:-ghcr.io/carldog/openchronicle-mcp:backup-drill-20260924-1fad2c4c@sha256:38b259a98f73e009d12a11edfd34298c72d7d3019c6ebe8f26ef553695f95758}"
EXPECTED_REVISION="${EXPECTED_REVISION:-1fad2c4c1a5a34c887913aa91f0fb901a6a52dd5}"
SEED="$HERE/${SEED_NAME:-pre-change-20260924T040030Z.db}"
SEED_SHA="${SEED_SHA:-eb85987e55c52dff87a4bfa9e4c83db73a3de77ec7481f1f97ae7ac06a689243}"
PROD_CONTAINER="${PROD_CONTAINER:-openchronicle-mcp-oc-1}"
BLOCKS="$HERE/blocks"
LOG="$HERE/drill-$(date -u +%Y%m%dT%H%M%SZ).log"
mkdir -p "$BLOCKS"
exec > >(tee -a "$LOG") 2>&1
T0=$(date +%s)
say() { echo "[$(( $(date +%s) - T0 ))s] $*"; }
fail() { say "DRILL FAILED: $*"; exit 1; }

# Printed values from earlier blocks, keyed by variable name.
declare -A VAL

extract() {  # extract <exact first-placeholder line prefix>
  awk -v want="$1" '
    /^```bash$/ { inb = 1; body = ""; hit = 0; next }
    inb && /^```$/ { inb = 0; if (hit) { printf "%s", body; found++ } ; next }
    inb { body = body $0 "\n"; if (index($0, want) == 1) hit = 1 }
    END { if (found != 1) exit 3 }
  ' "$RUNBOOK"
}

fill() {  # fill <block file>: rewrite VAR='...' lines whose VAR has a value
  local file=$1 line name out=""
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" =~ ^([A-Z_]+)=\'[^\']*\'$ ]]; then
      name=${BASH_REMATCH[1]}
      if [[ -n "${VAL[$name]+set}" ]]; then line="$name='${VAL[$name]}'"; fi
    fi
    out+="$line"$'\n'
  done < "$file"
  printf '%s' "$out" > "$file"
  # Placeholders may also sit inside a value, e.g. STAGE='.../candidate-<24 hex>.db'.
  if grep -qE "^[A-Z_]+='[^']*<" "$file"; then
    grep -nE "^[A-Z_]+='[^']*<" "$file"
    fail "unfilled placeholder in $file"
  fi
}

run_block() {  # run_block <label> <first-placeholder prefix>
  local label=$1 want=$2 file="$BLOCKS/$1.sh" out="$BLOCKS/$1.out" rc key value
  extract "$want" > "$file" || fail "block '$label' not found exactly once in the runbook"
  fill "$file"
  say "block $label: running"
  set +e
  bash "$file" > "$out" 2>&1
  rc=$?
  set -e
  sed 's/^/    | /' "$out"
  [[ $rc -eq 0 ]] || fail "block $label exited $rc"
  while IFS= read -r line; do
    if [[ "$line" =~ ^([A-Z_]+)=([^[:space:]]+) ]]; then
      key=${BASH_REMATCH[1]}; value=${BASH_REMATCH[2]}; VAL[$key]=$value
    fi
  done < "$out"
  say "block $label: ok"
}

wait_healthy() {
  local name=$1 status=""
  for _ in $(seq 1 60); do
    status=$(docker inspect -f '{{.State.Health.Status}}' "$name")
    [[ "$status" == healthy ]] && return 0
    sleep 2
  done
  fail "$name did not become healthy (last: $status)"
}

marker_present() {  # 0 = present, 1 = absent; any other error stops the drill
  local err
  if err=$(docker exec --user 1000:1000 "$1" python -c '
import sqlite3
c = sqlite3.connect("file:/data/openchronicle.db?mode=ro", uri=True)
c.execute("SELECT value FROM restore_drill_marker")' 2>&1); then
    return 0
  fi
  # Only this exact error means "absent"; anything else must not read as a pass.
  [[ "$err" == *"no such table: restore_drill_marker"* ]] && return 1
  fail "marker check failed unexpectedly: $err"
}

service_checks() {  # integrity, FK, counts, a known ID, search, build revision
  docker exec --user 1000:1000 "$1" python -c '
import json, sqlite3, urllib.request
c = sqlite3.connect("file:/data/openchronicle.db?mode=ro", uri=True)
r = {
  "integrity": c.execute("PRAGMA integrity_check").fetchone()[0],
  "fk_violations": c.execute("PRAGMA foreign_key_check").fetchone() is not None,
  "schema": c.execute("SELECT MAX(version) FROM schema_version").fetchone()[0],
  "memories": c.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0],
  "projects": c.execute("SELECT COUNT(*) FROM projects").fetchone()[0],
  "known_id": c.execute("SELECT COUNT(*) FROM memory_items WHERE id = ?", ("54f059eb-0370-4cbf-808a-7a9d678aeb7b",)).fetchone()[0],
}
h = json.load(urllib.request.urlopen("http://127.0.0.1:8000/api/v1/health", timeout=10))
s = json.load(urllib.request.urlopen("http://127.0.0.1:8000/api/v1/memory/search?query=backup&mode=keyword&top_k=3", timeout=10))
r["build_revision"] = h.get("build_revision"); r["search_hits"] = len(s)
print("CHECKS " + json.dumps(r, sort_keys=True))
assert r["integrity"] == "ok" and not r["fk_violations"] and r["known_id"] == 1 and r["search_hits"] > 0, r'
}

cleanup_drill() {  # remove only this run's drill container and volume
  local name=$1 vol=$2
  [[ "$name" == oc-restore-drill-* && "$vol" == oc-restore-drill-* ]] || fail "refusing to clean non-drill names: $name $vol"
  docker rm -f "$name" >/dev/null
  docker volume rm "$vol" >/dev/null
  say "removed $name and $vol"
}

leg() {  # leg <normal|abort>
  local leg=$1 op name vol
  say "===== $leg leg ====="
  VAL=([HOST_COPY]="$SEED" [DRILL_IMAGE_ID]="$IMAGE_ID")
  run_block "$leg-1-clone" "HOST_COPY='<absolute NAS path"
  name=${VAL[DRILL_NAME]}; vol=${VAL[DRILL_VOL]}
  [[ "$name" == oc-restore-drill-* && "$vol" == oc-restore-drill-* ]] || fail "clone printed non-drill names"
  op="restore-$leg-$(date +%s)"
  VAL+=([CID]="$name" [VOL]="$vol" [HELPER_IMAGE_ID]="$IMAGE_ID" [SERVING_IMAGE_ID]="$IMAGE_ID"
        [EXPECTED_STACK_PROJECT]=oc-restore-drill [OP]="$op")
  run_block "$leg-2-activate-dry-run" "CID='<observed currently serving oc container ID>'"
  if [[ "$leg" == abort ]]; then
    run_block "$leg-3-fault-injection" "VOL='<recorded DRILL_VOL of this second clone>'"
  else
    run_block "$leg-3-activate-apply" "CID='<same CID as the dry run>'"
    docker start "$name" >/dev/null
    wait_healthy "$name"
    if marker_present "$name"; then fail "post-snapshot marker present after activation"; fi
    say "candidate healthy; post-snapshot marker absent (expected)"
    service_checks "$name"
    say "latency probe (budget: zero failures; during-backup p95 <= 2x idle p95 and < 500 ms)"
    if docker exec -i --user 1000:1000 "$name" python - < "$PROBE"; then
      say "latency budget: PASS"
    else
      PROBE_FAILED=1
      say "latency budget: FAIL (recorded; the drill continues so the recovery path is still exercised)"
    fi
  fi
  run_block "$leg-4-rollback" "CID='<observed current or stopped candidate container ID>'"
  docker start "$name" >/dev/null
  wait_healthy "$name"
  run_block "$leg-5-marker-readback" "DRILL_NAME='<recorded DRILL_NAME>'"
  say "post-snapshot write survived rollback"
  service_checks "$name"
  run_block "$leg-6-retire-stage" "CID='<observed currently serving accepted container ID>'"
  cleanup_drill "$name" "$vol"
  say "===== $leg leg passed ====="
}

say "log: $LOG"
say "preflight"
[[ -f "$RUNBOOK" && -f "$PROBE" && -f "$SEED" ]] || fail "runbook, probe or seed missing next to this script"
test "$(sha256sum "$SEED" | cut -d' ' -f1)" = "$SEED_SHA" || fail "seed digest differs from the recorded off-NAS copy"
docker version --format 'docker {{.Server.Version}}' || fail "docker is not usable (run with sudo)"
PROD_BEFORE=$(docker inspect -f '{{.Id}} {{.State.StartedAt}} {{.RestartCount}} {{.State.Status}}' "$PROD_CONTAINER") \
  || fail "production container $PROD_CONTAINER not found; set PROD_CONTAINER"
say "production before: $PROD_BEFORE"
docker pull -q "$IMAGE_REF" >/dev/null
IMAGE_ID=$(docker image inspect -f '{{.Id}}' "$IMAGE_REF")
REV=$(docker run --rm --pull never --network none --read-only --entrypoint cat "$IMAGE_REF" /app/build-revision)
test "$REV" = "$EXPECTED_REVISION" || fail "drill image build revision is $REV"
say "drill image $IMAGE_ID (build $REV)"
PROBE_FAILED=0

leg normal
sleep 1  # the clone block names volumes by the second
leg abort

PROD_AFTER=$(docker inspect -f '{{.Id}} {{.State.StartedAt}} {{.RestartCount}} {{.State.Status}}' "$PROD_CONTAINER")
test "$PROD_AFTER" = "$PROD_BEFORE" || fail "production container changed: $PROD_AFTER"
say "production unchanged: $PROD_AFTER"
LEFT=$(docker ps -a --format '{{.Names}}' | grep -c '^oc-restore-drill-' || true)
say "drill containers left: $LEFT"
if [[ $PROBE_FAILED -ne 0 ]]; then
  say "DRILL COMPLETE: both recovery legs passed; latency budget FAILED"
  exit 2
fi
say "DRILL PASSED: both legs and the latency budget, in $(( $(date +%s) - T0 ))s"
