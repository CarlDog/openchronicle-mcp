# OpenChronicle v3 — Memory-Only Rewrite Plan

**Status:** **SHIPPED 2026-05-06.** v3 is live on the NAS at
`http://your-nas:18000` (HTTP `/api/v1/*`, MCP `/mcp`). This document
is historical reference for the design decisions and phase plan —
**except two sections that are declared LIVE and receive updates**
(the ambiguity was a 2026-08-15 review finding: the freshest state was
accumulating in a doc that disclaimed being current):

- **"Post-cutover follow-ups (tech debt)"** — the project backlog.
- **"Open Questions" 20-22** — active research threads.

Current state lives in
[CODEBASE_ASSESSMENT.md](CODEBASE_ASSESSMENT.md); releases in
[CHANGELOG.md](../CHANGELOG.md).
**Branch:** `main` (force-pushed from `v3/develop` during Phase 8 cutover).
**v2 archive:** `archive/openchronicle.v2` at `bb217d9` (frozen, immutable).
**Cutover artifacts:** Docker image `:v3.0.0-rc1`; rollback target
`:v2-final` (= `bb217d9`); cutover triage at
[docs/cutover-2026-05-06-triage.md](cutover-2026-05-06-triage.md) for
the actual lived experience vs. the planned sequence below.

## Phase Tracker

| Phase | Status | Notes |
|---|---|---|
| 0 — branch creation | ✅ done (2026-05-05) | `archive/openchronicle.v2` + `v3/develop` |
| 1 — interfaces slimmed | ✅ done (2026-05-05) | 173 files, 264+/35,460-; 570 tests passing |
| 2 — application slimmed | ✅ done (2026-05-05) | container/services/use_cases/dirs/plugins; 345 tests passing |
| 3+4 — infrastructure + domain slimmed | ✅ done (2026-05-05) | combined commit; sqlite_store 1882→470 LOC; schema 18→3 tables; `conversation_id` dropped from MemoryItem; `ProviderError` replaces `LLMProviderError`; 294 tests passing |
| 5 — schema migration + framework + online backup + export/import | ✅ done (2026-05-05) | versioned migrator (savepoint atomicity, idempotent), 001_initial.sql, online backup module (atomic .tmp→rename), `oc memory export/import`, `scripts/migrate_v2_to_v3.py` + `verify_v3_db.py`; 323 tests passing |
| 6 — ASGI unification + `OC_LOG_FORMAT` | ✅ done (2026-05-05) | FastMCP mounted at `/mcp`; single ASGI process; `OC_LOG_FORMAT=human` or `json` (Q19 locked); compose 3→1 service; 331 tests passing |
| 6.5 — maintenance loop + degradation | ✅ done (2026-05-05) | asyncio loop with per-job + global locks (skip-on-overlap, sequential within process), 5 job handlers (db_backup/db_vacuum/db_integrity_check/embedding_backfill/git_onboard_resync), `/api/v1/maintenance/status` endpoint, `oc maintenance` CLI, embedding-failure FTS5 fallback with `degraded` status surfacing; 349 tests passing |
| 7 — docs sweep + repo polish | ✅ done (2026-05-05) | every doc classified (update/archive/delete); v2 docs moved under `docs/archive/v2/`; new STABILITY.md, security_posture.md, MAINTENANCE.md; README rewritten per voice rules; pyproject 3.0.0.dev0 with dead extras dropped; 349 tests passing |
| 8 — production cutover | ✅ done (2026-05-06) | NAS stack 151 live on the v3 image (turbulent — see cutover-2026-05-06-triage.md); this row said "pending" until 2026-08-16, contradicting the SHIPPED header above |
| 9 — decommission | ✅ done (2026-08-28) | `v3.0.0` tagged; STABILITY.md's pre-tag escape hatch removed as it instructed; two genuinely dangling v2 volumes deleted (`oc-assets`, `oc-user-plugins`). The Day-7 list was CORRECTED before execution — it would have deleted the live stack 151 and the in-use `oc-output` volume |

**Locked decisions** (questions 1, 4, 6, 13, 14, 19 from "Open Questions"):

- ✅ Drop `memory_items.conversation_id` (Phase 5 schema work)
- ✅ Unified ASGI on port `:18000` (Phase 6)
- ✅ Cut plugin system entirely (done in Phase 2)
- ✅ MCP tool description quality pass (done in Phase 1)
- ✅ Ship `oc memory export/import` day 1 (Phase 5)
- ✅ `OC_LOG_FORMAT=human|json`, default human (Phase 6)

---

## TL;DR

- **v3 scope:** OC becomes the best memory database for LLM agents. Nothing else.
- **What goes:** conversation engine, all 5 LLM adapters, MoE, privacy gate, storytelling plugin, webhooks, assets, media, Discord, the v2 scheduler/orchestrator/manager-worker stack, ~1600 tests.
- **What stays:** memory + embeddings + projects + git-onboard + the two transports (MCP and HTTP REST) + a **minimal in-process maintenance loop** for DB hygiene and recurring sync jobs.
- **Architectural change:** fold MCP and HTTP into a single ASGI process / single container / single port.
- **Preservation strategy:** everything cut moves to `archive/openchronicle.v2`. No code is lost. Future projects (e.g. `narrator-mcp` if storytelling is revived) reach back into the archive.
- **Branch strategy:** mirrors v1→v2 transition. Develop on `refactor/v3-memory-core`, replace `main` when ready, archive v2 on its own branch.
- **Hardening pass baked in:** schema migration framework, backup-before-destructive-maintenance, SQLite online backup API, CI migration tests, explicit embedding-failure degradation policy, curated OpenAPI as the default surface. See "Hardening" section below.

---

## Strategic Intent

OpenChronicle today bundles four concerns: memory backend, conversation engine, storytelling extension, and orchestration/admin. The session that produced this plan (2026-05-02) confirmed that on the deployed NAS instance:

- **Webhooks:** zero subscriptions. Subsystem is dormant.
- **Storytelling:** not in active use.
- **Conversation engine:** dormant — `oc chat` is local-only, Discord is no-op (no token), `conversation_ask` is explicitly forbidden by CLAUDE.md, and the OWUI integration that would have driven it was reverted same-day.
- **Memory + embeddings:** actively used by every Claude Code session, every CLI invocation, every MCP-aware client.

This codebase is paying maintenance cost for ~70% of its surface that has no consumers. The lean answer is to cut it. v3 is the clean-room rewrite that carries forward only the value-dense subsystems.

The user's stated direction (multiple sessions): "OC stays lean, becomes the best at what it does." That thing is memory.

---

## Target Architecture

### Process model

- **Single ASGI process** hosting both transports.
- FastAPI as the host application.
- FastMCP mounted as an ASGI sub-app at `/mcp`.
- One Docker container, one port (default `:18000`, MCP at `/mcp`, REST at `/api/v1/*`, liveness at `/health`).
- The deployed NAS stack (`openchronicle-mcp`, stack 151) goes from 3 services (`serve`, `mcp`, `discord`) to **1 service**.

### Layers (hexagonal, slimmed)

```text
interfaces/                  CLI + ASGI app (FastAPI host)
  ↓
application/                 use cases + embedding service + git-onboard
  ↓
domain/                      MemoryItem, Project, ports
  ↑
infrastructure/              SQLite store + embedding adapters
```

### Tool surface

**MCP tools (~12, down from 32):**

- `memory_save`, `memory_search`, `memory_list`, `memory_get`, `memory_update`, `memory_delete`, `memory_pin`, `memory_stats`, `memory_embed`
- `project_list`, `project_create`
- `context_recent` (memory + git-onboard catch-up; no turn data)
- `health`
- `onboard_git` (memory generator from git history)

**HTTP REST endpoints (~15):**

- Memory CRUD + search + embed
- Project list/create
- `/health` (liveness probe, public)
- `/api/v1/health` (full diagnostics — embedding provider status, last maintenance run per job, DB size, last-vacuum age)
- `/api/v1/onboard/git` (mirror of MCP tool)
- `/api/v1/maintenance/status` (per-job last-run timestamp + outcome — see Phase 6.5)
- (NO conversation, NO assets, NO webhooks, NO media, NO stats endpoints)

**OpenAPI surface:** the *single* `/openapi.json` IS the curated surface — no separate `/memory-tools/openapi.json` route like the v2 OWUI integration experiment. The whole API is small enough that filtering is unnecessary; one spec, no mystery routes.

**CLI:**

- `oc memory <save|search|list|get|update|delete|pin|stats|embed>`
- `oc project <list|create>`
- `oc db <info|vacuum|backup|stats>`
- `oc onboard git`
- `oc maintenance <list|run-once>` — inspect configured jobs, manually trigger one (the loop also runs in `oc serve`)
- `oc serve` (starts the unified ASGI app + maintenance loop)
- `oc version`, `oc init`, `oc config show`
- (NO `oc chat`, `oc story <…>`, `oc convo <…>`, `oc asset <…>`, `oc webhook <…>`, `oc media`, `oc ollama`, `oc discord`, `oc scheduler`, `oc selftest`, `oc task`, `oc events`)

---

## Surface Comparison: v2 → v3

| Subsystem | v2 status | v3 fate |
|---|---|---|
| Memory CRUD + search + pin + stats | Working | **Stays, primary feature** |
| Embeddings (FTS5 + cosine via RRF) | Working | **Stays, primary feature** |
| Project namespacing | Working | **Stays** |
| Git-onboard (memory generator) | Working | **Stays** |
| HTTP API (memory routes only) | Working | **Stays, slimmed** |
| MCP server (memory tools only) | Working | **Stays, slimmed, mounted in ASGI** |
| `/health` liveness probe | Just added (2026-05-02) | **Stays** |
| Conversation engine (`ask_conversation` pipeline) | Dormant | **Cut → archive** |
| Conversation modes (general, persona, story) | Dormant | **Cut → archive** |
| 5 LLM adapters (openai, anthropic, groq, gemini, ollama) | Dormant | **Cut → archive** |
| Privacy gate (PII detection) | Dormant | **Cut → archive** |
| MoE consensus | Dormant | **Cut → archive** |
| Hybrid routing (rule + linear ML) | Dormant | **Cut → archive** |
| Hash-chained event audit trail | Implemented but engine-coupled | **Cut → archive** |
| Storytelling plugin | Not in active use | **Cut → archive** |
| Plugin system (mode builders, task handlers) | Implemented for storytelling | **Cut → archive** |
| Webhooks (HMAC signing, dispatcher, retry) | Zero subscriptions | **Delete entirely** (small enough to rebuild) |
| Asset storage + linking | Working | **Cut → archive** |
| Media generation (5 adapters) | Working | **Cut → archive** |
| Scheduler service (tick-driven, atomic claim, `scheduled_jobs` table, multi-worker) | Implemented | **Cut → archive** (orchestrator-coupled; overkill for v3 needs) |
| Maintenance loop (asyncio task, recurring jobs, no DB-backed queue) | Does not exist | **New in v3** — minimal replacement for the maintenance/sync use case |
| Discord interface | Token-gated no-op currently | **Cut → archive** |
| MoE/tool stats tracking | Implemented | **Cut → archive** |
| Manager/worker orchestration | Implemented | **Cut → archive** |

---

## Branch Strategy

Mirrors the v1→v2 pattern documented in CLAUDE.md.

### Step 1: Cut the v2 archive

```bash
# From current main HEAD (will include all of today's bug fixes)
git checkout main
git checkout -b archive/openchronicle.v2
git push origin archive/openchronicle.v2
```

This freezes v2 forever. All cut subsystems live on this branch. Future projects pull from here.

### Step 2: Create the v3 development branch

```bash
git checkout main
git checkout -b refactor/v3-memory-core
```

### Step 3: Develop v3 on the branch

- Delete in waves (interfaces → infrastructure → application → domain — outside-in).
- New code (unified ASGI, schema migration, slimmed Container) lands on this branch.
- Tests trimmed alongside.
- Commit liberally; the branch is the work-in-progress record.

### Step 4: Replace main

When v3 satisfies the "ready to ship" criteria below:

```bash
git checkout main
git reset --hard refactor/v3-memory-core
git push --force-with-lease origin main
```

(Force push is acceptable here per the v1→v2 precedent — same as the OpenAI-compat-layer drop on 2026-04-29.)

### Step 5: Production cutover

- Update Portainer stack 151 with new compose (single service)
- Run schema migration on the deployed DB (via the migration script written during v3 development)
- Verify smoke test (memory + search + onboard) end-to-end
- Delete the `mcp` and `discord` services from Portainer

---

## "Ready to Ship" Criteria for v3

Before v3 replaces main:

1. **All memory + embedding + project + onboard-git tests pass** (unit, functional)
2. **Unified ASGI app serves both transports** — Claude Code reaches MCP, `curl` reaches REST, both work against the same in-process container
3. **Schema migration script** runs cleanly on a copy of the v2 NAS DB and produces a v3-shaped DB with all existing memories at migration time (count varies; ~25+ as of plan v3) preserved, embedded, and searchable
4. **CI migration test passes** — fixture v2 DBs in `tests/fixtures/v2_dbs/` migrate cleanly with invariants asserted (memory count preserved, embeddings still resolve, FTS5 rebuild succeeds, `PRAGMA integrity_check = ok`)
5. **Schema migration framework operational** — `schema_version` table populated, runner applies pending migrations at startup, idempotent re-run is a no-op
6. **Smoke test** — equivalent to today's session walkthrough (memory CRUD, search, embed force-rerun, onboard_git) passes against a v3 instance running locally and against the staged NAS deployment
7. **Online backup verified** — `oc db backup` and maintenance `db_backup` job both produce valid backups while writes are happening concurrently (test exercises this)
8. **Embedding degradation tested** — provider-down scenarios for both search (FTS5 fallback + degraded flag) and save (queued backfill) covered by tests
9. **Maintenance loop runs in-process** — at least one tick of each enabled job observed in logs, `/api/v1/maintenance/status` reports per-job last-run
10. **Single-container compose** (`docker-compose.nas.yml` slimmed to one service) builds and deploys via Portainer redeploy
11. **No regressions** in the existing memories' content or embeddings; **embedding_backfill must have run at least once post-migration** so any v2 memories that lacked embeddings (~22 in the production DB as of 2026-05-02) gain them before search traffic hits
12. **CLAUDE.md updated** to reflect v3 architecture (drop sections about conversation/storytelling/etc.)
13. **Status doc updated** to a new `docs/CODEBASE_ASSESSMENT.md` rev for v3
14. **Full docs sweep complete** — every file in `docs/` and every doc-shaped file at the repo root has been classified (update / archive to `docs/archive/v2/` / delete) and processed; no v2-shaped docs remain in non-archive paths; cross-references all resolve; new docs (`STABILITY.md`, `security_posture.md`, `MAINTENANCE.md`) exist; repo README rewritten; Serena memories audited

---

## Kill List (Concrete)

### Files/directories to remove from v3

#### `src/openchronicle/core/domain/`

- `models/asset.py`
- `models/assist_result.py`
- `models/budget_policy.py`
- `models/conversation.py`
- `models/execution_record.py`
- `models/failure_category.py`
- `models/interaction_hint.py`
- `models/media.py`
- `models/moe_result.py`
- `models/privacy_report.py`
- `models/retry_policy.py`
- `models/scheduled_job.py`
- `models/smoke_result.py`
- `models/verification_status.py`
- `models/webhook.py`
- `ports/asset_store_port.py`
- `ports/conversation_store_port.py`
- `ports/interaction_router_port.py`
- `ports/llm_port.py`
- `ports/media_generation_port.py`
- `ports/plugin_port.py`
- `ports/privacy_gate_port.py`
- `ports/router_assist_port.py`
- `ports/storage_port.py` (refactor into memory_store_port; storage_port is the "everything" port)
- `ports/webhook_store_port.py`

**Keep in domain:**

- `models/memory_item.py`, `models/project.py`, `models/git_commit.py`
- `ports/memory_store_port.py`, `ports/embedding_port.py`
- `exceptions.py`, `time_utils.py`, `errors/`

#### `src/openchronicle/core/application/`

- `services/asset_storage.py`
- `services/llm_execution.py`
- `services/moe_execution.py`
- `services/ollama_service.py`
- `services/orchestrator.py`
- `services/output_manager.py`
- `services/scheduler.py` (replaced by minimal `services/maintenance_loop.py` — see "New Code Required" below)
- `services/webhook_dispatcher.py`
- `services/webhook_service.py`
- `routing/` (entire directory)
- Use cases (everything except memory + project + git-onboard):
  - `ask_conversation.py`, `assemble_context.py` (or simplify), `continue_project.py`, `convo_mode.py`
  - `create_conversation.py`, `delete_webhook.py`, `diagnose_runtime.py` (slim, may keep), `explain_turn.py`
  - `export_convo.py`, `external_turn.py`, `generate_media.py`, `link_asset.py`
  - `list_conversations.py`, `list_webhooks.py`
  - Many more — full audit during execution

**Keep in application:**

- `services/embedding_service.py`, `services/git_onboard.py`, `services/context_builder.py` (slim — memory only, no turns)
- `services/maintenance_loop.py` (NEW — see "New Code Required")
- `config/settings.py`, `config/env_helpers.py`, `config/paths.py` (slim)
- Use cases: `add_memory.py`, `delete_memory.py`, `list_memory.py`, `list_projects.py`, `create_project.py`, `init_config.py`, `init_runtime.py` (slim)

#### `src/openchronicle/core/infrastructure/`

- `llm/` (entire directory — 5 LLM adapters)
- `media/` (entire directory — 5 media adapters)
- `privacy/` (entire directory)
- `router_assist/` (entire directory)
- `routing/` (entire directory if separate from `routing/` above; check)

**Keep in infrastructure:**

- `embedding/` (stub, openai, ollama)
- `persistence/sqlite_store.py` (heavily slimmed — see schema section)
- `persistence/row_mappers.py` (slim)
- `wiring/container.py` (heavy slim — drop LLM/privacy/router/MoE wiring)
- `config/`, `logging/`

#### `src/openchronicle/interfaces/`

- `discord/` (entire directory)
- `api/routes/asset.py`, `api/routes/conversation.py`, `api/routes/hooks.py`
- `api/routes/media.py`, `api/routes/webhook.py`
- `mcp/tools/asset.py`, `mcp/tools/conversation.py`, `mcp/tools/media.py`, `mcp/tools/webhook.py`
- `cli/commands/asset.py`, `cli/commands/conversation.py`, `cli/commands/debug.py`
- `cli/commands/discord.py`, `cli/commands/media.py`, `cli/commands/ollama.py`, `cli/commands/openwebui.py`
- `cli/commands/output.py`, `cli/commands/scheduler.py`, `cli/commands/task.py`, `cli/commands/webhook_cmd.py`
- `cli/commands/mcp_cmd.py` (drop standalone; v3 has unified `oc serve`)

**Keep in interfaces:**

- `api/app.py` (slim — drop conversation/asset/webhook/media/hooks router includes; ADD MCP mount)
- `api/routes/memory.py`, `api/routes/project.py`, `api/routes/system.py`
- `api/middleware/` (auth, rate_limit, CORS — small, useful)
- `mcp/server.py` (slim — drop tool registrations for cut subsystems; refactor to mount in ASGI)
- `mcp/tools/memory.py`, `mcp/tools/project.py`, `mcp/tools/system.py`, `mcp/tools/onboard.py`
- `mcp/tools/context.py` (if context_recent stays; slim)
- `cli/main.py` (slim — drop dropped-command imports)
- `cli/commands/_helpers.py`, `cli/commands/db.py`, `cli/commands/memory.py`, `cli/commands/onboard.py`
- `cli/commands/project.py`, `cli/commands/system.py`, `cli/commands/config.py` (if exists)
- `serializers.py` (slim)

#### `plugins/`

- `storytelling/` (entire directory)
- Plugin system in core (loader, registry, mode builder protocol) — cut.

#### `tests/` — heavy cut

**Keep (~300 tests):**

- `test_embedding_*.py` (4 files: adapters, backfill, port, service, storage, wiring)
- `test_memory_*.py` (5 files: crud_parity, effectiveness, flow, pagination, tag_search, update)
- `test_cli_memory_delete.py`, `test_cli_db.py`, `test_cli_config.py`, `test_cli_json.py`, `test_cli_version.py`
- `test_http_api.py` (slim — drop conversation/asset/webhook/media route tests)
- `test_mcp_tools.py` (slim — drop conversation/asset/webhook/media tool tests)
- `test_mcp_config.py`, `test_mcp_tracking.py` (review; tracking might go)
- `test_no_secrets_committed.py`, `test_no_soft_deprecation.py`, `test_repo_hygiene.py`
- `test_architectural_posture.py` (slim — adjust for v3 layout)
- `test_core_agnosticism.py`, `test_policies_purity.py`
- `test_database_indexes.py`, `test_sqlite_pragmas_and_transactions.py`
- `test_runtime_paths.py`, `test_runtime_init.py`
- `test_config_completeness.py`, `test_config_file_integration.py`, `test_config_loader.py`
- `test_request_id.py`, `test_streaming_telemetry.py` (review)
- `test_store_delete.py`, `test_diagnose.py`
- `tests/integration/` (slim — keep memory+embedding integration scenarios; cut conversation/Discord)

**Cut (~1600 tests):**

- All `test_story_*.py` (10+ files)
- All `test_webhook_*.py` (7 files)
- All `test_asset_*.py` (5 files)
- All `test_discord_*.py` (7 files)
- All `test_moe_*.py` (3 files)
- All `test_task_*.py`, `test_scheduler_*.py`, `test_orchestrator_*.py`
- `test_conversation_flow.py`, `test_convo_*.py`, `test_ask_async.py`, `test_remember_turn.py`
- `test_llm_*.py` (3 files), `test_provider_*.py` (5 files), `test_smart_routing.py`
- `test_router_assist.py`, `test_predictor_seam.py`, `test_routing_discipline.py`, `test_provider_routing_enforcement.py`
- `test_privacy_*.py` (4 files), `test_allow_pii_override.py`
- `test_media_generation.py`, `test_ollama_service.py`
- `test_plugin_*.py` (6 files)
- `test_explain_turn.py`, `test_export_convo.py` (if exists)
- `test_continue_project.py`, `test_replay_project.py`, `test_resume_project.py`
- `test_atomic_execution_and_recovery.py`, `test_attempt_tracking.py`, `test_task_*` (many)
- `test_introspection.py`, `test_metrics.py`, `test_observability_events.py`
- `test_protocol_*.py`, `test_rpc_oneshot.py`, `test_serve_stdio.py`, `test_stdout_purity.py`
- `test_runnable_task_types_guard.py`, `test_smoke_live.py` (in integration/), `test_selftest_*.py`
- `test_openai_integration.py`, `test_openwebui_cli.py`
- `test_smart_routing.py`, `test_router_assist.py`
- `test_provider_setup.py`, `test_provider_facade_config_resolution.py`, `test_provider_registry.py`, `test_provider_wiring.py`, `test_provider_cli.py`
- `test_time_context.py` (review — might keep simplified)
- `test_verification_*.py`, `test_project_verification.py`
- `test_actionable_provider_errors.py`
- `test_acceptance_command.py`
- `test_budget_gate.py`
- `test_diagnose_model_configs.py`
- `test_pass_b_operational.py`
- `test_docs_contract_consistency.py` (rebuild for v3)
- `test_domain_exceptions.py` (review)
- `test_failure_category.py` (cut)
- `test_retry_policy.py` (cut)
- `test_runtime_paths.py` (review)

**Mark as needs-rebuild on v3:**

- `test_architectural_posture.py` — boundaries change with new layout
- `test_hexagonal_boundaries.py` — same
- `test_repo_hygiene.py` — file inventory changes
- `test_docs_contract_consistency.py` — docs change

#### Docs

**Keep + update:**

- `docs/CODEBASE_ASSESSMENT.md` — fully rewritten for v3
- `docs/architecture/ARCHITECTURE.md` — fully rewritten for v3
- `docs/cli/commands.md` — slimmed to v3 commands
- `docs/configuration/env_vars.md` — slimmed
- `docs/integrations/mcp_server_spec.md` — slimmed to memory-only spec
- `docs/V3_PLAN.md` — this doc (preserved as historical record post-v3)

**Cut:**

- `docs/architecture/PLUGINS.md`
- `docs/design/design_decisions.md` (rewrite for v3 decisions only, OR keep as v2 archive reference)
- `docs/protocol/stdio_rpc_v1.md` (RPC layer goes)

---

## Schema Changes (SQLite)

### Tables to drop

- `tasks`, `events`, `attempts`, `spans`, `task_results`
- `conversations`, `turns`, `turn_search` (FTS5)
- `assets`, `asset_links`
- `webhook_subscriptions`, `webhook_deliveries`
- `scheduled_jobs`
- `mcp_tool_calls`, `moe_runs` (telemetry tables)
- `git_onboarding_state` — KEEP (incremental watermark for git-onboard)

### Tables to keep (with possible slimming)

- `projects` (id, name, metadata, created_at)
- `memory_items` (everything; the conversation_id column becomes opaque session metadata or gets dropped — see open question)
- `memory_search` (FTS5) — generated from memory_items via triggers
- `memory_embeddings` (BLOB storage, FK to memory_items with CASCADE)

### Migration script (`scripts/migrate_v2_to_v3.py`)

1. Read v2 DB read-only
2. Create new v3-shaped DB next to it (or in tmpdir)
3. Copy `projects` table
4. Copy `memory_items` (preserving conversation_id IF we keep that column)
5. Copy `memory_embeddings` (FK should still resolve — same memory IDs)
6. Drop v2 tables that didn't get carried over
7. Run `PRAGMA integrity_check`
8. `VACUUM`
9. Atomic rename

Test against a copy of the live NAS DB before deploying.

---

## New Code Required

### 1. Unified ASGI app

- `interfaces/api/app.py` — slim, plus mount FastMCP at `/mcp`
- Verify FastMCP's `streamable_http_app()` returns an ASGI-compatible app that mounts cleanly under FastAPI
- Single uvicorn entry point in `oc serve`
- Health: `/health` (liveness, public, fast) + `/api/v1/health` (readiness, full diagnostics)

### 2. Slimmed Container

- `infrastructure/wiring/container.py` — drop LLM/privacy/router/MoE/scheduler/webhook/media/asset wiring
- Becomes: storage, embedding service, runtime paths, http config

### 3. Schema migration script (one-shot v2→v3)

- `scripts/migrate_v2_to_v3.py` (per above)
- Companion `scripts/verify_v3_db.py` for post-migration checks

### 4. Schema migration framework (forward-compat for v3.x)

The v2→v3 migration is a one-off. Once v3 ships, the schema *will* evolve again (cloud backup adds tables, embedding format may change, etc.) and we currently have nothing to lean on — schema setup happens ad-hoc inside `sqlite_store.py` init. v3 establishes a versioned migration runner so future schema changes are safe and auditable.

**Shape:**

- `infrastructure/persistence/migrations/` — directory of numbered SQL files (`001_initial.sql`, `002_add_maintenance_history.sql`, ...)
- `schema_version` table (single row: `version INT`, `applied_at TIMESTAMP`)
- Runner in `infrastructure/persistence/migrator.py` — applied at startup before any other DB access; reads current `schema_version`, applies pending files in order, records each application
- Each migration is plain SQL (no Python DSL) for grep-ability and readability
- Idempotent: re-running on an up-to-date DB is a no-op
- Failures abort startup with a clear error pointing at the offending migration file

**Why not Alembic?** Overkill. Single-table schema_version + numbered SQL files is ~50 LOC, zero dependencies, no DSL learning curve. If the schema ever gets complex enough that hand-rolled hurts (multiple developers, branching schemas, online schema changes), reconsider.

**Integration with v2→v3 migration:** `migrate_v2_to_v3.py` produces a v3-shaped DB at `schema_version=1`. The migration framework takes over from there.

### 5. Single-service compose

- `docker-compose.nas.yml` — drop `mcp` and `discord` service definitions; `serve` becomes the only service; rename to `oc` for clarity (optional)
- Internal port stays `8000`; host port stays `18000` (operator-friendly continuity)
- `:18001` (MCP) is now `/mcp` path on `:18000`

### 6. New CLI surface

- `oc serve` runs the unified ASGI (current behavior, just with embedded MCP) **and starts the maintenance loop in the same process**
- `oc maintenance list` — print configured jobs and their schedules
- `oc maintenance run-once <job_name>` — manually trigger a single job (for testing or ad-hoc maintenance)
- Drop `oc mcp serve` (no longer separate)
- Drop dropped commands (per kill list)

### 7. Maintenance loop (replaces v2 scheduler)

The v2 scheduler is overkill for v3 — it's a tick-driven, multi-worker job coordinator with atomic claim from the `scheduled_jobs` table, designed to hand work to parallel orchestrator workers. v3 has none of those: one ASGI process, no orchestrator, no manager/worker, no task queue.

What v3 actually needs is "wake up every N minutes, run this function, log the outcome, sleep again." That's `application/services/maintenance_loop.py` — a single asyncio task spawned in the ASGI app's lifespan.

**Day-1 jobs:**

| Job | Default interval | Handler does |
|---|---|---|
| `db_backup` | 1 day | Online backup via `sqlite3.Connection.backup()` to `${OC_DATA_DIR}/backups/auto/`, retains last 7 |
| `db_vacuum` | 7 days | **Triggers `db_backup` first**, then `PRAGMA wal_checkpoint(FULL)` then `VACUUM` |
| `db_integrity_check` | 7 days | `PRAGMA integrity_check`; on failure: triggers immediate `db_backup`, logs error, sets `/api/v1/health` degraded flag, halts further maintenance writes until cleared |
| `embedding_backfill` | 6 hours | Same as `oc memory embed --backfill` — only embeds memories without an embedding row, no-op when none |
| `git_onboard_resync` | (off by default) | Re-runs `onboard_git` for tracked repos when `OC_GIT_ONBOARD_REPOS` is set |

**Design constraints:**

- Pure asyncio, no DB-backed job queue, no multi-worker coordination
- `if not job._lock.locked(): await job.run()` — overlapping ticks skip, don't queue
- Jobs run sequentially within a tick (one at a time) — there's only one OC process and we don't want a vacuum stomping a backfill
- Each job is a coroutine `async def(container) -> None` registered by name; the loop is config-driven, not hardcoded
- Failures are logged + counted but never crash the loop
- The loop is **opt-out**: env var `OC_MAINTENANCE_DISABLED=1` short-circuits it (useful for tests, one-shot CLI invocations, and migration windows)
- **Backup-before-destructive policy:** any job that touches the whole file (`db_vacuum`, future schema migrations applied at runtime) runs `db_backup` first as part of the same job. Lesson from the 2026-04-29 WAL incident: structural writes are the highest-risk moments; cheap insurance is mandatory before them.

**Config shape (in `core.json`):**

```json
{
  "maintenance": {
    "enabled": true,
    "jobs": [
      {"name": "db_vacuum", "interval_seconds": 604800, "enabled": true},
      {"name": "db_integrity_check", "interval_seconds": 604800, "enabled": true},
      {"name": "embedding_backfill", "interval_seconds": 21600, "enabled": true},
      {"name": "git_onboard_resync", "interval_seconds": 3600, "enabled": false}
    ]
  }
}
```

Handler names are a small registry in `application/services/maintenance_loop.py` — a dict mapping `name → coroutine`. Adding a new job is: write the coroutine, register the name, add a config entry. No domain coupling.

**Why not just system cron / Synology Task Scheduler?**

Considered. Two reasons we want it in-process:

1. **Cloud backup (open question 12)** — when that lands, it wants in-process state (memory-write hooks, dirty-flag tracking) that an external cron can't see efficiently
2. **Single-container deployment promise** — telling operators "set up Synology Task Scheduler to call `docker exec` against your container" is friction we shouldn't add

LOC budget: target ~150 LOC in `maintenance_loop.py` + ~50 LOC in `cli/commands/maintenance.py` + ~10 tests covering the loop semantics (skip-overlap, opt-out env, sequential-within-tick, failure-isolation, backup-before-vacuum ordering).

### 8. Online backup via SQLite backup API

v2's `oc db backup` likely uses file-copy (`shutil.copy()`), which races against an active WAL. v3 fixes this in the rewrite: `oc db backup` and the maintenance loop's `db_backup` job both go through `sqlite3.Connection.backup()`, which is the atomic online-backup API SQLite provides for exactly this case.

**Shape:**

- `infrastructure/persistence/backup.py` — `def backup_to(src_db_path: Path, dest_db_path: Path) -> None` using stdlib `sqlite3.Connection.backup()`
- Used by both the CLI and the maintenance loop's `db_backup` job
- Auto-backups land in `${OC_DATA_DIR}/backups/auto/` with timestamp filenames; manual backups (CLI, no path arg) land in `${OC_DATA_DIR}/backups/manual/`
- Retention: auto-backups prune to last 7 (configurable). Manual backups never auto-prune.
- Atomic: backup either fully completes or leaves no partial file (write to `.tmp`, rename on success)

LOC budget: ~80 LOC + 8 tests (backup-during-write, retention pruning, integrity check on output, atomic-rename behavior).

### 9. Embedding-failure degradation policy

Today's behavior is implicit: if `OC_EMBEDDING_PROVIDER=openai` and OpenAI is down, what happens to a `memory_search` call is whatever the adapter's exception handling decides. v3 makes the policy explicit.

**Search path (`memory_search`):**

- Embedding provider failure → log warning, fall back to **FTS5-only** results, set `degraded: true` flag in response, increment a counter
- Response shape adds `embedding_status: "ok" | "degraded" | "disabled"` field (already partially present in v2; formalize)
- `/api/v1/health` reports current embedding status with last-failure timestamp + count

**Save path (`memory_save`):**

- Embedding provider failure → memory item still persists (write must not block on embeddings), embedding row is queued for backfill
- The maintenance loop's `embedding_backfill` job picks up queued items on its next tick
- `memory_save` response notes `embedding_status: "queued" | "ok" | "disabled"`

**No multi-provider failover.** One provider, configured. If you want resilience, run two OC instances with different providers — but that's not v3's problem.

Tests: provider-down search returns FTS5 results + degraded flag, provider-down save persists item + queues embedding, recovered provider drains backfill queue on next tick.

### 10. Updated docs

- New `docs/CODEBASE_ASSESSMENT.md` rev (v3, rev 1)
- Slim `docs/architecture/ARCHITECTURE.md`
- Update `CLAUDE.md` Current Sprint + integration sections

---

## Migration Plan (Phases)

### Phase 0: Branch creation (this session OR next)

- Create `archive/openchronicle.v2` from current main
- Create `refactor/v3-memory-core` from current main
- Push v2 archive
- Don't push v3 branch yet (private development, push when ready for review)

### Phase 1: Cut (interfaces layer first, outside-in)

- Delete `interfaces/discord/` entirely
- Delete dropped routes from `interfaces/api/routes/`
- Delete dropped tools from `interfaces/mcp/tools/`
- Delete dropped CLI commands
- Update `cli/main.py` dispatch table
- Run pytest; expect failures in cut directories' tests; delete those tests too
- Commit checkpoint: "v3 phase 1: interfaces slimmed"

### Phase 2: Cut application layer

- Delete dropped use cases
- Delete dropped services (orchestrator, scheduler, MoE, webhooks, etc.)
- Delete `routing/` directory
- Delete plugin system from core
- Run pytest; cut tests
- Commit: "v3 phase 2: application slimmed"

### Phase 3: Cut infrastructure layer

- Delete `llm/`, `media/`, `privacy/`, `router_assist/`
- Slim `wiring/container.py` to memory-only DI
- Run pytest; cut tests
- Commit: "v3 phase 3: infrastructure slimmed"

### Phase 4: Cut domain layer

- Delete dropped models and ports
- Trim `storage_port.py` → keep only memory-relevant methods
- Run pytest
- Commit: "v3 phase 4: domain slimmed"

### Phase 5: Schema migration + framework + online backup

- Slim `sqlite_store.py` to memory tables only
- Drop migrations for cut tables
- Write `scripts/migrate_v2_to_v3.py` (one-shot v2→v3) and `scripts/verify_v3_db.py`
- Build the ongoing migration framework: `infrastructure/persistence/migrations/` directory, `schema_version` table, `infrastructure/persistence/migrator.py` runner, applied at startup
- Migration #001 establishes the v3 schema (output of `migrate_v2_to_v3.py` should equal applying #001 to an empty DB — verify)
- Build `infrastructure/persistence/backup.py` using `sqlite3.Connection.backup()`; wire `oc db backup` through it
- CI migration test: capture fixture v2 DBs (small, anonymized) into `tests/fixtures/v2_dbs/`, write `tests/test_migration_v2_to_v3.py` that runs migration + invariant assertions
- Online backup test: concurrent-write scenario validates atomic snapshot
- Commit: "v3 phase 5: schema migration + framework + online backup"

### Phase 6: ASGI unification

- Mount FastMCP into FastAPI app
- Drop separate `mcp` service entry point
- Slim `docker-compose.nas.yml` to one service
- Verify locally: MCP via `/mcp` works, REST via `/api/v1/*` works
- Commit: "v3 phase 6: unified ASGI"

### Phase 6.5: Maintenance loop + embedding degradation policy

- Write `application/services/maintenance_loop.py` (~150 LOC, see "New Code Required" section 7)
- Register handler registry: `db_backup`, `db_vacuum`, `db_integrity_check`, `embedding_backfill`, `git_onboard_resync`
- Enforce backup-before-destructive ordering in code (not just by config) — `db_vacuum` invokes `db_backup` first; `db_integrity_check` failure triggers immediate `db_backup` and degraded-flag set
- Wire loop into the ASGI app's lifespan (`startup` → `asyncio.create_task`, `shutdown` → cancel + await)
- Add `cli/commands/maintenance.py` with `list` + `run-once` subcommands
- Add `maintenance` config block to `core.json` defaults
- Add `/api/v1/maintenance/status` endpoint reporting per-job last-run timestamp + outcome
- Implement embedding-failure degradation: search falls back to FTS5-only with `degraded: true` flag, save persists + queues backfill, `/api/v1/health` reports embedding status
- Tests: skip-overlap, opt-out env (`OC_MAINTENANCE_DISABLED`), sequential-within-tick, failure-isolation, backup-before-vacuum ordering, degraded-search behavior, queued-save-backfill behavior
- Commit: "v3 phase 6.5: maintenance loop + embedding degradation"

### Phase 7: Polish + docs (full sweep — every doc updated or archived)

**Discipline:** every file in `docs/` and every doc-shaped file at the repo root must be explicitly classified before Phase 7 ends. Three buckets, no fourth:

1. **Update in place** — doc still applies to v3, content needs revision
2. **Archive** — doc is v2-specific (storytelling, conversation, MoE, Discord, etc.), move to `docs/archive/v2/` with a one-line frontmatter note ("Archived 2026-05-XX. Describes v2 architecture; preserved for reference. See `archive/openchronicle.v2` branch for the corresponding code.")
3. **Delete** — doc is wholly obsolete (e.g. internal one-off planning notes, dead status snapshots) and not worth preserving even archived

**Process:**

- Phase 7 starts with `find docs -type f` → produce a checklist; classify each entry into update/archive/delete
- New `docs/archive/v2/README.md` is the index of archived docs with a one-line description per entry
- Cross-references in v3 docs that used to point at archived docs get updated (point at the archived path or removed entirely)
- `docs/V3_PLAN.md` (this file) gets a final-state header stamp ("v3 shipped 2026-05-XX; this plan is now historical reference")

**Concrete first-pass classification (subject to refinement during Phase 7):**

| Doc | Bucket | Notes |
|---|---|---|
| `docs/CODEBASE_ASSESSMENT.md` | **Rewrite** | New v3 rev 1; v2 version preserved at `docs/archive/v2/CODEBASE_ASSESSMENT.md` |
| `docs/V3_PLAN.md` | **Update** | Stamp as historical post-ship; keep at root of `docs/` for visibility |
| `docs/architecture/ARCHITECTURE.md` | **Rewrite** | v3 layout; archive v2 version |
| `docs/architecture/PLUGINS.md` | **Archive** | No plugin system in v3 |
| `docs/cli/commands.md` | **Rewrite** | v3 command surface only |
| `docs/configuration/env_vars.md` | **Rewrite** | Drop ~40 vars (LLM providers, Discord, MoE, etc.); slim to ~15 |
| `docs/design/design_decisions.md` | **Archive** | v2-era decisions; v3 decisions live in this V3_PLAN.md |
| `docs/protocol/stdio_rpc_v1.md` | **Archive** | RPC layer cut |
| `docs/integrations/mcp_server_spec.md` | **Rewrite** | Memory-only spec |
| `docs/BACKLOG.md` | **Update or Delete** | Likely obsolete; v3 has its own forward-looking items in this plan |
| `docs/api/STABILITY.md` | **NEW** | Per open question 18 — API + MCP tool stability promise |
| `docs/configuration/security_posture.md` | **NEW** | Per open question 15 — container hardening audit results |
| `docs/architecture/MAINTENANCE.md` | **NEW** | Per Phase 6.5 — maintenance loop config + handler reference |
| Repo-root `README.md` | **Rewrite** | See "README voice + posture" subsection below for the framing rules |
| Repo-root `CLAUDE.md` | **Update** | Drop sprint sections about cut subsystems, update env vars list, update integration sections |
| Any `MEMORY.md` / Serena memories | **Audit** | Stale entries about cut subsystems get rewritten or deleted |

**README voice + posture (standing rule, applies to all user-facing OC docs):**

The README is not a market-positioning document. It states what OC is, what it does, what it doesn't do, and how to use it. Two failure modes to avoid:

1. **Don't undersell.** OC is built carefully — clean hexagonal architecture, ~300+ tests, single-container deployment, schema migration framework, online backups, embedding degradation policy, maintenance loop. The bar is high. Don't pad with "this is just a personal project" qualifiers or "if it's useful to you, great" hedges. State what the work IS, confidently.
2. **Don't sell competitors' products.** No "consider also..." pointers to other memory tools in user-facing docs. If OC isn't right for someone, they'll find their own way. The README is not a market survey.

**The pitch shape:**

- Lead with what OC does: persistent memory, hybrid semantic + FTS5 search via RRF, project namespacing, git-onboard, MCP + HTTP REST in a single ASGI process, single container.
- State the design: SQLite + embeddings, hexagonal architecture, no telemetry, no third-party dependencies for the core path, runs on your hardware.
- State the scope honestly: memory + git-onboard + projects. Not conversation, not multi-tenant, not cloud-sync. By design.
- Quickstart: install, configure, first `memory_save`, first `memory_search`, done.
- No competitor section. No "alternatives" section.

**Other Phase 7 polish:**

- Update `pyproject.toml` to drop unused deps (`anthropic`, `groq`, `google-generativeai`, `discord.py`, `fastmcp` stays, `httpx` stays, etc.)
- Update `pyproject.toml` optional-extras (drop `[discord]`, drop `[ollama]` if no longer needed for embeddings — actually keep, ollama embeddings stay; drop the LLM-provider extras)
- Update GitHub repo description + topics to reflect "memory database for LLM agents"
- Update `.github/workflows/` if any reference cut subsystems

**Commit:** "v3 phase 7: docs sweep + deps + repo polish"

### Phase 8: Production cutover

**Pre-cutover checklist (must all be true before starting):**

1. Last v2 image **retagged** as `ghcr.io/carldog/openchronicle-mcp:v2-final` and pushed — `latest` will get overwritten by v3 builds and we need a known-good rollback target. **Easy path:** run the `Retag GHCR Image` workflow from the GitHub Actions UI with `source_tag=latest`, `dest_tag=v2-final` — it uses `docker buildx imagetools create` so the multi-arch manifest copies cleanly without re-pulling. Manual fallback (if running off-CI):

   ```bash
   docker login ghcr.io -u <gh-user> -p $(gh auth token)
   docker buildx imagetools create \
     --tag ghcr.io/carldog/openchronicle-mcp:v2-final \
     ghcr.io/carldog/openchronicle-mcp:latest
   ```

2. **Manual `oc db backup` taken** of the production DB and copied off the NAS (e.g. to local machine) — the migration is one-way without it
3. v3 image built and tagged `:v3.0.0-rc1`. Workflow trigger: push a git tag matching `v*` to `v3/develop`. The `docker-publish.yml` workflow has `tags: ["v*"]` + `type=ref,event=tag` metadata, which produces `ghcr.io/carldog/openchronicle-mcp:v3.0.0-rc1` without flipping `:latest` (the `is_default_branch` guard holds it on v2 until the merge to main):

   ```bash
   git tag v3.0.0-rc1
   git push origin v3.0.0-rc1
   # wait for the "Build and Push Docker Image" workflow to go green
   ```

4. Client Cutover Checklist (see new section below) reviewed; have all client config changes ready to paste
5. User has a 30-minute window where brief downtime is acceptable

**Staging dry run (recommended, not required):**

- Deploy v3 image to a STAGING port (e.g., `:28000`) via temporary stack copy
- Run schema migration on a CLONE of the production DB (do NOT touch the live DB)
- Smoke test the staging instance via direct HTTP calls + an ad-hoc Claude Code MCP config pointing at staging
- If staging is green for at least one full day with the maintenance loop running, proceed to cutover

**Cutover sequence:**

> **2026-05-06 cutover learnings folded in below.** The original sequence
> ran into corruption that the original steps didn't defend against.
> Step 4a (orphan WAL scrub at destination) and step 6 (capture v2 retag
> BEFORE force-pushing) are NEW based on what bit us. See
> `docs/cutover-2026-05-06-triage.md` for the full account.

1. Stop the v2 stack 151 in Portainer
2. **Take a fresh backup of the production DB** (in case the pre-flight backup is stale)
3. Run `scripts/migrate_v2_to_v3.py` on the production DB. **Note:** the script now refuses if `-wal`/`-shm` files exist at the destination path — pass `--force` if you trust they're orphans, otherwise scrub the destination dir first.
4. Run `scripts/verify_v3_db.py` — abort if any check fails. Pay attention to the new `warnings[]` field too: orphan SQLite sidecars at the destination path don't fail validation but indicate trouble (a process holds the DB open OR leftover sidecars from a prior DB are about to corrupt the next opener).
4a. **Verify the destination volume directory is clean.** Specifically: no `*-wal` or `*-shm` files matching the placed DB's path stem. SQLite associates sidecars by path; an orphan WAL from a prior process or DB will be applied on next open and produce `database disk image is malformed`. The 2026-05-06 cutover failed to carry 36 memories into live v3; 24 remained in the NAS rollback snapshot and all 36 in the laptop pre-cutover backup.
5. **Capture the v2 retag BEFORE the force-push.** Trigger the `Retag GHCR Image` workflow with `source_tag=latest` (or the v2 build's SHA tag, e.g. `bb217d9`) and `dest_tag=v2-final`. Verify it lands. The 2026-05-06 cutover did this AFTER the force-push and lost the race — `docker-publish.yml` overwrites `:latest` with v3 in ~5-10 min, and the original retag workflow had a lowercase IMAGE_NAME bug (fixed in commit 6ae71812) that ate a chance to retag in the window. Always do this step before step 6.
6. `docker-compose.nas.yml` is already in v3 single-service shape on `v3/develop`. Force-push `v3/develop` → `main` so future `:latest` builds carry v3 code:

   ```bash
   git push --force-with-lease origin v3/develop:main
   ```

7. Update Portainer stack 151's compose to point at v3 image (`ghcr.io/carldog/openchronicle-mcp:v3.0.0-rc1`); redeploy. Use the rc tag, not `:latest` — `:latest` gets flipped only after Day 7 of clean operation (step 14 of Phase 9 Day 0 / Day 7).
8. Wait for healthcheck green. **If you see `database disk image is malformed` in the container logs, STOP.** This is the WAL-orphan trap from the 2026-05-06 cutover. Do NOT let the container restart-loop against the corrupt DB — stop the container, check the volume directory for orphan `*-wal`/`*-shm` sidecars (very common cause), scrub them, then restart. See cutover-2026-05-06-triage.md for the full recovery procedure.
9. **Verify auth state.** Hit `POST /api/v1/project` with no `Authorization` header. If it succeeds, `OC_API_KEY` is empty and auth is disabled — decide deliberately whether that matches your security posture. If it returns 401, set `$OC_API_KEY` for the smoke-test step below. The 2026-05-06 cutover discovered auth was silently disabled; document the decision in the canonical `AGENTS.md` instructions and keep the `CLAUDE.md` mirror identical.
10. **Trigger one immediate run of `embedding_backfill`** (`oc maintenance run-once embedding_backfill`) to ensure any v2 memories without embeddings get them before search traffic hits
11. Run smoke test:

    ```bash
    python scripts/smoke_test.py http://your-nas:18000 <project-uuid>
    ```

    The script is stdlib-only and exits non-zero on the first failing step. It walks `/health`, `/api/v1/health`, `/api/v1/maintenance/status`, `/api/v1/project` (verifies the target project resolves), full memory CRUD + search + pin round-trip, and probes the `/mcp` mount (accepting 307/405 since streamable-HTTP doesn't answer GETs). Pair it with a manual `onboard_git` MCP call against a small public repo for the use case the script can't cover (since there's no HTTP-side `onboard_git` endpoint — it's an MCP-only tool).
12. Verify project UUID (current canonical: `fe2ef898-0152-40a4-af97-ed97cc86ca45` per `AGENTS.md`) still resolves
13. Update Client Cutover Checklist items (point clients at new endpoint)
14. Tag the merge commit `v3.0.0` (workflow rebuilds and publishes `:v3.0.0`); flipping `:latest` to v3 is deferred to Phase 9 Day 7 per the rollback policy

**If cutover fails (rollback procedure):**

1. Stop the v3 stack
2. Restore the pre-migration backup over the production DB (`/data/openchronicle.db`)
3. Update Portainer stack 151's compose back to v2 shape (3 services: serve/mcp/discord)
4. Update Portainer stack to point at `ghcr.io/carldog/openchronicle-mcp:v2-final`
5. Redeploy
6. Verify v2 health, walk back any client config changes already made
7. Postmortem before re-attempting

### Phase 9: Decommission

**Day 0 (immediately post-cutover):**

- Tag the merge commit `v3.0.0`
- Update README + GitHub repo description
- Confirm `archive/openchronicle.v2` is preserved on origin
- Confirm `ghcr.io/carldog/openchronicle-mcp:v2-final` is preserved (don't garbage-collect)
- **Drop `target-branch: v3/develop` lines from `.github/dependabot.yml`** so updates flow to the default branch (now v3) automatically
- Close out follow-up tasks from this session

**Day 7 post-cutover — CORRECTED 2026-08-28 before execution.**

> The original list was written during cutover planning and had gone
> dangerously stale. Two of its steps would have taken production down,
> and it is preserved here corrected rather than deleted so the failure
> mode stays visible:
>
> - It said **"delete the (now-stopped) v2 stack 151"**. There is no
>   separate v2 stack. Stack 151 was *reused* at the cutover and IS the
>   live v3 stack. Deleting it deletes production.
> - It said **"delete orphan volumes `oc-output`, `oc-assets`"**.
>   `oc-output` is mounted by the running container at `/output` —
>   confirmed by Docker's own dangling filter, which does not list it.
>
> It also missed two genuinely dead volumes. Verify against
> `portainer_list_volumes(dangling=true)` before deleting anything; do
> not trust a written list of volume names.

- **Do NOT delete stack 151.** It is the live v3 stack.
- Delete the volumes Docker reports as dangling, and only those. As of
  2026-08-28 that is `openchronicle-mcp_oc-assets` (v2 assets, feature
  cut) and `openchronicle-mcp_oc-user-plugins` (v2 plugin system, feature
  cut).
- `openchronicle-mcp_oc-config` is also dangling, but only because
  `HOST_CONFIG_DIR` points at a host bind path. It would come back into
  use if that variable were ever unset. Left in place deliberately.
- Keep `oc-data` and `oc-output` — both mounted by the live container.
- Remove orphan host bind paths if used:
  `/volume1/docker/openchronicle/{assets,output,plugins}` (the `config`
  path stays — v3 uses it).
- Delete the pre-migration backup ONLY if a fresh v3-shaped backup exists
  and integrity-checks ok.
- ~~Flip the `latest` Docker tag to v3 LAST — that is what cuts the
  rollback path.~~ **Already true, and has been for months.** This step
  reads as a careful manual action; in reality `test.yml`'s
  `type=raw,value=latest,enable={{is_default_branch}}` publishes
  `:latest` on EVERY push to main, so it has tracked v3 since the first
  post-cutover push. The rollback path this step meant to protect was cut
  long before Phase 9 ran. The real rollback surface is the preserved
  `:v2-final` image plus the eight `v3.0.0-rc*` tags, none of which
  `:latest` affects. Verified 2026-08-28: `:latest`, `:v3.0.0` and
  `:4ba1c5d` all resolve to the same version.

### Post-cutover follow-ups (tech debt)

These didn't block code-completeness or cutover but should land in a v3.0.x release:

- **MCP clients never see `error_code`; the REST surface does.**
  Found 2026-08-28 while capturing the MCP error-shape baseline
  (`tests/test_mcp_error_shape.py`). Domain exceptions carry a structured
  code — `NotFoundError(..., code=MEMORY_NOT_FOUND)`,
  `ValidationError(..., code=INVALID_ARGUMENT)` — and the REST surface
  maps it through the global handlers into an HTTP status plus an
  envelope field. The MCP path drops it: FastMCP stringifies the
  exception into text content, so a client gets
  `Error executing tool memory_get: Memory not found: <id>` and nothing
  machine-readable. The error-code convention that `AGENTS.md` documents
  is therefore REST-only in practice.

  Not a defect in FastMCP — it is the library's model — but it does mean
  an MCP client that wants to branch on failure kind has to substring
  -match our prose, which is exactly what the baseline test warns is
  unstable across a major version.

  **Deliberately not fixed alongside the baseline**: any fix reshapes the
  very surface that test was written to pin, so the baseline has to land
  first. Options when picked up: raise `ToolError` with the code in the
  message in a documented prefix form (cheap, still prose), or return a
  structured error payload as normal content with `isError` (breaks the
  "errors are text" convention, so a MINOR/MAJOR call under
  `docs/api/STABILITY.md`). Decide against the mcp 2.x migration, which
  may change the available mechanisms.

- **Ollama Cloud embeddings — NOT rejected, gated on a trigger that has not
  fired. Re-check periodically.**
  Investigated 2026-08-28. Ollama Cloud is a viable host that currently
  offers us nothing, which is different from being a dead end: the moment
  it lists an embedding model, it becomes an immediately usable provider
  and the work to adopt it is small and already scoped.

  **Baseline captured 2026-08-28** (so a future check is a diff, not a
  re-derivation): 19 hosted models — kimi-k2.6/k2.7-code/k3, gpt-oss:20b/120b,
  mistral-large-3:675b, glm-5.1/5.2/5.3/5.3-flash, minimax-m2.7/m3,
  nemotron-3-nano:30b/super/ultra, deepseek-v4-flash/pro, qwen3.5:397b,
  gemma4:31b. Capabilities across all 19 are drawn only from
  {completion, tools, thinking, vision} — **none advertises `embedding`**.
  Every known embedding model name 404s (nomic-embed-text, embeddinggemma,
  all-minilm, mxbai-embed-large, bge-m3, qwen3-embedding).
  `POST /api/embed` returns 401 (exists, auth-gated, nothing to serve);
  `POST /v1/embeddings` returns 404 (absent on the hosted service, though
  the *local* server registers it with cloud-passthrough middleware).

  **The re-check is free and needs no API key** — `/api/tags` is public:

  ```bash
  curl -sS https://ollama.com/api/tags | grep -Eio '"(model|name)":"[^"]+"' | sort -u
  ```

  If any embedding-capable model appears, confirm with
  `curl -sS -X POST https://ollama.com/api/show -d '{"model":"<name>"}'`
  and look for `"embedding"` in `capabilities`.

  **If the trigger fires, the work is known and small:** the adapter
  already targets `/api/embed`, which is the correct cloud path; the only
  code change is adding `Authorization: Bearer $OLLAMA_API_KEY` (confirmed
  against ollama-python `_client.py:108-110`, which sets exactly that
  header on the base client). Note this is a *different* mechanism from
  the local daemon's cloud proxy, which signs requests with an ed25519 key
  from `~/.ollama/id_ed25519` (`server/cloud_proxy.go`) — that path is for
  the daemon, not for a direct HTTP client like ours.

  **Cadence (widened 2026-08-29, operator-directed):** this check is now
  one leg of the **quarterly embedding-provider sweep** defined in
  [design/0006 §Recurring cadence](design/0006-embedding-provider-review.md)
  — the Ollama *library* embedding catalog is diffed alongside Ollama
  Cloud, so a new local candidate model is caught on the same clock as a
  new cloud host. Runs with the quarterly items in the phase-end audit
  (the AGENTS.md checklist carries the line). The operator holds an
  Ollama Cloud API key, so a live confirmation is available the day it
  becomes worth making.

- **NemoClaw review — operational/recovery hardening (research complete;
  unscheduled).**
  [The design review](design/0004-nemoclaw-repository-review.md) found no
  competing memory-retrieval feature and rejects NemoClaw's agent runtime,
  sandbox, model-routing, credential-broker, messaging, and lifecycle
  scope. The 2026-08-28 closeout completed two documentation findings:
  `AGENTS.md` is canonical with a byte-identical `CLAUDE.md` mirror and
  regression test, and all six verified public-fact errors were repaired.
  ~~Strict version dispatch and whole-envelope validation for portable
  JSON plus atomic private export~~ — **✅ SHIPPED 2026-08-28** (rev 116,
  first batch of the review's Phase B): import validates the entire
  envelope before the write transaction (version dispatch, required
  arrays, per-row types, project references, duplicate ids; rejections
  name collection/index/id) and `oc memory export --out` publishes via
  `mkstemp` + `os.replace`. ~~A least-privilege `onboard_git` child
  environment~~ — **✅ SHIPPED 2026-08-28** (rev 117): allowlisted clone
  env with a sentinel test, raw token never in the child,
  `GIT_TERMINAL_PROMPT=0`, `--no-checkout`, userinfo/query/fragment
  rejection, stderr scrubbing. ~~Explicit server-side clone
  *destination policy*~~ — **✅ DECIDED AND SHIPPED 2026-08-28** (rev
  119): the operator named no non-GitHub consumer, so the MCP surface
  clones `https://github.com/<owner>/<repo>` only; widening later means
  address-class rejection, not deleting the gate. Remaining right-sized
  work is the broader CLI/MCP/env documentation parity gates. ~~Immutable `build_revision` in full
  diagnostics~~ — **✅ SHIPPED 2026-08-28** (rev 118): CI bakes the full
  SHA to `/app/build-revision`, health/`oc version` report it, and the
  NAS compose requires an explicit `OC_TAG`.
  The review also makes stable operation identity + postcondition checking
  a prerequisite for the existing offline write-behind idea, and
  content-bound selection + post-swap writeability a prerequisite for the
  existing cloud-restore design. NemoClaw's composite embedding and
  staged-SQLite patterns corroborate items already recorded by the
  OpenClaw/Ollama reviews rather than creating duplicates. This entry
  records evidence and priority only; it does not authorize or schedule an
  implementation batch.

- **OpenClaw review — retrieval-integrity follow-up.** ✅ **Batch A
  SHIPPED 2026-08-28** (assessment revs 120-124, one commit per
  finding): project/tag eligibility now precedes the semantic top-N
  (`eligible_memory_ids`), FTS tag filtering runs in SQL before LIMIT
  on both branches, a content update invalidates the stored vector
  before re-embedding (failure leaves it missing, never stale),
  `top_k` is a total response budget across all three modes
  (operator-decided contract), and `include_pinned` is exposed on
  MCP + REST (operator decision, additive/MINOR). With correctness
  landed, ranking policy is unblocked per
  [the review](design/0002-openclaw-memory-review.md)'s own ordering
  rule — but composite embedding identity, MMR, supersession,
  provenance, deadlines, and shadow-index publication remain proposed
  or conditional inside the review rather than joining this backlog.
  ~~Still open from the review: batch B~~ — **✅ SHIPPED 2026-08-29**
  (rev 129): `memory_list` gained `tags`/`exclude_tags`/`order_by`
  on every surface, predicates in SQL before pagination,
  `order_by="created_at"` giving pure chronology with no pin float.
  The review's retrieval findings are now fully dispositioned.

- **Pinned prepend ignored the query.** ✅ Fully fixed 2026-08-23, in
  two passes — the first was incomplete and worth recording as such.
  - **Pass 1 (2026-08-17, rc8).** Observed live-verifying the rc7
    deploy (OC memory `4d1d7601`): a `top_k=2` unscoped
    `memory_search` returned 87 results — 85 `channel="pinned"`
    prepends ahead of the 2 requested hits. Shipped `pinned_limit`
    (default 10) to cap the prepend at the *newest* pins, kept the
    exclusion set covering ALL pins, and **deferred** the
    `include_pinned="relevant"` alternative as "inverts the
    pins-are-policy design".
  - **That was the wrong call, and the cap alone made things worse.**
    Because the ranked query hardcoded `pinned = 0`, pinned rows only
    ever reached a caller through the prepend — so capping it made
    every pin past the cap **unreachable by any query**. Proven live:
    an exact-phrase search for a pinned memory's own verbatim content
    returned `[]` with `pinned_limit=0`, while a gibberish query
    returned all 8 of a project's pins. Both symptoms, one root cause:
    "floats" and "is visible" were the same flag.
  - **Pass 2 (2026-08-23) separates them.** The float is now a real
    query (`MemoryStorePort.search_pinned`) — only pins that MATCH
    lead the page, best-matching first, capped by `pinned_limit`,
    scope-with-global. The exclusion covers only the pins actually
    floated, so an unfloated pin ranks normally and reports its true
    channel. `pinned_limit=0` means "don't float" and `include_pinned=
    False` means "hide"; the ranked query no longer hardcodes
    `pinned = 0`. The float policy moved out of the store into the
    application layer, so the store keeps two honest primitives
    (`search_pinned`, and `search_memory` + `exclude_ids`) and the
    caller never guesses which rows floated from their position.
  - **Lesson worth keeping:** the deferred option was deferred on a
    design-purity argument ("pins are policy, not relevance") without
    checking what the cap did to reachability. A cap on a channel that
    is a row's *only* route to the caller is a silent delete.

- **2026-08-15 full-repo review — Batches B–E queued.** A six-agent
  review (~60 findings; punch list in OC memory `e22472b8`, full report
  in the session artifact "OpenChronicle Repo Review") produced five
  work batches. **Batch A shipped 2026-08-16** (Python-floor truth,
  `context_recent` no-query fix, stateless streamable-HTTP, REST Host
  allowlist, empty-env normalization + compose reachability, CI
  paths-ignore/concurrency, `init-config` removal). **Batch B shipped
  2026-08-16** (`b387d584` + `5e196fdb`, 530 → 538 tests): hybrid
  `include_pinned=False` leak, `dimensions` fact-not-claim with
  blob-length reads, model-scoped `_semantic_search` — and the Q20/Q21
  research answers are recorded in Open Questions below (the design was
  approved and shipped 2026-08-17 as search-surface v2; see Q20/Q21).
  **Batch C shipped 2026-08-16** (`29528201`, 538 → 551 tests):
  watermark anchors `commits[0]`; unreachable-watermark auto-recovery
  (full-walk fallback + `watermark_unreachable` flag); `branch` param +
  resolved branch/head echo; orchestration promoted to
  `onboard_git_prepare` with the CLI sharing watermark semantics —
  closes OC memories `2f2992cd`, `2cc9e037`, `2c096329`. **Batch D
  shipped 2026-08-16 as v3.0.0-rc6** (`28b070c5`/`e25d71c1`/`f11a301c`
  - release commit, 551 → 563 tests): maintenance schedule persistence
  - burst-proof retention; fail-soft config paths; Dockerfile dep-layer
  reorder; version `3.0.0rc6` + CI tag↔version guard. Phase 9's
  destructive decommission (v3.0.0 tag, v2 stack/volume deletion) stays
  operator-gated. Originally queued as: **D — ops + release integrity**
  (persist
  maintenance `last_run_at` — today every container start fires every
  job and two backups, eroding the 7-slot retention under
  redeploy-bounce; fail-soft the remaining crash-loop config paths;
  version-bumps-with-tag flow + rc6; Phase 9 close). **E — docs SSOT +
  test debt** (status-doc rewrite; restore the never-committed
  `docs/archive/v2/` — `.gitignore` swallowed Phase 7's archive move;
  CHANGELOG decision; CLI smoke pass — the surface is ~80% untested;
  MCP handler-test gaps).

- **Rate limiter ceiling.** ✅ Landed 2026-05-11. Default bumped 120 → 600 RPM (`_DEFAULT_RPM` in `src/openchronicle/interfaces/api/middleware/rate_limit.py`); `.env.example` and `docs/configuration/env_vars.md` reconciled (both previously claimed `60`, a pre-existing drift). Single-user home-LAN deployments aren't IP-storming attackers; the option-(a) one-line bump was the right move. Option (b) — a bulk-search endpoint (`memory_search_bulk(queries: list[SearchQuery])`) for multi-type retrievals — is still cleaner long-term and remains on the backlog if mnemosyne's `gatherContext` burst pattern proves expensive at the new ceiling.
- **`project_delete` MCP tool / API surface.** ✅ Landed 2026-05-11 as part of the v3.0.x "project surface completion" pass. The bullets below record the rc4 shape and are historical; required `confirm` and the 18-tool surface superseded them on 2026-07-23 (see the next two shipped entries). Shipped together with `project_get`, `project_update`, and a symmetric `confirm` flag on `memory_delete`:
  - `delete_project` on `StoragePort` does the atomic cascade (project row + every `memory_items` row with that project_id; `memory_embeddings` cascade via the existing FK). `update_project` and `get_project` round out the port.
  - `mnemo_*` storytelling adjacent: the use case takes `confirm: bool = False`; the preview branch returns `{status: "preview", project_id, name, memory_count}` without touching the DB, and `confirm=True` returns `{status: "ok", project_id, name, deleted_memories}`.
  - REST: `DELETE /api/v1/project/{id}?confirm=true`, `GET /api/v1/project/{id}`, `PUT /api/v1/project/{id}` (with a Pydantic model-validator that rejects bodies setting neither name nor metadata → 422).
  - MCP: `project_get`, `project_update`, `project_delete` registered alongside the existing `project_create` / `project_list`. The bundled v3 MCP surface is now 17 tools.
  - CLI: `oc show-project` already existed; added `oc update-project --name --metadata` and `oc delete-project --confirm`.
  - `memory_delete` symmetric pass: same `confirm: bool = False` preview/ok shape on the MCP tool, REST route (`DELETE /api/v1/memory/{id}?confirm=true`), and CLI (`oc memory delete <id> --confirm`). Breaking change to the previous one-shot semantic — acceptable per the no-backwards-compat rule.
  - Tests: `tests/test_project_crud.py` is a real-SqliteStore integration suite covering cascade + update; HTTP and MCP tool tests round out the mock-container coverage. 386/386 pass.
- **Project-scoped `memory_list`.** ✅ Landed 2026-07-23. `memory_list` had no `project_id` even though its siblings `memory_search` and `memory_stats` both did, so answering "which projects have memories?" meant pulling every row's full content and filtering client-side — one dogfooding session burned 91,372 characters on exactly that (OC memory `ff7933df`). `project_id` now threads port → SQL → use case, using the `idx_memory_project_created` index that was already in `001_initial.sql`. The filter is **scope-strict** (`project_id = ?`), matching `count_memory`, `list_memory_by_source`, and the `delete_project` cascade. `pinned_items` keeps its scope-with-global rule (`project_id = ? OR project_id IS NULL`) deliberately — a standing rule that belongs to no single project still applies while working inside one, and making it strict would stop standing rules surfacing in project-scoped search. Both rules are now named in the `MemoryStorePort` class docstring, and `test_project_filter_disagrees_with_pinned_items_by_design` pins the divergence so a future reader doesn't "fix" one to match the other. Fallout: the in-Python project filters in `embedding_service.generate_missing` and `export_memory.execute` became a passed-through argument, and the dead `Page` protocol was deleted from `storage_port.py`.
- **Required `confirm` on both delete surfaces.** ✅ Landed 2026-07-23. `confirm` was `bool = False` on `memory_delete` and `project_delete`, so a call that omitted it got a preview — which is success-shaped. mnemosyne-mcp's `OcClient.memoryDelete` wrapper returns `Promise<void>` and never read the payload, so `mnemo_delete_entity` reported success while the memory stayed in the DB; it surfaced only when an integration test recalled the "deleted" entity (OC memory `a2cdfe56`). `confirm` is now required on both use cases, both MCP tools, and both REST routes (absence is a 422). Previews additionally carry `deleted: false` and a `next_step` string, and confirms carry `deleted: true`, so even a caller that only skims the payload sees the difference. The CLI is unchanged — argparse can't express a required boolean flag sensibly, and its failure mode was never silent (it prints "Re-run with --confirm"). No shared envelope helper was extracted: the payload is three lines of dict literal per use case, so `tests/test_delete_preview_envelope.py` enforces the invariant instead, which also catches a future delete surface that forgets the convention rather than only the ones that remember to call a helper. `test_confirm_is_required` asserts the default cannot be reintroduced.
- **Filtering and projection on the read surface.** ✅ Landed 2026-07-23. The read tools had no way to return less: `project_list` took zero arguments, and every listing returned full `content` / `metadata`. Finding 46 projects by name prefix meant pulling every project's multi-KB metadata blob (OC memory `837e85cc`), and listing 30 memories cost 91,372 characters (`ff7933df`). Two additions, both opt-in so no existing response shape moved. (1) `project_list` gains `name_contains`, a case-insensitive substring filter compiled to `LIKE ? ESCAPE ?` with `%`, `_`, and the escape character itself escaped in the caller's value — without that a project named `100%` matches every row, which is the quiet kind of wrong, so it has dedicated tests. (2) `memory_list`, `memory_search`, `context_recent`, and `project_list` gain `compact`. Compact **replaces** the expensive field rather than shortening it (`content` → `content_preview` + `content_length`; `metadata` → `metadata_keys` + `metadata_size`) so a consumer reading `content` can never silently receive a truncated string — the same class of failure as the delete preview. The preview length is a module constant, not a parameter: a bool needs no clamping, so MCP and REST take it verbatim and can't drift the way their `limit`/`top_k` range checks already have. `context_recent` now shares `memory_to_dict`, retiring a third hand-rolled memory shape and gaining `source`/`updated_at`. The CLI gets `--project-id` and `--name-contains` but no `--compact` flag: its output was already compact, so it just adopts the shared `content_preview()` helper (3 call sites, which is what earns the extraction).
- **Bounded, honest `onboard_git` cluster detail.** ✅ Landed 2026-07-23. `max_clusters` capped how many clusters came back but nothing capped the bulk inside each one, so onboarding a 491-commit repo returned 86,006 characters (OC memory `ff7933df`). Two knobs now bound it: `max_commits_per_cluster` (1-100, default 10, replacing a hardcoded `[:20]`) and `include_commit_detail` (default false), which gates the body, per-commit file list, and diffstat together. Grouping those three under one flag rather than three was deliberate — the 500-char body is the dominant term, so capping commit count alone only halves the payload. The separate, arguably more valuable half of this fix is honesty: the old formatter selected the 20 *largest-diff* commits and printed them in *size* order despite prefixing each line with a date, under a header reporting the true `Total commits: 153`. Selection still goes by churn (the best proxy for which commits carry the story) but presentation is now chronological, the header adds `Showing: n of N` whenever the cluster is capped, each cluster gains `shown_commit_count`, and a truncated file list appends `(+N more)` instead of just stopping. Also fixed here: the watermark anchored to `max(filtered)` rather than `max(commits)`, so any commit newer than the last *kept* one — a merge, a format commit, a version bump — was re-walked on every run, and a repo whose HEAD is a merge never advanced at all. The response gains `walked_commit_count` so the existing post-filter `commit_count` stops being ambiguous. Structurally, `key_files` and `suggested_tags` moved out of the MCP tool into `git_onboard.cluster_to_summary()`; that was clustering logic living in an interface module, and it was the reason no test could reach the response shape. `tests/test_onboard_git_tool.py` is new and includes the size cap that would have caught the original complaint.
- **Bulk project delete.** ✅ Landed 2026-07-23. `project_delete` is strictly one project per call, so clearing 46 stale test projects cost 92 tool calls under the preview/confirm two-step (OC memory `837e85cc`). New `project_delete_bulk` tool + `POST /api/v1/project/bulk-delete` (POST rather than DELETE-with-body, since proxies and clients routinely strip DELETE bodies and this one is load-bearing). A new tool rather than overloading the singular one: accepting a list there would mean either changing `project_id`'s type or adding a mutually-exclusive parameter, and neither is a schema an LLM should have to reason about. Surface is now 18 tools. Two deliberate divergences from `project_delete`, both documented in the tool description: unknown ids are reported in `missing` rather than raising, because aborting a 46-element batch over one typo forces the caller to diff two lists by hand and re-issue — exactly the friction being removed; and while *reporting* is per-item, *durability* is all-or-nothing, since the confirm loop runs inside one `store.transaction()` and each cascade nests as a savepoint. Duplicate ids collapse. `name` is preserved per project in both branches — the mistyped-UUID guard matters more at 46 ids than at one. No CLI twin: bulk in a shell is a `for` loop, and the 92-call cost is an MCP round-trip problem that doesn't exist there.
- **Version and capability signal on `health`.** ✅ Landed 2026-07-23. A downstream client had no way to tell which OC it was talking to, so a semantics change on an existing tool was undiscoverable without reading this repo's git log (OC memory `a2cdfe56`, suggestion 3). `health` now carries `package_version`, `schema_version`, `maintenance_degraded`, and `fts5_active`. The first two were already promised by `docs/api/STABILITY.md` and `docs/integrations/mcp_client_setup.md`, so this reconciles code to published docs rather than inventing a surface. `fts5_active` is the genuinely new one: search degrades to the Python fallback silently, and without this a caller cannot distinguish "results are poor" from "the fast path is gone". `maintenance_degraded` closes a real parity gap — the REST route appended it after building the payload, so the MCP tool was strictly poorer, and `tests/test_health_parity.py` now asserts the two key sets are identical so that can't recur. Along the way this fixed a live bug: `oc version` printed "unknown" because `pyproject.toml` declares the distribution as `openchronicle-mcp` while the CLI asked `importlib.metadata` for `openchronicle`; the existing test passed because it only checked that the substring "openchronicle" appeared, which the failure string satisfied. Version now has one source — new `src/openchronicle/version.py` reading package metadata — consumed by the CLI, the health payload, and `api/app.py`, whose hardcoded `"3.0.0-dev"` had already drifted from pyproject's `3.0.0.dev0`. Not done: passing a version to `FastMCP(...)` so the protocol handshake reports OC's version rather than a FastMCP default — no 1.x `FastMCP` constructor takes a `version` kwarg (re-confirmed against 1.29.0, 2026-08-28). Revisit when the SDK grows one.
- **`memory_stats` through `count_memory`.** ✅ Landed 2026-07-23. The stats body existed twice, verbatim, in the MCP tool and the REST route, and both did the thing `MemoryStorePort.count_memory`'s own docstring warns against — answering "how many?" by pulling every row into Python and taking `len(...)`. Worse, the project filter ran in Python, so a scoped stats call on a multi-project DB loaded every other project's rows only to discard them; that is the same root cause as the 91,372-character `memory_list` complaint. Extracted to `use_cases/stats_memory.py`: `total` comes from `count_memory` (a COUNT(\*) at the SQL layer) and the tag/source histograms still need row access — tags are a JSON column with no cheap aggregate — but read the project-scoped `list_memory` added in the first commit of this batch. Two verbatim copies plus a documented correctness rule clears the extraction bar; the REST duplicate is gone.
- **Dependency audit (unused deps only).** `pyproject.toml` extras (`[dev]`, `[mcp]`, `[openai]`, `[ollama]`) were trimmed during Phase 7 but never re-resolved against actual import use. Walk `pipdeptree` on a fresh `pip install -e ".[dev,mcp,openai,ollama]"` and prune anything not imported by `src/` or `tests/`. Likely candidates to drop or version-pin tighter: leftover transitive deps from the v2 cut. Vulnerability tracking is handled by `.github/dependabot.yml` (pip + github-actions + docker, weekly), so this audit is about *unused* deps, not insecure ones — Dependabot will open PRs for the latter on its own. Build-tooling CVEs (pip / setuptools / wheel on the `python:3.11-slim` base) were addressed pre-cutover by raising `build-system.requires` floors and adding a `pip install --upgrade pip setuptools wheel` step to the Dockerfile.
- **Report OC's version in the MCP handshake.** No 1.x `FastMCP(...)` constructor takes a `version` kwarg (re-confirmed against 1.29.0, 2026-08-28), so the protocol's `serverInfo.version` is whatever the SDK defaults to — which is worse than absent, because it looks like OC's version and isn't. `health.package_version` covers the need for now. **This is now a confirmed 2.x-only capability**: `MCPServer.__init__` in 2.1.1 takes `version: str = ""`, making it a concrete instance of trigger 2 on the mcp 2.x migration entry rather than a hypothetical one. Don't reach into private attributes to force it.
- **`_semantic_search` loads the whole embeddings table.** `embedding_service.py` reads every row of `memory_embeddings` and does an unfiltered numpy matmul per query, then applies the project filter in Python afterwards. Its own docstring names this the architectural ceiling and points at sqlite-vec as the fix. Fine at this deployment's size; the point at which it stops being fine is a row count nobody is currently watching.
- **`_cosine_similarity` has no production caller.** Kept deliberately for tests and diagnostics per a note in `embedding_service.py`. Either give it a caller or delete it and move the test coverage onto whatever replaced it — a helper that exists only to be tested is a slow leak.
- **CLI `--confirm` branch duplication.** `cmd_memory_delete` and `cmd_delete_project` each hand-roll the same "Would delete … Re-run with --confirm" branch. Left alone deliberately in the 2026-07-23 batch: ~8 trivial lines each, no shared correctness rule, so extracting costs more readability than it buys. Revisit only if a third such command appears.
- **mcp 2.x migration.** Deferred, not rejected — and the stated reason
  was wrong for a year. Corrected 2026-08-28 by inspecting the mcp 2.1.1
  wheel directly.

  **What is actually true.** In mcp 2.x, `mcp.server.fastmcp` is a
  tombstone module whose only content is a `raise ModuleNotFoundError`
  pointing at the migration guide. So the operational consequence stands:
  `interfaces/mcp/server.py` fails to import on a fresh resolve, and an
  unpinned rebuild ships a container that dies on startup. (Caught
  2026-07-29 while validating the python 3.14 image; the then-deployed NAS
  image only worked because it predated 2.0.0.)

  **What was false.** FastMCP did NOT "move to the standalone `fastmcp`
  package." It was **renamed in-tree** to
  `mcp.server.mcpserver.MCPServer`. The SDK's own tombstone message says
  so and links
  `https://py.sdk.modelcontextprotocol.io/v2/migration/#fastmcp-renamed-to-mcpserver`.
  That mattered: the false premise framed migration as adopting a
  third-party dependency, which is a far heavier and scarier decision than
  following a first-party rename with an official guide. `pyproject.toml`
  and `.github/dependabot.yml` repeated the same wrong reason and are now
  corrected.

  **Verified scope.** `create_server()` passes four load-bearing options
  to the `FastMCP` constructor. Against `MCPServer.__init__` in 2.1.1:

  | Option | Status in 2.x |
  |---|---|
  | `lifespan` | still a constructor arg; callable is typed `MCPServer[...]` rather than `FastMCP` |
  | `streamable_http_path` | moved off `__init__` to `streamable_http_app()` / `run_streamable_http_async()` |
  | `stateless_http` | moved off `__init__` to the same transport methods |
  | `transport_security` | moved off `__init__` to `run()` / `sse_app()` / the transport methods; `TransportSecuritySettings` itself is unchanged and still lives at `mcp.server.transport_security` |

  So the shape of the work is a rename plus relocating three options from
  construction to transport wiring — not a dependency swap and not a
  rewrite. It remains a MAJOR event under `docs/api/STABILITY.md`, but
  that cost is constant whenever it happens; it is not an argument for any
  particular timing.

  **Baselines now exist to prove it schema-invisible** (they did not when
  this was first deferred): `tests/test_mcp_tool_schema_snapshot.py` pins
  all 18 tools' `inputSchema` *and* `outputSchema`, and
  `tests/test_mcp_error_shape.py` pins the client-visible error envelope —
  both captured on 1.29.0. `tests/test_host_allowlist.py` pins that a
  forged Host is rejected through the mounted `/mcp`, which is the
  tripwire for `transport_security` being silently lost in the move to
  transport wiring.

  **Named revisit triggers** — re-evaluate when any one fires, rather than
  on a calendar:

  1. A security advisory lands against `mcp` 1.x, or 1.x stops receiving
     fixes.
  2. A capability we actually want ships 2.x-only (the handshake-version
     item above is the current candidate).
  3. Python 3.15 support, or another dependency in the graph, forces the
     floor past `mcp<2`.
  4. A fleet sibling migrates first and the port can be copied rather than
     derived.

  Cheapest re-check, so a future pass is a diff and not a re-derivation:

  ```bash
  pip download "mcp>=2,<3" --no-deps -d /tmp/mcp2 && \
    python -c "import zipfile,glob; z=zipfile.ZipFile(glob.glob('/tmp/mcp2/*.whl')[0]); \
    print(z.read('mcp/server/mcpserver/server.py').decode()[:2000])"
  ```

  Until a trigger fires, close Dependabot pip PRs bumping `mcp` past 1.x
  against this entry.
- **Docker base image refresh.** ✅ Landed 2026-07-29/30 (`9e71c207` + `c839ddb9`): base moved to `python:3.14-slim` with a multi-stage build, non-root `oc` user, and HEALTHCHECK. The follow-on truth-reconciliation (requires-python `>=3.14`, badge, docs) landed 2026-08-16 in review Batch A.
- **Consume the tracked lock in CI and Docker.** A generated `uv.lock` is now tracked for review and dependency inspection, but the build remains intentionally honest about its current behavior: CI and Docker still resolve/install from `pyproject.toml`, so the lock does not yet make either path reproducible. When scheduled, make frozen lock consumption authoritative on supported Python/OS markers, fail on drift, audit the exact locked runtime graph, and retain Dependabot for updates.
- **Offline / write-behind sync for LAN-unreachable clients.** OC's single-user home-LAN posture (no auth, NAS-only, per `docs/configuration/security_posture.md`) means any client MCP call fails outright — not gracefully degrades — the moment the client isn't on the LAN (VPN off, in-office, mobile). Surfaced 2026-07-30: a Claude Code session working on an unrelated repo (IRIS) finished a real milestone worth a `memory_save`, but the user was in-office and OC was unreachable; the only mitigation available was holding the draft in Claude's own local memory system and re-offering to file it next session — an entirely manual, per-session stopgap with no OC-side support, and it evaporates if the AI or user forgets. Two directions worth researching, not yet scoped or estimated: (a) a **client-side write-behind queue** — buffer `memory_save`/`project_*` calls locally (e.g. a JSON-lines journal) when the NAS request fails/times out, replay them through the real MCP tools once reachable; no server change needed, smallest lift, but doesn't help *reads* (`memory_search`, `context_recent`) while offline. (b) A **local shadow OC instance** — `oc serve` already runs standalone against a local SQLite DB for local dev (a separate memory pool from the NAS one per this file's Project Identity section); journal writes while offline and reconcile into the NAS DB on reconnect. Helps reads too, but needs a real merge story OC has no design for today — a memory created locally and one created on the NAS in the same offline window need distinguishable ids, not naive overwrite-by-id, and reconciliation ordering/conflict rules don't exist yet. Lean toward (a) first: smaller lift, and it covers the case that actually bit us (a write, not a read).

---

## Client Cutover Checklist

v3 consolidates two ports into one path. **Every MCP client breaks until reconfigured.** Walk this list during Phase 8 step 11.

### Endpoint changes

| What | v2 | v3 |
|---|---|---|
| HTTP REST | `http://your-nas:18000/api/v1/*` | `http://your-nas:18000/api/v1/*` (unchanged) |
| HTTP liveness | `http://your-nas:18000/health` | `http://your-nas:18000/health` (unchanged) |
| HTTP OpenAPI | `http://your-nas:18000/openapi.json` | `http://your-nas:18000/openapi.json` (unchanged, but content now reflects curated v3 surface) |
| MCP transport | `http://your-nas:18001/mcp` | `http://your-nas:18000/mcp` (port collapsed) |
| Discord bot | (separate `discord` service in stack) | (gone — bot no longer runs) |

### Known client configs to update

| Client / location | Action |
|---|---|
| `~/.claude.json` on the user's primary machine | Edit `mcpServers.openchronicle.url` from `:18001/mcp` → `:18000/mcp` |
| `~/.claude.json` on every other machine the user runs Claude Code from | Same edit. Enumerate machines beforehand. |
| Goose config (if registered) | Update OC server URL to `:18000/mcp` |
| Open WebUI tool server (if configured) | Update OpenAPI URL to `http://your-nas:18000` (still appends `/openapi.json` itself) |
| Synology Container Manager healthcheck (if pointed at `:18001`) | Update to `:18000/health` |
| Portainer stack 151 healthcheck | Should use `/health` (already correct, but verify) |
| Any home-grown scripts hitting `:18001` | Search the user's repos for `:18001` references; update or delete |
| `.claude/hooks/` scripts in this repo and elsewhere | Verify `oc memory ...` CLI calls still work (CLI surface unchanged for memory) |

### Verification per client

After updating each client's config, do a single round-trip call (`memory_search` for "v3 cutover" or similar) to confirm the tool is wired up and returning. If a client errors, fix the config; don't proceed to the next.

### Don't forget

- **MCP tool descriptions may have changed** during Phase 1 (per open question 13). Clients that cache tool definitions (Claude Code does) need a session restart, not just a config edit.
- **The Portainer auto-update setting** (`AutoUpdate.Interval=5m, ForcePullImage=true`) carries over fine but means once `:latest` flips to v3, any restart re-pulls v3. This is the point of no return — only flip `:latest` after Day 7 of clean v3 operation.

---

## Open Questions

1. **`memory_items.conversation_id` column** — keep as opaque session metadata for forward-compat with future external conversation engines, or drop entirely? Today the column is populated when memory is saved during a conversation_ask flow; with conversations gone, it'd always be NULL for newly-saved memories. Existing 23 memories all have `null` for conversation_id (they're all sourced from MCP saves and git onboarding). **Recommendation: drop.** Add back if a real consumer needs it.

2. **Hash-chained event audit trail** — useful for memory CRUD audit ("when did this memory get pinned?"). Currently coupled to the engine's event emission. Could be preserved as a memory-only audit log (events emitted by memory_save, memory_update, memory_delete, memory_pin). **Recommendation: defer.** v3 ships without events; if audit becomes important, add a slim memory-only event log later.

3. **Integration tests against live OpenAI embeddings** — useful smoke tests but require API keys. Decision: keep as opt-in (`OC_INTEGRATION_TESTS=1`), don't run in CI default.

4. **Single-port consolidation: `:18000` or `:18001`?** Today the deployed stack uses `:18000` for HTTP API and `:18001` for MCP. v3 consolidates to one. Operator continuity argues for `:18000` (matches existing ops scripts, browser bookmarks, etc.). MCP clients need their config updated either way. **Recommendation: `:18000`.**

5. **Should `git_commits` table stay?** It's a memory generator's artifact. Dropping it loses the incremental watermark. Recommendation: **keep `git_onboarding_state` table** (the watermark) but the `git_commits` table itself isn't actually persisted — the onboarding tool clones, analyzes, and discards. Confirm during execution.

6. **Plugin system entirely?** Without storytelling, the plugin system has zero consumers. **Recommendation: cut entirely.** If a future extension need emerges, design fresh.

7. **`oc init` and `oc config show`** — keep for operator UX (init creates the config dir, show prints current config). Slim significantly.

8. **`telemetry` events** — drop entirely. v3 doesn't track tokens or call counts.

9. **Auto-update on Portainer stack** — `AutoUpdate.Interval=5m, ForcePullImage=true` currently set on stack 151. Carries over fine to single-service compose. Keep.

10. **What to do with `docker-compose.nas.yml` git history?** It currently encodes 3-service shape. Either keep its history (more lines diffed in v3 cutover commit) or rewrite (clean v3 file with no v2 vestige). **Recommendation: rewrite as fresh file** — v3's compose is conceptually new, not an evolution.

11. **Maintenance job config defaults** — the loop ships with four jobs (`db_vacuum`, `db_integrity_check`, `embedding_backfill`, `git_onboard_resync`). Defaults proposed:
    - `db_vacuum`: every 7 days, on
    - `db_integrity_check`: every 7 days, on
    - `embedding_backfill`: every 6 hours, on
    - `git_onboard_resync`: every 1 hour, **off** (requires `OC_GIT_ONBOARD_REPOS` to be set; off-by-default avoids surprising any v2-DB users post-migration who haven't set up onboarding)

    **Open sub-questions:**
    - Are the default intervals right? (7 days for vacuum feels conservative for a low-write DB; could be 30. 6 hours for backfill assumes embeddings can briefly drift out of sync, which is fine for a single-user setup.)
    - Should `db_integrity_check` failure auto-trigger a backup before doing anything else? (Recommendation: yes — a corrupted DB should snapshot itself before any further writes.)
    - Should the loop expose a `/api/v1/maintenance/status` endpoint reporting last-run timestamp + outcome per job? (Recommendation: yes, useful for monitoring; implement in Phase 6.5.)

12. **Cloud storage backup/sync for the memory store** — **DESIGNED 2026-08-23: see [design/0001-cloud-backup.md](design/0001-cloud-backup.md).** Backup-only is confirmed as the shape (sync-as-store stays in Out of Scope, and §9 of that doc verifies backup-only does not foreclose it). The design is *proposed*, not shipped. Provider was decided 2026-08-23 (Dropbox — the operator's OneDrive preference lost to a scope limitation rclone cannot work around) and so was encryption (age, two recipients, independent custody). Three prerequisites the design surfaced have landed: `JobState.last_success_at` (§6.1), the `import --mode merge` hazard (§11.4), and the §11.3 git-onboard watermark filter. Open: whether to co-push the JSON envelope alongside the `.db` (§13.4) — the only remaining operator question, and it's optional. Original framing below, kept because the sub-questions are what the design answers:
    - **Backup-only (simpler):** a periodic job (daemon thread or external cron) that uploads `oc db backup` artifacts to cloud storage. SQLite stays the source of truth, cloud is disaster recovery + cross-device restore. Implementable as a single CLI command (`oc backup push --provider dropbox --token $TOKEN`) plus a scheduled-job loop. Pluggable provider abstraction so adding new clouds is trivial.
    - **Sync-as-store (much harder):** memories live IN cloud storage and the SQLite DB becomes a local cache. Requires conflict resolution, offline operation semantics, sync windows, integrity verification. Likely premature for v3 scope.
    - **Recommendation:** plan for backup-only as a v3.1 follow-up feature, not a day-1 ship item. Keep the v3 architecture LLM-side untouched, but design the storage layer with a clean enough seam that a backup-pushing daemon is straightforward to bolt on later. Specifically: keep `oc db backup` working (already exists in v2), keep DB writes through `SqliteStore`, don't bake cloud-specific assumptions into the core. If user wants this on day 1, it adds maybe 1-2 sessions of work for backup-only with one provider (Dropbox is easiest — official SDK, app-folder pattern keeps blast radius small).
    - **Open sub-questions:**
      - Should the backup target be the whole SQLite file, or a JSON export of memories+projects+embeddings? (Whole file is simpler, smaller diffs since it's incremental SQLite. JSON export is cross-version-portable.)
      - Should embeddings be backed up or regenerable? (Regenerable is cheaper to store but slow to restore for 1000s of memories.)
      - Sync window: every N minutes? On every memory write? Manual trigger only?
      - Encryption at rest in the cloud? OC's data is fairly sensitive (decisions, project context, sometimes secrets-adjacent memories). Recommend encrypting before upload via a user-supplied key.

13. **MCP tool description quality pass** — going from 32 tools to ~12 means the survivors carry more weight per-tool; LLM tool selection is description-dependent. Should Phase 1 (cuts) include a deliberate pass on the ~12 surviving tool descriptions, treating them as user-facing UX rather than incidental docstrings? **Recommendation: yes, allocate ~30 min in Phase 1.** Specifically: each tool's description should answer "when would I call this vs the other 11?" not "what does this do?"

14. **Memory export/import (JSON)** — open question 12 sub-bullet asks "whole SQLite file vs JSON export" for cloud backup. Independent of cloud backup, a `oc memory export --format json --out path` CLI is ~30 LOC and gives us a portable disaster-recovery surface that doesn't depend on SQLite version. Pairs with `oc memory import --format json --in path` for restore-into-fresh-DB. Should v3 ship this on day 1, or defer? **Recommendation: ship day 1.** Cheap, useful, validates the schema is sensibly serializable.

15. **Container hardening review** — quick audit during Phase 7: non-root user in image, read-only root FS where possible, resource limits in compose (`mem_limit`, `cpus`), log rotation. Most of this is probably already done in v2's Dockerfile/compose; v3 should verify rather than assume. **Recommendation: 1-hour audit in Phase 7, fix anything obviously missing, document the security posture in `docs/configuration/`.**

16. **Healthcheck depth** — confirm v3 preserves the v2 split: `/health` (fast/dumb liveness for prober ticks) vs `/api/v1/health` (full diagnostics). v3 `/api/v1/health` should additionally report:
    - Embedding provider status (ok / degraded / disabled, last failure timestamp + count)
    - Last maintenance run timestamp + outcome per job (also exposed via `/api/v1/maintenance/status`)
    - DB size on disk
    - ~~Last successful `db_vacuum` timestamp~~ ✅ 2026-08-23 — `JobState.last_success_at`, persisted and exposed per job at `/api/v1/maintenance/status`
    - ~~Last successful `db_backup` timestamp~~ ✅ 2026-08-23 — same field; covers the scheduled job. Two manual paths deliberately leave no timestamp: `oc db backup` (a direct operator action with its own console output) and `oc maintenance run-once db_backup`, which calls the handler directly and bypasses the loop entirely
    - Schema version (from `schema_version` table)

    **Recommendation: implement in Phase 6.5.**

17. **Ingest backpressure** — if a runaway script floods `memory_save`, today nothing throttles it; FTS5 rebuilds + embedding queue grows + disk fills. Should v3 enforce a per-source rate limit?
    - **MCP source:** yes, default cap of N writes/sec (e.g. 10/sec) — prevents accidental loop in a Claude session from chewing through quota. Configurable via `OC_INGEST_RATE_LIMIT_MCP`.
    - **CLI source:** no rate limit (operator intent is explicit).
    - **HTTP source:** existing rate-limit middleware already covers this; verify it covers `memory_save` specifically.
    - **Recommendation: implement in Phase 6.** Cheap addition since the middleware exists.

18. **API + MCP tool stability promise** — once v3 ships `/api/v1/memory/*` and the 12 MCP tools, what's the change-policy?
    - **Proposed rule:** `/api/v1/*` and MCP tool *schemas* are frozen post-v3.0.0; additive changes (new fields, new optional params) ok within `/api/v1/`; breaking changes require `/api/v2/` and parallel deployment for a deprecation window. MCP tool versioning rides the server's semver (`2.0.0` → `3.0.0` for v3.x cutover; tool schema breaks bump major).
    - **Recommendation: adopt the rule, document in `docs/integrations/mcp_server_spec.md` and a new `docs/api/STABILITY.md`.** No active external consumers today — this is for future-us.

19. **Logging format default** — v2 uses Python `logging` with default formatter (human-readable). v3 should pick a posture explicitly:
    - **JSON structured:** good for ingestion (Loki, OpenSearch, Datadog), bad for `docker logs` readability
    - **Human-readable:** opposite trade-off
    - **Recommendation:** env-var switchable via `OC_LOG_FORMAT=human|json`, default to `human`. Single-user personal project + Synology Container Manager log viewer favors readability. Operators wanting structured ingestion flip the env var. Implement during Phase 6 (ASGI unification, when logging gets touched anyway).

20. **Surface per-result confidence/relevance scores in `memory_search` responses.** The hybrid semantic+FTS5-via-RRF search (line 129: "Working, stays") fuses two ranking signals internally, but it's unconfirmed whether a normalized confidence/relevance score per result actually reaches the MCP/API response, or whether RRF's fused rank is only used internally to order results before returning bare content. Raised 2026-08-05 while building mnemosyne-mcp's Kindroid-generator story-context matching (a consumer of `memory_search`) — a caller today has no way to tell "OC is confident this is the right memory" from "this was the least-bad match in the topK window," which matters when something wants to act on a match automatically rather than show a ranked list to a human. **Needs research:** confirm current internals; if no score is surfaced, add one (RRF's fused score, or both raw FTS5 rank + cosine similarity) plus an optional caller-supplied confidence threshold that drops low-confidence results instead of always returning topK regardless of quality.
    - **IMPLEMENTED 2026-08-17 (search-surface v2).** Every `memory_search` / `context_recent`(with query) result now carries `relevance: {channel, rrf_score?, semantic_similarity?, keyword_rank?}` across MCP, REST, and CLI — `search_memory.execute` returns `list[ScoredMemory]` (frozen domain dataclass) from all three paths (hybrid, keyword-only, degraded). Per the caveat below, **no `min_confidence` threshold shipped**: RRF is rank-fusion, not calibrated confidence; the decision stands to observe real `semantic_similarity` values first and revisit a semantic-channel-only threshold if a consumer needs it. Original research record:
    - **Research done 2026-08-16 (review Batch B).** Confirmed: **no score of any kind reaches any surface.** `search_hybrid` computes RRF fused scores in its merge and discards them after ordering (returns `list[MemoryItem]`); `_semantic_search` computes cosine similarities and returns ranked ids only; the FTS5-only store path orders by bm25 rank internally and returns bare items. Surfacing scores therefore means changing the return shape of *three* paths (hybrid, FTS5-only, degraded-fallback) so they produce comparable fields, then threading through `search_memory.execute` → serializers → MCP/REST/CLI — a real surface change, deliberately NOT bolted onto the Batch B bug fixes. Design sketch for when it's picked up: per-result optional `relevance: {channel: hybrid|keyword|semantic, rrf_score?, semantic_similarity?, keyword_rank?}`. Caveat for the threshold half: RRF scores are rank-fusion values (bounded ≈2/61), not calibrated confidence — a raw threshold on them is close to meaningless across queries; `semantic_similarity` (unit cosine) is the only roughly interpretable knob, so if a threshold ships it should apply to that channel only. Recommend surfacing scores first (observability) and deciding thresholds after seeing real values. Prerequisite bugs fixed in Batch B: the three search-correctness defects (`b387d584`, `5e196fdb`) — scores surfaced before those fixes would have been confidently wrong.

21. **Explicit full-keyword / exact-match search mode.** Related to #20. Confirm whether `memory_search`'s FTS5 component can already be invoked in an exact-phrase/keyword-only mode (bypassing the semantic blend), or whether every call is always fused via RRF with no way to weight one signal exclusively. A caller wanting "does memory content literally contain this exact name/phrase" (e.g. mnemosyne-mcp's keyphrase-triggered story-context matching — built as client-side string matching today specifically because this wasn't confirmed available server-side) would benefit from a `mode: "hybrid" | "keyword" | "semantic"` parameter, or a documented query syntax for keyword-only queries. **Needs research**, same origin as #20.
    - **IMPLEMENTED 2026-08-17 (search-surface v2).** Both halves shipped: `mode: hybrid|keyword|semantic` on `memory_search` (MCP, REST, CLI) — `keyword` never touches the provider, `semantic` requires one and fails loudly (422/`PROVIDER_ERROR`) instead of silently degrading — and `phrase: bool` for exact adjacent-token phrase matching on the keyword channel (whole query as one quoted FTS5 phrase; whitespace-normalized substring match on the non-FTS5 fallback). mnemosyne-mcp's keyphrase matching can now be served server-side. Original research record:
    - **Research done 2026-08-16 (review Batch B).** Confirmed: **no per-call mode exists.** The dispatch is deployment-wide — `search_memory.execute` goes hybrid when an embedding service is wired (`OC_EMBEDDING_PROVIDER` set) and FTS5-only otherwise; a caller cannot choose per query, and semantic-only doesn't exist at all. A `mode` parameter would be additive and non-breaking (keyword → skip the embedding service; semantic → skip the keyword channel). Separate finding for the *exact-phrase* half: it is NOT what `mode=keyword` would give. `_fts5_escape` strips embedded quotes, wraps each whitespace token in double quotes, and **OR-joins the tokens** — so multi-word queries match any-token, and "does content contain this exact phrase" is not expressible today. True phrase match needs the whole query wrapped as one quoted FTS5 string (plus deciding how that composes with the escaping). If mnemosyne's keyphrase matching is the driving consumer, phrase support matters more than the mode knob — spec both together before building either.

22. **Word/term heatmaps over search results — exploratory, fit unconfirmed.** Raised by the operator alongside #20/#21: would some form of term-frequency / keyword-density "heatmap" over memory content (or over a search result set) be useful — e.g. visualizing which terms/entities dominate a project's memory, or which parts of a long memory a query actually matched on? No concrete consumer or use case pinned down yet, and it's explicitly uncertain whether this is worth building at all. Not a commitment — just a research thread to revisit once #20/#21 are better understood, since a heatmap would likely build on whatever scoring/matching primitives those add.

---

## Out of Scope (Explicitly NOT in v3)

These were considered during the hardening pass and *deliberately* rejected. Listed here so future sessions don't keep re-litigating them.

| Item | Why not |
|---|---|
| Multi-user / per-user namespacing | Single-user assumption stays. Projects already partition the keyspace; that's enough. |
| Memory versioning / edit history | `updated_at` is enough. If full audit becomes important, that's the events table from open question 2 — defer until a real consumer needs it. |
| Soft delete with recovery window | Hard delete stays. Backups are the recovery mechanism (and now they're automated + atomic). |
| Memory expiration / TTL | Out of scope. If wanted, an `oc memory delete --older-than 90d` CLI is enough; no need for in-DB expiry. |
| Provider failover for embeddings | One provider, configured. If down → degrade to FTS5 (open question / Phase 6.5). Don't build a multi-provider voting layer. |
| Embedding cost tracking | Personal project, no billing surface needed. |
| Memory similarity / "find related" tool | This is `memory_search` with the result's content as the query. No new endpoint or tool. |
| Reload-without-restart for config changes | Restart the container. It takes 2 seconds. Nothing in OC's surface needs hot-reload. |
| Hash-chained event audit trail | Open question 2 — defer until a real consumer needs it. v3 ships without events. |
| Telemetry / token tracking | Open question 8 — drop entirely. v3 doesn't track tokens or call counts. |
| Distributed deployment / clustering | Single container is the answer. |
| Auth beyond `OC_API_KEY` | Personal project, single-tenant. |
| Sync-as-store cloud architecture | Open question 12 — backup-only is the path; sync-as-store is premature. |
| Built-in observability stack (Prometheus, OTel) | Health endpoint + structured logs are enough. Operator can scrape if they want. |

---

## Intent and Context (Internal-Facing)

This section is for future developers (us, mostly) so we don't keep relitigating the same positioning questions every six months. **It is internal context, not user-facing copy.** None of the framing or product references here belong in the README or any user-facing doc.

### Project intent

OC exists to be the best version of itself: a memory MCP server that runs on your hardware, speaks the MCP protocol, stores decisions and context across sessions, and integrates cleanly with the user's actual stack (Claude Code on a Synology NAS via Portainer). The bar is high — clean architecture, honest tests, careful deployment. The scope is intentionally narrow: memory, embeddings, projects, git-onboard. We do those well. We don't try to do everything.

We are not chasing market share, benchmark wins, or feature parity with VC-backed products. We are building something we use, that we can trust, that will still work when we open it in three months. That's the standard.

### Competitive landscape (as of May 2026)

The agent-memory category is mature and crowded. Knowing what exists helps us make architectural decisions; it does not pressure us to feature-match.

**Major players:**

- **Mem0** — biggest community, "memory as a product," vector + graph backed
- **Zep** — temporal knowledge graph with bitemporal facts; enterprise-priced
- **Letta (formerly MemGPT)** — "memory as OS" approach + new "Context Repositories" feature (Feb 2026) using markdown files in git-backed repos with filesystem-shaped retrieval; argues `grep`/`search_files` semantics outperform specialized memory APIs because LLMs are post-trained on filesystem operations
- **Cognee** — knowledge-graph-first GraphRAG
- **Cloudflare Agent Memory** (private beta May 2026) — Durable Objects + Vectorize + Workers AI; multi-stage extraction with verification, classification into Facts/Events/Instructions/Tasks, keyed-fact supersession, 5 parallel retrieval channels (FTS, exact-key, raw, vector, HyDE) with RRF
- **doobidoo/mcp-memory-service** — closest direct architectural competitor; MCP + REST, knowledge graph with typed edges, autonomous consolidation, multiple storage backends (SQLite-vec / Cloudflare / Milvus); ~1.8k stars, 299 releases, accelerating cadence (5 releases in 2 months as of May 2026); ships features OC doesn't have (contradiction tracking, memory quality orchestrator, dormant memory detection, Remote MCP for browser-native claude.ai access, OAuth 2.1)
- **claude-mem (thedotmack)** — Claude Code-specific memory plugin, ~50-70K stars and growing rapidly; auto-captures session activity via Claude agent-sdk and re-injects on session start
- **codebase-memory-mcp / code-memory / agentmemory / Cipher MCP** — code-intelligence flavored MCP memory servers with AST parsing and codebase ingestion

**Anthropic native memory (the strategic context):**

Anthropic has shipped or is shipping memory natively across Claude surfaces:

- Claude.ai / Claude app memory (free tier, March 2026) — auto-summarizes conversations
- "Auto Dream" in Claude Code (reportedly shipped quietly) — Auto Memory takes notes during work; Auto Dream periodically reviews, strengthens what's relevant, removes stale, reorganizes into indexed topic files
- Claude Managed Agents memory (public beta, April 23, 2026) — filesystem-mounted memory, exportable via API/Console
- Memory Tool in Claude API (GA at `platform.claude.com`)

This is the elephant in the room for any memory MCP targeting Claude. It does not change OC's value but it does narrow the audience. People who use OC instead of Anthropic's native memory will do so because they want their own infrastructure, cross-tool MCP access (Goose, Open WebUI, etc.), explicit-save discipline rather than automatic capture, or independence from Anthropic's roadmap.

### Benchmarks (LongMemEval, LoCoMo, BEAM)

Standard benchmarks exist. Vendor-published scores are inconsistent (Mem0 self-reports 91.6% on LoCoMo while a Letta-published comparison reports Mem0g at 68.5% on the same benchmark — different methodology, different harness, different LLM). We don't chase these benchmarks. If we ever run them, it's curiosity, not pressure. Our use case (single user, Claude Code, NAS-hosted) doesn't map cleanly to either benchmark's methodology anyway.

A genuine finding from the literature worth knowing: **memory's value prop is token efficiency, not accuracy.** Long-context LLMs achieve higher factual recall on most memory benchmarks at low context sizes; memory systems win on token cost (~90% reduction) and on resilience at very long context (full-context shows ~30-55% accuracy drop at extreme histories). When framing OC's value internally, "compresses without falling off the cliff" is a more accurate framing than "more accurate than dumping context."

### Architectural philosophy reconciliation

Two competing camps in the literature:

- **"Filesystem all you need"** (Letta) — argues LLMs handle filesystem operations (`grep`, `cat`, `ls`) better than specialized memory APIs because they're post-trained on coding tasks; their LoCoMo benchmark (74% with filesystem ops vs Mem0g 68.5%) supports the position, though Letta's a memory company arguing for their product so eye with caution
- **"Purpose-built APIs outperform raw filesystem"** (Cloudflare) — argues constrained, well-designed APIs outperform raw filesystem access for cost and complex reasoning; their multi-channel retrieval architecture supports the position, though Cloudflare's also a memory company arguing for their product

The honest read: both are self-serving. The truth probably depends on the agent's post-training and the workload. For OC, the pragmatic posture is: **keep the tool *interface* filesystem-shaped semantically (clear verbs, predictable behavior, agent-friendly tool descriptions) even if the *implementation* uses whatever's most accurate underneath.** This is why our MCP tool surface should look like `memory_save / memory_search / memory_get / memory_delete` rather than something more exotic — the verbs map to operations LLMs already know.

If we ever revisit storage architecture, Letta's Context Repositories (markdown-files-in-git) is worth understanding as a v4-or-later alternative philosophy. For v3, SQLite + embeddings stays.

### Why we're shipping v3 anyway

After all of the above: yes, the category is crowded, yes Anthropic is moving in natively, yes others ship faster. We ship v3 because:

1. We use OC. v2 is feature-complete but bloated; v3 is leaner and more correct.
2. Our use case is real and ongoing — Claude Code sessions across multiple machines, decisions worth preserving, context that survives compression.
3. The architecture work in v3 (schema migration framework, online backups, embedding degradation policy, maintenance loop) makes OC genuinely better at its narrow job.
4. Building it carefully is its own reward. Future-us will thank us.

This section gets re-evaluated on the v4 conversation, not before.

---

## What Stays in `archive/openchronicle.v2`

The branch is a feature museum. Specifically preserved for future resurrection:

- **Storytelling plugin** — full game mechanics, narrative engines, persona extractor, scene management, bookmarks, timelines. ~1300+ LOC across `plugins/storytelling/`. ~208 tests.
- **5 LLM adapters** — async-native OpenAI, Anthropic, Groq, Gemini, Ollama with streaming + tool use + 53 contract tests.
- **Privacy gate** — 6 PII categories with Luhn validation.
- **MoE consensus engine** — Jaccard scoring, parallel quality pool, 32 tests.
- **Hybrid routing** — rule + linear ML assist, NSFW scoring, mode detection, 1278+ test lines.
- **Hash-chained event audit trail** — verification + replay services.
- **`prepare_ask` pipeline** — memory injection, system prompt assembly, time context, mode-aware builders.
- **Conversation engine** — `ask_conversation`, conversation persistence, turn history, mode parity.
- **Asset management** — file storage, SHA-256 dedup, generic linking, 4 MCP tools, 4 CLI commands.
- **Media generation** — 5 adapters (stub, Ollama, OpenAI gpt-image-1, Gemini, xAI Grok Imagine).
- **Webhook service** — HMAC signing, background dispatcher with retry, fnmatch event filtering, 74 tests.
- **Discord interface** — bot, slash commands, session mapping, message splitting, PID file guard, 85 tests.
- **Scheduler** — tick-driven, atomic claim, 53 tests.
- **MCP tool tracking** — usage stats per tool.
- **Manager/worker orchestration** — task parallelism + worker coordination.

Each of the above is git-checkout-able from v2 archive when a future project needs it.

---

## Risks + Mitigations

| Risk | Mitigation |
|---|---|
| v3 ships missing a feature actively in use | Today's smoke test confirms what's used. If something's discovered later, copy from v2 archive. Net cost: a session of work. |
| Schema migration corrupts the live DB | Test migration on a copy first. Take a `oc db backup` before running on production. Keep v2 stack reachable for rollback. |
| FastMCP doesn't mount cleanly into FastAPI | Verify in Phase 6 with a spike. Fallback: keep two ASGI apps in one process via uvicorn path-based routing. |
| Force-pushing main breaks existing workflows | The v1→v2 force-push precedent suggests this is acceptable. Coordinate with any active sessions before the push. |
| The v3 branch becomes "perfect/never-shipping" | The kill list is the discipline. Phases 1-4 are pure deletion — they should compress to a single afternoon if scope holds. |
| Loss of OWUI/external HTTP integrations | None currently active (the OWUI integration was reverted today). |
| Existing memories' embeddings break with schema changes | They shouldn't — `memory_embeddings` table stays. Verify in migration script. |
| MCP clients silently break post-cutover (config drift) | Client Cutover Checklist enumerates every known client; verification per client is a hard gate before declaring cutover complete. |
| Pre-migration backup is unrecoverable when needed | Backup is taken twice (pre-flight + immediately before migration), copied off the NAS, and only deleted after Day 7 success. Online backup API ensures backups are integrity-checkable. |

---

## Estimated Effort

Rough order-of-magnitude:

- Phase 0 (branch creation): **5 minutes**
- Phase 1-4 (cuts): **1-2 sessions**, mostly mechanical deletion
- Phase 5 (schema migration + framework + online backup): **1.5 sessions** including migration script, framework, backup module, fixture DBs, CI test
- Phase 6 (ASGI unification): **1 session** including verification
- Phase 6.5 (maintenance loop + embedding degradation): **1 session** (~150 LOC loop + ~80 LOC backup + ~50 LOC CLI + degradation policy + ~25 tests)
- Phase 7 (docs sweep + deps + repo polish): **1.5-2 sessions** — full classification of every doc, archive v2 versions, rewrite the major surfaces (CODEBASE_ASSESSMENT, ARCHITECTURE, env_vars, README, CLAUDE.md), write three new docs (STABILITY, security_posture, MAINTENANCE), audit Serena memories
- Phase 8 (production cutover): **30 minutes** for migration + redeploy + smoke test
- Phase 9 (decommission): **15 minutes**

Total: **~7-8.5 focused sessions** if scope holds.

---

## Decisions Captured Before Writing This Plan

From the 2026-05-02 evening session:

- v3 is a clean-room rewrite, not refactor (matches v1→v2 pattern) — **confirmed**
- MCP and HTTP fold into one ASGI process — **proposed by Claude, confirmed by user**
- Webhooks: not used → cut entirely (no archive needed) — **confirmed by user** ("nope, not currently")
- Storytelling: not used → archive on v2, possibly resurrect as `narrator-mcp` later — **confirmed by user** ("no, not currently")
- Conversation engine: archive on v2, moves with the next consumer (likely storytelling) — **confirmed by user**
- Lean focus: "OC stays lean, becomes the best at what it does" — **stated by user**

---

## What This Plan Does NOT Cover (Out of Scope for v3)

- Building `narrator-mcp` (the future storytelling project). v3 just makes room for it.
- Changing the MCP protocol or transport (still streamable-http, still FastMCP).
- Migrating to a different programming language. (Python stays.)
- Replacing SQLite. (Stays.)
- Multi-tenancy or auth beyond the existing `OC_API_KEY` middleware.
- Distributed deployment. (Single container is the answer.)
- Observability beyond the existing health endpoint.

---

## Next Steps

1. **User reviews this plan** before any branch creation or code changes.
2. **Discuss + adjust** in the next session — refine the kill list, answer open questions, confirm phase ordering.
3. **Sign-off** triggers Phase 0 (branch creation).
4. Sessions following the sign-off execute Phases 1-9.

This document remains the canonical source of truth for v3 scope until v3 ships, at which point it becomes a historical artifact.
