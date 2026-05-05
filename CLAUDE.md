# CLAUDE.md

## Project Status File

**`docs/CODEBASE_ASSESSMENT.md`** — single source of truth for this project.

## Project-Specific Notes

- **Docs + memories before every commit.** Standing rule (2026-05-05). Before
  any `git commit` on this repo, update the affected docs (at minimum
  `docs/CODEBASE_ASSESSMENT.md`; for in-flight work also `docs/V3_PLAN.md`
  status section and the CLAUDE.md "Current Sprint" section), and save a
  milestone/decision/scope memory to OC if the MCP server is reachable. The
  commit and the docs land together — never one without the other.
- **No backwards compatibility.** Personal project, no public users, no production.
  Break whatever needs breaking.
- **`main` is v2.** The v1 codebase is archived on `archive/openchronicle.v1`.
  The `refactor/new-core-from-scratch` branch no longer exists — all development
  happens on `main`.
- **Post-CI redeploy convention.** When a push to `main` changes anything that
  ships in the runtime image (`src/`, `plugins/`, `pyproject.toml`, `Dockerfile`,
  `docker-compose.nas.yml`) and both GitHub Actions workflows go green
  (`Test` + `Build and Push Docker Image`), redeploy the NAS-hosted stack via
  `portainer-mcp`. Doc-only / hook-only / workflow-only pushes don't need a
  redeploy — the user will trigger one manually if needed.

  Lookup the stack id dynamically (don't hardcode it):

  ```text
  portainer_list_stacks → filter for name == "openchronicle-mcp" → use that .Id
  portainer_redeploy_git_stack(stack_id=<id>, confirm=true, pull_image=true)
  ```

  Verify with `mcp__openchronicle__health` — a recent `db_modified_utc` confirms
  the new container is alive.

## Current Sprint

**Status:** v3 active development on `v3/develop`. Phases 0-2 complete
(2026-05-05). v2 frozen at `archive/openchronicle.v2`; the deployed NAS
stack 151 still runs v2 until Phase 8 cutover.

**Phase progress:**

- ✅ **Phase 0** — `archive/openchronicle.v2` snapshot pushed, `v3/develop`
  branch created
- ✅ **Phase 1** (interfaces slimmed) — Discord/asset/conversation/webhook/
  media/hooks deletion across API+MCP+CLI; chat/rpc/stdio modules removed;
  MCP tool descriptions rewritten; 570 tests passing
- ✅ **Phase 2** (application slimmed) — orchestrator/scheduler/MoE/webhook/
  asset/output/llm services deleted, routing/runtime/replay/observability/
  policies directories deleted, ~30 use cases cut, plugins/ removed,
  container reduced to memory + embedding + git-onboard wiring; 345 tests
- ✅ **Phase 3+4** (infrastructure + domain slimmed) — combined commit:
  llm/media/privacy/router_assist/routing/logging dirs deleted; sqlite_store
  rewritten 1882→470 LOC; schema reduced 18→3 tables (projects, memory_items,
  memory_embeddings) + memory FTS5; 15 cut domain models, 9 cut ports, 3 cut
  services; `conversation_id` dropped from MemoryItem (Q1 locked); new
  `ProviderError`/`ConfigError` domain exceptions; git_onboard service drops
  LLM synthesis (caller-side now); 294 tests passing
- ✅ **Phase 5** (schema migration + framework + online backup +
  export/import) — versioned `Migrator` with savepoint-atomic application
  of `migrations/NNN_*.sql` files; `001_initial.sql` is the v3 baseline;
  `infrastructure/persistence/backup.py` uses `sqlite3.Connection.backup()`
  with atomic `.tmp`→rename; `oc memory export/import` (JSON envelope,
  format_version=1, embeddings excluded); one-shot `scripts/migrate_v2_to_v3.py`
  and `scripts/verify_v3_db.py`; 323 tests passing
- ✅ **Phase 6** (ASGI unification + `OC_LOG_FORMAT`) — FastAPI host mounts
  FastMCP's streamable-HTTP app at `/mcp`; lifespan drives FastMCP's
  session_manager so anyio task groups attach/detach with uvicorn
  shutdown; `OC_LOG_FORMAT=human|json` (Q19 locked default `human`) via
  new `interfaces/logging_setup.py`; `docker-compose.nas.yml` collapsed
  from 3 services to 1; Dockerfile drops dead extras
  (anthropic/groq/gemini/discord) and dead paths; 331 tests passing
- ✅ **Phase 6.5** (maintenance loop + embedding degradation policy) —
  asyncio `MaintenanceLoop` with per-job + global locks (overlap-skip
  observable across ticks, sequential within process), 5 job handlers
  (db_backup with 7-backup retention, db_vacuum runs db_backup first,
  db_integrity_check toggles `container.maintenance_degraded`,
  embedding_backfill, git_onboard_resync placeholder), wired into
  FastAPI lifespan; new `/api/v1/maintenance/status` endpoint;
  `oc maintenance list/run-once` CLI; `OC_MAINTENANCE_DISABLED` opt-out;
  `EmbeddingService.search_hybrid` falls back to FTS5-only on provider
  failure and bumps failure counter; container `embedding_status_dict`
  reports `degraded`/`active` with counts; 349 tests passing
- ✅ **Phase 7** (docs sweep + repo polish) — every doc classified
  into update/archive/delete; v2 docs moved under `docs/archive/v2/`
  with an index README; v3 docs rewritten (ARCHITECTURE, cli/commands,
  env_vars, config_files, mcp_client_setup, mcp_server_spec,
  docker_local_dev); three new docs (api/STABILITY.md,
  configuration/security_posture.md, architecture/MAINTENANCE.md);
  README rewritten per V3_PLAN voice rules; pyproject bumped to
  v3.0.0.dev0 with dead extras dropped. Repo polish swept additional
  v2 cruft (model configs, fixtures, integration tests, PowerShell
  scripts for cut commands, dead compose overlays, stale CI extras).
  349 tests passing
- ⏭ **Phase 8** (NAS cutover) — next: take production backup, run
  `scripts/migrate_v2_to_v3.py` on a copy of the live DB, deploy v3
  image to NAS stack 151, run `oc maintenance run-once
  embedding_backfill`, verify via smoke test, update client configs
- pending: Phase 9 (decommission, Day 7+ post-cutover)

**Locked decisions** (open questions 1, 4, 6, 13, 14, 19): drop
`memory_items.conversation_id`; unified ASGI on port `:18000`; cut plugin
system entirely; MCP tool description quality pass done; ship
`oc memory export/import` day 1; `OC_LOG_FORMAT=human|json` default human.

See [docs/V3_PLAN.md](docs/V3_PLAN.md) for the canonical phase tracker and
[docs/CODEBASE_ASSESSMENT.md](docs/CODEBASE_ASSESSMENT.md) for the v2 → v3
delta.

**2026-05-02 plan deltas (two passes):**

1. **Scheduler decision flipped** — v2 scheduler stays cut (orchestrator-coupled,
   overkill), replaced by a minimal in-process maintenance loop as new Phase 6.5
   handling DB hygiene, embedding backfill, optional git-onboard resync. ~150 LOC,
   no DB-backed queue, configured via `core.json`.
2. **Hardening pass** — six tier-1 items folded into the plan: schema migration
   framework (versioned forward-compat, not just the v2→v3 one-shot),
   backup-before-destructive-maintenance policy, SQLite online backup API
   (replacing v2's likely file-copy bug), CI migration tests against fixture v2
   DBs, explicit embedding-failure degradation policy (FTS5 fallback for search,
   queued backfill for save), curated OpenAPI as the default surface (no more
   `/memory-tools/openapi.json` hack). Tier-2 items added as open questions
   13-18; tier-3 items appended as an explicit "Out of Scope" appendix so they
   don't keep getting re-litigated.
3. **Phase 7 docs sweep expanded** — every doc in the repo gets classified
   (update / archive to `docs/archive/v2/` / delete), three new docs added
   (`api/STABILITY.md`, `configuration/security_posture.md`,
   `architecture/MAINTENANCE.md`), Serena memories audited for stale
   v2 references. Phase 7 grew from "1 session" to "1.5-2 sessions" to reflect
   the real scope.

See [docs/V3_PLAN.md](docs/V3_PLAN.md) for full details.

While v2 is in maintenance mode, the deployed NAS stack 151 stays on the v2
codebase running healthy (memory + embedding + search verified end-to-end as
of 2026-05-02). See [docs/CODEBASE_ASSESSMENT.md](docs/CODEBASE_ASSESSMENT.md)
for v2 feature status.

**Prior phase context:** Backlog reclassification (extension / external-MCP / core
lens). The `storytelling` extension lives in this repo's `plugins/storytelling/`.
Media generation is done (`MediaGenerationPort` with 5 adapters:
stub, Ollama, OpenAI gpt-image-1, Gemini dual-surface, xAI Grok Imagine; unified model
config with `image_generation` capability tag; `OC_MEDIA_MODEL` derives provider; 69 tests).
Ollama CLI is done (`oc ollama list|show|add|remove|sync`, capability inference from
Ollama API, operates against resolved config dir, 32 tests).
Capability-aware routing is done (`ModelConfigLoader` parses capabilities,
`RouterPolicy` filters by `required_capabilities`, `NO_CAPABLE_MODEL` error, 12 tests).
HTTP API is done (`interfaces/api/`, FastAPI, 41 REST endpoints mirroring MCP tools,
API key auth, rate limiting, shared serializers, 51+ tests, auto-starts with `oc serve`).
MoE execution strategy is done (`application/services/moe_execution.py`, Jaccard
consensus, `--moe` CLI/MCP, 32 tests).
MCP server is done (`interfaces/mcp/`, 32 tools, 47 tests + 7 posture, `oc mcp serve`
CLI, stdio + SSE transports, lazy import guard).
Asset management is done (`domain/models/asset.py`, `application/services/asset_storage.py`,
`application/use_cases/upload_asset.py`, `application/use_cases/link_asset.py`,
4 MCP tools, 4 CLI commands, SHA-256 dedup, generic linking, 40 tests).
Discord interface is done (`interfaces/discord/`, `commands.Bot` subclass, 6 slash
commands, session mapping, message splitting, 85 tests, `oc discord start` CLI).
Scheduler service is done (tick-driven, atomic claim, 53 tests, CLI + RPC).
LLMPort function calling/tool use is done (all 6 adapters, 53 contract tests).
Time context injection is done (current time, last interaction timestamp,
seconds delta — raw data in every conversation turn for bot time awareness).
File-based config is done (single `core.json`, enriched model configs, plugin
configs co-located at `plugins/<name>/config.json`).
Memory System Phase 1 is done (`memory_update` use case with `updated_at` tracking,
tag-filtered search with AND logic on `search_memory`, 19 new tests).
Memory System Phase 1.1 is done (interface parity: `memory_get`/`delete`/`stats` on MCP + API,
pagination with `offset`, source index, streaming telemetry fix, observability events
`memory.search_completed` + `context.assembly_breakdown`, 27 new tests).
Config externalization is done (conversation defaults + Discord operational
settings wired through three-layer precedence, hygiene test prevents drift).
Docker CI is done (GitHub Actions multi-arch build to `ghcr.io/carldog/openchronicle-mcp`,
`latest` + SHA tags, GHA cache, `.gitattributes` for LF shell scripts).
Enterprise Tightening Pass A is done (domain exceptions `NotFoundError`/`ValidationError`,
global FastAPI exception handlers, Pydantic `Field()`/`Query()` input validation,
sqlite_store rowcount checks, file path validation, ~30 use-case migration sites,
32 new tests, 1128 total).
Enterprise Tightening Pass B is done (DRY extraction `utc_now()`/`parse_csv_tags()`,
LLM adapter timeouts with `OC_LLM_TIMEOUT` env var, container lifecycle `close()`/
context manager, config `__post_init__` validation, CORS tightening, logging in 12
use cases + 2 services, error code normalization to SCREAMING_SNAKE_CASE, CLI bug
fixes, 49 new tests, 1177 total).
Enterprise Tightening Pass C is done (API/MCP parity `search_turns` endpoint,
`Path()` validation on all API path params, `Query()` constraints on system routes,
MCP tool input validation/clamping across 7 tools, Gemini error code classification,
`OLLAMA_HOST` documented, 21 new tests, 1198 total).
Memory System Phase 2 is done (external turn recording `turn_record` MCP + API,
standalone context assembly `context_assemble` MCP + API with shared `context_builder`
service refactored from `prepare_ask`, incremental `onboard_git` with watermark tracking,
`list_memory_by_source` promoted to `MemoryStorePort`, 39 new tests, 1237 total).
Memory v1 (Phase 3) is done (embedding-based semantic search via `EmbeddingPort` ABC
with stub/OpenAI/Ollama adapters, `EmbeddingService` hybrid FTS5+cosine retrieval via
Reciprocal Rank Fusion, `memory_embeddings` table with BLOB storage and CASCADE cleanup,
backfill CLI/MCP/API, backwards-compatible default `OC_EMBEDDING_PROVIDER=none`,
54 new tests, 1291 total).
Webhook Service (Phase 4) is done (`application/services/webhook_service.py`,
`application/services/webhook_dispatcher.py`, HMAC-SHA256 signing, background
dispatcher thread with queue + exponential backoff retry, composite `emit_event`
pattern, `fnmatch` glob event filtering, 3 MCP tools, 5 API endpoints, 4 CLI
commands, 74 new tests, 1365 total).
Data directory centralization is done (`application/config/paths.py`, `RuntimePaths`
frozen dataclass with 7 fields, four-layer precedence: constructor > per-path env >
`OC_DATA_DIR`-derived > default, `SqliteStore`/`AssetFileStorage` defaults removed,
`CoreContainer`/CLI/Discord all wired through `RuntimePaths.resolve()`, Docker
entrypoint expanded, 12 new tests).
Embedding observability is done (health endpoint reports embedding status
active/disabled/failed with coverage stats, startup INFO logging on adapter init,
per-item backfill resilience with error isolation, configurable timeout via
`OC_EMBEDDING_TIMEOUT` env var / `embedding.timeout` core.json key, 1438 total).
Plugin repo separation reverted (2026-04-29) — `OpenChronicle/plugins` deleted
along with the connector model; storytelling stays in this repo's `plugins/`.
Phase 5 IDE automation hooks prototype is done (Claude Code `PreCompact` hook
injects OC context memories before compression, `SessionStart(compact)` hook
reloads after compression, `--full` flag on `oc memory search` for
machine-readable context injection, hooks in `.claude/hooks/` gitignored).
Storytelling Plugin Phase 3 is done (conversation mode integration: `ModePromptBuilder`
protocol in `PluginRegistry` port, `prepare_ask()` delegates system prompt to active
mode's builder, story builder assembles characters/style guides/locations/worldbuilding
from project memory via tag-filtered search, `make_memory_search_closure` extracted to
`context_builder.py`, CLI `oc story characters|locations|search`, 20 new tests, 1767 total).
Storytelling Plugin Phases 4-7 are done (game mechanics engine with dice/resolution/stats/branching,
bookmark & timeline with auto-bookmark on scene save, narrative engines with LLM-based
consistency checking and emotional arc analysis, persona extractor stub with text-only
extraction; 13 new files, 12 new handlers, 11 new CLI commands, 208 new tests, 1975 total).
OpenAI-compatible API layer dropped (2026-04-29) — `interfaces/api/routes/openai_compat.py`,
`tests/test_openai_compat.py`, `tests/integration/test_openai_stress.py` deleted (645 + 844 + 894 LOC,
56 tests). OC's brain now reaches MCP-aware clients (Claude Code, Goose, Open WebUI tool loop)
via `conversation_*` MCP tools — chat-box-driven path through OC's pipeline retired alongside
its `_get_or_create_webui_session` race condition.
Conversation mode parity is done (`conversation_set_mode`/`conversation_get_mode`
MCP tools, `POST`/`GET /api/v1/conversation/{id}/mode` endpoints, wraps existing
`convo_mode` use case; closes the gap that left story/persona modes unreachable
from MCP/API clients despite working in CLI + Discord, 6 new tests).
2026-04-29 incident remediation + connector model retired (production DB
`memory_embeddings` B-tree corruption recovered via Plan B rebuild —
plex memory items stripped, 49 non-plex items preserved, integrity_check ok;
`hello_plugin`/`plaid_connector`/`plex_connector` deleted from `plugins/` along
with 8 dedicated test files; 4 fixture-using tests migrated from `hello.echo` to
`story.draft`; storytelling plugin gained `PLUGIN_ID`/`NAME`/`VERSION`/`ENTRYPOINT`
metadata constants — contract was previously enforced only via hello_plugin;
`/data` migrated from Windows bind-mount to Docker named volume `oc-data` to fix
SQLite WAL fsync risk on bind-mount FS; root cause: plex webhook bombardment +
unclean container restart on bind-mount = torn checkpoint write; 1921 tests pass).

## Build and Development

```bash
# Install in development mode
pip install -e ".[dev]"

# With optional LLM providers
pip install -e ".[openai]"    # OpenAI support
pip install -e ".[ollama]"    # Ollama support
pip install -e ".[discord]"   # Discord bot support
pip install -e ".[mcp]"      # MCP server support

# Setup pre-commit hooks
pip install pre-commit && pre-commit install
```

## Testing

```bash
# Run all tests (excludes integration tests by default)
pytest

# Run integration tests (requires OC_LLM_PROVIDER, OPENAI_API_KEY env vars)
pytest -m integration

# Run specific test file or single test
pytest tests/test_budget_gate.py
pytest tests/test_budget_gate.py::test_specific_name -v
```

## Linting and Formatting

```bash
# Format and lint with ruff
ruff format src tests plugins
ruff check --fix src tests plugins

# Type checking
mypy src tests plugins --config-file=pyproject.toml

# Markdown linting
npm run lint:md:fix

# Run all checks (what pre-commit does)
pre-commit run --all-files
```

## Architecture

Python 3.11+ project using **hexagonal architecture**: `domain/` (pure business
logic, ports) -> `application/` (use cases, policies, orchestration) ->
`infrastructure/` (LLM adapters, persistence, routing). CLI and API live in
`interfaces/`. See [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)
for the full directory tree and layer descriptions.

**Key Concepts:**

- **Ports**: Abstract interfaces in `domain/ports/` that infrastructure implements
- **Event Model**: Hash-chained events for tamper-evident task timelines (`prev_hash` -> `hash`)
- **Task Handlers**: Async functions registered by handler name (e.g., `story.draft`)
- **Plugins**: Loaded from `OC_PLUGIN_DIR` (default `plugins/`), via `importlib.util`. The only current extension is `storytelling`, in this repo's `plugins/` directory. Plugins can register **mode prompt builders** (`ModePromptBuilder` protocol) to override system prompts when a conversation is in their mode. Domain integrations (Plex, etc.) belong as their own MCP servers, composed by the client — not as plugins inside OC
- **Routing**: Provider/model selection via pools (fast, quality, nsfw) with fallback support
- **Scheduler**: Core service in `application/services/scheduler.py` (not a plugin)
- **Discord**: Interfaces driver in `interfaces/discord/` (optional extra, not a plugin)
- **MCP Server**: Interfaces driver in `interfaces/mcp/` (optional extra, 32 tools, FastMCP)
- **HTTP API**: Interfaces driver in `interfaces/api/` (FastAPI, 41 REST endpoints, auto-starts with `oc serve`)
- **MoE Execution**: `application/services/moe_execution.py` — Mixture-of-Experts consensus strategy (`--moe` flag)
- **Asset Management**: `domain/models/asset.py` + `application/services/asset_storage.py` — filesystem storage, SHA-256 dedup, generic entity linking
- **Embedding Service**: `application/services/embedding_service.py` — hybrid FTS5+cosine search via RRF, `EmbeddingPort` (stub/OpenAI/Ollama adapters), `OC_EMBEDDING_PROVIDER` env var

## Conventions

**Naming:**

- Event types: dot-separated lowercase (`llm.requested`, `task.completed`)
- Task types: use `plugin.invoke` with handler in payload (not dotted task types)
- Handler names: dot-separated lowercase (`story.draft`)
- Error codes: SCREAMING_SNAKE_CASE (`INVALID_ARGUMENT`, `BUDGET_EXCEEDED`)

**Patterns:**

- All task handlers are async functions
- Strict typing enforced by mypy
- Domain models use `@dataclass`
- Tests use pytest fixtures; integration tests marked with `@pytest.mark.integration`
- Not-found conditions raise `NotFoundError` (from `domain/exceptions.py`), caught globally → HTTP 404
- Validation failures raise `ValidationError` (aliased `DomainValidationError` to avoid Pydantic collision), caught globally → HTTP 422
- Global exception handlers in `interfaces/api/app.py` eliminate per-route try/except
- Pydantic `Field()` constraints on request bodies; `Query()` constraints on query parameters
- Use `utc_now()` from `domain/time_utils.py` for current UTC time (not inline `datetime.now(UTC)`)
- Use `parse_csv_tags()` from `application/config/env_helpers.py` for comma-separated tag parsing
- Error code string values are `SCREAMING_SNAKE_CASE` (e.g., `"TIMEOUT"`, `"PROVIDER_ERROR"`)

**Secrets:**

- Zero secrets in repo (enforced by `test_no_secrets_committed.py`)
- Use `.env.local` (git-ignored) or `config/` directory for secrets
- Test placeholders: `changeme`, `replace_me`, `your_key_here`, `test-key`

## Environment Variables

Most-used variables for quick reference:

| Variable | Purpose | Default |
| ---------- | --------- | --------- |
| `OC_LLM_PROVIDER` | Provider selection (`stub`, `openai`, `ollama`, `anthropic`, `groq`, `gemini`) | `stub` |
| `OPENAI_API_KEY` | OpenAI authentication | - |
| `ANTHROPIC_API_KEY` | Anthropic authentication | - |
| `GROQ_API_KEY` | Groq authentication | - |
| `GEMINI_API_KEY` | Gemini authentication (also accepts `GOOGLE_API_KEY`) | - |
| `OC_DATA_DIR` | Root data directory (derives all data paths when set) | *(unset)* |
| `OC_DB_PATH` | SQLite database location | `data/openchronicle.db` |
| `OC_EMBEDDING_PROVIDER` | Embedding provider (`none`, `stub`, `openai`, `ollama`) | `none` |
| `OC_EMBEDDING_MODEL` | Embedding model name (provider-specific default) | *(provider default)* |
| `OC_EMBEDDING_DIMENSIONS` | Override embedding dimensions | *(provider default)* |

Full reference (~63 variables covering budget, rate limiting, routing, privacy,
telemetry, embedding, and more): [docs/configuration/env_vars.md](docs/configuration/env_vars.md)

## OpenChronicle Memory Integration

OC is available as an MCP server. It provides persistent memory that
survives context compression and session boundaries. **Use it.**

Context compression loses the "why" — decisions made, approaches
rejected, working state, user preferences expressed mid-session. The
status doc (`CODEBASE_ASSESSMENT.md`) tracks project-level state but
not conversational context. OC memory fills that gap.

### Setup

OC runs on the NAS as a Portainer stack (see `docker-compose.nas.yml`).
The MCP server is registered at user scope in `~/.claude.json` as
`openchronicle` pointing at `http://carldog-nas:18001/mcp` (HTTP
streamable-http transport). No project-level setup required.

If you need to register it on a fresh machine:

```bash
claude mcp add --scope user --transport http openchronicle http://carldog-nas:18001/mcp
```

For local dev (without the NAS), the alternative is project-scope
`.claude/settings.json` pointing at `oc mcp serve` — but that uses the
local OC store, which is a different memory pool than the NAS one.

### Project Identity

Use `project_id: "87de0f7d-d6ab-4b83-8613-b2b5ff60a57b"` in all `memory_save`
calls on the NAS-hosted OC. This is a FK to the projects table — freeform
strings will fail. (Project name on the NAS is currently
`smoke-test-2026-04-29` — rename to a canonical name still TBD.)

The old project_id `0db2b2ff-f995-4f59-b059-0fae5c78909d` was on the
LOCAL OC instance (Windows machine, ~95 historical memories) and is no
longer valid against the NAS DB. Local OC will be torn down once the
NAS one has proven itself for a session or two.

If the NAS DB is recreated, create a new project with `project_create`
and update this UUID.

### Session Protocol Addition

After the standard session protocol (Serena onboarding, status doc,
CLAUDE.md sprint), add:

- Call `memory_search` with keywords relevant to the current task or
  the user's first message. Review results for prior decisions,
  rejected approaches, and working context from previous sessions.

This step is **especially critical after context compression**, where
the compression summary is a lossy snapshot. OC memory is the lossless
record.

### When to Save

Call `memory_save` when any of these happen during a session:

- **Decision made.** Architecture, design, or approach chosen. Include
  what was decided, alternatives considered, and the reasoning.
- **Approach rejected.** Something was tried and didn't work. Save what
  it was, why it failed, and what replaced it.
- **Milestone completed.** A feature or significant unit of work is done.
  Summarize what was built and any non-obvious gotchas.
- **User preference expressed.** The user states a workflow preference,
  convention, or standing instruction that isn't already in CLAUDE.md
  or working-style.md.
- **Scope change.** The user redirects mid-task. Save what changed and
  why, so future sessions don't re-tread the old path.
- **Pre-compression.** If a session is getting long (many tool calls,
  complex multi-step work), proactively save working context — what
  we're doing, where we are in it, what's left. Don't wait to be asked.
  There is no hook for compression; the only mitigation is saving early.

**Tagging convention:**

| Tag | When |
| ----- | ------ |
| `decision` | Architectural or design decisions |
| `rejected` | Approaches tried and abandoned |
| `milestone` | Completed work summaries |
| `context` | Working state snapshots (proactive saves) |
| `convention` | Patterns, preferences, recurring gotchas |
| `scope` | Scope changes and reprioritizations |

Pin memories that represent standing rules or conventions.

**Don't save:**

- Routine file edits or commands (too granular, no retrieval value)
- Anything already captured in `docs/CODEBASE_ASSESSMENT.md`
- Speculative plans that haven't been confirmed by the user

### When to Load

Call `memory_search` at these points:

- **Session start / post-compression.** Search for the current task
  topic. This is non-negotiable after compression.
- **Before starting a new area of work.** Check if prior context exists.
- **When something feels familiar.** If a problem seems like it was
  discussed before, search before re-deriving from scratch.

### Tools to Use / Avoid

| Tool | Use | Notes |
| ------ | ----- | ------- |
| `memory_save` | **Yes** | Primary persistence mechanism |
| `memory_search` | **Yes** | Primary retrieval mechanism |
| `memory_list` | Occasionally | Browse recent memories when search terms are unclear |
| `memory_pin` | Yes | Pin standing conventions and rules |
| `memory_update` | Yes | Update content/tags of existing memories |
| `context_recent` | Occasionally | Catch up on prior OC activity |
| `health` | Rarely | Diagnostics only |
| `conversation_ask` | **Never** | Routes through a second LLM — you ARE the LLM |
| `conversation_*` | **No** | Not needed for Claude Code use case |

### Known Gaps

- **No compression hook.** We can't detect when compression is about to
  happen. Mitigation: save-as-you-go discipline.
- **Search is keyword-based by default.** Set `OC_EMBEDDING_PROVIDER`
  to enable hybrid semantic+keyword search. Without it, quality depends
  on good content and tags. Write memories as if future-you is searching
  for them with obvious keywords.

## Key Files

- `pyproject.toml` - Project config, dependencies, tool settings
- `docs/architecture/ARCHITECTURE.md` - Detailed architecture documentation
- `docs/architecture/PLUGINS.md` - Plugin development guide
- `docs/cli/commands.md` - CLI command reference (all `oc` subcommands)
- `docs/configuration/env_vars.md` - Full environment variables reference
- `docs/design/design_decisions.md` - Core subsystem design rationale
- `docs/protocol/stdio_rpc_v1.md` - RPC protocol specification
- `docs/integrations/mcp_server_spec.md` - OC MCP server spec (Goose/Serena triangle)
- `docs/BACKLOG.md` - Feature and implementation backlog
- `tests/test_architectural_posture.py` - Posture enforcement (core agnostic, session isolation, enqueue allowlist)
- `tests/test_hexagonal_boundaries.py` - Layer boundary enforcement (domain, application, core vs discord/mcp)
- `src/openchronicle/core/application/services/orchestrator.py` - Main orchestrator
- `src/openchronicle/interfaces/api/app.py` - HTTP API app factory (FastAPI)
- `src/openchronicle/interfaces/serializers.py` - Shared dict serializers (MCP + API)
- `src/openchronicle/interfaces/cli/main.py` - CLI entry point (`oc` command)
