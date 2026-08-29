# Maintenance loop

OpenChronicle v3 runs a single in-process asyncio loop alongside the
ASGI app. Every tick (default 1 second) it checks each configured job's
schedule and dispatches due work as a background task. The loop is
slim by design: no DB-backed queue, no manager/worker, no atomic
claim. v3 has one process and a shared SQLite file — the v2 scheduler
was overkill.

## Default jobs

| Job | Default interval | What it does |
|---|---|---|
| `db_backup` | 1 day | Online backup via `sqlite3.Connection.backup()` to `${OC_DATA_DIR}/backups/auto/`; retention keeps the union of the 7 newest files and the newest file per day for the 7 most recent days with backups (a same-day burst can't evict older days) |
| `db_vacuum` | 7 days | Runs `db_backup` first (backup-before-destructive policy enforced in code), then `PRAGMA wal_checkpoint(FULL)` and `VACUUM` |
| `db_integrity_check` | 7 days | `PRAGMA integrity_check`. On failure: emergency `db_backup`, sets `container.maintenance_degraded = True` (surfaces via `/api/v1/health` and the MCP `health` tool), raises so the loop counts it. On success: clears any prior degraded flag. |
| `embedding_backfill` | 6 hours | Equivalent to `oc memory embed`; no-op when the embedding service is unset or nothing is missing |
| `git_onboard_resync` | 1 hour, OFF by default | Placeholder. Full implementation lands when the tracked-repo list spec is finalized. |

## Configuration

`core.json` `maintenance` section:

```json
{
  "maintenance": {
    "jobs": [
      {"name": "db_vacuum",          "interval_seconds": 604800, "enabled": true},
      {"name": "db_integrity_check", "interval_seconds": 604800, "enabled": true},
      {"name": "embedding_backfill", "interval_seconds": 21600,  "enabled": true},
      {"name": "db_backup",          "interval_seconds": 86400,  "enabled": true},
      {"name": "git_onboard_resync", "interval_seconds": 3600,   "enabled": false}
    ]
  }
}
```

**The `jobs` list MERGES onto the defaults — it does not replace them.**
An entry overrides the matching default *by name*; every job it does not
mention keeps its default interval and enabled state, and jobs added in
future releases appear automatically even against an older config file.
So a config that tunes one interval is safe:

```json
{"maintenance": {"jobs": [{"name": "db_backup", "interval_seconds": 43200}]}}
```

leaves `db_vacuum`, `db_integrity_check`, `embedding_backfill` and
`git_onboard_resync` exactly as shipped.

**Omitting a job does NOT disable it.** Set `"enabled": false` explicitly
— the same way the example expresses "off" for `git_onboard_resync`.

Ordering always follows `_DEFAULT_JOBS` in code — `db_vacuum`,
`db_integrity_check`, `embedding_backfill`, `db_backup`,
`git_onboard_resync` — not the file, and not the reading order of the
table above, which groups by topic. So the status surface is stable
however the JSON is arranged. Unknown job names are
skipped with a warning (typo-safe); a missing `maintenance` section falls
back to the defaults.

This was a total replacement until 2026-08-28, which cost jobs two ways:
tuning one interval meant hand-copying every other job or losing it
(including `db_backup`), and because the entrypoint seeds `/config` from
the image's `core.json.example` ONCE — `cp -rn` plus a `.bootstrapped`
marker mean it is never refreshed on upgrade — an operator who
bootstrapped `core.json` from that example would have dropped every job
added in any later release — silently, since the loop only ever
warned about *unknown* names, never missing ones.

`OC_MAINTENANCE_DISABLED=1` (or `true`/`yes`/`on`) short-circuits the
loop entirely. Useful for tests, one-shot CLI invocations, and
migration windows.

## Concurrency contract

- **Per-job lock** detects cross-tick overlap. If tick N+1 wakes while
  job's lock is still held from tick N, the new tick records
  `runs_skipped_overlap` and moves on. No queueing.
- **Global lock** serializes all jobs across the process. Two jobs
  never run concurrently. This is the guarantee that a vacuum + a
  backfill can't race the same DB.
- **Failure isolation**: handler exceptions are logged + counted on the
  job's `runs_failed` and `last_error`, never crash the loop.

The combination produces "sequential within process, skip on overlap"
semantics — what the V3 plan calls for.

## Schedule persistence

Two per-job timestamps persist to `maintenance_state.json` next to the
DB (atomic tmp + replace, written after every job run). Counters
(`runs_total` etc.) stay per-process; only these survive a restart.

`last_run_at` exists so a container restart doesn't make every enabled
job due at once — that cost two backups per restart under the
redeploy-on-push deployment model, eroding the backup retention window
to same-day snapshots (2026-08-15 review).

`last_success_at` exists for the opposite reason. It advances only on a
run that completed without raising, and a later failure never clears
it, so it answers **"when did this job last actually work"** — the one
question a silently-failing job cannot fake, since `last_run_at` keeps
advancing forever on a job that raises every time. It is persisted
specifically because every push to main bounces this container: an
in-process-only marker would let a job that has been failing for weeks
present a clean surface after each redeploy. On a successful run both
timestamps come from a single clock read and are exactly equal.

A corrupt or missing state file degrades to pre-persistence behavior
with a warning — it can never block boot. Each block is parsed
independently and per-entry, so a state file written before
`last_success_at` existed loads fine (the block is simply absent), and
one unparseable value costs that job that one timestamp rather than
taking the file, the job's other timestamp, or another job with it.

## Status surface

```bash
# CLI
oc maintenance list              # show jobs + intervals + enabled state
oc maintenance run-once db_backup

# HTTP
GET /api/v1/maintenance/status
```

**`oc maintenance run-once` bypasses the loop.** It calls the handler
directly, so it takes no global lock, increments no counters, and
advances neither timestamp — a manual run is invisible to the status
surface and to any staleness check built on it. That is fine for its
purpose (an operator watching console output) but it means "nothing has
run for 48 hours" stays true even if you just ran one by hand.
`MaintenanceLoop.run_once` is the full-machinery path and currently has
no production callers.

Status payload per job:

```json
{
  "name": "db_backup",
  "interval_seconds": 86400,
  "enabled": true,
  "last_run_at": "2026-05-05T14:00:00+00:00",
  "last_success_at": "2026-05-05T14:00:00+00:00",
  "last_outcome": "ok",
  "last_error": null,
  "runs_total": 12,
  "runs_ok": 12,
  "runs_failed": 0,
  "runs_skipped_overlap": 0
}
```

`/api/v1/health` carries `maintenance_degraded` so operators can detect
an integrity-check failure without polling the dedicated endpoint.

## Embedding degradation policy

Independent of the loop but related: when `EmbeddingService.search_hybrid`
makes a semantic-search call and the provider raises, the service
catches the exception, falls back to FTS5-only results, increments
`search_failure_count`, and records `last_failure_at`. The next
successful semantic search resets the counter.

`container.embedding_status_dict` reports:

| Field | When |
|---|---|
| `status: "active"` | provider configured + most recent search succeeded |
| `status: "degraded"` | provider configured + at least one recent failure |
| `status: "disabled"` | `OC_EMBEDDING_PROVIDER=none` (default) |
| `status: "failed"` | adapter init failed at startup; FTS5-only |

`/api/v1/health` and the MCP `health` tool both return this shape, so
clients see degradation cleanly without parsing logs.

### Classified permanent outcomes (ADR 0009)

An upstream rejection classified as `CONTENT_TOO_LONG` (the content
exceeds the embedding model's context) is a designed outcome, not
degradation: NO failure counter moves — not on save, not on backfill,
and not for an over-length *query* (caller content, keyword-only
results). The row parks as a `status='content_too_long'` tombstone and
stops being retried; a backfill run reports parked rows in the
`tombstoned` count (neither `generated` nor `failed`), and the
`embedding_backfill` job treats a tombstoned-only run as a success.

### Coverage-field relationships

`embedding_status` coverage fields, after ADR 0009's tombstones:

- `embedded` = rows with `status='ok'` (real vectors, current or stale).
- `unembeddable` = CURRENT tombstones only — identity **and** content
  hash match the active space. It clears on its own when the content
  is shortened or the model/provider changes; `force=true` retries.
- `missing` = total memories − ALL rows (a tombstone is known, not
  missing).
- `stale` = `space_mismatch` + `content_mismatch`, counting
  regeneration work **regardless of row status**: a NON-current
  tombstone is a genuine backfill candidate and lands in these
  buckets.

Consequences worth stating so nobody re-derives them wrong:
`stale ⊆ embedded` **no longer holds** (a non-current tombstone is in
a stale bucket but not in `embedded` — after a provider switch a
corpus with 9 parked rows reads `embedded: 863, stale: 872`). The
invariants that DO hold are `embedded + tombstones = total rows` and
`missing = total memories − total rows`. Health fields legitimately
overlay (an ok-but-stale row is in `embedded` AND a stale bucket);
the underlying ROW classes partition cleanly: every
`memory_embeddings` row is exactly one of {`status='ok'`, current
tombstone, non-current tombstone}.

## Tests

- `tests/test_maintenance_loop.py` — loop semantics (overlap-skip,
  disabled jobs, status snapshot, env-var opt-out, config loading,
  retention prune)
- `tests/test_embedding_degradation.py` — FTS5 fallback path, counter
  reset on recovery, container status reporting

## Source

- `application/services/maintenance_loop.py` — `MaintenanceLoop`,
  `JobState`, `load_jobs`, `is_disabled`
- `infrastructure/maintenance/jobs.py` — handler implementations
- `interfaces/api/app.py` — lifespan integration
- `interfaces/api/routes/system.py` — `/api/v1/maintenance/status`
- `interfaces/cli/commands/maintenance.py` — `oc maintenance ...`
