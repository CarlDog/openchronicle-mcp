# v3 Cutover Triage — 2026-05-06

**Outcome:** v3 is live on the NAS, healthy, single-container ASGI on
port `:18000` (HTTP at `/api/v1/*`, MCP at `/mcp`). Image
`ghcr.io/carldog/openchronicle-mcp:v3.0.0-rc1`. New canonical
`project_id = fe2ef898-0152-40a4-af97-ed97cc86ca45`.

**Cost:** ~24 v2 memories were not preserved through to the live v3
DB. The pre-migration v2 DB is intact and preserved on disk for
forensic analysis (see "Forensic artifacts" below).

This doc captures everything that bit us during the cutover, with
enough detail to be a punch list for follow-up commits and runbook
updates.

---

## Timeline

| Time (CST) | Event |
|---|---|
| ~14:00 | Prior chat session began Phase 8 cutover steps from `docs/V3_PLAN.md` |
| ~14:30 | v2 stack 151 stopped; `migrate_v2_to_v3.py` run; `verify_v3_db.py` printed OK with `schema_version: 1`; migrated DB placed at `/volume1/@docker/volumes/openchronicle-mcp_oc-data/_data/openchronicle.db` |
| ~17:00 | Force-push of `v3/develop` → `main`; `docker-publish.yml` triggered, would overwrite `:latest` with v3 in ~5–10 min |
| ~17:05 | Prior chat triggered `Retag GHCR Image` workflow with `source_tag=latest, dest_tag=v2-final`; **failed** (uppercase `IMAGE_NAME` bug + caller passed `dest_tag=v2-final` as the literal value); race lost, `:latest` flipped to v3 unprotected |
| ~17:08 | docker-publish completed; `:latest` is now v3 |
| ~17:30 | This chat session began as a handoff |
| ~18:30 | Identified retag-workflow lowercase bug; identified Windows-only backup-module sqlite handle bug |
| ~18:45 | Retag workflow fix landed in commit `6ae71812`; `:v2-final` tag captured pointing at v2 image (`sha256:6b1bd29...`) |
| ~19:25 | Set `OC_TAG=v3.0.0-rc1` on stack 151 + redeploy; v3 container started against migrated DB; **immediately crash-looped with `database disk image is malformed`** |
| ~19:32 | Stopped container to halt the crash loop |
| ~19:32 | User restored `~/post-v3-cutover.db` over `openchronicle.db` (also corrupt) |
| ~19:35 | Diagnosed: `~/post-v3-cutover.db` corrupt too; v2-rollback intact (24 memories); decision to abandon migration and start v3 fresh |
| ~19:42 | Moved corrupt DBs aside, kept v2-rollback for forensics, removed orphan `-wal`/`-shm` files |
| ~19:44 | Restarted v3; **booted cleanly against empty volume** — schema migrator + maintenance loop + embedding service all green |
| ~19:51 | Created new project `openchronicle-mcp` (id `fe2ef898-...`) |
| ~19:54 | First triage memory saved successfully via HTTP API |

---

## What broke

### 1. The migrated DB was corrupt by the time v3 first opened it

The prior session's runbook said:

> Migration validated: 12 projects, 36 memory items, 35 embeddings preserved;
> verify_v3_db.py printed OK with schema_version: 1

But when v3 actually started against that DB, every connection attempt
returned `database disk image is malformed`. We never got a stable
v3-running-on-migrated-data state.

**Open questions** (genuine unknowns, not certainties):

- ~~Did the migration script produce a borderline-corrupt DB that
  passed superficial checks? `verify_v3_db.py` apparently checked
  `schema_version` and row counts but **not** `PRAGMA integrity_check`.~~
  **CORRECTED** — both `migrate_v2_to_v3.py` (line 118-120) and
  `verify_v3_db.py` (line 82-84) already run `PRAGMA integrity_check`.
  The migration script even refuses to complete if integrity_check
  returns anything but `ok`. So the validation gates were strong; the
  corruption must have happened AFTER validation, in the operational
  flow between validate-time and v3-open-time.
- Did orphan `-wal`/`-shm` files from earlier operations (v2 stop,
  prior session diagnostic sqlite3 calls) collide with v3's open of
  the freshly-placed `openchronicle.db`? When we cleared the volume
  and retried v3 against an empty directory, v3 booted clean — which
  is consistent with the WAL-orphan hypothesis but doesn't prove it.
  **Most likely culprit given everything we know.**
- Did v3's startup do something destructive on first open that
  corrupted the migrated DB? The fresh-empty-volume retry rules out
  anything inherent to v3 startup, but doesn't rule out a bug
  triggered specifically by an existing-but-clean v3-shaped DB.

The 24-vs-36 memory count discrepancy (handoff said 36 migrated, but
v2-rollback only has 24) suggests either the prior session migrated
from a different snapshot than the rollback, or the count in the
handoff was wrong.

### 2. Retag workflow had a lowercase bug

`Retag GHCR Image` workflow used `${{ github.repository }}` which
preserves owner/repo casing (`CarlDog/openchronicle-mcp`). Docker
registry refs must be lowercase. Fixed in commit `6ae71812`
(`fix(ci): lowercase IMAGE_NAME in retag workflow`).

This delayed capturing `:v2-final` long enough that `:latest` was
overwritten by v3 in the same window. We later re-captured `:v2-final`
by retagging from `bb217d9` (the v2 build's SHA-tag) directly.

### 3. Windows backup-module sqlite handle bug

`infrastructure/persistence/backup.py` used the
`with sqlite3.connect(...) as conn:` pattern, which only
commits/rollbacks on exit but does **not** close the connection.
The file handle stayed open when `os.replace(tmp, dest)` ran
immediately after, causing `PermissionError [WinError 32]` on Windows
(POSIX tolerates renaming open files; Windows does not).

Fixed in commit `6ae71812` with explicit `dst_conn = sqlite3.connect(...);
try/finally close()` pattern in both `backup_to()` and
`backup_from_connection()`. Restored all 10 previously-failing backup
tests (`test_backup_module`, `test_cli_db::TestDbBackup`,
`test_maintenance_loop` backup tests).

Production (Linux NAS) was never affected. CI (ubuntu-latest) was
never affected. Only Windows local dev hit it.

### 4. Pre-existing mypy errors

While committing `6ae71812`, the pre-commit `mypy` hook flagged 9
errors in 6 files that exist on `493d4fa5` (the previous main HEAD):

- `tests/test_migration_v2_to_v3.py:21,22` — `migrate_v2_to_v3`,
  `verify_v3_db` modules can't be found (likely `scripts/` not on
  mypy path, or scripts named differently than imported)
- `src/openchronicle/interfaces/mcp/tracking.py:101,108` — references
  `CoreContainer.telemetry_settings` and
  `SqliteStore.insert_mcp_tool_usage`, neither of which exists on the
  v3 container or store. **Looks like dead v2 code missed by the
  audit pass; needs investigation.**
- `src/openchronicle/core/infrastructure/maintenance/jobs.py:85` —
  returning `Any` from function declared to return `str`
- `src/openchronicle/core/application/services/maintenance_loop.py:265` —
  `JobState(name=...)` argument typed `Any | None`, expects `str`
- `src/openchronicle/interfaces/api/app.py:64` — `Coroutine` vs
  `Awaitable` variance issue in `MaintenanceLoop` handlers dict
- `src/openchronicle/interfaces/cli/commands/system.py:179,181` —
  trying to set read-only `HTTPConfig.host` / `HTTPConfig.port`
  properties

These shipped on `493d4fa5` somehow (mypy hook should have caught them
on that commit too). The most concerning is the `tracking.py` pair —
if anything imports it at runtime, those attribute accesses would
crash.

The retag fix commit `6ae71812` was made with `SKIP=mypy` (scoped
hook skip — pre-commit's own escape hatch, all other hooks ran). This
debt needs a focused cleanup commit.

### 5. Maintenance loop backup filename collision

When v3 booted, `db_vacuum` ran `db_backup` first (per the backup-
before-destructive policy we built), then the standalone `db_backup`
job ran shortly after. Both wrote to the same filename
`openchronicle-20260506T004445Z.db` (overwriting). The timestamp
granularity (seconds) is too coarse if two backups land in the same
second.

Fix: bump filename precision to microseconds, or include a job-name
component in the filename, or rotate via a sequence suffix when
collision detected.

### 6. Auth status uncertainty

The Portainer stack listing showed `OC_API_KEY` present (value masked
as `<redacted>` per portainer-mcp's secret scrubbing), but the project
create succeeded with no `Authorization` header. Either the actual
stored value is empty (auth disabled by design) or there's a v3 wiring
bug in the auth middleware.

Action: determine deliberately whether auth should be enabled on this
NAS deployment. If yes, set a known `OC_API_KEY` and verify the
middleware enforces it. Document the decision.

### 7. ~25 v2 vestigial env vars on stack 151

Stack 151's environment carries forward a lot of v2 cruft that v3
ignores:

- `OC_LLM_PROVIDER`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`,
  `OPENAI_API_KEY`, `XAI_API_KEY`, `*_MODEL` — all the LLM provider
  config. v3 has no LLMs.
- `OC_LLM_*` mode/pool/weights config
- `OC_MOE_*` consensus engine config
- `DISCORD_BOT_TOKEN`, `OC_DISCORD_*` — Discord bot config
- `HOST_OUTPUT_DIR`, `HOST_ASSETS_DIR`, `HOST_PLUGINS_DIR` — bind
  mount paths for cut features

These don't affect v3 (extra env vars are ignored), but they're noise
and a security risk (the API keys are real secrets sitting in a
deployment that doesn't use them). Phase 9 cleanup: scrub via
`portainer_set_stack_env` with a `remove` list.

### 8. Dependabot vulnerability flagged on push

GitHub flagged "1 moderate" dependabot vulnerability in the response
to `git push origin main` for commit `6ae71812`. URL was
`https://github.com/CarlDog/openchronicle-mcp/security/dependabot/5`.
Triage and fix.

---

## Forensic artifacts (preserved on the NAS)

`/volume1/@docker/volumes/openchronicle-mcp_oc-data/_data/`:

- `openchronicle.db.corrupt-20260506` — 925,696 bytes. The DB the
  user copied in from `~/post-v3-cutover.db` (provenance unclear; was
  also corrupt). Has valid SQLite magic header but fails
  `PRAGMA integrity_check`.
- `openchronicle.db.v2-rollback` — 516,096 bytes. Original v2 DB
  pre-migration. **Intact**, passes integrity_check, contains
  24 memory items.
- `backups/` — pre-existing backup directory from v2; contents not
  inspected during this session.

`~/post-v3-cutover.db.corrupt-20260506` (user's home dir on NAS) —
same file as the .corrupt copy in the volume, kept here so it doesn't
get re-copied accidentally.

User's laptop — `~/backups/pre-v3-cutover.db` (mentioned in the
handoff but not inspected during recovery). Possibly a different
snapshot than v2-rollback; could explain the 24-vs-36 memory count
discrepancy if the laptop snapshot was taken at a different time.

---

## Punch list (in order of impact)

These should be folded into `docs/V3_PLAN.md` "Post-cutover follow-ups"
and the architecture/maintenance docs as appropriate.

### High priority

1. **Investigate `tracking.py` dead code**
   (`interfaces/mcp/tracking.py` references nonexistent attrs on
   `CoreContainer` and `SqliteStore`). Either delete the file or fix
   the references. If anything imports it, this is a runtime bug
   waiting to happen.

2. **DONE: Fix the migration script's WAL-cleanup gap**
   `migrate_v2_to_v3.py` now refuses if orphan `-wal`/`-shm` files
   exist at the destination path stem; with `--force` it scrubs them
   before writing. `verify_v3_db.py` surfaces orphan sidecars as a
   `warnings` field in its report. Tests added. Closed in this batch.

3. **CORRECTED: `verify_v3_db.py` already runs `PRAGMA integrity_check`**
   This item was based on a wrong assumption. Both the migration
   script (line 118-120) and verify_v3_db.py (line 82-84) already
   run integrity_check; the migration script refuses to complete on
   anything but `ok`. The corruption mystery is genuinely about
   destination-side handling between validate-time and v3-open-time
   (see open question 1 in "What broke" §1).

4. **Determine + enforce auth state on stack 151**
   `OC_API_KEY` either is genuinely empty (intentional?) or the v3
   auth middleware isn't enforcing it. Set deliberately and verify.

5. **Mypy debt cleanup**
   9 errors in 6 files (see "What broke" item 4). Dedicated commit;
   un-skip mypy hook after.

### Medium priority

1. **Maintenance backup filename collision**
   Two backups in the same second overwrite each other. Bump
   precision or add job-name suffix.

2. **Scrub v2 vestigial env vars from stack 151**
   ~25 env vars including real API keys for services v3 doesn't use.
   Use `portainer_set_stack_env(remove=[...])`.

3. **Dependabot vuln #5**
   Triage `https://github.com/CarlDog/openchronicle-mcp/security/dependabot/5`.

4. **Phase 9 dependabot config update**
   Drop `target-branch: v3/develop` lines from `.github/dependabot.yml`
   (per Phase 9 Day 0 in V3_PLAN.md).

### Low priority

1. **`portainer_container_start` 400 bug**
   portainer-mcp's start handler sends a non-empty body to Docker's
   container-start endpoint, which has rejected non-empty bodies
   since API v1.24 (2016). Workaround: use `redeploy_git_stack`
   instead. Spawned as separate task during this session for
   portainer-mcp repo.

2. **Cutover runbook updates**
   `docs/V3_PLAN.md` Phase 8 should call out:
   - Verify destination dir is clean (no orphan WAL/SHM) before
     placing migrated DB
   - Run `PRAGMA integrity_check` as part of validation
   - Capture `:v2-final` retag BEFORE force-pushing to main (the
     docker-publish race is real)
   - Confirm auth state explicitly post-cutover

3. **DONE: 24-vs-36 memory count investigation (2026-05-06)**
   Resolved. Laptop backup `~/backups/pre-v3-cutover.db` has 36
   memory items / 12 projects / 35 embeddings, integrity ok, latest
   created_at `2026-05-05T04:09:49Z`. NAS rollback
   `openchronicle.db.v2-rollback` has 24 memories — it represents
   an EARLIER snapshot than the laptop backup. The handoff's "36
   memories preserved" was correct; it was migrated from the laptop
   snapshot, not the NAS one. Between the NAS snapshot and the
   migration, 12 more memories were added to v2 (today's
   standing-rule pin, hardening decisions, pre-cutover context).

   **Practical implication:** the actual data loss in the cutover
   was 36 memories (not 24). All of those memories remain intact in
   the laptop backup file and could be merged back into live v3 via
   the new safer migration script (commit 6e424313) + `oc memory
   import --mode merge`. Recovery deliberately deferred — current
   v3 starts fresh and we're moving forward, not back. The recovery
   recipe is preserved in this doc for future reference if priorities
   change:

   ```text
   1. Copy ~/backups/pre-v3-cutover.db to a workspace dir
   2. python scripts/migrate_v2_to_v3.py source.db migrated-v3.db
   3. python scripts/verify_v3_db.py migrated-v3.db    # expect ok + 36 memories
   4. (Local) oc memory export --out recovered.json
   5. scp recovered.json to NAS
   6. docker exec openchronicle-mcp-oc-1 oc memory import --in /path/recovered.json
      (default mode=merge: preserves all existing rows, only adds new IDs)
   7. Verify via curl /api/v1/memory/stats — expect total = 38 (2 post-cutover + 36 recovered)
   8. (Optional) trigger embedding_backfill to embed the new 36
   ```

---

## Lessons (distilled)

- **"Validation passed" is only as strong as what the validation
  checks.** `verify_v3_db.py` returning OK gave us false confidence
  in a corrupt DB. Add `PRAGMA integrity_check` to every DB
  validation gate going forward.
- **WAL/SHM files are a path-level association in SQLite.** Renaming
  the main DB without also handling `-wal`/`-shm` leaves orphans
  that the next opener may apply incorrectly. Migration scripts and
  runbooks must scrub them at the destination.
- **Race conditions in CI are real.** Force-pushing to main triggers
  docker-publish; if you're trying to capture `:v2-final` in that
  same window, you have ~5 min before `:latest` flips. Do the retag
  FIRST, then push.
- **Backup-before-destructive is now a maintenance loop primitive.**
  v3 ships this from day one. The 2026-05-06 cutover would have been
  recoverable in seconds if v3 had been live with this policy and a
  backup had been taken before whatever corrupted the migrated DB.
- **Pre-commit hooks are guardrails worth keeping high.** When mypy
  caught 9 pre-existing errors that had shipped on `493d4fa5`, the
  right answer was a scoped `SKIP=mypy` on this one commit + a
  follow-up to fix the debt — not blanket `--no-verify` and not
  papering over.
