# 0017 — Exposed local backups and guarded restore preparation

**Status:** Operator-requested implementation plan; source/PR and production
acceptance tracked separately · **Date:** 2026-09-23 · **Precedes:** design
0016 track 2, the timestamp migration.

## Problem and decision

The live database and automatic snapshots occupy the `oc-data` Docker named
volume at `/data`; the operator-accessible `\\carldog-nas\docker\openchronicle`
share exposes `assets`, `config`, `output`, and `plugins`, but none of those
contains the database. The MCP inventory can describe timestamp values but
cannot provide an immutable raw SQLite copy for a migration rehearsal.

Keep the live database in its named volume. Add a dedicated host directory,
`/volume1/docker/openchronicle/exports`, bind-mounted at `/exports`.
Set `OC_BACKUP_DIR=/exports/backups` so the existing online backup engine writes
scheduled and manual snapshots there. The desktop path is
`\\carldog-nas\docker\openchronicle\exports\backups`. Do not mount over
`/data/backups`: that would hide snapshots already in the named volume.
The new path is a **local snapshot export**, not the offsite cloud transport
proposed in design 0001. It does not make the live SQLite file an SMB file.

## Surfaces and trust boundary

`OC_BACKUP_DIR` is optional. When absent, scheduled backups retain their
current location beside the database. When explicitly set, it must be an
absolute, existing, writable directory. A missing or unwritable configured
mount fails clearly; it must not silently fall back into the named volume.
The container runs as uid 1000; prepare the host directory with appropriate
ownership/ACL before deployment. Do not recursively chown the snapshot tree
at every start. Restrict SMB access because local snapshots contain the full
plaintext corpus.

MCP backup tools are **off by default**, and available only on the mounted
HTTP MCP surface when `OC_BACKUP_MCP_ENABLED=true`, `OC_BACKUP_DIR` is
explicitly configured, and the HTTP API has a nonempty effective API key.
An enabled-but-unauthenticated configuration fails startup. Stdio MCP never
registers these tools. Tool inputs are artifact IDs, not paths; the server
chooses destinations inside the configured directory. No tool returns raw
database bytes. The current auth-disabled LAN deployment therefore needs an
authentication/client transition before these MCP tools are enabled; daily
scheduled backups can use the bind mount independently.

| Tool | Effect and result |
|---|---|
| `db_backup_create` | One online SQLite snapshot under `manual/`; returns an artifact ID and metadata. No overwrite or caller path. |
| `db_backup_list` | Lists completed `auto/` and `manual/` snapshots, bounded and newest-first. |
| `db_backup_verify` | Reopens one artifact read-only, checks checksum and SQLite integrity, and reports schema and row counts. |
| `db_restore_plan` | Read-only comparison of a verified artifact with the current database, including schema and counts; explicitly says no restore occurred. |
| `db_restore_stage` | After re-verification, copies the candidate into a private staging directory on the database volume, verifies it again, and returns an ID. Does not replace the live database. |

Snapshots are produced by the existing `sqlite3.Connection.backup()` path,
written to a sibling temporary file, checked and renamed. A sidecar manifest
records SHA-256, schema version, size and creation time; only a complete
artifact pair is offered for restore. Pre-upgrade/manual artifacts are not
subject to automatic retention. Automatic retention keeps its existing
seven-newest-plus-seven-day policy and removes each pruned sidecar together
with its database. A share writer could forge a checksum, so ACLs remain the
security boundary; checksums detect accidental damage, not hostile writers.

The final restore is deliberately **offline**. A serving process has an open
WAL-mode connection; replacing its file from an MCP request risks old WAL/SHM
sidecars and concurrent writes. The operator stops the service, takes and
verifies a pre-restore snapshot, checks the staged candidate on the database
volume, performs the same-filesystem replacement with WAL/SHM handling, then
restarts and independently checks health, schema, counts, search and selected
IDs. Implementing that cutover command is a separately reviewed phase after
the staged workflow is drilled; `db_restore_stage` is not a claim that a
restore happened. Do not use an MCP `confirm=true` as the final authority:
an autonomous client could supply it itself.

## Adversarial review and changes from the first sketch

| Failure attempt | Design response |
|---|---|
| Move the live DB to the exposed share for easy copying. | Rejected: external writes or a raw copy of a WAL-mode file can damage or misrepresent the live store. Export consistent snapshots instead. |
| Mount the share at `/data/backups`. | Rejected: the mount hides prior named-volume backups. Use `/exports` and leave history untouched. |
| Expose `db_restore_execute(confirm=true)` on the normal MCP server. | Rejected: confirmation is self-service, and the live connection remains open. MCP verifies/stages; offline operator action performs cutover. |
| Enable backup tools while LAN MCP auth is disabled. | Fail startup for the explicitly enabled configuration. Stdio registration stays off. Scheduled backups remain independent of MCP auth. |
| Trust a filename or JSON manifest from the share. | Strict generated IDs, fixed root, no arbitrary paths, checksum plus read-only integrity check, and validation again after staging. ACLs still gate hostile modification. |
| Prune the pre-upgrade recovery point during a burst of automatic backups. | Separate `manual/` from `auto/`; automatic retention never touches manual snapshots. |
| Rename a candidate from the share over `/data/openchronicle.db`. | Rejected: cross-filesystem rename is not atomic. Copy and reverify on the database volume; activate only while stopped. |
| Ship the timestamp migration in the same release that first creates its backup facility. | Rejected: deploy and restore-drill this capability first. Production v3.3.0 needs an interim console `oc db backup` after the new mount or a separate backup-capability release. |

## Bounded implementation and acceptance sequence

1. Add the independent backup-root setting and bind mount to the repository
   compose, with no live stack change. Reuse the existing online backup
   engine for scheduled and manual snapshots. Add manifest publication and
   fail-closed path handling, while preserving old backups in the named volume.
2. Add the guarded HTTP-MCP tools above. Cover unauthenticated/off-by-default
   registration, path traversal, tampering, incomplete artifacts, concurrent
   creation, schema mismatch, and stage re-verification. Keep the default MCP
   tool inventory unchanged.
3. Verify locally with disposable WAL-mode databases, interrupted writes,
   round-trip restore to a *separate* database, and the repository's required
   full checks. Open an independent PR against `main`; exact-head CI must pass.
4. Before deploying, prepare the host directory and verify uid 1000 write
   access and restricted SMB ACLs. Reconcile the detached Portainer stack's
   stored compose deliberately; a repository compose edit does not apply it.
   Decide how to release this capability without implicitly clearing design
   0010's unresolved metrics gate. No timestamp migration in this release.
5. On the actual NAS, create a snapshot, read it through the exposed share,
   compare its digest, restore into a disposable database, run integrity and
   row/search/embedding checks, and record time and request-tail impact.
   Retain a manual pre-upgrade snapshot. Only after this drill may design 0016
   track 2's production migration gate be reconsidered.

**Stop** on an unwriteable mount, broad share ACL, failed hash/integrity or
restore comparison, unacceptable request-tail impact, or an unresolved release
gate. A green PR proves source, not durable production backups.

The exposed `assets` and `output` directories and the broader persistent
storage layout need a separate architecture review. Inventory actual mounts,
logs, retention and recovery before deciding whether either folder is still
needed or whether logs and other durable data should move to an external mount.
This work does not delete or repurpose either directory.
