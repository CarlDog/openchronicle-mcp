# Local snapshot export and restore rehearsal

This runbook implements [design 0017](../design/0017-exposed-backup-and-restore.md).
It is a source plan until the detached production stack has been deliberately
updated and an actual NAS restore drill has passed. It precedes the timestamp
migration. A green PR alone is not a recoverable production backup. `/exports`
is on the **same NAS** as the live volume; keep a verified copy on a separate
device before changing the stack and again immediately before migration.

This document is not yet an executable production restore procedure. The
offline activation commands, ownership checks and rollback must be frozen,
reviewed and rehearsed on disposable copies before they can be used live.

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
ACLs. A configured missing or unwritable `OC_BACKUP_DIR` fails startup rather
than writing into the named volume by accident.

Before that stack edit, record the old compose, environment, image digest,
database schema, project-ID fingerprint, row counts and selected memory IDs.
The currently exposed SMB share contains neither the live DB nor old backups.
Obtain an approved NAS Docker admin/console path first. With the running
v3.3.0 container, use its existing `oc db backup <destination>` command to
make a consistent snapshot **inside an accessible container volume**, then
extract that artifact with Docker's copy facility and move it to a different
device. Do not `docker cp` the live `/data/openchronicle.db` file: its committed data may
still be in the WAL. Discover and record the actual container ID and artifact
path rather than assuming them from this runbook. Hash and open the extracted
snapshot, run both SQLite integrity and foreign-key checks, and compare its
schema/IDs/counts with the preflight inventory. Preserve the old image and
recovery copy until the new facility is accepted. If this baseline copy cannot
be made or opened, stop the rollout; installing the backup feature is itself
a change that needs a recovery point. The Portainer MCP surface currently
offers stack inspection and changes, but no container exec/copy operation; the
SMB share alone does not close this prerequisite.

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
4. On a disposable clone with committed writes still in its WAL, rehearse the
   reviewed **offline activation and rollback** procedure, including stop,
   preserving the old DB and sidecars together, same-volume replacement,
   restart with the correct image, verification, then rollback. Make a write
   after the candidate snapshot and prove that rollback recovers it. Repeat
   once with an intentionally aborted activation. A successful open of a copy
   or a staged file does not substitute for this drill.

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

The exact offline activation command and rollback sequence require a separate
review and the disposable drills above before use. Keep both the pre-upgrade
and candidate image digests available: the wrong image may migrate a restored
database on startup. `db_restore_stage` does not establish that recovery
succeeded. Do not run the timestamp migration until this boundary is closed
with evidence and a fresh independently retained pre-upgrade snapshot.
