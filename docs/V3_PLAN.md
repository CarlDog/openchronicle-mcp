# OpenChronicle v3 — Memory-Only Rewrite Plan

**Status:** Draft, 2026-05-02. Not started. Awaiting branch creation.
**Author of this draft:** Claude (this session)
**User sign-off required before any code changes.**

---

## TL;DR

- **v3 scope:** OC becomes the best memory database for LLM agents. Nothing else.
- **What goes:** conversation engine, all 5 LLM adapters, MoE, privacy gate, storytelling plugin, webhooks, assets, media, scheduler, Discord, ~1600 tests.
- **What stays:** memory + embeddings + projects + git-onboard + the two transports (MCP and HTTP REST).
- **Architectural change:** fold MCP and HTTP into a single ASGI process / single container / single port.
- **Preservation strategy:** everything cut moves to `archive/openchronicle.v2`. No code is lost. Future projects (e.g. `narrator-mcp` if storytelling is revived) reach back into the archive.
- **Branch strategy:** mirrors v1→v2 transition. Develop on `refactor/v3-memory-core`, replace `main` when ready, archive v2 on its own branch.

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
- `/api/v1/health` (full diagnostics)
- `/api/v1/onboard/git` (mirror of MCP tool)
- (NO conversation, NO assets, NO webhooks, NO media, NO stats endpoints)

**CLI:**

- `oc memory <save|search|list|get|update|delete|pin|stats|embed>`
- `oc project <list|create>`
- `oc db <info|vacuum|backup|stats>`
- `oc onboard git`
- `oc serve` (starts the unified ASGI app)
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
| Scheduler service | Implemented | **Cut → archive** |
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
3. **Schema migration script** runs cleanly on a copy of the v2 NAS DB and produces a v3-shaped DB with all 23 existing memories preserved, embedded, and searchable
4. **Smoke test** — equivalent to today's session walkthrough (memory CRUD, search, embed force-rerun, onboard_git) passes against a v3 instance running locally and against the staged NAS deployment
5. **Single-container compose** (`docker-compose.nas.yml` slimmed to one service) builds and deploys via Portainer redeploy
6. **No regressions** in the existing 23 memories' content or embeddings
7. **CLAUDE.md updated** to reflect v3 architecture (drop sections about conversation/storytelling/etc.)
8. **Status doc updated** to a new `docs/CODEBASE_ASSESSMENT.md` rev for v3

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
- `services/scheduler.py`
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

### 3. Schema migration script

- `scripts/migrate_v2_to_v3.py` (per above)
- Companion `scripts/verify_v3_db.py` for post-migration checks

### 4. Single-service compose

- `docker-compose.nas.yml` — drop `mcp` and `discord` service definitions; `serve` becomes the only service; rename to `oc` for clarity (optional)
- Internal port stays `8000`; host port stays `18000` (operator-friendly continuity)
- `:18001` (MCP) is now `/mcp` path on `:18000`

### 5. New CLI surface

- `oc serve` runs the unified ASGI (current behavior, just with embedded MCP)
- Drop `oc mcp serve` (no longer separate)
- Drop dropped commands (per kill list)

### 6. Updated docs

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

### Phase 5: Schema migration

- Slim `sqlite_store.py` to memory tables only
- Drop migrations for cut tables
- Write `scripts/migrate_v2_to_v3.py`
- Test against a copy of the v2 NAS DB
- Commit: "v3 phase 5: schema migration"

### Phase 6: ASGI unification

- Mount FastMCP into FastAPI app
- Drop separate `mcp` service entry point
- Slim `docker-compose.nas.yml` to one service
- Verify locally: MCP via `/mcp` works, REST via `/api/v1/*` works
- Commit: "v3 phase 6: unified ASGI"

### Phase 7: Polish + docs

- Rewrite `docs/CODEBASE_ASSESSMENT.md` for v3
- Slim `docs/architecture/ARCHITECTURE.md`
- Update `CLAUDE.md`
- Update `pyproject.toml` to drop unused deps (`anthropic`, `groq`, `google-generativeai`, `discord.py`, etc.)
- Commit: "v3 phase 7: docs + deps"

### Phase 8: Production cutover

- Deploy v3 image to a STAGING port (e.g., `:28000`) via temporary stack copy
- Run schema migration on a clone of the production DB
- Smoke test the staging instance
- If green: stop the v2 stack 151, run migration on production DB, replace stack with v3 compose, redeploy
- If red: roll back, debug, re-stage

### Phase 9: Decommission

- Tag the merge commit `v3.0.0`
- Update README + GitHub repo description
- Confirm `archive/openchronicle.v2` is preserved on origin
- Close out follow-up tasks from this session

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

11. **Cloud storage backup/sync for the memory store** — should v3 support pushing the SQLite DB (or individual memory items) to cloud providers (Dropbox, Google Drive, Box, S3) as an online backup/sync mechanism? Two shapes worth considering:
    - **Backup-only (simpler):** a periodic job (daemon thread or external cron) that uploads `oc db backup` artifacts to cloud storage. SQLite stays the source of truth, cloud is disaster recovery + cross-device restore. Implementable as a single CLI command (`oc backup push --provider dropbox --token $TOKEN`) plus a scheduled-job loop. Pluggable provider abstraction so adding new clouds is trivial.
    - **Sync-as-store (much harder):** memories live IN cloud storage and the SQLite DB becomes a local cache. Requires conflict resolution, offline operation semantics, sync windows, integrity verification. Likely premature for v3 scope.
    - **Recommendation:** plan for backup-only as a v3.1 follow-up feature, not a day-1 ship item. Keep the v3 architecture LLM-side untouched, but design the storage layer with a clean enough seam that a backup-pushing daemon is straightforward to bolt on later. Specifically: keep `oc db backup` working (already exists in v2), keep DB writes through `SqliteStore`, don't bake cloud-specific assumptions into the core. If user wants this on day 1, it adds maybe 1-2 sessions of work for backup-only with one provider (Dropbox is easiest — official SDK, app-folder pattern keeps blast radius small).
    - **Open sub-questions:**
      - Should the backup target be the whole SQLite file, or a JSON export of memories+projects+embeddings? (Whole file is simpler, smaller diffs since it's incremental SQLite. JSON export is cross-version-portable.)
      - Should embeddings be backed up or regenerable? (Regenerable is cheaper to store but slow to restore for 1000s of memories.)
      - Sync window: every N minutes? On every memory write? Manual trigger only?
      - Encryption at rest in the cloud? OC's data is fairly sensitive (decisions, project context, sometimes secrets-adjacent memories). Recommend encrypting before upload via a user-supplied key.

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
| Existing 23 memories' embeddings break with schema changes | They shouldn't — `memory_embeddings` table stays. Verify in migration script. |

---

## Estimated Effort

Rough order-of-magnitude:

- Phase 0 (branch creation): **5 minutes**
- Phase 1-4 (cuts): **1-2 sessions**, mostly mechanical deletion
- Phase 5 (schema migration): **1 session** including migration script + tests
- Phase 6 (ASGI unification): **1 session** including verification
- Phase 7 (docs + deps): **1 session**
- Phase 8 (production cutover): **30 minutes** for migration + redeploy + smoke test
- Phase 9 (decommission): **15 minutes**

Total: **~5-6 focused sessions** if scope holds.

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
