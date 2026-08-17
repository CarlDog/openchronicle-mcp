# Changelog

Release history for OpenChronicle v3. One entry per Docker-tagged
release; the deployed release is whichever tag the Portainer stack's
`OC_TAG` env points at. Created 2026-08-16 (review Batch E),
reconstructed from the status-doc revision addenda for rc1-rc5.

## Unreleased (on main since rc6)

Review Batch E (docs SSOT + test debt) plus the post-review polish
batch; 563 → 591 tests.

- **Error honesty:** a wrong `project_id` on memory_save answers 404
  "Project not found" instead of a raw FK-constraint 500; malformed
  `created_at` answers 422 with an ISO 8601 hint on both surfaces;
  `memory_get`'s 404 carries the `code` field like its siblings;
  MCP `project_update` with neither field raises the 422-mapped
  validation error instead of a bare store ValueError; Ollama
  connection-refused reports `CONNECTION_ERROR`, not `TIMEOUT`.
- **Parity by construction:** the health payload and the embed outcome
  mapping each live in one shared builder instead of verbatim copies
  per surface.
- **Ops:** `oc memory import` is transactional (a bad row rolls back
  the whole restore instead of half-applying); the rate limiter sweeps
  idle clients' expired windows (slow leak fixed).
- Removed the dead `oc onboard git --no-llm` flag.

- The v2 documentation archive `docs/archive/v2/` actually exists now —
  Phase 7's move had been silently swallowed by a v2-era `.gitignore`
  rule; restored from the `archive/openchronicle.v2` branch.
- The status doc is a current-state snapshot (this CHANGELOG absorbed
  its release narrative); V3_PLAN declares which sections are live;
  CLAUDE.md's sprint holds only in-flight work.
- Test debt: end-to-end CLI smoke pass (the surface was ~80% untested);
  handler tests for the six uncovered MCP tools incl. `memory_embed`'s
  outcome mapping at both surfaces; structural guards (all tools are
  coroutines, `confirm` stays default-free on project deletes,
  unconditional `mcp` import so a failed pin resolve can't silently
  skip the suite); mock containers stopped fabricating v2 attributes.

## v3.0.0-rc6 — 2026-08-16

The 2026-08-15 full-repo review, Batches A-D (~40 findings fixed;
510 → 563 tests). First release where `health.package_version` reports
the real version.

- **Search correctness:** hybrid search honors `include_pinned=False`
  (pinned rows no longer re-enter via the semantic channel); the
  embeddings `dimensions` column records the actual vector length and
  reads unpack by blob length (healing poisoned rows); semantic search
  is scoped to the active embedding model (stale-model rows no longer
  crash the matmul or corrupt ranking cross-space).
- **`context_recent`** with no query now lists recent items instead of
  searching `""` (which returned pinned-only on FTS5 deployments);
  REST search rejects empty queries (422) for MCP parity.
- **`onboard_git` robustness:** watermark anchors the ancestry head
  (`commits[0]`), not max author date; unreachable watermarks
  auto-fall-back to a full walk (memories kept, `watermark_unreachable`
  flagged) instead of a raw git error; new `branch` param with the
  resolved branch + head SHA echoed on every response; CLI and MCP
  share one orchestration (`onboard_git_prepare`) — the CLI now saves a
  watermark and runs incrementally. Breaking:
  `extract_commits_from_url` returns `ExtractedHistory`;
  `run_git_onboard_raw` → `materialize_clusters`.
- **Transport & security:** stateless streamable-HTTP (no
  session-per-abandoned-client leak); Host-header allowlist on the REST
  surface (`OC_API_ALLOWED_HOSTS`, falling back to
  `OC_MCP_ALLOWED_HOSTS`) closing the DNS-rebinding gap `/mcp` was
  already guarded against.
- **Config honesty:** empty env vars fall through to `core.json`
  everywhere (compose `${VAR:-}` injection was silently shadowing file
  config); six previously Portainer-unreachable vars added to compose;
  four remaining crash-loop startup paths fail soft with a warning.
- **Ops:** maintenance job schedule persists across restarts
  (`maintenance_state.json`); backup retention keeps newest-7 ∪
  newest-per-day×7 so same-day bursts can't evict older days;
  Dockerfile dependency layer survives source edits.
- **Release integrity:** Python floor declared `>=3.14` (it already
  was, de facto); version single-source moved to `3.0.0rc6` with a CI
  tag↔version guard; `oc init-config` (a v2 zombie writing config v3
  never read) deleted; README quick starts fixed.

## v3.0.0-rc5 — 2026-07-24

Read-surface + delete-safety batch (433 → 510 tests; 17 → 18 tools),
plus the 2026-07-02 hardening batch. Driven by three dogfooding
memories.

- Required `confirm` on `memory_delete` / `project_delete` (omission
  raises / 422s instead of returning a success-shaped preview).
- Project-scoped `memory_list`; `name_contains` on `project_list`;
  opt-in `compact` projection across the read surface.
- Bounded, honest `onboard_git` cluster detail
  (`max_commits_per_cluster`, `include_commit_detail`, chronological
  presentation, `Showing: n of N`); watermark advances past
  filtered-out HEADs.
- New `project_delete_bulk` (per-item reporting, all-or-nothing
  durability).
- `health` gains `package_version`, `schema_version`,
  `maintenance_degraded`, `fts5_active`; `oc version` fixed (looked up
  the wrong distribution name).
- From 2026-07-02: SQLite connection serialized behind an RLock; all
  MCP tools async with `asyncio.to_thread`; git-onboard multi-line
  body fix + clone-URL transport allowlist.

## v3.0.0-rc4 — 2026-05-11

- Rate-limit default raised 120 → 600 RPM (mnemosyne burst incident).
- Full project CRUD (`project_get`/`project_update`/`project_delete`
  with preview/confirm) across port, use cases, REST, MCP, CLI;
  symmetric `confirm` flag added to `memory_delete`. 17 tools.

## v3.0.0-rc1 / rc2 / rc3 — 2026-05-06

Phase 8 NAS cutover day (turbulent — full account in
[docs/cutover-2026-05-06-triage.md](docs/cutover-2026-05-06-triage.md)).

- rc1: first v3 image live on stack 151; the migrated v2 DB arrived
  corrupt and v3 restarted against a fresh volume (36 v2 memories not
  carried forward; v2 DB preserved on disk).
- rc2: MCP transport fixes — mount path-doubling and the
  `OC_MCP_ALLOWED_HOSTS` Host-header allowlist (421 gotcha).
- rc3: senior-dev review batch — numpy vectorized semantic search
  (~265x), API consistency cleanups, ruff backlog cleared, real MCP
  initialize handshake in the smoke test.

## Pre-release

v3 phases 0-7 (the v2 → v3 slimming: interfaces, application,
infrastructure/domain, migration framework, ASGI unification,
maintenance loop, docs sweep) are chronicled in
[docs/V3_PLAN.md](docs/V3_PLAN.md). The v2 era is frozen at
`archive/openchronicle.v2` and documented in
[docs/archive/v2/](docs/archive/v2/README.md).
