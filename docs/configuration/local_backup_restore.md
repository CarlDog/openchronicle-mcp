# Local snapshot export and restore rehearsal

This runbook implements [design 0017](../design/0017-exposed-backup-and-restore.md).
It is a source plan until the detached production stack has been deliberately
updated and an actual NAS restore drill has passed. It precedes the timestamp
migration. A green PR alone is not a recoverable production backup. `/exports`
is on the **same NAS** as the live volume; keep a verified copy on a separate
device before changing the stack and again immediately before migration.

The commands below are a guarded operator procedure, **not evidence of a NAS
drill**. Run them on a disposable clone and independently review the recorded
results before any production restore or timestamp migration. Every example
uses NAS Bash, an explicit container/image/volume identity, and a separate
helper process. Do not paste a command with placeholder values into the NAS.

## Prepare the NAS mount

Create `/volume1/docker/openchronicle/exports/backups` on the host, owned or
writable by container uid 1000, with operator-only SMB access. The repository
compose binds `/volume1/docker/openchronicle/exports` to `/exports` with host
path autocreation disabled, and sets `OC_BACKUP_DIR=/exports/backups`. On the
desktop, inspect `\\carldog-nas\docker\openchronicle\exports\backups`.
This is a snapshot export directory; the live database stays in `oc-data` at
`/data/openchronicle.db`. Existing snapshots in that volume remain untouched.

Stack 151 is detached from Git. Review its stored compose and the proposed
bind mount before changing it; a Git push or tag does not update the stack's
mounts. Confirm free capacity for at least one current snapshot plus a
restore-stage copy, filesystem permissions for uid 1000, and restricted SMB
ACLs. A configured missing or unwritable `OC_BACKUP_DIR` logs an ERROR at
startup and fails every catalog backup; it never writes into the named volume
or the container layer instead. The service keeps running, so check the
startup log and the `db_backup` job status after any mount change.

Before that stack edit, record the old compose, environment (without
publishing secrets), image ID, database schema, project-ID fingerprint, row
counts and selected memory IDs. The currently exposed SMB share contains
neither the live DB nor old backups. An approved NAS Docker admin/console path
is required. The Portainer MCP surface cannot exec or copy container files;
the SMB share alone does not close this prerequisite.

### Bootstrap a pre-change copy from v3.3.0

Find the production `oc` container with `docker ps --format
'{{.ID}} {{.Names}} {{.Label "com.docker.compose.project"}}
{{.Label "com.docker.compose.service"}}'`, compare the project and service
labels with the recorded Portainer stack, and set `CID` to that **observed**
container ID. In NAS Bash, run these guarded commands before editing the
stack. Preserve their non-secret output in the deployment record:

```bash
set -euo pipefail
CID='<observed production oc container ID>'
EXPECTED_STACK_PROJECT='<observed compose project label for this Portainer stack>'
test -n "$CID" && test -n "$EXPECTED_STACK_PROJECT"
docker inspect "$CID" >/dev/null
test "$(docker inspect -f '{{.State.Running}}' "$CID")" = true
test "$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$CID")" = oc
test "$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$CID")" = "$EXPECTED_STACK_PROJECT"
docker exec --user 1000:1000 "$CID" python -c 'import os; assert os.environ["OC_DB_PATH"] == "/data/openchronicle.db"'
MOUNT=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Type}}|{{.Name}}|{{.RW}}{{end}}{{end}}' "$CID")
IFS='|' read -r MOUNT_TYPE VOL MOUNT_RW <<< "$MOUNT"
test "$MOUNT_TYPE" = volume && test "$MOUNT_RW" = true && test -n "$VOL"
docker volume inspect "$VOL" >/dev/null
OLD_IMAGE_ID=$(docker inspect -f '{{.Image}}' "$CID")
docker image inspect "$OLD_IMAGE_ID" >/dev/null
docker exec "$CID" cat /app/build-revision
LIVE_BYTES=$(docker exec --user 1000:1000 "$CID" python -c '
import os
base="/data/openchronicle.db"
print(sum(os.path.getsize(path) for path in (base,base+"-wal",base+"-shm") if os.path.isfile(path)))')
VOL_FREE_BYTES=$(docker exec --user 1000:1000 "$CID" python -c 'import shutil; print(shutil.disk_usage("/data").free)')
HOST_FREE_KB=$(df -Pk /volume1/docker/openchronicle | awk 'NR==2 {print $4}')
[[ "$LIVE_BYTES" =~ ^[0-9]+$ ]] && test "$LIVE_BYTES" -gt 0
[[ "$VOL_FREE_BYTES" =~ ^[0-9]+$ ]] && [[ "$HOST_FREE_KB" =~ ^[0-9]+$ ]]
NEEDED=$((3 * LIVE_BYTES + 64 * 1024 * 1024))
test "$VOL_FREE_BYTES" -ge "$NEEDED"
test "$((HOST_FREE_KB * 1024))" -ge "$NEEDED"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
SNAP="/data/backups/manual/pre-change-$STAMP.db"
docker exec --user 1000:1000 "$CID" oc db backup "$SNAP"
docker exec --user 1000:1000 "$CID" sha256sum "$SNAP"
umask 077
mkdir -p /volume1/docker/openchronicle/exports/bootstrap
chmod 0700 /volume1/docker/openchronicle/exports/bootstrap
HOST_COPY="/volume1/docker/openchronicle/exports/bootstrap/pre-change-$STAMP.db"
docker cp "$CID:$SNAP" "$HOST_COPY"
sha256sum "$HOST_COPY"
docker run --rm --pull never --network none --read-only \
  --mount "type=bind,source=$HOST_COPY,target=/snapshot.db,readonly" \
  --entrypoint python "$OLD_IMAGE_ID" -c '
import hashlib, json, sqlite3
c = sqlite3.connect("file:/snapshot.db?mode=ro&immutable=1", uri=True)
assert c.execute("PRAGMA integrity_check").fetchone() == ("ok",)
assert c.execute("PRAGMA foreign_key_check").fetchone() is None
ids = [str(row[0]) for row in c.execute("SELECT id FROM projects ORDER BY id")]
print(json.dumps({"schema": c.execute("SELECT MAX(version) FROM schema_version").fetchone()[0],
                  "project_identity_sha256": hashlib.sha256("\n".join(ids).encode()).hexdigest(),
                  "project_count": len(ids),
                  "memory_count": c.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0],
                  "embedding_count": c.execute("SELECT COUNT(*) FROM memory_embeddings").fetchone()[0]}))
c.close()'
```

The two NAS digests must match, and the read-only verifier must exit zero.
Compare its schema, project fingerprint and counts with the separately
recorded inventory; verify selected memory IDs on a disposable instance.
Before the workstation copy, confirm the SMB operator can traverse and read
`exports/bootstrap` and that other principals cannot. If mode `0700` blocks
the intended identity, adjust ownership or the NAS ACL narrowly; never make
the plaintext snapshot world-readable.
From the operator workstation, copy the SMB-visible artifact to an
**independent device** using PowerShell, substituting an actual local or
offsite destination for `DEST`:

```powershell
$source = '\\carldog-nas\docker\openchronicle\exports\bootstrap\pre-change-<STAMP>.db'
$dest = '<absolute path on a device independent of the NAS>'
Copy-Item -LiteralPath $source -Destination $dest -ErrorAction Stop
$sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash
$destHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $dest).Hash
if ($sourceHash -ne $destHash) { throw 'Independent copy hash mismatch' }
```

Compare the hash with the two NAS digests and open the independent copy
read-only for the same checks. Record its verified location and custody before
any stack change; an SMB path on the NAS is **not** an independent device.
Never
`docker cp` the live `/data/openchronicle.db`: committed writes may still be
in the WAL. Retain the old image ID, old compose and the independent copy. If
any check fails, stop the rollout; the backup feature itself needs a recovery
point.

## Enable and use the MCP surface

Scheduled backups need `OC_BACKUP_DIR` but do not need MCP auth. The five MCP
tools remain absent until `OC_BACKUP_MCP_ENABLED=true` and a nonempty effective
`OC_API_KEY` are set. Migrate every client to bearer auth before enabling the
tools. The stdio server never registers them. Do not place the API key in a
tracked file or a backup manifest.

Use `db_backup_create` for a manual recovery point. Record its artifact ID,
size, schema version, row counts and SHA-256. Use `db_backup_list` to find
completed artifacts and `db_backup_verify` before any reliance on one. A
manual snapshot is never subject to automatic pruning. `db_restore_plan`
compares the candidate with the current store and makes no change.
`db_restore_stage` copies and re-verifies the candidate under
`/data/.restore-stage`; it returns `restored: false`. A second stage is
rejected until the previous one is handled offline.

## Disposable restore drill

1. Create and verify a fresh manual artifact. Read the `.db` file through the
   exposed SMB share, retain it on a device outside the NAS, and calculate its
   SHA-256 there; compare it with the manifest and MCP verification result.
   Preserve both the export and independent copy.
2. Copy the artifact into a **separate disposable database location**, never
   over `/data/openchronicle.db`. Open the copy with SQLite and run
   `PRAGMA integrity_check` and `PRAGMA foreign_key_check`; compare schema
   version, project IDs, memory and embedding counts with the manifest. Start
   a disposable OpenChronicle instance using the pinned release image against
   that copy and check representative ID reads and search. Record any schema
   change caused by startup.
3. Run `db_restore_plan` and `db_restore_stage` for the same artifact. Inspect
   the staged file's digest and integrity on the DB volume. Record the drill's
   duration and the serving process's request-tail latency while the backup
   was made. A failed digest, missing data, unacceptable latency, or broad
   share ACL blocks the timestamp upgrade.
4. On a disposable clone, stop the serving container **before** making a
   post-snapshot write with a separate WAL writer that disables auto-checkpoint
   and exits abruptly. Confirm a nonempty `openchronicle.db-wal` immediately
   before activation: a later graceful stop could checkpoint it away. Rehearse the
   exact commands below, including rollback that recovers the post-snapshot
   write. Repeat with an intentionally aborted activation. Do not crash the
   production writer for this drill. Record elapsed recovery time and all
   identity, integrity and request checks.

To prepare that clone on the NAS after the feature image is published, use a
verified copy of the bootstrap snapshot and a **new named volume**. The volume
name and container labels below are deliberately distinct from production.
This seeds only disposable storage; retain the external copy unchanged. Use
the exact pinned image ID planned for this drill, with embedding and
maintenance disabled, and inspect any startup schema migration before
creating the candidate:

```bash
set -euo pipefail
HOST_COPY='<absolute NAS path to the verified bootstrap snapshot>'
DRILL_IMAGE_ID='<verified release image ID containing offline_restore.py>'
test -f "$HOST_COPY"
docker image inspect "$DRILL_IMAGE_ID" >/dev/null
DRILL_SUFFIX=$(date -u +%Y%m%dT%H%M%SZ)
DRILL_VOL="oc-restore-drill-$DRILL_SUFFIX"
DRILL_NAME="oc-restore-drill-$DRILL_SUFFIX"
docker volume create "$DRILL_VOL" >/dev/null
docker run --rm --pull never --network none --read-only \
  --mount "type=volume,source=$DRILL_VOL,target=/data" \
  --mount "type=bind,source=$HOST_COPY,target=/snapshot.db,readonly" \
  --entrypoint sh "$DRILL_IMAGE_ID" -c \
  'cp /snapshot.db /data/openchronicle.db && chown 1000:1000 /data /data/openchronicle.db'
docker run -d --pull never --name "$DRILL_NAME" --network none \
  --label com.docker.compose.project=oc-restore-drill \
  --label com.docker.compose.service=oc \
  --mount "type=volume,source=$DRILL_VOL,target=/data" \
  --env OC_DB_PATH=/data/openchronicle.db \
  --env OC_EMBEDDING_PROVIDER=none --env OC_MAINTENANCE_DISABLED=1 \
  "$DRILL_IMAGE_ID" >/dev/null
for attempt in {1..30}; do
  HEALTH=$(docker inspect -f '{{.State.Health.Status}}' "$DRILL_NAME")
  if [ "$HEALTH" = healthy ]; then break; fi
  sleep 2
done
test "$HEALTH" = healthy
STAGE=/data/.restore-stage/candidate-aaaaaaaaaaaaaaaaaaaaaaaa.db
docker exec --user 1000:1000 "$DRILL_NAME" oc db backup "$STAGE"
META=$(docker run --rm --pull never --network none --read-only --user 1000:1000 \
  --mount "type=volume,source=$DRILL_VOL,target=/data" \
  --entrypoint python "$DRILL_IMAGE_ID" -c '
from pathlib import Path
from scripts.offline_restore import _inspect
m = _inspect(Path("/data/.restore-stage/candidate-aaaaaaaaaaaaaaaaaaaaaaaa.db"))
print(m["sha256"], m["schema_version"], m["project_identity_sha256"])')
read -r EXPECTED_SHA EXPECTED_SCHEMA EXPECTED_PROJECT <<< "$META"
docker stop --time 60 "$DRILL_NAME"
test "$(docker inspect -f '{{.State.Running}}' "$DRILL_NAME")" = false
docker run --rm --pull never --network none --user 1000:1000 \
  --mount "type=volume,source=$DRILL_VOL,target=/data" \
  --entrypoint python "$DRILL_IMAGE_ID" -c '
import os, sqlite3
c = sqlite3.connect("/data/openchronicle.db")
c.execute("PRAGMA journal_mode=WAL")
c.execute("PRAGMA wal_autocheckpoint=0")
c.execute("CREATE TABLE restore_drill_marker (value TEXT NOT NULL)")
c.execute("INSERT INTO restore_drill_marker VALUES (?)", ("post-snapshot-write",))
c.commit()
os._exit(0)'
docker run --rm --pull never --network none --read-only --user 1000:1000 \
  --mount "type=volume,source=$DRILL_VOL,target=/data" \
  --entrypoint sh "$DRILL_IMAGE_ID" -c 'test -s /data/openchronicle.db-wal'
```

Use `CID=$(docker inspect -f '{{.Id}}' "$DRILL_NAME")`, `VOL=$DRILL_VOL`,
`SERVING_IMAGE_ID=$DRILL_IMAGE_ID`, `HELPER_IMAGE_ID=$DRILL_IMAGE_ID`,
`EXPECTED_STACK_PROJECT=oc-restore-drill`, the `STAGE` and three `EXPECTED_*`
values above, plus a unique `OP`, in the activation block below. The helper's
dry-run and apply must finish with `phase=activated`; after the candidate
starts, the marker table should be absent. Run the rollback block against the
same disposable container/volume, restart the recorded image, and query
`SELECT value FROM restore_drill_marker` to prove the post-snapshot write
survived. The exact readback after restart is:

```bash
docker exec --user 1000:1000 "$DRILL_NAME" python -c '
import sqlite3
c = sqlite3.connect("file:/data/openchronicle.db?mode=ro", uri=True)
assert c.execute("SELECT value FROM restore_drill_marker").fetchone() == ("post-snapshot-write",)
c.close()'
```

Repeat the clone setup on a **new disposable volume** for the
aborted-activation leg. After the same stop, separate WAL write and
nonempty-WAL check, set `VOL` to that drill volume, `OP` to a new operation ID,
and run the activation block through its dry-run so the `offline` function is
defined. Use this deterministic failure injection instead of the normal apply.
It calls the same activation
function but deliberately fails at the final main-file replacement, after
moving the old sidecars. It has no effect on the production volume:

```bash
[[ "$VOL" == oc-restore-drill-* ]] && test "$VOL" = "$DRILL_VOL"
if docker run --rm --pull never --network none --read-only --tmpfs /tmp \
  --user 1000:1000 --mount "type=volume,source=$VOL,target=/data" \
  --env STAGE="$STAGE" --env OP="$OP" --env EXPECTED_SHA="$EXPECTED_SHA" \
  --env EXPECTED_SCHEMA="$EXPECTED_SCHEMA" --env EXPECTED_PROJECT="$EXPECTED_PROJECT" \
  --entrypoint python "$DRILL_IMAGE_ID" -c '
import os
from pathlib import Path
from scripts import offline_restore as helper
replace = helper.os.replace
def abort_at_swap(source, target):
    if Path(source).name.startswith(".incoming-") and Path(target) == Path("/data/openchronicle.db"):
        raise OSError("intentional disposable activation abort")
    return replace(source, target)
helper.os.replace = abort_at_swap
helper.activate(Path("/data/openchronicle.db"), Path(os.environ["STAGE"]),
                os.environ["OP"], os.environ["EXPECTED_SHA"],
                int(os.environ["EXPECTED_SCHEMA"]), os.environ["EXPECTED_PROJECT"], apply=True)'; then
  echo 'Fault injection did not abort; stop the drill' >&2
  exit 1
fi
STATUS=$(offline status --db /data/openchronicle.db --operation-id "$OP")
[[ "$STATUS" == *'"phase": "prepared"'* ]]
docker run --rm --pull never --network none --read-only --user 1000:1000 \
  --mount "type=volume,source=$VOL,target=/data" \
  --entrypoint sh "$DRILL_IMAGE_ID" -c "test -s /data/.recovery/$OP/raw-old/openchronicle.db-wal"
```

Run the self-contained rollback block below while the
disposable service remains stopped. Restart and run the marker readback.
Preserve logs and elapsed recovery time. The source-level pytest uses the
same WAL and abort shape, but Docker execution and image/volume ownership
still require the NAS drill. This is a same-image recovery drill for the
backup facility. Before the later **timestamp migration**, run a separate
disposable old-image/new-image cutover: start the pre-upgrade database under
the recorded old image, start the candidate under the new image, then restore
the old snapshot and prove it starts under the old image with the original
schema and selected reads. That image-pair evidence is not supplied by this
backup-facility drill and remains a timestamp release gate.

## Offline activation and rollback

Stage and verify the selected artifact while the service is running. Record
the returned absolute `stage_path`, SHA-256, schema version and project-ID
fingerprint, plus the artifact and operation IDs. Retain a verified off-NAS
snapshot. Record the old and candidate image IDs. Prepare enough free space on
the data volume for the old raw DB/WAL/SHM family, a consolidated old snapshot,
an incoming candidate, a forward-state archive, a rollback incoming file and
16 MiB margin. Stop all writers and freeze Portainer or any other reconciler
that could restart them. The helper checks identity and space again; it never
opens the application container or its migration path.

At the time of activation, rediscover the **currently serving** `CID` and
`VOL` with the bootstrap inspection commands; a prior stack edit may have
recreated the container. Record its `SERVING_IMAGE_ID` and assert the data
volume is the expected original volume. Set `HELPER_IMAGE_ID` from the
**published, locally present, exact release image** containing
`/app/scripts/offline_restore.py`;
record its `/app/build-revision` and compare with that release's CI commit.
Set the other values from `db_restore_stage` and the verified manifest, not
from a filename guess. A different image is used for the helper only; it has
no network or secrets mount. Agree a maintenance freeze that prevents
Portainer stack edits, webhooks, scheduled reconciliation and other container
starts for this stack during the swap. Record the Docker restart policy, set it
temporarily to `no`, and restore the intended policy only after runtime
validation. This controls Docker's restart policy but cannot stop a separate
Portainer redeploy; an unexpected volume user is an abort condition. The
serving container remains stopped until activation succeeds.

```bash
set -euo pipefail
CID='<observed currently serving oc container ID>'
VOL='<recorded original data volume name>'
HELPER_IMAGE_ID='<verified image ID containing offline_restore.py>'
SERVING_IMAGE_ID='<recorded currently serving image ID>'
EXPECTED_STACK_PROJECT='<recorded compose project label>'
STAGE='/data/.restore-stage/candidate-<24 hex characters>.db'
EXPECTED_SHA='<64-character digest from verified stage>'
EXPECTED_SCHEMA='<integer schema version from verified artifact>'
EXPECTED_PROJECT='<64-character project-ID digest from verified artifact>'
OP='restore-<unique lowercase operation ID>'
test -n "$CID" && test -n "$VOL" && test -n "$EXPECTED_STACK_PROJECT"
docker inspect "$CID" >/dev/null
docker image inspect "$HELPER_IMAGE_ID" >/dev/null
docker run --rm --pull never --network none --read-only --entrypoint cat "$HELPER_IMAGE_ID" /app/build-revision
test "$(docker inspect -f '{{.Image}}' "$CID")" = "$SERVING_IMAGE_ID"
test "$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$CID")" = oc
test "$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$CID")" = "$EXPECTED_STACK_PROJECT"
test "$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}' "$CID")" = "$VOL"
docker volume inspect "$VOL" >/dev/null
OLD_RESTART_POLICY=$(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$CID")
docker update --restart=no "$CID" >/dev/null
test "$(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$CID")" = no
if [ "$(docker inspect -f '{{.State.Running}}' "$CID")" = true ]; then
  docker stop --time 60 "$CID"
fi
test "$(docker inspect -f '{{.State.Running}}' "$CID")" = false
USERS=$(docker ps -q --filter "volume=$VOL")
test -z "$USERS"
offline() {
  docker run --rm --pull never --network none --read-only --tmpfs /tmp \
    --user 1000:1000 --mount "type=volume,source=$VOL,target=/data" \
    --entrypoint python --env OC_OFFLINE_RESTORE=1 "$HELPER_IMAGE_ID" \
    /app/scripts/offline_restore.py "$@"
}
offline activate --db /data/openchronicle.db --operation-id "$OP" \
  --candidate "$STAGE" --expected-sha256 "$EXPECTED_SHA" \
  --expected-schema "$EXPECTED_SCHEMA" --expected-project-sha256 "$EXPECTED_PROJECT"
```

The first block stops the service and runs a **dry-run only**. For normal
activation, continue with this separate apply block in the same frozen
maintenance session. For the aborted disposable drill, use the guarded fault
injection above instead; never run this normal apply block for that leg.

```bash
test "$(docker inspect -f '{{.State.Running}}' "$CID")" = false
USERS=$(docker ps -q --filter "volume=$VOL")
test -z "$USERS"
offline activate --db /data/openchronicle.db --operation-id "$OP" \
  --candidate "$STAGE" --expected-sha256 "$EXPECTED_SHA" \
  --expected-schema "$EXPECTED_SCHEMA" --expected-project-sha256 "$EXPECTED_PROJECT" --apply
offline status --db /data/openchronicle.db --operation-id "$OP"
USERS=$(docker ps -q --filter "volume=$VOL")
test -z "$USERS"
```

Keep the service stopped if either call fails or
the `state.json` phase is not `activated`. The helper keeps the original raw
DB/WAL/SHM in `/data/.recovery/$OP/raw-old`, and a separately verified,
consolidated `old-consistent.db` for rollback. It copies the candidate on the
same volume, moves old sidecars away, then atomically replaces the main DB.
Never copy an external file directly over the live DB. Start the **recorded
matching image** through the reviewed Portainer stack procedure; for a
same-image drill or recovery using the original stopped container, use
`docker start "$CID"`. Check health/build SHA, SQLite integrity and foreign
keys, schema, project IDs, memory/embedding counts, selected memory reads and
search. After any Portainer recreation, rediscover the new container and
verify its `/data` mount name still equals the recorded `VOL` before accepting
its health or data results. Compare request tail latency under the intended
load. Do not retire
the old state or off-NAS copy on a successful startup alone. If the original
container continues to serve, restore its recorded restart policy with
`docker update --restart="$OLD_RESTART_POLICY" "$CID"` **after** validation;
if Portainer created a new container, verify its policy against the reviewed
stack configuration instead.

For rollback, use a **new NAS Bash session** if necessary. Rediscover the
currently serving candidate container, or the stopped container after an
aborted activation, and re-enter the recorded IDs. This block does not depend
on the activation shell. Stop every writer and freeze Portainer changes again;
retain the candidate image and its state. Do not run rollback if a new volume
user appears.

```bash
set -euo pipefail
CID='<observed current or stopped candidate container ID>'
VOL='<recorded original data volume name>'
HELPER_IMAGE_ID='<recorded helper image ID>'
EXPECTED_STACK_PROJECT='<recorded compose project label>'
OP='<recorded operation ID>'
test -n "$CID" && test -n "$VOL" && test -n "$EXPECTED_STACK_PROJECT"
docker inspect "$CID" >/dev/null
test "$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$CID")" = oc
test "$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$CID")" = "$EXPECTED_STACK_PROJECT"
test "$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}' "$CID")" = "$VOL"
docker volume inspect "$VOL" >/dev/null
docker image inspect "$HELPER_IMAGE_ID" >/dev/null
docker run --rm --pull never --network none --read-only --entrypoint cat "$HELPER_IMAGE_ID" /app/build-revision
ROLLBACK_RESTART_POLICY=$(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$CID")
docker update --restart=no "$CID" >/dev/null
if [ "$(docker inspect -f '{{.State.Running}}' "$CID")" = true ]; then
  docker stop --time 60 "$CID"
fi
test "$(docker inspect -f '{{.State.Running}}' "$CID")" = false
offline() {
  docker run --rm --pull never --network none --read-only --tmpfs /tmp \
    --user 1000:1000 --mount "type=volume,source=$VOL,target=/data" \
    --entrypoint python --env OC_OFFLINE_RESTORE=1 "$HELPER_IMAGE_ID" \
    /app/scripts/offline_restore.py "$@"
}
USERS=$(docker ps -q --filter "volume=$VOL")
test -z "$USERS"
offline rollback --db /data/openchronicle.db --operation-id "$OP"
USERS=$(docker ps -q --filter "volume=$VOL")
test -z "$USERS"
offline rollback --db /data/openchronicle.db --operation-id "$OP" --apply
offline status --db /data/openchronicle.db --operation-id "$OP"
USERS=$(docker ps -q --filter "volume=$VOL")
test -z "$USERS"
```

The rollback dry-run verifies the consolidated old snapshot. The apply step
archives the forward DB family before replacement and writes phase
`rolled_back`. If it is interrupted, leave all services stopped. A retry is
allowed only when the forward archive and checksums are complete; a partial
archive fails closed and requires inspected manual recovery. Restore the
recorded **old** stack image/configuration before restarting; `docker start
"$CID"` is appropriate only when that original old-image container still
exists. Recheck the same data and runtime indicators, including the
post-snapshot WAL write in a drill. Never let a new image remigrate a rolled
back database. Restore the verified old-image container's intended restart
policy only after its data and build identity pass. If a new container was
created, check its policy against the reviewed old stack definition.

Only after independently accepting the restored state, retire the staged
candidate so a later `db_restore_stage` can run. Keep the exported backup and
recovery directory; this removes only the verified staged copy. This is a
separate bounded stop/start operation and works from a new NAS Bash session:

```bash
set -euo pipefail
CID='<observed currently serving accepted container ID>'
VOL='<recorded original data volume name>'
HELPER_IMAGE_ID='<recorded helper image ID>'
EXPECTED_STACK_PROJECT='<recorded compose project label>'
OP='<recorded operation ID>'
test -n "$CID" && test -n "$VOL" && test -n "$EXPECTED_STACK_PROJECT"
docker inspect "$CID" >/dev/null
test "$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$CID")" = oc
test "$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$CID")" = "$EXPECTED_STACK_PROJECT"
test "$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}' "$CID")" = "$VOL"
docker volume inspect "$VOL" >/dev/null
docker image inspect "$HELPER_IMAGE_ID" >/dev/null
RETIRE_RESTART_POLICY=$(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$CID")
docker update --restart=no "$CID" >/dev/null
docker stop --time 60 "$CID"
test "$(docker inspect -f '{{.State.Running}}' "$CID")" = false
USERS=$(docker ps -q --filter "volume=$VOL")
test -z "$USERS"
offline() {
  docker run --rm --pull never --network none --read-only --tmpfs /tmp \
    --user 1000:1000 --mount "type=volume,source=$VOL,target=/data" \
    --entrypoint python --env OC_OFFLINE_RESTORE=1 "$HELPER_IMAGE_ID" \
    /app/scripts/offline_restore.py "$@"
}
offline retire-stage --db /data/openchronicle.db --operation-id "$OP"
USERS=$(docker ps -q --filter "volume=$VOL")
test -z "$USERS"
offline retire-stage --db /data/openchronicle.db --operation-id "$OP" --apply
offline status --db /data/openchronicle.db --operation-id "$OP"
USERS=$(docker ps -q --filter "volume=$VOL")
test -z "$USERS"
```

Confirm `stage_retirement: done`, then restart the recorded accepted image
and restore its intended restart policy after health, schema and data checks.
An interrupted retirement is retryable. Do not delete a staged file by hand
or retire it while activation is incomplete.

## Production recovery boundary

There is no live MCP restore-execute tool. For an actual recovery, first
quiesce writes. If the running store is healthy enough, take and verify a
separate pre-restore snapshot **before** stopping it; also retain an off-NAS
copy. If the store is damaged, use a previously verified artifact instead of
making a fresh snapshot a blocker. Stop every writer and the service. Identify
the exact staged file and live DB path; ensure both are on the same filesystem.
Keep the live database and its `-wal`/`-shm` files together as rollback state;
never place a candidate beside old sidecars. Restart only after the file,
ownership, image digest and schema expectation have been independently checked.
Then verify health/build identity, integrity, foreign keys, counts,
representative IDs and search. Retain the old database, sidecars and off-NAS
copy until acceptance.

The helper's file operations passed local disposable SQLite tests, including
committed WAL data and interrupted swaps. **The Docker invocation, complete NAS
procedure and off-device handoff have not been rehearsed and remain release
gates.** Keep both image IDs available: the wrong
image may migrate a restored database on startup. `db_restore_stage` does not
establish that recovery succeeded. Do not run the timestamp migration until
the NAS drill and a fresh independently retained pre-upgrade snapshot pass.
