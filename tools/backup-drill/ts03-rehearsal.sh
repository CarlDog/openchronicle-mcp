#!/usr/bin/env bash
# TS-03 rehearsal for PR #38 (migration 005), on disposable volumes only.
# Recorded run: assessment rev 292 (passed 2026-10-03 at a18212f4 against
# the 2026-10-03T15:17Z catalogued snapshot).
#
# Run on the NAS as a user who can run docker (sudo bash tools/backup-drill/ts03-rehearsal.sh).
# It never stops, edits or recreates the production container
# `openchronicle-mcp` and never mounts its data volume. Its only production
# touches: one `docker inspect` to find the exports path, and (unless
# TAKE_SNAPSHOT=0) one `oc maintenance run-once db_backup`, the same
# catalogued snapshot the nightly job writes.
#
# Phases (each prints PASS or stops with FAIL):
#   1  fresh snapshot, its manifest digest, and its counts
#   2  build the candidate image from PR #38's head, verify its revision
#   3  runbook pre-flight: the new image's migration on a tmpfs copy
#   4  image pair: old image (v3.7.0) serves the copy, then the new one migrates it
#   5  refusal: a planted naive value stops the new image; the old one still serves
#   6  ordered rollback after 005: stop + restart policy no, stage, activate at
#      --expected-schema 4, start the old image, restore the restart policy
#   7  cleanup (KEEP=1 keeps the disposable volumes and containers)
# Portainer freeze and recreation cannot be scripted; see the end of the output.
set -euo pipefail

OLD_IMAGE="${OLD_IMAGE:-ghcr.io/carldog/openchronicle-mcp:v3.7.0}"
NEW_SHA="${NEW_SHA:-a18212f46fe44af3d2db5a973d887fcefd191b9b}"
NEW_IMAGE="openchronicle-mcp:ts03-${NEW_SHA:0:8}"
PROD=openchronicle-mcp
RUN="ts03-$(date -u +%Y%m%dT%H%M%SZ)"
WORK="${WORK:-/tmp/oc-$RUN}"
VOL_A="oc-$RUN-pair"
VOL_B="oc-$RUN-refusal"
CREATED_CONTAINERS=()
CREATED_VOLUMES=()

phase() { printf '\n===== %s =====\n' "$*"; }
pass() { printf 'PASS: %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

cleanup() {
  if [ "${KEEP:-0}" = 1 ]; then
    echo "KEEP=1: leaving ${CREATED_CONTAINERS[*]:-} ${CREATED_VOLUMES[*]:-}"
    return
  fi
  for c in "${CREATED_CONTAINERS[@]:-}"; do [ -n "$c" ] && docker rm -f "$c" >/dev/null 2>&1 || true; done
  for v in "${CREATED_VOLUMES[@]:-}"; do [ -n "$v" ] && docker volume rm "$v" >/dev/null 2>&1 || true; done
  rm -rf "$WORK"
}
trap cleanup EXIT

# Read-only counts of an OpenChronicle database: schema, rows, and timestamps
# that are not stored in UTC (+00:00). Prints one JSON line.
INSPECT_PY='
import json, sqlite3, sys
path, mode = sys.argv[1], sys.argv[2]
uri = f"file:{path}?mode=ro" + ("&immutable=1" if mode == "stopped" else "")
c = sqlite3.connect(uri, uri=True)
q = lambda s, *a: c.execute(s, a).fetchone()[0]
cols = [("projects", "created_at"), ("memory_items", "created_at"), ("memory_items", "updated_at")]
print(json.dumps({
    "integrity": q("PRAGMA integrity_check"),
    "schema": q("SELECT MAX(version) FROM schema_version"),
    "projects": q("SELECT count(*) FROM projects"),
    "memories": q("SELECT count(*) FROM memory_items"),
    "embeddings": q("SELECT count(*) FROM memory_embeddings"),
    "non_utc": sum(q(f"SELECT count(*) FROM {t} WHERE {col} IS NOT NULL AND {col} NOT LIKE ?", "%+00:00") for t, col in cols),
    "naive": sum(q(f"SELECT count(*) FROM {t} WHERE {col} IS NOT NULL AND substr({col}, 20) NOT GLOB ?", "*[+-][0-9][0-9]:[0-9][0-9]") for t, col in cols),
}, sort_keys=True))
'
# Inspect a stopped volume through a throwaway container. A read-only
# connection, not an immutable one, so a leftover WAL is still read.
inspect_vol() {
  docker run --rm --pull never --network none --user 1000:1000 \
    --mount "type=volume,source=$1,target=/data" \
    --entrypoint python "$OLD_IMAGE" -c "$INSPECT_PY" /data/openchronicle.db live
}
# Inspect the database a running container serves.
inspect_live() {
  docker exec --user 1000:1000 "$1" python -c "$INSPECT_PY" /data/openchronicle.db live
}
# Read one key from a JSON line on stdin (dotted path).
jget() {
  docker run --rm -i --pull never --network none --entrypoint python "$OLD_IMAGE" -c '
import json, sys
d = json.load(sys.stdin)
for k in sys.argv[1].split("."):
    d = d[k]
print(d)' "$1"
}
same_counts() {  # same_counts JSON_A JSON_B: projects, memories, embeddings match
  for k in projects memories embeddings; do
    [ "$(jget "$k" <<<"$1")" = "$(jget "$k" <<<"$2")" ] || return 1
  done
}
seed_volume() {  # seed_volume VOL: a new volume holding a copy of the snapshot
  docker volume create "$1" >/dev/null
  CREATED_VOLUMES+=("$1")
  docker run --rm --pull never --network none --read-only \
    --mount "type=volume,source=$1,target=/data" \
    --mount "type=bind,source=$SNAP,target=/snapshot.db,readonly" \
    --entrypoint sh "$OLD_IMAGE" -c \
    'cp /snapshot.db /data/openchronicle.db && chown -R 1000:1000 /data'
}
start_oc() {  # start_oc NAME IMAGE VOL RESTART_POLICY
  docker run -d --pull never --name "$1" --network none --restart "$4" \
    --label "oc.rehearsal=$RUN" \
    --mount "type=volume,source=$3,target=/data" \
    --env OC_DB_PATH=/data/openchronicle.db --env OC_EMBEDDING_PROVIDER=none \
    --env OC_MAINTENANCE_DISABLED=1 --env OC_API_KEY= \
    "$2" >/dev/null
  CREATED_CONTAINERS+=("$1")
}
wait_healthy() {  # wait_healthy NAME: /health answers 200 within 90 s
  for _ in $(seq 1 45); do
    if docker exec "$1" python -c 'import urllib.request as u,sys; sys.exit(0 if u.urlopen("http://127.0.0.1:8000/health",timeout=3).status==200 else 1)' 2>/dev/null; then
      return 0
    fi
    [ "$(docker inspect -f '{{.State.Running}}' "$1")" = true ] || break
    sleep 2
  done
  docker logs --tail 30 "$1" >&2 || true
  return 1
}
users_of() {  # users_of VOL: fail, naming them, if a running container mounts VOL
  local u
  u=$(docker ps --no-trunc --format '{{.ID}} {{.Names}} {{.Status}} {{.Mounts}}' | grep -F "$1" || true)
  [ -z "$u" ] || { echo "$u" >&2; fail "running containers still mount $1"; }
}
offline() {  # the offline restore helper against VOL_A, as uid 1000
  docker run --rm --pull never --network none --read-only --tmpfs /tmp \
    --user 1000:1000 --mount "type=volume,source=$VOL_A,target=/data" \
    --entrypoint python --env OC_OFFLINE_RESTORE=1 "$OLD_IMAGE" \
    /app/scripts/offline_restore.py "$@"
}

mkdir -p "$WORK"
docker pull -q "$OLD_IMAGE" >/dev/null
docker run --rm --pull never --network none --entrypoint cat "$OLD_IMAGE" /app/build-revision

phase "1. Fresh snapshot"
EXPORTS=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/exports"}}{{.Source}}{{end}}{{end}}' "$PROD")
[ -n "$EXPORTS" ] || fail "could not find the production /exports bind"
if [ "${TAKE_SNAPSHOT:-1}" = 1 ]; then
  docker exec --user 1000:1000 "$PROD" oc maintenance run-once db_backup
fi
SNAP=$(ls -1t "$EXPORTS"/backups/auto/openchronicle-*.db | head -n 1)
MANIFEST="${SNAP%.db}.json"
[ -f "$MANIFEST" ] || fail "no manifest beside $SNAP"
SNAP_SHA=$(jget sha256 <"$MANIFEST")
[[ "$SNAP_SHA" =~ ^[0-9a-f]{64}$ ]] || fail "manifest sha256 is not a digest"
echo "snapshot: $SNAP"
echo "manifest sha256: $SNAP_SHA"
[ "$(sha256sum "$SNAP" | cut -d' ' -f1)" = "$SNAP_SHA" ] || fail "snapshot does not match its manifest"
BASE=$(docker run --rm --pull never --network none --read-only --user 1000:1000 \
  --mount "type=bind,source=$SNAP,target=/s.db,readonly" \
  --entrypoint python "$OLD_IMAGE" -c "$INSPECT_PY" /s.db stopped)
echo "snapshot: $BASE"
[ "$(jget integrity <<<"$BASE")" = ok ] || fail "snapshot integrity"
[ "$(jget schema <<<"$BASE")" = 4 ] || fail "snapshot is not at schema 4"
[ "$(jget naive <<<"$BASE")" = 0 ] || fail "snapshot already holds naive values: 005 would refuse in production"
pass "snapshot verified against its manifest; schema 4, $(jget non_utc <<<"$BASE") non-UTC values, 0 naive"

phase "2. Candidate image from PR #38 at $NEW_SHA"
curl -fsSL "https://codeload.github.com/CarlDog/openchronicle-mcp/tar.gz/$NEW_SHA" | tar -xz -C "$WORK"
docker build -q --build-arg "OC_BUILD_REVISION=$NEW_SHA" -t "$NEW_IMAGE" "$WORK/openchronicle-mcp-$NEW_SHA" >/dev/null
NEW_IMAGE_ID=$(docker image inspect -f '{{.Id}}' "$NEW_IMAGE")
REV=$(docker run --rm --pull never --network none --read-only --entrypoint cat "$NEW_IMAGE" /app/build-revision)
[ "$REV" = "$NEW_SHA" ] || fail "build revision $REV"
pass "built $NEW_IMAGE ($NEW_IMAGE_ID), revision $REV"

phase "3. Pre-flight (runbook block) on a tmpfs copy"
set +e
PRE=$(docker run --rm --pull never --network none --read-only --tmpfs /tmp \
  --user 1000:1000 \
  --mount "type=bind,source=$SNAP,target=/snapshot.db,readonly" \
  --env OC_DB_PATH=/tmp/preflight.db --env OC_CONFIG_DIR=/tmp/config \
  --env OC_EMBEDDING_PROVIDER=none \
  --entrypoint sh "$NEW_IMAGE_ID" -c \
  'cp /snapshot.db /tmp/preflight.db && mkdir /tmp/config && oc db info' 2>&1)
RC=$?
set -e
echo "$PRE"
[ $RC = 0 ] || fail "pre-flight exited $RC"
grep -q 'Integrity: ok' <<<"$PRE" || fail "pre-flight integrity"
pass "pre-flight exits 0 with Integrity: ok"

phase "4. Image pair: v3.7.0 serves the copy, then the candidate migrates it"
seed_volume "$VOL_A"
OLD_A="oc-$RUN-old"
start_oc "$OLD_A" "$OLD_IMAGE" "$VOL_A" unless-stopped
wait_healthy "$OLD_A" || fail "old image did not become healthy"
S=$(inspect_live "$OLD_A"); echo "old image serving: $S"
[ "$(jget schema <<<"$S")" = 4 ] || fail "old image changed the schema"
docker stop --time 60 "$OLD_A" >/dev/null
# Remove it, so nothing (restart policy, daemon restart) can bring it back
# onto the volume the candidate is about to migrate.
docker rm "$OLD_A" >/dev/null
users_of "$VOL_A"
NEW_A="oc-$RUN-new"
T0=$(date +%s)
start_oc "$NEW_A" "$NEW_IMAGE_ID" "$VOL_A" unless-stopped
wait_healthy "$NEW_A" || fail "new image did not become healthy"
echo "boot plus migration: $(( $(date +%s) - T0 )) s"
docker logs "$NEW_A" 2>&1 | grep -E 'Applying migration 005|Migrations applied' || fail "no migration lines in the log"
M=$(inspect_live "$NEW_A"); echo "new image serving: $M"
[ "$(jget schema <<<"$M")" = 5 ] || fail "schema is not 5"
[ "$(jget non_utc <<<"$M")" = 0 ] || fail "non-UTC values remain"
[ "$(jget integrity <<<"$M")" = ok ] || fail "integrity after 005"
same_counts "$BASE" "$M" || fail "counts changed in migration"
pass "005 applied on boot: schema 5, 0 non-UTC, integrity ok, counts unchanged"

phase "5. Refusal: a naive value stops the candidate and changes nothing"
seed_volume "$VOL_B"
docker run --rm --pull never --network none --user 1000:1000 \
  --mount "type=volume,source=$VOL_B,target=/data" \
  --entrypoint python "$OLD_IMAGE" -c '
import sqlite3
c = sqlite3.connect("/data/openchronicle.db")
rid = c.execute("SELECT id FROM memory_items ORDER BY id LIMIT 1").fetchone()[0]
c.execute("UPDATE memory_items SET created_at = substr(created_at, 1, 19) WHERE id = ?", (rid,))
c.commit()
c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
print("planted naive created_at on", rid)'
B0=$(inspect_vol "$VOL_B"); echo "before: $B0"
[ "$(jget naive <<<"$B0")" = 1 ] || fail "plant did not take"
NEW_B="oc-$RUN-refuse"
start_oc "$NEW_B" "$NEW_IMAGE_ID" "$VOL_B" no
EXIT=$(timeout 120 docker wait "$NEW_B") || fail "candidate did not exit on the naive value"
echo "candidate exit code: $EXIT"
[ "$EXIT" != 0 ] || fail "candidate exited 0"
docker logs "$NEW_B" 2>&1 | grep -E 'Cannot start: Migration 005_normalize_timestamps.sql failed' || fail "no refusal message"
B1=$(inspect_vol "$VOL_B"); echo "after: $B1"
[ "$B0" = "$B1" ] || fail "the refused boot changed the database"
OLD_B="oc-$RUN-tagback"
start_oc "$OLD_B" "$OLD_IMAGE" "$VOL_B" unless-stopped
wait_healthy "$OLD_B" || fail "old image did not serve the refused volume"
pass "refused at boot with the database unchanged (schema 4); v3.7.0 serves it again"

phase "6. Ordered rollback after 005 (the production order)"
OLD_RESTART_POLICY=$(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$NEW_A")
echo "OLD_RESTART_POLICY=$OLD_RESTART_POLICY"
docker update --restart=no "$NEW_A" >/dev/null
[ "$(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$NEW_A")" = no ] || fail "restart policy"
state_of() { docker inspect -f 'running={{.State.Running}} status={{.State.Status}} restarting={{.State.Restarting}} restarts={{.RestartCount}} started={{.State.StartedAt}} finished={{.State.FinishedAt}} exit={{.State.ExitCode}} policy={{.HostConfig.RestartPolicy.Name}}' "$1"; }
echo "before stop: $(state_of "$NEW_A")"
T0=$(date +%s)
echo "docker stop said: $(docker stop --time 60 "$NEW_A" 2>&1); exit $?; $(( $(date +%s) - T0 )) s"
for _ in $(seq 1 35); do
  [ "$(docker inspect -f '{{.State.Running}}' "$NEW_A")" = false ] && break
  sleep 2
done
echo "after stop:  $(state_of "$NEW_A")"
docker logs --tail 15 "$NEW_A" 2>&1 | sed 's/^/  log: /'
[ "$(docker inspect -f '{{.State.Running}}' "$NEW_A")" = false ] || fail "docker stop left $NEW_A running (see the state lines above)"
users_of "$VOL_A"
# The production host-source stage block: the snapshot bind-mounted read-only.
stage() {
  docker run --rm --pull never --network none --read-only --tmpfs /tmp \
    --user 1000:1000 --mount "type=volume,source=$VOL_A,target=/data" \
    --mount "type=bind,source=$SNAP,target=/import/snapshot.db,readonly" \
    --entrypoint python --env OC_OFFLINE_RESTORE=1 "$OLD_IMAGE" \
    /app/scripts/offline_restore.py stage --db /data/openchronicle.db \
    --source /import/snapshot.db --expected-sha256 "$SNAP_SHA" "$@"
}
stage >/dev/null
STAGED=$(stage --apply); echo "$STAGED"
STAGE_PATH=$(jget stage_path <<<"$STAGED")
EXP_SHA=$(jget candidate.sha256 <<<"$STAGED")
EXP_SCHEMA=$(jget candidate.schema_version <<<"$STAGED")
EXP_PROJECT=$(jget candidate.project_identity_sha256 <<<"$STAGED")
[ "$EXP_SCHEMA" = 4 ] || fail "staged candidate is not schema 4"
OP="restore-$(echo "$RUN" | tr 'A-Z' 'a-z')"
offline activate --db /data/openchronicle.db --operation-id "$OP" \
  --candidate "$STAGE_PATH" --expected-sha256 "$EXP_SHA" \
  --expected-schema 4 --expected-project-sha256 "$EXP_PROJECT" >/dev/null
offline activate --db /data/openchronicle.db --operation-id "$OP" \
  --candidate "$STAGE_PATH" --expected-sha256 "$EXP_SHA" \
  --expected-schema 4 --expected-project-sha256 "$EXP_PROJECT" --apply >/dev/null
STATUS=$(offline status --db /data/openchronicle.db --operation-id "$OP"); echo "$STATUS"
[ "$(jget state.phase <<<"$STATUS")" = activated ] || fail "phase is not activated"
[ "$(jget state.write_probe <<<"$STATUS")" = ok ] || fail "write_probe is not ok"
offline retire-stage --db /data/openchronicle.db --operation-id "$OP" --apply >/dev/null
# "Move OC_TAG": the previous image on the restored volume, never the stopped candidate.
OLD_A2="oc-$RUN-rolledback"
start_oc "$OLD_A2" "$OLD_IMAGE" "$VOL_A" no
wait_healthy "$OLD_A2" || fail "old image did not serve the restored volume"
R=$(inspect_live "$OLD_A2"); echo "after rollback: $R"
[ "$(jget schema <<<"$R")" = 4 ] || fail "restored schema is not 4"
[ "$(jget non_utc <<<"$R")" = "$(jget non_utc <<<"$BASE")" ] || fail "restored timestamps differ from the snapshot"
same_counts "$BASE" "$R" || fail "restored counts differ from the snapshot"
docker update --restart="$OLD_RESTART_POLICY" "$OLD_A2" >/dev/null
[ "$(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$OLD_A2")" = "$OLD_RESTART_POLICY" ] || fail "restart policy not restored"
pass "rolled back to the pre-005 snapshot: schema 4, counts and timestamps match; policy back to $OLD_RESTART_POLICY"

phase "7. Result"
pass "TS-03 rehearsal complete for $NEW_SHA against $(basename "$SNAP")"
cat <<EOF
Not scripted (do these by hand in Portainer, on the real stack only at deploy time):
  - freeze: no stack edits, webhooks or redeploys between stop and tag move;
  - recreation: moving OC_TAG on a file-based stack recreates the container,
    so the rollback order is stop, stage, activate, then move OC_TAG.
Keep everything above this line as the rehearsal record.
EOF
