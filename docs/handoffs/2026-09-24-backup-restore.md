# Backup and restore continuation handoff — 2026-09-24 UTC

Resume pointers only. The [assessment](../CODEBASE_ASSESSMENT.md) holds
current state (revs 217-227), [design 0017](../design/0017-exposed-backup-and-restore.md)
holds the decisions and review record, and the
[runbook](../configuration/local_backup_restore.md) holds the procedure.
Recheck live state before acting.

**Correction.** An earlier version of this handoff said an independent
pass "found no further P0/P1 defect". A Claude adversarial review of
`f65be230` on 2026-09-24 found several P1 defects:

- the verifier deleted the emergency backup of a corrupt store;
- merging would have shipped that to the nightly backup;
- the helper wedged on a damaged live store;
- production activation depended on MCP tools that cannot register
  while auth is disabled.

Their fixes are on draft PR #39 (revs 221-227). The operator decided on
2026-09-24 to park the MCP tools, keep auth disabled, and restore a damaged
store automatically.

## Resume here

1. Check `git status --short --branch` and PR #39's head and checks. Read
   the assessment's backup item and the V3_PLAN backup entry.
2. Search OpenChronicle for stable key
   `CarlDog/openchronicle-mcp#backup-restore-tools` (memory
   `54f059eb-0370-4cbf-808a-7a9d678aeb7b`) and update that record.
3. Source: the fix round has had its own independent review (rev 227).
   Merge is the operator's call; it changes the nightly backup path, so
   decide whether it rides v3.4.0.
4. Next operational step: the off-NAS v3.3.0 copy, through NAS Bash or the
   runbook's Portainer console route, before any stack change.
5. The NAS drill needs a helper image: a release (design 0010 gate) or an
   authorized non-release image.

Timestamp PR #38 stays downstream of all of this. No NAS drill, off-device
copy, merge, release, stack change, live restore or migration had occurred
at this update.
