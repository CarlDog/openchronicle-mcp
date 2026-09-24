# Backup and restore continuation handoff — 2026-09-24 UTC

This is a working-state snapshot for continuing the exposed backup/restore
work. [The assessment](../CODEBASE_ASSESSMENT.md) is the current-state source
of truth; [design 0017](../design/0017-exposed-backup-and-restore.md) records
the decision and adversarial reviews; the
[operator runbook](../configuration/local_backup_restore.md) contains the
guarded commands and acceptance evidence. Recheck live state before acting on
this dated handoff.

## Resume here

1. Check `git status --short --branch` and the current head and checks of
   [draft PR #39](https://github.com/CarlDog/openchronicle-mcp/pull/39).
   Its pre-handoff implementation checkpoint was
   `5f9fe0064c57489cc3e78b413ad1aacf7694a79d`: Windows and Ubuntu tests,
   quality, CodeQL, and secret scan passed on that exact commit. The image
   build was skipped on the PR. Recheck checks after any new commit.
2. Read the assessment, design, runbook, and the live backup entry in
   [V3_PLAN](../V3_PLAN.md#post-cutover-follow-ups-tech-debt). Search the
   OpenChronicle project for stable key
   `CarlDog/openchronicle-mcp#backup-restore-tools`, then read memory
   `54f059eb-0370-4cbf-808a-7a9d678aeb7b`. Update that record rather than
   creating another. Issue status has not been verified.
3. Refresh production identity through OpenChronicle health and inspect the
   actual Portainer stack, mounts, image and access route before preparing an
   operational action. The last health read at 2026-09-24 01:37 UTC reported
   `v3.3.0`, build `7349f94ab8bd8b9a8c60e1def63ad4997f7f9a45`, schema 4,
   active Ollama embeddings, and no missing or stale embeddings. Health does
   not establish the current stored Portainer compose or a recoverable backup.

## State and next gate

PR #39 adds a fixed-root `/exports/backups` SQLite snapshot catalog, verified
manifest publication, optional authenticated MCP create/list/verify/plan/stage
tools, and a separate offline activation/rollback helper. Local disposable
tests covered committed WAL writes and interrupted cutovers. The full Windows
suite passed 1,169 tests with one Linux-only skip; Ruff, mypy, Markdown, Bash
syntax and commit hooks passed at the implementation checkpoint. An independent
source/runbook adversarial pass found no further P0/P1 defect. This is source
evidence, not a NAS drill or a production recovery claim.

The next operational prerequisite is an **approved NAS Docker admin or console
route**. The known SMB share exposes neither the live database nor existing
backups. Before editing the detached production stack, use the existing
v3.3.0 `oc db backup` through that route, extract the consistent artifact,
verify its digest, SQLite integrity, foreign keys and inventory, then copy and
hash it on a device independent of the NAS, and open that copy read-only for
the same checks. Record the old image ID, stored
compose, volume identity and non-secret verification evidence. The runbook's
[bootstrap section](../configuration/local_backup_restore.md#bootstrap-a-pre-change-copy-from-v330)
is the procedure; stop if any check or access prerequisite fails. `/exports`
is on the same NAS and is not the independent recovery copy.

Only after that recovery point exists: resolve the separate
[design 0010](../design/0010-performance-measurement.md) release decision;
review and deliberately reconcile the detached Portainer stack's mount, uid
permissions, auth and client transition; then run and independently review the
runbook's [disposable NAS Docker drill](../configuration/local_backup_restore.md#disposable-restore-drill)
and [offline activation/rollback](../configuration/local_backup_restore.md#offline-activation-and-rollback)
on a WAL-bearing clone, including abort and retry. Keep the old and candidate
image/database pairs pinned. Source review and merge can proceed separately,
but neither satisfies these operational gates. The broader persistent-storage
review of `assets`, `output`, logs and mounts is a separate V3_PLAN item.

The [timestamp ordering PR #38](https://github.com/CarlDog/openchronicle-mcp/pull/38)
is also draft and must remain downstream. Immediately before that migration,
take another fresh verified off-NAS copy and rehearse the exact old/new
image-and-database pairs. Do not infer that staging through MCP replaces the
live WAL database; the live cutover is offline. No NAS Docker drill, verified
off-device pre-change copy, PR #39 merge, tagged release, production mount
change, live restore, or timestamp migration had occurred at this handoff.
