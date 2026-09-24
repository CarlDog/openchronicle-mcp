# 0017 — Exposed local backups and guarded restore preparation

**Status:** Operator-requested implementation plan; source/PR and production
acceptance tracked separately · **Date:** 2026-09-23 · **Precedes:** design
0016 track 2, the timestamp migration. **Second adversarial pass:**
2026-09-24 UTC. **Offline-procedure adversarial pass:** 2026-09-24 UTC.

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
"Clearly" means an ERROR log at startup and a failed backup job, not a
failed startup: under `restart: unless-stopped` a startup failure crash-loops
the memory service and blocks every CLI command, including the emergency
`oc db backup` (Claude review, 2026-09-24).
The container runs as uid 1000; prepare the host directory with appropriate
ownership/ACL before deployment. Do not recursively chown the snapshot tree
at every start. Restrict SMB access because local snapshots contain the full
plaintext corpus.

MCP backup tools are **off by default**, and available only on the mounted
HTTP MCP surface when `OC_BACKUP_MCP_ENABLED=true`, `OC_BACKUP_DIR` is
explicitly configured, and the HTTP API has a nonempty effective API key.
An enabled-but-unauthenticated or unrecognized setting logs an error and
leaves the tools unregistered; it does not stop startup. Stdio MCP never
registers these tools. Tool inputs are artifact IDs, not paths; the server
chooses destinations inside the configured directory. No tool returns raw
database bytes. **The tools are parked** (operator decision, 2026-09-24):
auth stays disabled on the LAN deployment as decided on 2026-05-06, so the
tools cannot register there, and no auth change is planned or implied. The
production restore path does not depend on them. Daily scheduled backups use
the bind mount independently.

| Tool | Effect and result |
|---|---|
| `db_backup_create` | One online SQLite snapshot under `manual/`; returns an artifact ID and metadata. No overwrite or caller path. |
| `db_backup_list` | Lists completed `auto/` and `manual/` snapshots, bounded and newest-first. |
| `db_backup_verify` | Reopens one artifact read-only, checks checksum and SQLite integrity, and reports schema and row counts. |
| `db_restore_plan` | Read-only comparison of a verified artifact with the current database, including schema and counts. Returns `stop_reasons` (a newer schema, or a different project identity, meaning another instance) and `memory_delta`: a decrease is expected when restoring an older snapshot, so only the operator can judge it. Explicitly says no restore occurred. |
| `db_restore_stage` | Refuses on any `db_restore_plan` stop reason. After re-verification, copies the candidate into a private staging directory on the database volume, verifies it again, and returns an ID. Does not replace the live database. |

Snapshots are produced by the existing `sqlite3.Connection.backup()` path,
written to a sibling temporary file, checked and renamed. Verification runs
both `PRAGMA integrity_check` and `PRAGMA foreign_key_check`: SQLite's
integrity check does not detect broken foreign keys. A snapshot that fails
either check is a faithful copy of a damaged live store, and may be its
newest copy: it is kept as `*.db.failed-verify`, outside the catalog and
retention names, and the operation fails. It is never deleted, so the
integrity job's emergency backup still leaves evidence (Claude review,
2026-09-24). Snapshots are published in rollback-journal mode, so opening
one read-only never creates `-wal`/`-shm` files. A sidecar manifest
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
writer. A standalone helper, run as PID 1 of a network-isolated disposable
container with only the verified data volume, archives the old database **and
its WAL/SHM state together**, consolidates an old-state rollback snapshot
from a disposable copy of that archive (SQLite never opens the live files, so
even a read-only open cannot create or delete their sidecars), copies the
staged candidate on the same volume, moves old sidecars,
then atomically replaces the main file. It records durable recovery phases;
rollback first archives the forward state and verifies its checksums. A
partial forward archive fails closed. The helper refuses the live service's
`docker exec` context. Restart the appropriate pinned image and independently
check health, schema, counts, search and selected IDs. If the live store is
already damaged, use a previously verified recovery point; do not make a fresh
snapshot a prerequisite that prevents recovery.

**A damaged live store does not block activation** (operator decision,
2026-09-24; this replaces the earlier "manual recovery from the raw
triplet" rule, which in practice wedged the helper in phase `archiving`).
The old state is assessed, never required to pass: integrity, foreign keys
and identity are recorded separately in `state.json`, and an SQLite error
from any of them is a verdict. Rollback reinstalls the consolidated copy
whenever it is recognisably an OpenChronicle database, faithfully including
any damage. If SQLite cannot read the old state at all (`SQLITE_CORRUPT` or
`SQLITE_NOTADB` while consolidating), or the copy has no readable identity
(for example a zero-length main file), activation still proceeds, rollback
is refused, and the exact old family stays in `raw-old`; the way out is
another activation of a verified artifact under a new operation ID. Any
other consolidation error (disk, lock, I/O) stops activation in phase
`archiving`, where the live family is unchanged. No force flag exists, and
the helper never reattaches a WAL. `db_restore_stage` is not a claim that a
restore happened.
Do not use an MCP `confirm=true` as final authority: an autonomous client could
supply it itself.

## Adversarial review and changes from the first sketch

| Failure attempt | Design response |
|---|---|
| Move the live DB to the exposed share for easy copying. | Rejected: external writes or a raw copy of a WAL-mode file can damage or misrepresent the live store. Export consistent snapshots instead. |
| Mount the share at `/data/backups`. | Rejected: the mount hides prior named-volume backups. Use `/exports` and leave history untouched. |
| Expose `db_restore_execute(confirm=true)` on the normal MCP server. | Rejected: confirmation is self-service, and the live connection remains open. MCP verifies/stages; offline operator action performs cutover. |
| Enable backup tools while LAN MCP auth is disabled. | Log an error and leave the tools unregistered (originally: fail startup, which crash-loops under `unless-stopped`). Stdio registration stays off. Scheduled backups remain independent of MCP auth. |
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
| The disposable copy opens, but the actual offline replacement fails or reattaches an old WAL. | Rehearse the **exact** [offline helper procedure](../configuration/local_backup_restore.md#offline-activation-and-rollback) on a disposable clone with a deliberately retained nonempty WAL, including activation, restart, validation and rollback. Opening a separate copy and `db_restore_stage` alone do not pass this gate. |
| The replacement opens under the wrong image and immediately migrates again. | Pin and retain the pre-upgrade and candidate image tags/digests; test forward startup and rollback startup with the corresponding image and database pair. Compare schema before and after each start. |
| `integrity_check` reports `ok` for orphaned rows. | Verify `foreign_key_check` as well; reject an artifact if either check fails, and cover the distinction in a regression test. |
| A snapshot from a different instance has a valid manifest. | Record the expected source environment, schema, project-ID fingerprint, selected memory IDs and counts. Treat any identity mismatch or unexplained row decrease as a stop condition; a hash proves file integrity, not that this is the intended corpus. |
| The first rollout of the backup facility itself goes wrong. | Produce and independently retain a v3.3.0 recovery copy **before** modifying the detached stack or starting the new image. Record the old stack definition, env, image digest, mounts and rollback procedure. Resolve design 0010's release gate explicitly rather than treating this PR's green CI as approval to ship. |
| The operator can only reach the SMB share, which has no database or old backups. | This is a current bootstrap blocker. Obtain an approved NAS Docker admin/console path, run the existing v3.3.0 `oc db backup` against the live container, extract the resulting snapshot without raw-copying the live WAL database, then hash, open and retain it off-NAS. Do not change the stack first merely to expose the volume. Record the actual container/volume/path discovered at execution time. |
| A successful drill depends on undocumented manual improvisation. | The guarded [runbook](../configuration/local_backup_restore.md) supplies bootstrap, helper activation and rollback commands with identity checks, expected phases and stop conditions. Have an independent checker review the filled values and outputs, then execute twice on disposable copies, including one aborted activation. Record artifacts and elapsed recovery time. Local tests do not substitute for the NAS drill. |

Source PR review and exact-head CI can complete before NAS rollout; merging
source does not satisfy operational acceptance. Before a release or stack
change, the bootstrap recovery copy and design 0010 decision must be resolved.
Before timestamp migration, the deployed feature, off-NAS copy and full
recovery rehearsal must pass. PR #39 is **not** a safety net on its own.
SQLite documents that the WAL is part of the database's persistent state and
cannot be discarded just because the main file exists:
[WAL file handling](https://www.sqlite.org/wal.html#the_wal_file).

## Offline-procedure adversarial pass — disposition

The independently reviewed helper and operator procedure produced further
failure cases. This pass reviews the *source procedure*; no Docker/NAS drill,
release, deployment or production restore is claimed.

| Finding | Disposition |
|---|---|
| A rollback retry could trust a partial forward archive or silently discard new WAL writes. | Archive and checksum each forward-state member before setting `rolling_back`; reject incomplete archives. On retry, compare current/displaced WAL and SHM with recorded checksums, and fail closed on reappearance or modification. Disposable tests cover interrupted activation, interrupted rollback and a tampered displaced WAL. |
| A successful activation left `*.db` in `.restore-stage`, blocking every future stage. | A guarded `retire-stage` action verifies the recorded candidate and completed operation phase, then records two-phase retirement. It removes only the staged copy after operator acceptance; recovery and exported artifacts remain. |
| The shell's `test -z "$(docker ps ...)"` could pass after a Docker query failure. | Assign the Docker output first under `set -e`, then test it. Recheck before each apply and after completion. Rollback and stage retirement now have self-contained, re-identifying commands for a new shell. |
| A graceful stop after the deliberate WAL write could erase the very condition the drill meant to test. | Stop the disposable service first, then use an abruptly exited separate writer and assert a nonempty WAL immediately before activation. The runbook includes a disposable volume setup and deterministic aborted-swap injection. |
| An incomplete snapshot publication could lose a directory entry on power loss or evict a valid artifact under retention. | Fsync the catalog directory after DB/manifest publication; count only complete DB/manifest pairs for automatic retention and leave incomplete/legacy files for review. |
| A container could restart or Portainer could recreate it during the offline swap. | The runbook requires a recorded maintenance freeze, disables the container restart policy temporarily, checks the same volume for active users before and after each operation, and verifies the recreated container's volume. This is an **operational control**, not a machine-enforced lock against all external actors. Its real NAS behavior must pass the disposable drill before production use. |
| The bootstrap copy and off-NAS handoff could be mistaken for a verified safety net. | The runbook now checks capacity before two NAS-side copies, verifies snapshot structure and identity read-only, and requires an independently hashed copy on a separate device. The real transfer and access controls remain acceptance evidence to collect. |

## Bounded implementation and acceptance sequence

1. Add the independent backup-root setting and bind mount to the repository
   compose, with no live stack change. Reuse the existing online backup
   engine for scheduled and manual snapshots. Add manifest publication and
   fail-closed path handling, while preserving old backups in the named volume.
2. Add the guarded HTTP-MCP tools above. Cover unauthenticated/off-by-default
   registration, path traversal, tampering, incomplete artifacts, concurrent
   creation, schema mismatch, and stage re-verification. Keep the default MCP
   tool inventory unchanged.
3. Verify locally with disposable WAL-mode databases, an abruptly exited WAL
   writer, offline activation and rollback, interrupted activation/rollback,
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
