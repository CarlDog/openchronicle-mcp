# OpenChronicle v2 — Senior Developer Codebase Assessment

**Date:** 2026-05-05
**Branch:** `main` is v2 (frozen). Active development on `v3/develop`.
**Revision:** 53 (v3 development; phases 0-4 complete on `v3/develop`)

> **⚠ v3 in active development.** This document describes v2, which is now
> frozen. The v2 snapshot is preserved at `archive/openchronicle.v2`. Active
> development happens on `v3/develop`. See [V3_PLAN.md](V3_PLAN.md) for the
> living plan and phase tracker.
>
> **v3 phase progress:**
> - **Phase 0** (branching) — done.
> - **Phase 1** (interfaces slimmed) — done. 570 tests passing.
> - **Phase 2** (application slimmed) — done. Container reduced to memory +
>   embedding + git-onboard wiring; orchestrator/scheduler/MoE/webhook/asset/
>   media/llm services + routing/runtime/replay/observability/policies dirs
>   + ~30 use cases + plugins/ deleted. 345 tests passing.
> - **Phase 3+4** (infrastructure + domain slimmed) — done. Combined commit
>   because the layers are intertwined: infrastructure adapter dirs (llm/,
>   media/, privacy/, router_assist/, routing/, logging/) deleted; sqlite_store
>   rewritten 1882 → ~470 LOC, schema reduced from 18 → 3 tables (projects,
>   memory_items, memory_embeddings) plus memory FTS5; 15 cut domain models +
>   9 cut domain ports + 3 cut domain services removed; `conversation_id` field
>   dropped from `MemoryItem` (Q1 locked decision); `LLMProviderError` in cut
>   `llm_port` replaced with new `ProviderError` in `domain.exceptions`;
>   `ConfigError` added; serializers slimmed to project + memory only;
>   `git_onboard` service drops LLM synthesis (caller-side now via MCP tool's
>   cluster output); CLI db commands rewritten for the v3 table set. 294 tests
>   passing, 0 failing.
> - **Phase 5** (schema migration + framework + online backup +
>   export/import) — pending.
> - **Phase 6** (ASGI unification + `OC_LOG_FORMAT`) — pending.
> - **Phase 6.5** (maintenance loop + embedding degradation policy) — pending.
> - **Phase 7** (docs sweep + repo polish) — pending. This document gets
>   rewritten as v3 rev 1 in Phase 7.

---

## Executive Summary

OpenChronicle started as a solution to a real problem: chat context dies between
sessions, and there's no way to carry a narrative (or any LLM interaction) forward
durably. V1 grew into a comprehensive narrative AI engine with 13+ orchestrators,
character AI, and 15+ providers. V2 is a clean-room rebuild recognizing that the
*actual* underlying problem — durable context, explainable routing, and auditable
decisions across LLM interactions — is domain-agnostic.

The core is now **feature-complete for the "core done" milestone.** The full
pipeline works end-to-end: conversation → context assembly → memory retrieval →
provider routing → LLM call → streaming response → turn persistence → event
logging. The CLI has an interactive chat REPL with streaming, conversation
shortcuts (`--resume`, `--latest`), and a clean dispatch-table architecture.
Tests are strong (1,656 unit/functional, 24 real-world integration, 14 Discord
integration, 18 concurrency stress), architecture is enforced, and the STDIO RPC
daemon mode exists. Integration
tests auto-detect application configuration (config directory, provider, credentials
from model configs) via a shared `conftest.py` — only `OC_INTEGRATION_TESTS=1` is
needed to run. The full pipeline has been validated against OpenAI (gpt-4o-mini) and
Anthropic (Claude Sonnet 4) with all 13 integration scenarios passing.

A **concurrency audit** revealed 4 race conditions in the persistence and event
logging layers. All four have been fixed: hash chain forking (`EventLogger.append`
now transactional with timestamp refresh under lock), duplicate turn indices
(`BEGIN IMMEDIATE` serializes writers), and lost updates (`link_memory_to_turn`
wrapped in transaction). Write lock starvation (T4) is fixed with a two-layer
approach: `execute_task()` was split into short transactions so LLM calls no
longer hold the write lock, and `transaction()` now retries `BEGIN IMMEDIATE`
with exponential backoff (3 retries, 0.5–2s delays with jitter) when SQLite's
`busy_timeout` expires. Connection setup uses `isolation_level=None` to bypass
Python's legacy implicit transaction handling, which silently undermined
explicit `BEGIN IMMEDIATE` in multi-threaded scenarios.

Six operational CLI utilities were added to close day-one gaps: `oc version`,
`oc db info|vacuum|backup|stats`, `oc config show`, `oc show-project`,
`oc events`, and `oc convo delete` + `oc memory delete`. These required two
domain port additions (`delete_conversation`, `delete_memory`) with cascade
logic in SqliteStore. CLI command reference documented in `docs/cli/commands.md`.

All subsystems now use three-layer config precedence (env var > `core.json` >
dataclass default). Conversation defaults and Discord operational settings were
the last holdouts — both are now externalized with a hygiene test
(`test_config_completeness.py`) that enforces config-code default synchronization
via `inspect.signature()`.

The **hexagonal boundary** between application and infrastructure layers is now
fully enforced: zero `core.application` → `core.infrastructure` imports.
`CoreContainer` moved to `infrastructure/wiring/`, config utilities moved to
`application/config/`, and concrete infra types replaced with Protocol-based
dependency injection. Posture tests (`test_architectural_posture.py`) verify
core runs without Discord installed, no Discord imports leak inward,
multi-session isolation holds, and the enqueue allowlist stays tight.

A **routing policy bug** was found and fixed: `prepare_ask()`, `execute()`, and
`enqueue()` in `ask_conversation.py` were constructing `RouterPolicy()` with no
arguments (defaulting to `stub:stub-model`), ignoring the configured policy built
by `CoreContainer`. `router_policy` is now a required parameter threaded through
the entire call chain — all callers pass `container.router_policy`. The Ollama
adapter's streaming error handler was also fixed (couldn't read response body on
a streaming `httpx` response without calling `aread()` first).

The Discord bot now writes a **PID file** (`data/discord_bot.pid`) on startup and
cleans it up on shutdown. If a prior instance is still alive, startup exits with
an error. `--force` overrides the check. Cross-platform: uses `PermissionError`
vs generic `OSError` distinction since Windows doesn't raise `ProcessLookupError`.

**HTTP API** (Decision #6) is implemented — FastAPI/uvicorn are core dependencies,
25 REST endpoints mirroring the MCP tool surface, starts automatically with
`oc serve` in a daemon thread. Includes API key auth (timing-safe), per-client
rate limiting (thread-safe sliding window), optional CORS, and proper HTTP error
codes. Shared serializers (`interfaces/serializers.py`) eliminate duplication
between MCP tools and API routes.

**Enterprise tightening — Pass A (Error Handling + Validation) is complete.**
Domain exception taxonomy (`NotFoundError`, `ValidationError`) with global
FastAPI exception handlers (404, 422, 400, 500). ~30 use-case sites migrated
from bare `ValueError`. Pydantic `Field()` constraints on all request models,
`Query()` constraints on all query parameters. Rowcount checks in sqlite_store
(3 update methods + TOCTOU fix). File path validation in `upload_asset`.
32 new tests.

**Enterprise tightening — Pass B (Operational Hardening + DRY Extraction) is complete.**
DRY extraction: `utc_now()` in `domain/time_utils.py` (replaced 6 duplicate
`_utc_now()` functions + 2 cross-file imports), `parse_csv_tags()` in
`env_helpers.py` (replaced 5 inline tag-parsing sites). LLM adapter timeouts:
`timeout_seconds` parameter on all 5 adapters, wired from `ResolvedModelConfig.timeout`
via `OC_LLM_TIMEOUT` env var fallback. Container lifecycle: `SqliteStore.close()`,
`CoreContainer.close()`, context manager protocol, partial-init cleanup.
Config validation: `__post_init__` on `ConversationSettings`, `MoESettings`,
`TelemetrySettings`, `HTTPConfig` (boundary value enforcement). CORS tightened
from `allow_methods=["*"]` to explicit list. Logging added to 12 use cases + 2
services; silent exception handlers in `continue_project` and `export_convo` now
log with `_logger.exception()`. Ollama adapter: specific `json.JSONDecodeError`
catch, `PROVIDER_ERROR` code for HTTP errors. Error codes normalized: all 13
lower_snake values changed to SCREAMING_SNAKE_CASE. CLI bug: removed unreachable
code in `cmd_memory_delete`, added error handling to `cmd_memory_pin`.
49 new tests, 1177 total passing.

**Enterprise tightening — Pass C (Interface Hardening + API/MCP Parity) is complete.**
API/MCP parity: `POST /api/v1/conversation/search-turns` closes the last REST
mirror gap (MCP `search_turns` tool had no HTTP equivalent). Path parameter
validation: `Annotated[str, Path(min_length=1, max_length=200)]` on all API path
params (`conversation_id`, `memory_id`, `asset_id`). System route validation:
`Query(max_length=...)` on `tool_stats` and `moe_stats` query params. MCP tool
validation: input clamping (`top_k`, `offset`, `limit`, `turn_limit`,
`memory_limit`) and rejection (empty `query`, empty `content`, overlength
`content`/`prompt`) across 7 MCP tools — uses graceful clamping for numeric
bounds (MCP callers are LLM agents), hard rejection for clearly invalid inputs.
Gemini adapter error codes: `_classify_gemini_error()` maps exceptions to
`TIMEOUT`, `CONNECTION_ERROR`, `PROVIDER_ERROR`, or `UNKNOWN_ERROR` (was `None`).
`OLLAMA_HOST` documented in env vars reference.
21 new tests, 1198 total passing.

**Storytelling plugin Phases 4-7 are done.** Phase 4 (Game Mechanics Engine): full
TTRPG system with `DiceType` (9 types), `ResolutionType` (13), `DifficultyLevel`
(6 with D&D-style DCs), `OutcomeType` (5 with nat-20/nat-1 crit detection),
`StatBlock` (14 stats, D&D modifier calc, memory-backed persistence), `NarrativeBranch`
(LLM-driven branching from resolution outcomes); scene handler injects resolution/branch
context into prompts. Phase 5 (Bookmark & Timeline): `BookmarkType` (4 types),
memory-backed CRUD, `Timeline` assembly with chapter grouping, auto-bookmark on scene
save. Phase 6 (Narrative Engines): `ConsistencyChecker` (LLM-based contradiction
detection with severity levels), `EmotionalAnalyzer` (9 emotion labels, loop detection,
per-character arcs); scene handler integrates both via `--check-consistency` and
`--analyze-emotion` flags. Phase 7 (Persona Extractor): text-only extraction with
multimodal deferred; domain models, LLM extraction, memory persistence. 12 new
handlers, 11 new CLI commands, 13 new files. 208 new tests, 1975 total.

**What's next:** Multimodal conversation input (vision input via asset system),
or Phase 5 IDE automation hooks (prototype exists). The `storytelling`
extension lives in this repo's `plugins/` (the `OpenChronicle/plugins` repo
was deleted as part of the 2026-04-29 cleanup). Media generation is done
(Decision #7) — `MediaGenerationPort` with 5 adapters (stub, Ollama, OpenAI
gpt-image-1, Gemini dual-surface, xAI Grok Imagine). Ollama CLI model management
is done — `oc ollama list|show|add|remove|sync` with capability inference from
Ollama API metadata (vision via clip, diffusion via safetensors, tools via template).

MoE (Mixture-of-Experts) execution strategy is implemented — Jaccard-based
consensus scoring, `--moe` CLI/MCP flag, quality pool parallel execution, 32 tests.
MCP server (Decision #5) is implemented — unblocks Goose + Serena triangle, VS
Code integration, and any MCP-compatible client. MCP tool usage tracking and MoE
usage tracking provide operational observability — dedicated tables, aggregate
stats queries, `tool_stats` and `moe_stats` MCP tools.

**Overall: Core feature-complete, Discord + MCP + HTTP API interfaces operational, MoE consensus execution implemented, MCP/MoE usage tracking operational, config fully externalized, hex boundaries enforced, concurrency-safe for multi-process deployment. Memory system Phase 3 complete: embedding-based semantic search via provider-agnostic `EmbeddingPort` (stub, OpenAI, Ollama adapters), hybrid FTS5+cosine retrieval combined via Reciprocal Rank Fusion (RRF), embeddings stored as BLOB in SQLite with CASCADE cleanup, backfill CLI/MCP/API, backwards-compatible default (keyword-only when `OC_EMBEDDING_PROVIDER=none`). Embedding observability added: health endpoint reports embedding status (active/disabled/failed with coverage stats), startup logging on adapter init, per-item backfill resilience with error isolation, configurable timeout via `OC_EMBEDDING_TIMEOUT`. Phase 4 Webhook Service complete: outbound webhooks with HMAC-SHA256 signing, background dispatcher thread with queue + exponential backoff retry, composite `emit_event` pattern (zero call-site changes), fnmatch glob event filtering, recursion prevention. Phase 5 IDE automation hooks prototyped: Claude Code `PreCompact` and `SessionStart(compact)` hooks inject OC memories around context compression via `oc memory search --full`. Media generation complete: `MediaGenerationPort` with 5 adapters (stub, Ollama, OpenAI gpt-image-1, Gemini dual-surface, xAI Grok Imagine), unified model config with `image_generation` capability tag (no separate `OC_MEDIA_PROVIDER`), asset storage with SHA-256 dedup, CLI/MCP/API interfaces. Model config system extended with `type` and `description` fields, `find_media_model()`/`list_by_capability()` lookup methods. Plugins repo separation later reverted (2026-04-29) — `OpenChronicle/plugins` deleted, storytelling stays in this repo. Ollama CLI model management: `oc ollama list|show|add|remove|sync` with capability inference from Ollama API metadata, operates against resolved config directory. Storytelling plugin Phase 3 (conversation mode integration): plugins register mode prompt builders via `PluginRegistry`, `prepare_ask()` delegates system prompt construction to the active mode's builder, story builder assembles characters/style guides/locations/worldbuilding from project memory; CLI convenience commands `oc story characters|locations|search`. 32 MCP tools, 41 REST endpoints, 1,874 tests. Enterprise tightening Passes A/B/C complete. OpenAI-compatible API layer dropped (2026-04-29) — chat-box-driven path through OC's pipeline retired in favor of MCP-tool composition (Claude Code, Goose, Open WebUI tool loop reach OC's brain via `conversation_*` MCP tools). Conversation mode parity added: `conversation_set_mode`/`conversation_get_mode` MCP + API endpoints close the gap that left story/persona modes unreachable from MCP clients.**

**Deployment ergonomics + CI scaffold alignment (2026-05-01/02):** Multi-OS GitHub Actions test workflow (`test.yml`, ubuntu/windows/macos matrix, ruff lint + format check + mypy) brings OC into line with the sibling `*-mcp` repos. Author-identity + PII pre-commit checks added (per global `security.md`). Three real bugs surfaced and fixed by the new multi-OS CI: `PidFile.is_alive()` now uses `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` on Windows instead of `os.kill(pid, 0)` (the latter TERMINATES the target process on Windows rather than probing existence — production hazard, not just a test fragility); media-adapter latency switched from `time.monotonic()` to `time.perf_counter()` (Windows monotonic resolution is ~15ms, breaking sub-tick elapsed assertions); `list_events`/`list_tasks_by_project` order by `rowid` (insertion order) instead of random-UUID `id` as tiebreaker (deterministic across OSes; 19 other `ORDER BY (created_at, id)` sites in `sqlite_store.py` flagged as a future mechanical sweep). Server-side `onboard_git`: MCP tool now clones `repo_url` server-side (was failing in containerized deployments that couldn't see the caller's filesystem); `OC_GIT_TOKEN` env var unlocks private-repo onboarding via URL-scoped HTTP Basic auth (raw token kept off argv via `GIT_CONFIG_PARAMETERS`). Bind-mount support for the four content dirs: `HOST_CONFIG_DIR`/`HOST_OUTPUT_DIR`/`HOST_ASSETS_DIR`/`HOST_PLUGINS_DIR` env vars switch between bind-mount and named-volume modes via docker-compose smart short-syntax fallback (`${HOST_X_DIR:-oc-x}:/x`). DB stays locked to the `oc-data` named volume — never operator-relocatable, since SQLite WAL on a bind-mount FS is what caused the 2026-04 corruption. `OC_USER_PLUGINS_DIR` enables a second plugin discovery root layered on top of the always-loaded `/app/plugins` (multi-dir `PluginLoader` with collision detection, 4 new tests). Config bootstrap on first run: image bakes `config/models/*.json` defaults into `/config-defaults/`, entrypoint copies into bind-mounted `OC_CONFIG_DIR` once (marker-file gated, `cp -n` no-clobber as safety net), so fresh deployments get 9 example model configs without manual scp. Discord re-enabled in `docker-compose.nas.yml` with token-gated no-op (clean exit-0 when `DISCORD_BOT_TOKEN` unset, `restart: on-failure` prevents the loop). NAS compose expanded to expose ~19 routing/MoE/per-provider env-var slots (`XAI_API_KEY`, `OPENAI_BASE_URL`, `ANTHROPIC_BASE_URL`, per-provider `*_MODEL`, `OC_LLM_*_POOL`, `OC_MOE_*`) so multi-provider features become Portainer-tunable without compose edits. Post-CI NAS redeploy convention documented in CLAUDE.md (push to main → both workflows green → portainer-mcp redeploy of the stack with matching name; doc-only / hook-only / workflow-only pushes exempt).

**Open WebUI tool-spec experiment tried and reverted (2026-05-02):** A `/memory-tools/openapi.json` filtered tool spec was added to give Open WebUI's OpenAPI tool server a curated ~10-endpoint subset (memory + project) instead of the full 41-endpoint surface, on the theory that LLMs degrade past ~10–15 tools. The filter, the URL-pattern fix (Open WebUI's discovery requires `/openapi.json` suffix and uses the spec's `servers` field as the API base), and the `OC_API_CORS_ORIGINS` env-var passthrough all landed and worked mechanically. The integration never reached a working chat experience — primary suspect was Ollama tool-call capability on the chat side, not OC's wiring. The three OWUI-specific commits (filter, fix, docs) were reverted same-day to keep the surface clean for the deferred "OC personality split" conversation: scope OC down to MCP server + storytelling, drop the chat-box-driven tool-server shim. The CORS env passthrough, bind-mount support, multi-dir PluginLoader, and config bootstrap that landed alongside the experiment were kept as deployment ergonomics worth retaining regardless of OWUI direction.

---

## Project Origin and Evolution

Understanding where this project came from is essential for making good decisions
about where it goes.

### The Arc

1. **Personal pain point** — Chat sessions die. Stories lose continuity between
   sessions. No LLM tool provides durable multi-session context.

2. **V1: Storytelling framework** — Built durable memory, character AI, timeline
   rollback, scene management, image generation. 13+ orchestrators, 15+ providers.
   Comprehensive but monolithic. Plugins leaked into core.

3. **Generalization insight** — The memory/context/routing infrastructure isn't
   story-specific. Any LLM interaction benefits from durable context, explainable
   routing, and auditable decisions.

4. **V2: Clean-room rebuild** — Strip to a domain-agnostic orchestration core.
   Hexagonal architecture (enforced by tests). Hash-chained events. Plugin-based
   extensibility. Rebuild v1 features as plugins on a stable foundation.

5. **Evolution within v2** — Early v2 was "pure platform" (core does nothing,
   plugins do everything). Then LLM orchestration moved to core. Then the default
   UX pivoted from manager/worker to conversation-first. Memory v0, explainability,
   and privacy gates were added. Manager/worker became optional/advanced.

### What Never Changed

- Hexagonal architecture, enforced by tests
- Determinism and auditability as product features
- Loud failures, no spooky defaults
- Local-first, provider-agnostic
- No soft deprecation, no tech debt breadcrumbs
- Core stays standalone; everything else is plugins

### What Evolved

- Manager/worker: "the default" → "optional advanced layer"
- Server mode: HTTP socket → STDIO RPC (what shipped)
- Primary UX: task orchestration → conversation-first
- Memory: unmentioned → "dumb but correct" keyword-based v0

---

## Current State: What Works

### End-to-End Conversation Pipeline (Functional)

The complete flow works today:

```text
User prompt
  → Conversation lookup + turn history assembly
  → Pinned memory retrieval
  → Keyword-based memory search
  → System prompt construction with memory context + time context
  → Interaction routing (rule-based + optional ML assist)
  → Privacy gate check (optional PII detection)
  → Provider/model selection via routing policy
  → LLM call with fallback execution
  → Response capture + metadata parsing
  → Atomic turn persistence (index, text, provider, model, routing reasons)
  → Event emission (hash-chained, tamper-evident)
  → Telemetry recording (tokens, latency, memory usage)
```

This is tested end-to-end in `test_conversation_flow.py`, `test_smoke_live.py`,
and the 13-scenario real-world integration suite (`test_real_world.py`) which
validates against live providers (OpenAI, Anthropic).

### Infrastructure Inventory

| Subsystem | Status | Evidence |
| ----------- | -------- | ---------- |
| **5 LLM providers** (OpenAI, Anthropic, Groq, Gemini, Ollama) | Working | Async-native adapters, contract tests |
| **Provider routing** (pools, fallback, NSFW, budget-aware) | Working | 1,278-line test suite |
| **SQLite persistence** (16 tables, 72+ methods, WAL mode) | Working | Handles tasks, conversations, memory, events, scheduled jobs, delete + cascade, MCP/MoE usage tracking, memory embeddings, webhooks + deliveries |
| **Hash-chained events** (SHA256, prev_hash → hash) | Working | Verification + replay services |
| **Privacy gate** (6 PII categories, Luhn validation) | Working | Rule-based, provider-aware |
| **Interaction routing** (rule + hybrid ML assist) | Working | NSFW scoring, mode detection |
| **Memory v1** (hybrid search: FTS5 keyword + embedding cosine via RRF) | Working | `EmbeddingPort` ABC, stub/OpenAI/Ollama adapters, `EmbeddingService` with hybrid `search_hybrid()`, embeddings stored as BLOB in `memory_embeddings` table, backfill CLI/MCP/API with per-item resilience, backwards-compatible default (`OC_EMBEDDING_PROVIDER=none`), embedding status in health endpoint, startup logging, configurable timeout (`OC_EMBEDDING_TIMEOUT`) |
| **Budget/rate limiting** | Working | Token limits, call limits, rate gates |
| **Plugin system** (discover, load, register, invoke, mode builders) | Working | 2 example plugins, collision detection, mode prompt builder registry |
| **Scheduler** (tick-driven, atomic claim, drift prevention) | Working | Core service, 6 CLI + 6 RPC commands, 53 tests |
| **STDIO RPC** (24 commands, serve + oneshot) | Working | Request dedup, telemetry, error codes |
| **CLI** (76+ subcommands) | Working | Project/task/convo/memory/diagnostics/db maintenance/config/version/events/delete/scheduler |
| **File-based configuration** (single `core.json`, three-layer precedence) | Working | All subsystems wired: routing, budget, retry, privacy, telemetry, conversation, Discord. Secrets (API keys, bot token) follow same precedence — no env-only exceptions. Enriched `models/*.json` + per-plugin JSON. Hygiene test enforces config-code default sync |
| **Config-driven wiring** (JSON model configs, env vars) | Working | Per-(provider, model) resolution |
| **Time context** (current time, last interaction, seconds delta) | Working | Injected in `prepare_ask()`, raw ISO + integer data, 5 tests |
| **Discord interface** (bot, slash commands, session, formatting) | Working | `commands.Bot` subclass, 6 slash commands, session mapping, message splitting, PID file guard, config from `core.json`, 71 tests |
| **MCP server interface** (32 tools, FastMCP, stdio + SSE) | Working | Memory (save/search/list/pin/update/get/delete/stats/embed), conversation (create/list/history/ask/set_mode/get_mode), context, system, onboard, asset, webhook, media tools; `@track_tool` decorator; lazy import guard; posture-enforced isolation |
| **Asset management** (filesystem storage, SHA-256 dedup, generic linking) | Working | Asset/AssetLink models, AssetStorePort, AssetFileStorage, upload/link use cases, 4 MCP tools, 4 CLI commands, 48 tests |
| **Webhook service** (outbound HTTP POST, HMAC-SHA256, background dispatch) | Working | WebhookSubscription/DeliveryAttempt models, WebhookStorePort, WebhookService, WebhookDispatcher (daemon thread + queue), composite emit_event, fnmatch glob filtering, exponential backoff retry, 3 MCP tools, 5 REST endpoints, 4 CLI commands, 74 tests |
| **HTTP API interface** (FastAPI, always-on daemon, 41 REST endpoints) | Working | App factory, API key auth (timing-safe), per-client rate limiting (thread-safe), CORS, middleware stack, shared serializers, 54+ tests |
| **Media generation** (5 adapters, unified model config) | Working | `MediaGenerationPort` ABC, stub/Ollama/OpenAI/Gemini/xAI adapters, `image_generation` capability tag in `config/models/`, `OC_MEDIA_MODEL` derives provider from config, asset storage + SHA-256 dedup, CLI/MCP/API interfaces, 69 tests |
| **Ollama CLI** (model discovery, config management) | Working | `oc ollama list\|show\|add\|remove\|sync`, `OllamaService` talks to Ollama HTTP API (`/api/tags`, `/api/show`), capability inference (vision/diffusion/tools), operates against resolved config dir (`RuntimePaths`), 32 tests |
| **Test suite** (1656 unit/functional, 24 real-world integration, 14 Discord integration, 18 concurrency stress) | Passing | 15 test categories + Discord + MCP + Assets + HTTP API + Embedding + Webhooks + Media + Ollama + Storytelling conversation mode, architecture guards, posture enforcement, live provider validation, concurrency race proofs, config drift detection, auto-detecting conftest, DB isolation fixture |

### Architecture (Enforced and Clean)

```text
interfaces/ (CLI, RPC, Discord, MCP, API)
    ↓ calls
application/ (use cases, orchestrator, policies, routing, config)
    ↓ depends on
domain/ (models, ports, services)
    ↑ implements
infrastructure/ (LLM adapters, SQLite, privacy, router assist, wiring)
```

Boundary discipline enforced by `test_hexagonal_boundaries.py` (5 tests) and
`test_architectural_posture.py` (24 tests): domain imports nothing outward,
application imports nothing from infrastructure, core imports nothing from
any interface layer. Composition root (`CoreContainer`) lives in `infrastructure/wiring/`.

Enforced by: `test_hexagonal_boundaries.py`, `test_core_agnosticism.py`,
`test_policies_purity.py`. Domain has zero infrastructure imports. Application has
zero SDK imports. This is genuinely enforced, not aspirational.

---

## Core Gaps (All Resolved)

The following gaps were identified at the start of the v2 rebuild and have all
been closed. Kept here for architectural context — see Definition of Done and
Refactoring Priorities sections for implementation details.

| # | Gap | Resolution |
| --- | ----- | ------------ |
| 1 | No interactive chat experience | `oc chat` REPL with auto-create, `--resume`, streaming (e368db4) |
| 2 | No streaming responses | `stream_async()` on LLMPort + all 6 adapters (6416c76) |
| 3 | God Functions in interface layer | Dispatch tables in `cli/commands/` + `rpc_handlers.py` (e368db4) |
| 4 | Manager/worker methods need decomposition | Phase-separated into 6 private helpers + dataclass (f4416d0) |
| 5 | `ask_conversation.execute()` too large | Split into `prepare_ask()` / `finalize_turn()` pipeline (95cab4c) |

---

## Concurrency Issues (Audited and Fixed)

The persistence and event logging layers were originally written for
single-connection access. A concurrency audit identified 4 race conditions, all
proven exploitable by `test_stress.py`. All four have been fixed.

| # | Issue | Fix | Status |
| --- | ------- | ----- | -------- |
| 1 | **Hash chain fork** — `EventLogger.append()` read-compute-write race | Wrapped in `BEGIN IMMEDIATE` transaction + timestamp refresh under lock | **Fixed** |
| 2 | **Duplicate turn index** — `next_turn_index()` reads MAX in deferred BEGIN | `BEGIN IMMEDIATE` serializes all write transactions | **Fixed** |
| 3 | **Lost memory link** — `link_memory_to_turn()` JSON read-modify-write race | Wrapped in `BEGIN IMMEDIATE` transaction | **Fixed** |
| 4 | **Write lock starvation** — long transaction blocks all writers | Short transactions + application-level retry with exponential backoff in `transaction()` | **Fixed** |

Additional fixes applied during implementation:

- **`isolation_level=None`** on connection setup — Python's legacy implicit
  transaction handling silently undermined explicit `BEGIN IMMEDIATE` in
  multi-threaded scenarios. Uses `isolation_level=None` (works on Python 3.11+)
  instead of the 3.12+-only `autocommit` attribute. Explicit `COMMIT`/`ROLLBACK`
  via `execute()` instead of `conn.commit()`/`conn.rollback()`.
- **Timestamp refresh under lock** — events constructed before lock acquisition
  had `created_at` timestamps that didn't match serialization order, causing
  `ORDER BY created_at` to return stale `prev_hash` values.

**Multi-process safe.** Scheduler service, Discord driver, and concurrent
processes can now share the database.

---

## 2026-04 Incident Remediation

**What happened.** Production SQLite DB at
`C:/Docker/openchronicle/data/openchronicle.db` developed B-tree corruption in
the `memory_embeddings` table — multiple "2nd reference to page X" errors and
"Rowid out of order" — surfaced when the running container's `add_memory`
INSERT failed with `database disk image is malformed`. The corruption survived
clean shutdowns, so it was on-disk, not in-flight. No backup was usable
(`.bak` was 344 KB from 2026-03-09, predating most data).

**Root cause.** Three contributors compound:

1. **Plex webhook bombardment.** `plex_connector` registered `plex.webhook`,
   accepting POSTs from Plex Media Server for every `media.scrobble` event.
   At peak the SERVE container received multiple webhooks/sec, each triggering
   a `memory_save` → row insert + FTS5 trigger + (when embeddings were
   configured) embedding generation + INSERT into `memory_embeddings`. Plex
   memory items grew to 89% of `memory_items` (1,168 of 1,306).
2. **Windows bind-mount fsync.** `/data` was a bind-mount from
   `C:/Docker/openchronicle/data` into the container. Docker Desktop on Windows
   implements bind-mounts via virtualization (9P/WSL2); SQLite WAL relies on
   POSIX `fsync` semantics that bind-mounts do not honor strictly. SQLite docs
   warn against this configuration.
3. **Unclean restart during checkpoint.** Container logs showed restart clusters
   (3 restarts on 2026-03-19, more on 2026-04-15) consistent with Docker Desktop
   updates or Windows reboots. A restart during a WAL checkpoint, on a
   bind-mount FS that lied about fsync, produced a half-written checkpoint —
   the on-disk B-tree gained the cross-page references that
   `integrity_check` later flagged.

**Recovery.** Plan B (gold-standard SQLite recovery): bypass the corrupt B-tree
entirely rather than trust SQLite to walk it.

1. Stopped Docker writers (`serve`, `mcp`).
2. Cold-copied the corrupt DB as evidence (`openchronicle.db.corrupt-2026-04-29`).
3. Disabled `plex_connector` (rename `plugin.py` → `plugin.py.disabled`).
4. Built a recovery script (`recover_db.py`): opened corrupt DB read-only,
   replayed schema into a fresh DB skipping FTS5 shadow tables (auto-managed),
   union-collected `memory_items` IDs from PK and rowid scan paths to maximize
   coverage (1,301 of 1,306 reachable), per-row refetch via PK with try/except
   (436 rows had unreadable content/tags pages — overflow page corruption),
   stripped 816 plex-tagged rows per user request, recreated `memory_embeddings`
   empty (regenerable via backfill).
5. Verified: `PRAGMA integrity_check: ok`. Data: 49 non-plex memory items, all
   1,131 tasks, 3,995 events, 16 turns, 2 conversations.
6. Pre-existing data: 250 FK violations on `spans → tasks` (orphans from old
   data), carried forward unchanged — separate cleanup.

**Mitigations.**

| Mitigation | Status |
| ---------- | ------ |
| Disable plex bombardment (delete `plex_connector`) | **Done** |
| Delete other connectors (`plaid_connector`, `hello_plugin`) | **Done** |
| Move `/data` from Windows bind-mount to Docker named volume `oc-data` | **Done** (in `docker-compose.local.example.yml`) |
| Fix `.bak` strategy (current backup gap is 7+ weeks) | **Open** — separate task: cron `oc db backup` |
| Address 250 pre-existing `spans → tasks` FK orphans | **Open** — separate cleanup |
| Audit other plugin/connector backlogs against connector-vs-extension lens | **Open** — strategic discussion in progress |

**External action required.** Plex Media Server still has a webhook URL
pointing at OC's `/api/v1/hooks/plex.webhook`. Now that the handler is gone,
Plex requests return 404. Remove the webhook from Plex MS settings to stop
the requests entirely.

---

## Definition of Done: Core v2

"Core done" means: a fully operational daemon that you can interact with like a
chatbot via CLI, with durable memory, explainable routing, and a stable plugin
surface. No backwards compatibility concerns. No production deployment yet.

### Must Have (Blocking for "Core Done")

| # | Item | Status | Why It's Blocking |
| --- | ------ | -------- | ------------------- |
| 1 | **Interactive chat REPL** (`oc chat`) | Done (e368db4) | Can't "interact like a chatbot" without it |
| 2 | **Streaming responses** (LLMPort + adapters + CLI, with `--no-stream` toggle) | Done (6416c76) | Chatbot UX with 10s wait for response is broken |
| 3 | **Interface layer refactoring** (God Functions → dispatch tables) | Done (e368db4) | Untestable interface layer is a stability risk |
| 4 | **Conversation UX shortcuts** (auto-create, resume latest, etc.) | Done (a946e7c) | UUID juggling prevents casual use |

### Should Have (Quality, Not Functionality)

| # | Item | Status | Impact |
| --- | ------ | -------- | -------- |
| 5 | **Decompose `ask_conversation.execute()`** | Done | Testability, readability |
| 6 | **Decompose orchestrator manager/worker methods** | Done | Phase-separated into 6 private helpers + dataclass |
| 7 | **SqliteStore row mapper extraction** | Done | Cognitive load reduction |

### Defer to Plugin Phase

| Item | Reason |
| ------ | -------- |
| ~~HTTP API~~ | ✅ Core interface (`interfaces/api/`, FastAPI, always-on daemon) |
| ONNX router assist | Linear model works; ONNX is a performance optimization |
| Embeddings / vector memory search | Keyword search works for v0; embeddings are a plugin concern |
| ~~Docker hardening~~ | ✅ CI builds multi-arch image to `ghcr.io/carldog/openchronicle-mcp` on push to main |
| ~~Scheduler~~ | ✅ Core service (`application/services/scheduler.py`, 53 tests) |
| ~~Discord driver~~ | ✅ Interfaces driver (`interfaces/discord/`, 85 tests, optional extra) |
| ~~OC MCP Server~~ | ✅ Interfaces driver (`interfaces/mcp/`, 32 tools, 47+7 tests, optional extra) |

---

## What "Core Done" Looks Like in Practice

```bash
# Bootstrap (one-time)
oc init

# Start the daemon
oc serve &

# Start chatting (interactive REPL)
oc chat
> Hello! What can you help me with?
Assistant: I can help with a variety of tasks...  [streams token by token]
> Remember that I prefer Python for code examples
[Memory saved: "User prefers Python for code examples"]
> /explain
[Shows: provider=openai, model=gpt-4o, memory items retrieved: 3, routing: quality pool]
> /quit

# Resume later
oc chat --resume
> What programming language do I prefer?
Assistant: You prefer Python for code examples.  [memory retrieval working]

# Or use one-shot commands
oc convo ask --latest "Quick question about X"

# Or drive programmatically via RPC
echo '{"command":"convo.ask","args":{...}}' | oc rpc

# Plugins extend without modifying core
oc plugin list
oc task submit --handler story.draft --input '{"prompt":"..."}'
```

---

## Refactoring Priorities (Ordered)

### Phase 1: Interface Layer — DONE (e368db4)

- `main.py` split from 1,852 → ~350 lines via `cli/commands/` dispatch tables
- `stdio.py` split into `rpc_handlers.py` (18 handlers) + slim dispatch
- `oc chat` REPL built with auto-create, `--resume`, streaming

### Phase 2: Streaming — DONE (6416c76)

- `StreamChunk` dataclass + `stream_async()` on `LLMPort` with fallback default
- Native streaming in all 6 adapters (stub, OpenAI, Anthropic, Groq, Gemini, Ollama)
- `stream_with_route()` execution boundary + `_stream_turn()` in chat REPL
- `--no-stream` opt-out toggle

### Phase 3: Conversation UX — DONE (a946e7c)

- Auto-create conversations in `oc chat`
- `oc chat --resume` picks up most recent conversation
- `oc convo ask/show/export --latest` resolves most recent conversation

### Phase 4: Internal Quality — DONE

**4a. Decompose `ask_conversation.execute()`** — Done. Extracted into
`prepare_ask()` (phases 1-5), `finalize_turn()` (phases 7-9), and
`_record_error_telemetry()`. `execute()` is now a ~35-line orchestrator.
Streaming path in `chat.py` rewritten to use the full pipeline (memory,
privacy, routing, telemetry).

**4b. Decompose orchestrator manager/worker methods** — Done. Extracted
`_WorkerRoutingContext` dataclass, `_resolve_worker_modes` (4-way mode
resolution), and 5 `_worker_*` phase helpers. `_run_worker_summarize` is now a
~20-line orchestrator calling setup → budget → rate-limit → execute → record.
`_run_analysis_summary` uses `_resolve_worker_modes` (~85 lines, down from ~119).

**4c. Extract SqliteStore row mappers** — Done. Extracted 10 `_row_to_*` methods
and `_parse_dt` to `row_mappers.py` as module-level functions. 21 callsites
updated. `sqlite_store.py` reduced by ~165 lines.

---

## What's Working Well (Don't Touch)

- **Hexagonal architecture enforcement tests** — These are the immune system
- **Hash-chained event model** — Core differentiator, enables verification/replay
- **Provider routing/pool system** — Most polished subsystem (1,278-line test suite)
- **Config-driven adapter wiring** — JSON configs, env fallbacks, lazy instantiation
- **Zero-tolerance test policies** — no tech debt markers, no soft deprecation, no secrets
- **STDIO RPC protocol spec** — Well-designed integration contract for future clients
- **Plugin system simplicity** — `register()` + handler functions (v1's complex
  plugins were a mistake)
- **Privacy gate** — 6 PII categories, Luhn validation, provider-aware. Blocking
  dependency for Discord integration
- **Memory v0** — "Dumb but correct" keyword search is the right starting point
- **`archive/openchronicle.v1` branch** — Preserved as design reference and plugin feature roadmap

---

## Subsystem Detail

### Use Case Layer (27 files, ~2,924 lines)

The use case layer has a healthy distribution: 16 thin wrappers (~328 lines total)
that forward to ports, and 8 complex orchestration files (~2,393 lines) with real
business logic. This is correct architecture — not everything needs to be complex.

**Heavyweights:**

| File | Lines | Complexity |
| ------ | ------- | ------------ |
| `ask_conversation.py` | 936 | Full conversation turn orchestration |
| `smoke_live.py` | 360 | End-to-end provider testing |
| `task_once.py` | 333 | Task execution with error handling |
| `selftest_run.py` | 330 | Comprehensive workflow testing |
| `replay_project.py` | 283 | Event replay engine |
| `diagnose_runtime.py` | 283 | Runtime diagnostics |
| `explain_turn.py` | 267 | Turn analysis via event correlation |
| `resume_project.py` | 160 | Orphaned task recovery |

**Concern:** The boundary between "what belongs in a use case" vs "what belongs in
the orchestrator" is unclear. `run_task.py` is 28 lines (pure forwarding) while
`ask_conversation.py` is 936 lines (full orchestration). The orchestrator also owns
built-in handler logic that could be use cases.

### Domain Layer (15 models, 9 ports, 3 services)

Clean and well-typed. Key models:

- **`Project`, `Agent`, `Task`, `Event`** — Core execution entities with hash chains
- **`Conversation`, `Turn`** — Chat interaction history with full metadata per turn
- **`MemoryItem`** — Persistent knowledge with tags, pinning, conversation/project scope
- **`BudgetPolicy`, `TaskRetryPolicy`** — Policy-as-data pattern
- **`InteractionHint`, `RouterAssistResult`** — Routing decision outputs

Ports define clean contracts: `StoragePort` (38 methods), `ConversationStorePort`
(12 methods, including cascade delete), `MemoryStorePort` (8 methods, including
delete with turn reference cleanup), `LLMPort` (2 methods), plus single-method
ports for routing, privacy, and plugin hosting.

**Concern:** `StoragePort` at 38 abstract methods is doing too much. The task tree
navigation methods feel like read-model concerns that could be a separate port.

### Infrastructure Layer

**Complete:** SQLite persistence (13 tables, crash recovery, transactions), privacy
gate (6 PII categories), rule routing (NSFW + mode detection), hybrid routing
(rule + ML), linear router assist (logistic regression), event logger (hash chains),
file-based configuration (single `core.json` with three-layer precedence:
dataclass defaults → JSON file → env var override; enriched model configs with
limits, capabilities, cost tracking, and performance metadata; per-plugin JSON config).

**Stub only:** ONNX router assist (intentional placeholder).

### Test Suite (152 files, 1656 unit/functional + 24 real-world integration + 14 Discord integration + 18 concurrency stress)

Well-organized into 12 categories: business logic (23), CLI/RPC (23), hygiene (11),
infrastructure (11), contract (8), policy (5), memory (5), architecture guard (4),
advanced (5), data format (4), plugin (2), integration (4 + conftest).

**Real-world integration** (`test_real_world.py`): 13 scenarios exercising the
full stack against live LLM providers — single/multi-turn, memory save/recall,
pinned memory, hash chain verification, token tracking, event chain completeness,
privacy gate PII detection, conversation resume, export with verify/explain,
streaming vs non-streaming, and conversation mode. Validated against OpenAI
(gpt-4o-mini) and Anthropic (Claude Sonnet 4). Manual checklist covers
interactive features (streaming visual, chat resume, quit, diagnose).

**Discord integration** (`test_discord_integration.py`): 14 scenarios exercising the
Discord bot's glue code against real infrastructure — session creation/reuse,
multi-user isolation, `/newconvo` flow, memory save/recall via Discord path,
stale session auto-recovery, event chain integrity verification, plus 7 realistic
user session simulations (casual greeting, factual Q&A, context retention,
conversation reset, multi-turn task coherence, concurrent user isolation, and
turn persistence verification).

**Integration test auto-detection** (`tests/integration/conftest.py`): Session-scoped
conftest auto-detects the application's config directory (well-known deployment paths
with `models/*.json`, e.g. `C:\Docker\openchronicle\config`), LLM provider (from env
vars or model config scan), and credentials (embedded in model config JSON files).
Only `OC_INTEGRATION_TESTS=1` is needed to run — no manual `OC_CONFIG_DIR` or
`OC_LLM_PROVIDER` setup. Explicit env vars always take precedence. Smoke tests
(`test_smoke_live.py`) adapted to handle config-embedded credentials (skip
credential-removal tests when keys aren't in env vars).

**Concurrency stress tests** (`test_stress.py`): 6 threading-based tests using
separate `SqliteStore` connections to the same database file (simulating
multi-process access). Each thread gets its own `sqlite3.Connection` with
independent locks and WAL snapshots. Results:

| Test | Target | Outcome |
| ------ | -------- | --------- |
| T1: Hash chain fork | `EventLogger.append()` read-compute-write race | **pass** — 300 events, chain intact, no collisions |
| T2: Duplicate turn index | `next_turn_index()` + deferred BEGIN | **pass** — 10 turns, distinct indices |
| T3: Lost update | `link_memory_to_turn()` JSON read-modify-write | **pass** — all 10 memory IDs survive |
| T4: Write lock starvation | Long transaction blocks other writers | **pass** — application-level retry recovers after holder releases |
| T5: Independent chains (baseline) | Concurrent writes to different task_ids | **pass** — database fundamentally sound |
| T6: Scheduler tick no double-fire | Concurrent `tick()` atomic claiming | **pass** — 20 jobs, each fired exactly once |

**Strongest coverage:** Provider routing, budget enforcement, conversation flow,
event verification, architectural boundaries, live provider validation,
concurrency race conditions.

Interface layer was split into dispatch tables (e368db4), unlocking
command-level testing.

---

## V1 → V2: What Changed and Why

| V1 Feature | V2 Status | Notes |
| ------------ | ----------- | ------- |
| 13+ orchestrators | 1 orchestrator + use cases | Intentional simplification |
| 15+ LLM providers | 5 providers (async-native) | OpenAI, Anthropic, Groq, Gemini, Ollama |
| Character AI | Not ported | Plugin territory |
| Timeline rollback | Hash-chained events | Cryptographic > database integrity |
| Multi-tier memory (Redis + SQLite) | Single-tier SQLite | Simpler, may need tiers later |
| Content analysis (two-tier LLM) | Router assist (linear/ONNX) | Lighter weight |
| Scene management, narrative engines | Not ported | Plugin territory |
| Image generation | Not ported | Plugin territory |
| Plugin: full domain/app/infra per plugin | Plugin: handler + register() | Intentionally simpler |
| Web UI templates | Not ported | HTTP API is core; web UI is separate concern |
| CLI commands only | CLI + STDIO RPC daemon | Headless operation enabled |
| Database integrity | Cryptographic integrity | Hash-chained events are the upgrade |

**The v2 strategy is correct:** Build a hardcore core with clean boundaries, then
re-implement v1 features as plugins. The `archive/openchronicle.v1` branch is both
historical context and a feature roadmap for the plugin phase.

---

## Post-Core Roadmap

A plugin-readiness audit (2026-02-13) identified that the plugin system works for
stateless task handlers but cannot support stateful, long-running, or
service-dependent features. See Decision #4 below for the architectural response.
Enriched plugin handler context (2026-03-02) addresses the stateful gap for
connector-style plugins: handlers now receive pre-bound `memory_save`,
`memory_search`, `memory_update`, `llm_complete`, and `plugin_config` closures
in their context dict. Plugins never import core internals — all capabilities
are injected at invocation time.

Generic inbound hooks endpoint (2026-03-02) adds `POST /api/v1/hooks/{handler_name}`
to the HTTP API — a fire-and-forget webhook receiver that validates the handler
exists, parses JSON or multipart form-data, submits a `plugin.invoke` task, and
returns 202 with the task ID. Execution happens in a FastAPI `BackgroundTasks`
callback. 5 tests.

**Connector model retired (2026-04-29).** Domain integrations (Plex, Plaid,
etc.) no longer live as plugins inside OC — they belong as their own MCP
servers, composed by the client. The `plex_connector`, `plaid_connector`, and
`hello_plugin` directories were removed from `plugins/`, along with 8 dedicated
tests. Only `storytelling` remains as the reference extension plugin (it
modifies OC's conversation behavior via mode prompt builders, not a connector).
The plugin loader contract is unchanged — task handlers and mode builders are
still the plugin extension surface. See "2026-04 Incident Remediation" below.

```text
Core Done
  ✓ LLMPort: function calling / tool use (done)
  ✓ Scheduler (core — application/services)
  ✓ Discord Driver (core — interfaces/)
  ✓ OC MCP Server (core — interfaces/mcp, Decision #5)
  ✓ Docker CI (ghcr.io/carldog/openchronicle-mcp, multi-arch, GitHub Actions)
  ✓ MoE Mode (core — application/services/moe_execution.py, uses LLMPort + routing)
  ✓ HTTP API (core — interfaces/api, always-on daemon, Decision #6)
  ✓ Capability-Aware Routing (core — wire model config capabilities into routing)
  ✓ Media Generation (core — MediaGenerationPort, 5 adapters, unified model config, Decision #7)
  ✓ Ollama CLI (core — oc ollama list|show|add|remove|sync, capability inference, config management)
  → Multimodal Conversation Input (core — vision input via asset system)
  ✓ Webhooks (core — webhook_service.py + webhook_dispatcher.py, HMAC signing, background dispatch)
  ✓ Embedding Observability (health status, startup logging, backfill resilience, configurable timeout)
  ✓ Inbound Hooks Endpoint (core — interfaces/api/routes/hooks.py, generic POST dispatch to plugin handlers)
  ~ Phase 5 IDE Hooks (prototype — Claude Code PreCompact/SessionStart hooks, `oc memory search --full`)
  → Security Scanner (plugin — stateless handler)
  → Dev Agent Runner (core — needs LLM + sandbox)
  → Serena MCP (core — inside sandbox only)
  ✓ Memory Embeddings (core — EmbeddingPort, hybrid FTS5+cosine search via RRF)
  → VS Code / Copilot SDK (MCP client or external via RPC)
  → Goose Integration (MCP client — uses OC MCP + Serena MCP)
  → Private Git Server (plugin or external)
```

**Taxonomy:** Features that need persistent state, lifecycle hooks, or direct
service access are core features (in `application/` or `interfaces/`). Stateless
input→output handlers remain plugins. External clients compose via MCP or STDIO
RPC. See Decision #5 for the MCP-first integration strategy.

---

## Resolved Decisions

### 1. Manager/worker stays in core (Decision: 2026-02-12)

**Decision:** Keep manager/worker in core, decompose the methods.

**Rationale:** Manager/worker is a **runtime capability**, like multi-threading —
not every workflow uses it, but it's the kind of thing that belongs in the engine.
Plugins shouldn't have to reimplement task parallelism and worker coordination.

**Action:** Decompose `_run_worker_summarize()` (339 lines) and
`_run_analysis_summary()` (119 lines) into phase-separated methods (setup, prompt
building, LLM call, result parsing, worker spawning). No architectural change,
just internal readability.

### 2. Streaming is must-have, with opt-out toggle (Decision: 2026-02-12)

**Decision:** Streaming is blocking for core-done. Non-streaming remains as an
option via `--no-stream` flag / `OC_STREAM=0` env var.

**Rationale:** A chatbot without streaming feels broken in 2026. But programmatic
callers (RPC, Discord driver) and user preference may want complete responses.
Both paths need to work.

**Action:** Add `stream_async()` to `LLMPort`, implement in all 5 adapters, wire
through CLI (`oc chat`, `oc convo ask`). RPC gets both `convo.ask` (existing,
complete response) and `convo.ask_stream` (chunked). Non-streaming path is not
throwaway — it stays as the default for RPC and as the user opt-out.

### 3. Memory self-report: keep lenient, remove strict mode (Decision: 2026-02-12)

**Decision:** Keep self-report as opt-in lenient telemetry. Remove strict mode.
Invest further only alongside memory v1 (embeddings).

**Rationale:** Memory is the core product feature — OpenChronicle exists because
chat context dies between sessions. Knowing whether injected memory is actually
being used by the LLM is critical signal for validating that the product works.
Self-report via `<OC_META>` blocks is the cheapest available feedback mechanism.

However, it depends entirely on LLM compliance, which varies by model. Strict
mode punishes the user for something outside their control (LLM formatting). A
bad self-report should log a warning, never fail a turn.

**What self-report is:** V0 of a memory effectiveness feedback loop. The data
collected now (even noisy) becomes baseline data for future approaches:
retrieval relevance scoring, response analysis, A/B testing with/without memory.

**What self-report is NOT:** A correctness mechanism. The turn succeeds regardless.

**Action:** Remove strict mode code path. Keep lenient self-report as opt-in
telemetry. Surface usage data in `--explain` output. Revisit when building memory
v1 (embeddings/vector search) — self-report data will inform retrieval quality.

### 4. Hybrid plugin taxonomy: core vs plugin vs external (Decision: 2026-02-13)

**Decision:** Scheduler and Discord driver are core features, not plugins. The
plugin system stays as-is for stateless task handlers.

**Rationale:** A plugin-readiness audit found the plugin API provides
`(task, context) → result` with minimal context (`agent_id`, `attempt_id`,
`emit_event`). Stateful features need persistent storage, lifecycle hooks, direct
service access, event subscription, and configuration — all of which the plugin
API lacks. Building a mini-framework inside the plugin API to support these would
duplicate what core already provides.

The scheduler is a **runtime concern** (like the event logger or transaction
retry). The Discord driver is an **interface** (like CLI or STDIO RPC). Neither
is an optional bolt-on — they need the same level of access as core services.

**Taxonomy:**

| Feature needs... | Lives in... | Examples |
| ------------------ | ------------- | ---------- |
| Persistent state, lifecycle, service access, or LLM orchestration | Core (`application/` or `interfaces/`) | Scheduler, Discord, MCP server, HTTP API, Dev Agent Runner, MoE Mode |
| Behavior-modifying extension (mode prompt builder, conversation hooks) | Plugin (this repo's `plugins/`) | Storytelling |
| Domain-specific data integration | External MCP server (separate repo) | Plex sync, banking, file indexers |
| External process composing via MCP or RPC | External client | Goose, VS Code, Claude Desktop, CI integrations |

**Action:** Build scheduler in `application/services/`, Discord driver in
`interfaces/discord/`. Keep the plugin system for what it's good at. Close one
core gap first: add function calling / tool use to LLMPort (done — ToolDefinition,
ToolCall, tool_calls on LLMResponse/StreamChunk, tools/tool_choice params on all
6 adapters + facade + execution layer, 53 contract tests).

### 5. MCP-first integration strategy: OC as an MCP server (Decision: 2026-02-20)

**Decision:** Build an OC MCP server as a core interface (`interfaces/mcp/`).
This is the primary integration path for external agents (Goose, VS Code, Claude
Desktop) rather than requiring each to implement a custom STDIO RPC client.

**Rationale:** Three tools compose naturally:

| Tool | Role | Persistence |
| ------ | ------ | ------------- |
| **Serena** (MCP server) | Code understanding — what the code **is** | Stateless |
| **OpenChronicle** (MCP server) | Persistent memory — what was **decided** and **why** | Persistent |
| **Goose** (MCP client) | Agent execution — edit files, run commands, iterate | Ephemeral |

Goose already speaks MCP. Serena is already an MCP server. Making OC an MCP
server completes the triangle with zero custom glue code per client. Any
MCP-compatible agent gets persistent memory and conversation capabilities.

The MCP server is a transport layer exposing existing core capabilities (memory
ports, `AskConversation`, health checks) — same category as CLI, STDIO RPC, and
Discord. It needs direct access to `CoreContainer` and the full port surface,
so it cannot be a plugin (same reasoning as Decision #4 for Discord).

**What this changes in the roadmap:**

- **OC MCP Server** becomes next priority after security scanner (or parallel).
  16 tools, maps 1:1 to existing ports/use cases.
- **Goose integration** no longer requires Dev Agent Runner, Security Scanner,
  or Sandbox Runner as prerequisites. Goose connects to OC MCP server directly.
- **VS Code / Copilot SDK** can also connect via MCP instead of custom RPC
  client.
- **Dev Agent Runner** remains on the roadmap as an upgrade path where OC
  orchestrates Goose (flipped control, full audit trail via event chain).

**Architecture:**

```text
interfaces/mcp/
  server.py           # MCP server setup, tool registration
  tools/
    memory.py         # memory_search, memory_save, memory_list, memory_pin, memory_update, memory_get, memory_delete, memory_stats
    conversation.py   # conversation_ask, conversation_history, conversation_list, conversation_create
    context.py        # context_recent
    system.py         # health, tool_stats, moe_stats, search_turns, onboard_git
    asset.py          # asset_upload, asset_list, asset_get, asset_link
    webhook.py        # webhook_register, webhook_list, webhook_delete
    project.py        # project_create, project_list
```

**Posture:** Optional extra (`.[mcp]`). Core runs without MCP SDK. All MCP
imports lazy, confined to `interfaces/mcp/`. Enforced by posture tests.

**Spec:** [`docs/integrations/mcp_server_spec.md`](integrations/mcp_server_spec.md)

### 6. HTTP API is always-on core infrastructure (Decision: 2026-02-22)

**Decision:** The HTTP API is a core interface that starts automatically as part
of `oc serve`. FastAPI and uvicorn are core dependencies, not an optional extra.
The implementation lives in `interfaces/api/`.

**Rationale:** The HTTP API is the same tier as CLI, STDIO RPC, Discord, and
MCP — an interface layer that needs the full `CoreContainer`. It is not an
optional bolt-on because:

1. **Daemon infrastructure.** When OC runs as a daemon, the HTTP API is always
   listening. Webhooks (both inbound and outbound) depend on it. External
   integrations (connectors, plugins with route registration) compose through it.
2. **Plugin route registration.** Plugins can register HTTP routes (mounted under
   `/api/v1/plugins/` namespace), enabling webhook consumption and custom
   endpoints without modifying core.
3. **Standard REST surface.** Mirrors MCP tools 1:1 as REST endpoints, plus
   streaming (SSE), webhooks, and plugin routes. Any HTTP client gets the same
   capabilities as MCP clients.

Unlike Discord and MCP (optional extras with lazy imports), the HTTP API has no
optional SDK dependency — FastAPI is lightweight and always installed. No posture
test for "core runs without HTTP API" because it is core infrastructure.

**Architecture:**

```text
interfaces/api/
  app.py              # FastAPI app factory (create_app(container, config))
  config.py           # HTTPConfig (host, port, auth settings)
  middleware/
    auth.py            # API key / token auth
    privacy.py         # Privacy gate middleware
    rate_limit.py      # Per-client rate limiting
  routes/
    memory.py          # /api/v1/memory/*
    conversation.py    # /api/v1/conversation/*
    project.py         # /api/v1/project/*
    asset.py           # /api/v1/asset/*
    webhook.py         # /api/v1/webhook/*
    system.py          # /api/v1/health, /api/v1/stats
```

**Posture:** Core dependency (not optional). Hexagonal boundary enforced — no
`core.*` module imports from `interfaces/api/`.

### 7. Media generation is a core capability (Decision: 2026-02-22, Implemented: 2026-02-25)

**Decision:** Media generation (image, video) is a core capability with its own
port (`MediaGenerationPort`), adapters, and unified model config. Not a plugin.

**Rationale:** Media generation needs:

1. **Its own port.** Different input/output types from text completion (prompts →
   binary media), different cost model, different routing needs. Extending
   `LLMPort` would violate interface segregation.
2. **Unified model config.** Media models live in `config/models/` alongside LLM
   models with `"image_generation": true` capability tag. Provider is derived
   from the model config — no separate `OC_MEDIA_PROVIDER` env var. Single knob:
   `OC_MEDIA_MODEL`.
3. **Asset integration.** Generated media flows through the existing asset system
   (SHA-256 dedup, generic linking). A use case orchestrates port + asset storage.
4. **Provider adapters.** Ollama (Flux diffusion), OpenAI (gpt-image-1), Google
   (Gemini native + Imagen dual-surface), xAI (Grok Imagine). Each normalizes
   to `MediaResult`.

**Architecture:**

```text
core/domain/models/media.py                   # MediaRequest, MediaResult
core/domain/ports/media_generation_port.py    # Port ABC
core/infrastructure/media/
  stub_adapter.py                              # Testing (deterministic PNG)
  ollama_adapter.py                            # Ollama /api/generate (diffusion)
  openai_adapter.py                            # OpenAI /v1/images/generations
  gemini_adapter.py                            # Gemini dual-surface (native + Imagen)
  xai_adapter.py                               # xAI Grok Imagine (OpenAI-compatible)
core/application/use_cases/generate_media.py   # Orchestrates port + asset storage
config/models/ollama_flux.json                 # image_generation capability
config/models/openai_gpt_image_1.json          # image_generation capability
config/models/gemini_flash_image_gen.json      # image_generation capability
config/models/xai_grok_imagine.json            # image_generation capability
```

**Model config extensions:** `ModelConfigEntry` gained `type` (default `"llm"`,
media models use `"media"`) and `description` fields. `ModelConfigLoader` gained
`find_media_model()`, `list_by_capability()`, and `find_by_model()` methods.

**Implementation:** Complete. 5 adapters, CLI/MCP/API interfaces, 69 tests.

---

## Files to Know

| File | Lines | Role | Status |
| ------ | ------- | ------ | -------- |
| `interfaces/cli/main.py` | ~400 | CLI entry point | Clean (dispatch tables) |
| `interfaces/cli/commands/db.py` | ~170 | DB maintenance CLI | New (info, vacuum, backup, stats) |
| `interfaces/cli/stdio.py` | ~200 | RPC dispatch | Clean (handlers extracted) |
| `services/orchestrator.py` | 927 | Task orchestration | Clean (phases decomposed) |
| `persistence/sqlite_store.py` | ~1,332 | All persistence | Clean (mappers extracted, delete + cascade, scheduled jobs, MCP/MoE tracking) |
| `persistence/row_mappers.py` | ~180 | Row → domain model | Clean |
| `use_cases/ask_conversation.py` | ~936 | Conversation logic | Clean (prepare/finalize pipeline, MoE recording) |
| `infrastructure/llm/provider_facade.py` | ~291 | Provider routing | Clean |
| `application/routing/router_policy.py` | 236 | Route decisions | Clean |
| `domain/ports/llm_port.py` | 146 | LLM contract | Clean (includes streaming) |
| `application/services/llm_execution.py` | ~200 | LLM call + fallback | Clean |
| `services/scheduler.py` | ~250 | Tick-driven scheduler | New (core service) |
| `interfaces/discord/bot.py` | ~130 | Discord bot | Clean (commands.Bot, on_message, streaming pipeline) |
| `interfaces/discord/pid_file.py` | ~60 | PID file guard | New (atomic write, cross-platform alive check) |
| `interfaces/discord/commands.py` | ~170 | Slash commands | New (6 commands, Cog pattern) |
| `interfaces/api/app.py` | ~105 | HTTP API app factory | New (FastAPI, lifespan, middleware, route registration, global exception handlers) |
| `interfaces/api/middleware/auth.py` | ~65 | API key auth | New (timing-safe, Bearer + X-API-Key, configurable exemptions) |
| `interfaces/api/middleware/rate_limit.py` | ~70 | Rate limiting | New (thread-safe sliding window, memory-leak-safe) |
| `interfaces/serializers.py` | ~90 | Shared model serializers | New (6 functions, used by MCP tools + API routes) |
| `services/webhook_service.py` | ~120 | Webhook CRUD + HMAC + delivery | New (httpx, fnmatch, secrets) |
| `services/webhook_dispatcher.py` | ~110 | Background event dispatch | New (daemon thread, queue, retry) |
| `infrastructure/media/` | ~790 | Media adapters | New (stub, Ollama, OpenAI, Gemini, xAI — 5 adapters, config-driven) |
| `services/ollama_service.py` | ~240 | Ollama model discovery | New (HTTP API client, capability inference, config generation, diff/sync) |
| `interfaces/cli/commands/ollama.py` | ~270 | Ollama CLI commands | New (list, show, add, remove, sync — 5 subcommands) |
| `infrastructure/wiring/container.py` | ~465 | DI container | Clean (file-based config, exposes router_policy, composite emit_event, embedding_status_dict, media port via model config lookup) |
