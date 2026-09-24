# 0017 — Exposed local backups and guarded restore preparation

**Status:** Operator-requested implementation plan; source/PR and production
acceptance tracked separately · **Date:** 2026-09-23 · **Precedes:** design
0016 track 2, the timestamp migration. **Second adversarial pass:**
2026-09-24 UTC.

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
written to a sibling temporary file, checked and renamed. Verification runs
both `PRAGMA integrity_check` and `PRAGMA foreign_key_check`: SQLite's
integrity check does not detect broken foreign keys. A sidecar manifest
records SHA-256, schema version, size and creation time; only a complete
artifact pair is offered for restore. Pre-upgrade/manual artifacts are not
subject to automatic retention. Automatic retention keeps its existing
seven-newest-plus-seven-day policy and removes each pruned sidecar together
with its database. A share writer could forge a checksum, so ACLs remain the
security boundary; checksums detect accidental damage, not hostile writers.

The final restore is deliberately **offline**. A serving process has an open
WAL-mode connection; replacing its file from an MCP request risks old WAL/SHM
sidecars and concurrent writes. Quiesce writes, take and verify a pre-restore
snapshot while the service still runs if it is healthy enough, then stop every
writer. Keep the old database **and its WAL/SHM state together** for rollback;
verify and activate the staged candidate on the database volume, restart the
appropriate pinned image, and independently check health, schema, counts,
search and selected IDs. If the live store is already damaged, use a previously
verified recovery point; do not make a fresh snapshot a prerequisite that
prevents recovery. `db_restore_stage` is not a claim that a restore happened.
Do not use an MCP `confirm=true` as final authority: an autonomous client could
supply it itself.

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

## Second adversarial pass — release blockers

The first draft proved *snapshot creation* and *candidate opening*, but not
recovery. The following are P0 gates, not optional follow-ups:

| Failure attempt | Required evidence before timestamp work |
|---|---|
| The NAS or its volume fails after a successful local snapshot. | Retain at least one verified, independently hashed copy outside the NAS failure domain before changing the live stack, and a fresh one immediately before migration. The `/exports` share is access, not an independent backup. Record its custody and do not prune it until rollback is retired. |
| The disposable copy opens, but the actual offline replacement fails or reattaches an old WAL. | Rehearse the **exact** stop, sidecar-preservation, same-volume activation, restart, validation and rollback procedure on a disposable clone with pending WAL writes. The activation procedure or utility must be reviewed and repeatable before any production migration. Opening a separate copy and `db_restore_stage` alone do not pass this gate. |
| The replacement opens under the wrong image and immediately migrates again. | Pin and retain the pre-upgrade and candidate image tags/digests; test forward startup and rollback startup with the corresponding image and database pair. Compare schema before and after each start. |
| `integrity_check` reports `ok` for orphaned rows. | Verify `foreign_key_check` as well; reject an artifact if either check fails, and cover the distinction in a regression test. |
| A snapshot from a different instance has a valid manifest. | Record the expected source environment, schema, project-ID fingerprint, selected memory IDs and counts. Treat any identity mismatch or unexplained row decrease as a stop condition; a hash proves file integrity, not that this is the intended corpus. |
| The first rollout of the backup facility itself goes wrong. | Produce and independently retain a v3.3.0 recovery copy **before** modifying the detached stack or starting the new image. Record the old stack definition, env, image digest, mounts and rollback procedure. Resolve design 0010's release gate explicitly rather than treating this PR's green CI as approval to ship. |
| The operator can only reach the SMB share, which has no database or old backups. | This is a current bootstrap blocker. Obtain an approved NAS Docker admin/console path, run the existing v3.3.0 `oc db backup` against the live container, extract the resulting snapshot without raw-copying the live WAL database, then hash, open and retain it off-NAS. Do not change the stack first merely to expose the volume. Record the actual container/volume/path discovered at execution time. |
| A successful drill depends on undocumented manual improvisation. | Freeze a runbook with exact, separately reviewed commands, operator/checker roles, expected outputs, stop conditions and rollback triggers; execute it twice on disposable copies, including one aborted or failed activation. Record the artifacts and elapsed recovery time. |

Source PR review and exact-head CI can complete before NAS rollout; merging
source does not satisfy operational acceptance. Before a release or stack
change, the bootstrap recovery copy and design 0010 decision must be resolved.
Before timestamp migration, the deployed feature, off-NAS copy and full
recovery rehearsal must pass. PR #39 is **not** a safety net on its own.
SQLite documents that the WAL is part of the database's persistent state and
cannot be discarded just because the main file exists:
[WAL file handling](https://www.sqlite.org/wal.html#the_wal_file).

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
   round-trip restore to a *separate* database, relational integrity checks,
   and the repository's required full checks. PR #39 can pass source review
   independently of NAS acceptance; exact-head CI must pass after every source
   change. Do not equate merge with release or a validated recovery path.
4. Before changing the live stack, inventory its exact database/sidecars,
   image digest, compose, env, mounts, writers, schema, counts, selected IDs,
   free space and rollback route. An approved NAS Docker admin/console path is
   required to run the existing v3.3.0 `oc db backup` and extract its artifact;
   the currently available SMB share cannot do this. Retain a verified copy
   outside the NAS **before** editing the stack. Prepare the host directory and prove uid
   1000 access and restricted SMB ACLs. Reconcile the detached stored compose
   deliberately; a repository compose edit does not apply it. Resolve design
   0010's release gate. No timestamp migration in this release.
5. On the actual NAS, create a snapshot, read it through the exposed share,
   compare its digest with an independent off-NAS copy, restore into a
   disposable database, run integrity, foreign-key, row, ID, search and
   embedding checks, and record duration and request-tail impact.
6. Rehearse the frozen offline activation **and rollback** procedure on a
   disposable clone with a nonempty WAL, using the pinned pre-upgrade and
   candidate images. Demonstrate that writes after the candidate snapshot
   appear in the saved pre-restore state, and that rollback restores them.
   Capture exact commands, outputs and evidence; any manual ambiguity fails
   the drill.
7. Immediately before the timestamp migration, take another verified manual
   snapshot, retain an off-NAS copy, recheck production schema/identity and
   raw timestamp shapes, and reconfirm the image/DB rollback pair. Only then
   may design 0016 track 2's migration gate be reconsidered.

**Stop** on an unwriteable mount, broad share ACL, failed hash/integrity or
restore comparison, unacceptable request-tail impact, or an unresolved release
gate. A green PR proves source, not durable production backups.

The exposed `assets` and `output` directories and the broader persistent
storage layout need a separate architecture review. Inventory actual mounts,
logs, retention and recovery before deciding whether either folder is still
needed or whether logs and other durable data should move to an external mount.
This work does not delete or repurpose either directory.
