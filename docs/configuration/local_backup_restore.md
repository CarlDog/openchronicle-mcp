# Local snapshot export and restore rehearsal

This runbook implements [design 0017](../design/0017-exposed-backup-and-restore.md).
It is a source plan until the detached production stack has been deliberately
updated and an actual NAS restore drill has passed. It precedes the timestamp
migration. A green PR alone is not a recoverable production backup.

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
   exposed SMB share and calculate its SHA-256 independently; compare it with
   the manifest and MCP verification result. Preserve this artifact.
2. Copy the artifact into a **separate disposable database location**, never
   over `/data/openchronicle.db`. Open the copy with SQLite and run
   `PRAGMA integrity_check`; compare schema version, project IDs, memory and
   embedding counts with the manifest. Start a disposable OpenChronicle
   instance against that copy and check representative ID reads and search.
3. Run `db_restore_plan` and `db_restore_stage` for the same artifact. Inspect
   the staged file's digest and integrity on the DB volume. Record the drill's
   duration and the serving process's request-tail latency while the backup
   was made. A failed digest, missing data, unacceptable latency, or broad
   share ACL blocks the timestamp upgrade.

## Production recovery boundary

There is no live MCP restore-execute tool. For an actual recovery, first stop
all writers and the OpenChronicle service. Take and verify a separate
pre-restore snapshot while the store is still healthy. Identify the exact
staged file and live DB path; ensure both are on the same filesystem. With the
service stopped, handle the live `-wal` and `-shm` sidecars as a unit with the
old database, retain the old database for rollback, and activate the verified
staged file. Do not leave old sidecars beside the replacement. Restart only
after the file and ownership have been independently checked. Then verify
health/build identity, integrity, schema, counts, representative IDs and
search; retain the old database and manual snapshot until acceptance.

The exact offline activation command and rollback sequence require a separate
review and production drill before use. `db_restore_stage` does not establish
that recovery succeeded. Do not run the timestamp migration until this
boundary is closed with evidence.
