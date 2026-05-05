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
| `db_backup` | 1 day | Online backup via `sqlite3.Connection.backup()` to `${OC_DATA_DIR}/backups/auto/`; retains the last 7 by mtime |
| `db_vacuum` | 7 days | Runs `db_backup` first (backup-before-destructive policy enforced in code), then `PRAGMA wal_checkpoint(FULL)` and `VACUUM` |
| `db_integrity_check` | 7 days | `PRAGMA integrity_check`. On failure: emergency `db_backup`, sets `container.maintenance_degraded = True` (surfaces via `/health`), raises so the loop counts it. On success: clears any prior degraded flag. |
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

Unknown job names in config are silently dropped (typo-safe). Missing
section falls back to the defaults above.

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

## Status surface

```bash
# CLI
oc maintenance list              # show jobs + intervals + enabled state
oc maintenance run-once db_backup

# HTTP
GET /api/v1/maintenance/status
```

Status payload per job:

```json
{
  "name": "db_backup",
  "interval_seconds": 86400,
  "enabled": true,
  "last_run_at": "2026-05-05T14:00:00+00:00",
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
