# Design Decisions

Durable design rationale for core OpenChronicle v2 subsystems.

## Attempt Tracking

Each task execution generates a unique `attempt_id` (uuid4 hex) threaded
through all lifecycle events (`task.started`, `task.completed`, `task.failed`,
`llm.execution_recorded`). This enables distinguishing multiple execution
attempts of the same task for future retry/resume logic.

**Event schemas:**

- `task.started` payload: `{ "attempt_id": str }`
- `task.completed` payload: `{ "result": ..., "attempt_id": str }`
- `task.failed` payload: `{ "exception_type": str, "message": str, "attempt_id": str }`

**Replay behavior:**

- Tracks `dict[task_id, list[TaskAttempt]]`
- Latest attempt determines task status
- Backward-compatible: old events without `attempt_id` use `event.id` as fallback

**Design principles:**

- Deterministic (time-based creation order)
- Crash-safe (replayed from persisted events, no in-memory state)
- Minimal (no new persistence tables; uses existing event log)
- Focused (tracking only; does not affect execution semantics)

## Budget Enforcement

Budget enforcement uses replay-derived usage to prevent LLM execution when
constraints are exceeded.

**Domain model:** `BudgetPolicy` with optional `max_total_tokens` and
`max_llm_calls` constraints.

**`budget.blocked` event payload:**

```text
reason:           "max_llm_calls" | "max_total_tokens"
policy:           { max_total_tokens, max_llm_calls }
current_usage:    { total_llm_calls, total_tokens }
projected_tokens: int (estimated tokens for attempted call)
```

**Usage derivation:**

- Counts `llm.execution_recorded` events as authoritative execution records
- Extracts `total_tokens` from payloads; falls back to
  `prompt_tokens + completion_tokens`
- Crash-safe: results depend only on event log

**Explicit-blocking principle:** No silent degradation. When budget is exceeded,
the system emits `budget.blocked` and raises `BudgetExceededError`. Blocks are
terminal and visible.

## Verification Semantics

Verification is orthogonal to execution. A completed task can have failed
verification (code compiles but tests fail), and a failed task can be verified
(error handling worked correctly).

**`VerificationStatus` enum:** `NOT_VERIFIED`, `VERIFIED`, `FAILED`

**Event schemas:**

- `task.verified` payload:
  `{ "attempt_id": str, "verification_type": str, "reason": str | None }`
- `task.verification_failed` payload:
  `{ "attempt_id": str, "verification_type": str, "reason": str | None }`

**Design principles:**

- Explicit and event-driven (never implicit)
- Per-attempt tracking with latest-event-wins semantics
- Deterministic replay (same events produce same state)
- Foundation only: no actual verification logic (pytest, linting) included

## Diagnose Enhancement

The `oc diagnose` command provides config-first provider troubleshooting.

**Model config discovery:**

- Scans `<OC_CONFIG_DIR>/models/*.json`
- Reports per-provider statistics: enabled/disabled count, API key
  set/missing count
- Deterministic ordering (sorted by filename)
- Defensive error handling (diagnose never crashes)

**`DiagnosticsReport` extensions:**

- `models_dir`, `models_dir_exists`
- `model_config_files_count`
- `model_config_provider_summary` (per-provider stats)
- `model_config_load_errors` (parse errors without content leakage)

**Config-first provider hints:** Primary guidance points to
`<OC_CONFIG_DIR>/models/<provider>_*.json`; env var setup marked as "legacy".

**Secret safety:** API key values never appear in output. Only reports "set" or
"missing" with counts.
