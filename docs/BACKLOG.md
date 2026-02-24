# OpenChronicle v2 - Feature & Implementation Backlog

This document tracks planned features, implementation gaps, and future work for the OpenChronicle v2 project.

**Last Updated:** 2026-02-21

---

## Status Legend

| Symbol | Meaning             |
| ------ | ------------------- |
| ✅     | Implemented         |
| 🟡     | In Progress         |
| 🔴     | Not Started         |
| ⚪     | Stubbed/Placeholder |
| ⏸️     | Deferred            |

---

## Priority 0 — Foundation (Blocking)

### 0.1 Scheduler Service (Core)

**Status:** ✅ Implemented
**Effort:** Medium
**Rationale:** Enables scheduled responses, periodic scans, metrics snapshots. Unlocks downstream features (Discord, security scanner, dev agent runner). Built as a core service in `application/services/` per Decision #4 (hybrid taxonomy).

**Requirements:**

- [x] Job store (core SQLite — `scheduled_jobs` table, 16 columns, 2 indexes)
- [x] One-shot scheduled tasks (auto-complete after fire)
- [x] Recurring jobs (interval-based, `cron_expr` column reserved for v1)
- [x] Deterministic execution order (`next_due_at ASC`, `created_at ASC`, `id ASC`)
- [x] `scheduler.tick(now, max_jobs)` — atomic claim via `BEGIN IMMEDIATE`, drift prevention
- [x] `scheduler.serve()` — async polling loop with clean shutdown
- [x] Job lifecycle: active/paused/completed/cancelled with state transition validation
- [x] CLI: `oc scheduler {add|list|pause|resume|cancel|tick}`
- [x] RPC: `scheduler.{add|list|pause|resume|cancel|tick}` (6 handlers)
- [x] Events: `scheduler.job_created/paused/resumed/cancelled/fired/tick_completed`

**Acceptance Criteria:**

- [x] Jobs persist across restarts (SQLite)
- [x] Deterministic ordering verified by tests
- [x] No double-fire under concurrent tick() (concurrency stress test T6)
- [x] 53 tests (28 service, 13 storage, 12 CLI)

---

## Priority 1 — Client Integrations

### 1.1 Discord Interface (Core Driver)

**Status:** ✅ Implemented
**Location:** `src/openchronicle/interfaces/discord/` (optional `[discord]` extra)
**Tests:** 71 unit tests (`test_discord_*.py`) + 14 integration tests

Implemented as a core interfaces driver per Decision #4 (hybrid taxonomy).
The driver interacts with core directly via the container (same process), not
via STDIO RPC. Core remains fully functional without Discord installed — the
`discord.py` package is an optional extra, all discord imports are lazy and
confined to `interfaces/discord/` and `interfaces/cli/commands/discord.py`.

**Implemented:**

- [x] Discord bot receiving messages (`commands.Bot` subclass)
- [x] 6 slash commands: `/newconvo`, `/remember`, `/forget`, `/explain`, `/mode`, `/history`
- [x] Session-to-conversation mapping (file-backed, multi-user)
- [x] Message splitting for Discord's 2000-char limit
- [x] Privacy gate and interaction routing honored
- [x] Config from `core.json` + env vars (three-layer precedence)
- [x] `oc discord start` CLI command with lazy import guard

**Architectural posture (enforced by tests):**

- Core must remain fully functional without Discord (`test_architectural_posture.py`)
- No `core.*` module imports discord (`test_hexagonal_boundaries.py`)
- Multi-session isolation: no module-level mutable state (`test_architectural_posture.py`)

---

## Priority 2 — OC MCP Server (Core Interface)

### 2.1 MCP Server Interface

**Status:** ✅ Implemented
**Location:** `src/openchronicle/interfaces/mcp/` (optional `[mcp]` extra)
**Tests:** 21 unit tests (`test_mcp_config.py`, `test_mcp_tools.py`) + 7 posture tests
**Spec:** [`docs/integrations/mcp_server_spec.md`](integrations/mcp_server_spec.md)

Exposes OC's persistent memory and conversation capabilities via Model Context
Protocol. Enables any MCP-compatible agent (Goose, Claude Desktop, VS Code) to
use OC without custom integration code. See Decision #5 in assessment.

**Key insight — the OC + Serena + Goose triangle:**

- Serena MCP = code understanding (what the code IS)
- OC MCP = persistent memory (what was DECIDED and WHY)
- Goose = agent execution (hands that do the work)

**Implemented:**

- [x] `memory_search` — keyword search across memory items
- [x] `memory_save` — store a memory item (tagged, optionally pinned)
- [x] `memory_list` — list memories (by conversation, project, or all)
- [x] `memory_pin` — pin/unpin a memory for persistent retrieval
- [x] `memory_update` — update content and/or tags of an existing memory
- [x] `memory_search` tag filter — AND-logic tag filtering on search results
- [x] `memory_get` — retrieve a single memory item by ID
- [x] `memory_delete` — delete a memory item (emits `memory.deleted` event)
- [x] `memory_stats` — aggregate counts (total, pinned, by tag, by source)
- [x] `conversation_ask` — send a message through full OC pipeline (async)
- [x] `conversation_history` — retrieve recent turns
- [x] `conversation_list` — list conversations
- [x] `conversation_create` — create a new conversation
- [x] `context_recent` — recent activity summary for a topic/conversation
- [x] `health` — health check (runtime diagnostics)
- [x] `oc mcp serve` CLI command (stdio transport)
- [x] Optional SSE transport (`--transport sse --port 8080`)
- [x] Posture tests (core runs without MCP SDK, no inward imports)
- [x] `python -m openchronicle.interfaces.mcp` entry point

**Architectural posture (enforced by tests):**

- Core must remain fully functional without MCP SDK (`test_architectural_posture.py`)
- No `core.*` module imports mcp (`test_hexagonal_boundaries.py`)
- All MCP imports are lazy, confined to `interfaces/mcp/` and `cli/commands/mcp_cmd.py`

---

## Priority 3 — Safety & Security

### 3.1 Dev Folder Security Scanner Plugin

**Status:** 🔴 Not Started
**Effort:** Medium
**Depends On:** Scheduler Service (core)

**Requirements:**

- [ ] Integrate existing scanners (not inventing new ones):
  - [ ] Secrets scanning: gitleaks or trufflehog
  - [ ] Dependency vulnerability: osv-scanner
  - [ ] Container scanning: trivy (optional)
  - [ ] Static analysis: semgrep rules (optional)
- [ ] Deterministic scan runs with stable tool versions
- [ ] Reports stored in output directory with timestamps + "latest" pointer
- [ ] Alert channels: CLI/RPC retrieval
- [ ] Optional Discord alerts (if Discord interface configured)

**Acceptance Criteria:**

- Scans run on schedule via scheduler service
- Reports are JSON-serializable and timestamped
- No false positives in baseline scan of clean repo

---

## Priority 4 — Workflow Automation

### 4.1 Dev Agent Runner (Sandboxed)

**Status:** 🔴 Not Started
**Effort:** Large (3+ weeks)
**Depends On:** Scheduler, Security Scanner
**Risk:** High — requires careful security design

**Requirements:**

- [ ] Sandboxed execution environment (dedicated container image)
- [ ] Plan + constraints + workspace + tool permissions model
- [ ] Explicit mounts (read-only vs read-write)
- [ ] Network restrictions (no network by default)
- [ ] Complete audit logging (commands, files touched, outputs, errors)
- [ ] Outputs: patch/branch or artifact bundle (never direct upstream push)

**Security Baseline:**

- [ ] Default deny: network, secrets access, external repo push
- [ ] Explicit allow-lists for commands, directories
- [ ] Time/resource limits enforced
- [ ] Human review gate before any upstream push

### 4.2 Serena MCP Capabilities Integration

**Status:** ⏸️ Deferred
**Depends On:** Dev Agent Runner (stable)

**Approach:**

- Start with "compatibility mode": allow Serena-like flows only inside sandbox runner container
- Integrate only after sandbox runner is stable, network policy is explicit, scanning pipeline exists

---

## Priority 5 — Advanced LLM Features

### 5.1 Mixture-of-Experts Mode (Core — Execution Strategy)

**Status:** ✅ Implemented
**Location:** `src/openchronicle/core/application/services/moe_execution.py`
**Effort:** Medium
**Priority:** Implemented

**Why core, not plugin:** MoE needs `LLMPort` to make N expert calls with
explicit model selection, `RouterPolicy` / `ProviderFacade` to route each expert
to a different provider/model, and response aggregation logic. The plugin API
provides `(task, context) → result` with no LLM access. MoE is an execution
strategy (like streaming vs non-streaming), not a stateless handler.

**Implementation:**

- [x] Run N experts via LLMPort with different model selections (quality pool candidates)
- [x] Select output via Jaccard-based consensus scoring (deterministic, no LLM-as-judge)
- [x] Produce aggregator decision with explainability via `moe.consensus_run` event
- [x] Deterministic selection rules with weight tiebreaker + stable sort
- [x] Event emission: `moe.consensus_run` with full expert breakdown
- [x] Config: `MoESettings` in `core.json` `"moe"` section, env var overrides
- [x] CLI: `oc chat --moe`, `oc convo ask --moe`
- [x] MCP: `conversation_ask(moe=true)`
- [x] 32 tests (consensus scoring, execute_moe, config loading, hygiene)

**Constraints (preserved):**

- Optional, not default UX (per-call `--moe` flag)
- Clear cost implications (N× token cost)
- Opt-in per conversation or per ask (not global default)

---

## Priority 6 — HTTP API (Core Interface)

### 6.1 HTTP API Server

**Status:** ✅ Done
**Location:** `src/openchronicle/interfaces/api/` (core dependency, not optional)
**Effort:** Medium
**Classification:** Core interface (Decision #6)

Always-on daemon infrastructure. FastAPI/uvicorn are core dependencies. The HTTP
API starts as part of `oc serve` alongside STDIO RPC. Mirrors MCP tools 1:1 as
REST endpoints — any HTTP client gets the same capabilities as MCP clients.

**Why core, not optional:** The HTTP API is the same tier as CLI, STDIO RPC,
Discord, and MCP. Webhooks (inbound and outbound) depend on it. Plugins register
routes through it. External integrations compose through it. It has no optional
SDK dependency — FastAPI is lightweight and always installed.

**Implemented:**

- [x] FastAPI app factory with lifespan container injection
- [x] `HTTPConfig` dataclass (host, port, api_key), three-layer precedence
- [x] Authentication middleware (API key, configurable exempt paths)
- [x] Per-client rate limiting middleware (sliding window, thread-safe, memory leak eviction)
- [x] Core routes mirroring MCP surface (19 endpoints):
  - [x] `/api/v1/memory/*` (search, save, list, pin, update)
  - [x] `/api/v1/conversation/*` (ask, history, list, create, context_recent)
  - [x] `/api/v1/project/*` (create, list)
  - [x] `/api/v1/asset/*` (upload, list, get, link)
  - [x] `/api/v1/health`, `/api/v1/stats` (tool_stats, moe_stats)
- [x] OpenAPI documentation (auto-generated by FastAPI)
- [x] Shared serializers (`interfaces/serializers.py`) — MCP + API use same dict helpers
- [x] Optional CORS via `OC_API_CORS_ORIGINS`
- [x] Wire HTTP server startup into `oc serve` (daemon thread)
- [x] 51 tests (`tests/test_http_api.py`)

**Deferred to future work:**

- [ ] SSE streaming for conversation_ask
- [ ] Privacy gate middleware (PII detection on inbound)
- [ ] Plugin route registration (mounted under `/api/v1/plugins/`)
- [ ] Hexagonal boundary tests (no `core.*` imports from `interfaces/api/`)

### 6.2 Webhook Service (Core)

**Status:** 🔴 Not Started
**Effort:** Medium
**Depends On:** HTTP API (P6.1)
**Classification:** Core service (`application/services/webhook_service.py`)

Webhooks are a core service that the HTTP API exposes, not just an HTTP feature.

**Requirements:**

- [ ] **Outbound:** Event listener → filter by subscription → HTTP POST with
      retry + HMAC signing
- [ ] **Inbound:** Receive POST → validate signature → transform payload →
      emit internal event
- [ ] **Storage:** `webhooks` table in SQLite (endpoint, event_types, secret,
      active)
- [ ] **Retry:** Existing `RetryController` pattern (exponential backoff with
      jitter)
- [ ] **Routes:** `POST /api/v1/webhooks` (register), `GET /api/v1/webhooks`
      (list), `DELETE /api/v1/webhooks/{id}` (remove),
      `POST /api/v1/webhooks/inbound/{source}` (receive)

---

## Priority 7 — Core Capabilities

### 7.1 Capability-Aware Routing

**Status:** ✅ Implemented
**Effort:** Small
**Classification:** Core enhancement (routing + model config)

`ModelConfigLoader` parses the `capabilities` dict from model configs.
`RouterPolicy` filters pool candidates by `required_capabilities` (opt-in).
`NO_CAPABLE_MODEL` error when no candidate matches. 12 tests.

**Requirements:**

- [x] Parse `capabilities` dict in `ModelConfigLoader`
- [x] Add capability filter to routing — select only models matching required
      capabilities
- [x] New capability flags: `text_generation`, `image_generation`,
      `video_generation`, `vision`
- [x] Optional `generation_pool` in `PoolConfig` for media generation models

### 7.2 Media Generation (Core Capability)

**Status:** 🔴 Not Started
**Effort:** Medium-Large
**Depends On:** Capability-Aware Routing (P7.1)
**Classification:** Core capability (Decision #7)

Locally hosted media generation (image, video) via a new port. Different
input/output types from text completion, different routing needs, different
cost model.

**Why core, not plugin:** Needs its own port (`MediaGenerationPort`), adapters
(Ollama, OpenAI), capability-aware routing, and asset integration. The plugin
API provides `(task, context) → result` with no LLM or asset access.

**Requirements:**

- [ ] `MediaGenerationPort` ABC (`generate_async`, `supported_media_types`)
- [ ] `MediaRequest` / `MediaResult` domain models
- [ ] Ollama media adapter (flux, sdxl, stable-diffusion via Ollama API)
- [ ] OpenAI media adapter (DALL-E)
- [ ] Stub adapter for testing
- [ ] `generate_media` use case (orchestrates port + asset storage)
- [ ] CLI: `oc media generate`
- [ ] MCP tool: `media_generate`
- [ ] HTTP API routes: `/api/v1/media/generate`

### 7.3 Multimodal Conversation Input

**Status:** 🔴 Not Started
**Effort:** Medium
**Depends On:** Capability-Aware Routing (P7.1)
**Classification:** Core enhancement (LLM port + adapters)

Send images to vision-capable models via the conversation pipeline. Currently
deferred in `docs/architecture/ASSETS.md`.

**Requirements:**

- [ ] Extend message format to include `image_url` content blocks
- [ ] Wire asset IDs → base64 or URL in `prepare_ask()`
- [ ] Add `asset_ids` parameter to `ask_conversation.execute()`
- [ ] Route to vision-capable models when images are present
- [ ] Adapter support in OpenAI, Anthropic, Ollama (vision models)

---

## Priority 8 — Memory Enhancement

Memory improvements are tracked in two dimensions:

- **Search technology:** v0 (keyword/FTS5) → v1 (embeddings/semantic)
- **Improvement phases:** Phase 1 (update + tag filter) → Phase 2 (context
  assembly + turn recording) → Phase 3 (incremental onboard)

### 8.0 Memory Phase 1 (Update + Tag-Filtered Search)

**Status:** ✅ Implemented
**Commit:** `d19617c`

- [x] `memory_update` use case — update content and/or tags, `updated_at` tracking
- [x] Tag-filtered search — AND-logic tag parameter on `search_memory()`
- [x] Schema migration (`updated_at` column, idempotent ALTER TABLE)
- [x] All interfaces: MCP tool, API endpoint, CLI command, serializer
- [x] 19 new tests (11 update, 8 tag search)

### 8.0.05 Memory Phase 1.1 (Interface Parity + Observability)

**Status:** ✅ Implemented

- [x] `delete_memory` use case — captures project_id before deletion, emits `memory.deleted` event
- [x] MCP tools: `memory_get`, `memory_delete`, `memory_stats` (21→24 tools)
- [x] API routes: `GET /memory/{id}`, `DELETE /memory/{id}`, `GET /memory/stats` (19→22 endpoints)
- [x] Pagination — `offset` parameter on `list_memory()` and `search_memory()` (all interfaces)
- [x] Source index — `idx_memory_source` on `memory_items(source)`
- [x] Streaming telemetry fix — `_stream_turn()` now passes telemetry to `prepare_ask()` and `finalize_turn()`
- [x] Observability events: `memory.search_completed` (latency, result count), `context.assembly_breakdown` (phase timing)
- [x] Fixed `MetricsTracker` protocol conformance (`Sequence` → `Iterable` for input params)
- [x] 27 new tests across 4 files

### 8.0.1 Memory Phase 2 (Context Assembly + Turn Recording)

**Status:** 🔴 Not Started
**Effort:** Medium
**Classification:** Core enhancement

- [ ] **Standalone context assembly** — expose OC's internal context assembly
      logic (`prepare_ask()` retrieval) as a standalone capability. MCP clients
      and API callers get retrieval intelligence without forcing an LLM call.
- [ ] **External turn recording** — allow MCP clients and API callers to record
      their conversation turns in OC. More data → better retrieval → better
      context in future interactions.

### 8.0.2 Memory Phase 3 (Incremental Git Onboard)

**Status:** 🔴 Not Started
**Effort:** Small-Medium

- [ ] Add watermark tracking so `onboard_git` processes only new commits since
      last run, enabling continuous narrative capture.

### 8.1 Memory v1 (Embeddings / Semantic Search)

**Status:** 🔴 Not Started
**Effort:** Medium-Large
**Classification:** Core enhancement (upgrades existing `MemoryStorePort`)

Memory v0 uses keyword-based search — functional but limited. Memory v1
introduces embedding-based semantic search for higher recall and relevance.

**Why core, not plugin:** Memory is the foundational product feature — OC
exists because chat context dies between sessions. Improving retrieval
quality affects every conversation turn. The memory port surface
(`MemoryStorePort`) is already in core; embeddings enhance it.

**Requirements:**

- [ ] Embedding generation (per memory item, on save)
- [ ] Vector similarity search (cosine or dot product)
- [ ] Hybrid retrieval: semantic search + existing keyword search
- [ ] Embedding provider abstraction (local vs API-based)
- [ ] Incremental re-embedding on memory update
- [ ] Storage: embeddings table or extension to existing memory table

**Open questions (decide at implementation time):**

- Embedding provider: local (sentence-transformers) vs API (OpenAI embeddings)?
- Storage: SQLite with vector extension (sqlite-vec) vs separate vector store?
- Retrieval strategy: semantic-only, keyword-only, or hybrid scoring?

**Context:** Decision #3 in `docs/CODEBASE_ASSESSMENT.md` established memory
self-report as v0 baseline. Memory v1 is the planned upgrade path. Self-report
data collected now informs retrieval quality when embeddings are added.

---

## Priority 9 — IDE / Developer Platform Integrations

### 9.1 VS Code Copilot SDK Integration

**Status:** 🔴 Not Started
**Effort:** Medium
**Depends On:** OC MCP Server (P2)

**Approach:** VS Code supports MCP servers natively. Primary integration path is
OC MCP server (same as Goose). Custom Copilot SDK integration is a secondary
option if deeper IDE integration is needed.

**Requirements:**

- [ ] VS Code MCP config pointing to `oc mcp serve`
- [ ] Authenticate explicitly (user-managed)
- [ ] Sanitize payloads / respect PII gate

### 9.1.1 IDE Event-Triggered Memory Integration

**Status:** 🔴 Not Started
**Effort:** Medium
**Depends On:** OC MCP Server (P2), Memory Phase 2 (P8.0.1)

Configure MCP so that IDE events (session start, file save, commit, context
compression, etc.) automatically trigger OC memory operations without manual
tool invocation. The goal is seamless, automatic memory utilization.

**Target IDEs:**

- [ ] **Claude Code** — hooks system (`user_prompt_submit`, session start/end)
      for auto-save/load of working context
- [ ] **Goose** — MCP event subscriptions for auto-memory on session boundaries
- [ ] **VS Code** — extension events (workspace open, file save) mapped to OC
      memory operations via MCP

**Requirements:**

- [ ] Define event-to-action mapping (which IDE events trigger which OC operations)
- [ ] MCP server-side event subscription capability (or polling)
- [ ] Auto-context injection on session start (load relevant memories)
- [ ] Auto-save working context on session end / context compression
- [ ] User-configurable triggers (enable/disable per event type)

### 9.2 Goose (Block) Integration (MCP Client)

**Status:** 🔴 Not Started
**Effort:** Low (once OC MCP server exists)
**Depends On:** OC MCP Server (P2)

**What it is:** Goose is an open-source, local, extensible AI agent aimed at
automating engineering tasks end-to-end (CLI + desktop), with native MCP server
support.

**Why we care:** Goose + OC MCP + Serena MCP forms a triangle where Goose is the
agent (hands), Serena provides code understanding (eyes), and OC provides
persistent memory (long-term memory). No single tool does all three.

**Integration approach (Decision #5 — MCP-first):**

Goose connects to OC as an MCP server. No custom Goose extension code. No
sandbox runner prerequisite. Goose orchestrates; OC serves memory and
conversation capabilities.

```text
Goose (orchestrating agent)
  ├── Serena MCP server  →  code understanding (what IS)
  └── OC MCP server      →  persistent memory (what WAS and WHY)
```

**What Goose gets from OC via MCP:**

- Cross-session memory (save/search/pin knowledge that persists)
- Conversation history (resume context from prior sessions)
- Full conversation pipeline (routing, privacy gate, telemetry)
- Audit trail (hash-chained events for every interaction)

**MVP:**

- [ ] OC MCP server running (`oc mcp serve`)
- [ ] Goose profile config pointing to both OC and Serena MCP servers
- [ ] Manual validation: Goose saves a memory via OC, exits, new session
      retrieves it

**Upgrade path (later — Dev Agent Runner):**

The MCP approach has Goose orchestrating and OC serving. The Dev Agent Runner
(P4.1) flips the control: OC orchestrates Goose as a sandboxed worker with full
audit trail, security scanning, and network policy. The MCP server is a
prerequisite for both approaches.

**Security guardrails for the upgrade path (non-negotiable, same as before):**

- Default no internet unless explicitly enabled per run
- Strict allowlists for writable paths, executable commands, max runtime
- No pushing to external remotes
- All outputs pass through scanning pipeline before being considered trusted

**Notes:**

- Goose remains a replaceable agent runtime. Any MCP-compatible agent (Claude
  Desktop, VS Code Copilot, custom agents) gets the same OC capabilities.

---

## Priority 10 — Platform Infrastructure

### 10.1 Private Git Server Integration

**Status:** 🔴 Not Started
**Effort:** Medium
**Depends On:** Dev Agent Runner

**Approach:**

- Self-hosted Git (Gitea/GitLab) behind network
- Clone/pull in sandbox, produce branches/patches
- Manual human review gate before any upstream push

---

## Priority 11 — Personal Life Connectors

These connectors extend OC beyond developer tooling into personal AI
assistant territory. All connectors are **read-only by default** — OC
observes and advises, it does not impersonate or take actions on the
user's behalf. Each connector is a plugin or core driver (classification
TBD at implementation time based on how deeply it needs core access).

### 11.1 Google Account Connector

**Status:** 🔴 Not Started
**Effort:** Medium-Large
**Depends On:** Asset System (for Drive file references), Scheduler (for periodic sync)

Read-only integration with Google Workspace services. OC becomes a
time-aware assistant that knows your schedule, can summarize emails, and
has context from your documents — without impersonating you.

**Scope (read-only, no impersonation):**

- [ ] **Google Calendar** — event awareness, schedule context, upcoming reminders.
      OC knows what's on the calendar and can factor it into conversations.
- [ ] **Gmail** — email summaries, search, thread context. OC can summarize
      unread mail, find past emails by topic, surface relevant threads.
- [ ] **Google Drive** — file listing, document context, search. Ties into
      the asset system for file references without duplicating storage.

**Technical approach:**

- [ ] OAuth 2.0 flow (offline access, refresh tokens)
- [ ] Google API client (`google-api-python-client`)
- [ ] Credential storage (encrypted at rest, git-ignored)
- [ ] Periodic sync via scheduler (calendar events, recent emails)
- [ ] MCP tools: `google_calendar_today`, `google_email_summary`,
      `google_drive_search` (tentative)

**Security constraints:**

- Read-only OAuth scopes only (no send, no modify, no delete)
- Credentials never logged or stored in event trail
- PII gate applies to all Google-sourced content

### 11.2 Plex Media Server Connector

**Status:** 🔴 Not Started
**Effort:** Medium
**Depends On:** Scheduler (for periodic sync)

Integration with a local Plex Media Server. OC tracks your media library,
remembers what you've watched, and can monitor server health.

**Scope:**

- [ ] **Library management** — browse libraries, search media, metadata
      access. OC knows what's in your collection.
- [ ] **Watch history / recommendations** — track viewed content, suggest
      unwatched items based on preferences and history.
- [ ] **Server monitoring** — transcoding status, storage usage, active
      streams, server health checks.

**Technical approach:**

- [ ] Plex API via `plexapi` Python library (or direct REST)
- [ ] Plex token authentication
- [ ] Periodic library/watch-history sync via scheduler
- [ ] MCP tools: `plex_search`, `plex_recently_watched`, `plex_server_status`
      (tentative)
- [ ] Memory integration: watch history stored as OC memories for
      cross-session recommendations

### 11.3 Personal Finance Connector

**Status:** 🔴 Not Started
**Effort:** Large
**Depends On:** Scheduler (for periodic sync)
**Risk:** Medium — financial data requires careful security handling

OC helps manage personal finances: transaction tracking, spending
categorization, bill/subscription monitoring, and investment overview.

**Scope:**

- [ ] **Transaction aggregation** — pull transactions from bank accounts,
      categorize spending, track against budgets. Plaid or similar
      aggregation service.
- [ ] **Bill / subscription tracking** — identify recurring charges, track
      due dates, flag unusual amounts or new subscriptions.
- [ ] **Investment tracking** — portfolio overview, market data, basic
      performance metrics.

**Technical approach:**

- [ ] Plaid API for bank/transaction aggregation (or open-source
      alternative)
- [ ] Market data API for investment tracking (Alpha Vantage, Yahoo
      Finance, or similar)
- [ ] Encrypted credential storage (separate from general config)
- [ ] Periodic transaction sync via scheduler
- [ ] MCP tools: `finance_transactions`, `finance_bills`,
      `finance_portfolio` (tentative)
- [ ] Spending categorization (rule-based initially, LLM-assisted later)

**Security constraints (non-negotiable):**

- All financial credentials encrypted at rest
- No financial data in event trail or general logs
- PII gate enforced on all financial content
- No write/transfer capabilities (read-only aggregation)
- Audit log for every data access

---

## Infrastructure Gaps

### Output Directory Utilization

**Status:** ⚪ Reserved
**Env Var:** `OC_OUTPUT_DIR`

**Planned Uses:**

- [ ] Scheduler job outputs
- [ ] Security scanner reports
- [ ] Dev agent artifacts
- [ ] Export bundles

---

## Testing Gaps

### Performance Testing

**Status:** 🔴 Not Started

**Requirements:**

- [ ] Load testing for rate limiting / concurrency scenarios
- [ ] Performance regression testing suite
- [ ] Benchmark tracking over time

### Plugin Integration Testing

**Status:** 🟡 Partial

**Requirements:**

- [ ] Standardized plugin test harness
- [ ] Mock core for plugin unit tests
- [ ] Integration test templates

---

## Documentation Gaps

### Missing Documentation

- [ ] **Performance/Optimization Guide** — Scaling, caching strategies, perf tuning
- [ ] **Debugging Guide** — Troubleshooting procedures, common issues
- [ ] **Security Hardening Guide** — Production hardening beyond privacy gate
- [ ] **Contribution Guidelines** — CONTRIBUTING.md with PR process
- [ ] **Plugin development entry point** — consolidate 4 plugin docs into single
      learning path with end-to-end tutorial (audit M3)
- [ ] **Docker minimal build guide** — document building provider-specific images,
      size optimization (audit L1)
- [ ] **Pre-commit hooks in README** — add quick-start note for hook setup (audit L2)

### Audit Findings (2026-02-23, Medium/Low)

Deferred items from fresh-eyes usability audit:

| ID | Finding | Severity | Notes |
| ---- | --------- | ---------- | ------- |
| M1 | HTTP API has 19 endpoints, not 21 — delta is `search_turns` and `context_recent` as standalone MCP tool | Medium | Decide if API should gain these 2 endpoints |
| M4 | ARCHITECTURE.md route section structure correct but endpoint count was wrong | Medium | Fixed in C1 pass |
| M6 | Routing terminology inconsistent ("Router assist" vs "Router policy" vs "Smart routing") | Low | Context usually clarifies; glossary entry would help |

---

## Technical Debt

### Known Issues

| Issue                               | Location                                                      | Priority |
| ----------------------------------- | ------------------------------------------------------------- | -------- |
| FTS5 rebuild on every startup       | `infrastructure/persistence/sqlite_store.py _ensure_fts5()`   | Low      |
| Ollama token counts are estimates   | `infrastructure/llm/ollama_adapter.py`                        | Low      |
| ~~Unicode encoding on Windows CLI~~ | `interfaces/cli/main.py`                                      | ✅ Fixed |
| ~~Test subprocess PATH issue~~      | `tests/test_task_submit_rpc.py`                               | ✅ Fixed |
| ~~Docker acceptance JSON escaping~~ | `tools/docker/acceptance.ps1`                                 | ✅ Fixed |
| ~~docker-compose .env required~~    | `docker-compose.yml`                                          | ✅ Fixed |
| ~~Smoke test assertion too strict~~ | `tests/integration/test_smoke_live.py`                        | ✅ Fixed |

### Code Quality Enforcement

All enforced via CI/tests:

- ✅ No tech debt marker comments (`test_no_soft_deprecation.py`)
- ✅ No secrets committed (`test_no_secrets_committed.py`)
- ✅ Strict mypy typing required
- ✅ Ruff formatting + linting required

---

## Implementation Sequence

Recommended order based on dependencies:

```text
1. Scheduler Service (P0) ✅
   └── Core service in application/services/

2. Discord Interface (P1) ✅
   └── Core driver in interfaces/discord/

3. OC MCP Server (P2) ✅
   └── Core interface in interfaces/mcp/
   └── 21 tools, maps to existing ports/use cases
   └── Unblocks: Goose, VS Code, Claude Desktop, any MCP client

4. Mixture-of-Experts (P5) ✅
   └── Core execution strategy in application/services/
   └── Jaccard consensus, --moe CLI/MCP flag, 32 tests

5. HTTP API (P6) ✅
   └── Core interface in interfaces/api/
   └── FastAPI, 21 REST endpoints, API key auth, rate limiting, 51 tests
   └── Starts with oc serve, shared serializers with MCP

6. Capability-Aware Routing (P7.1) ✅
   └── capabilities dict parsed in ModelConfigLoader, get_capabilities() method
   └── RouterPolicy filters pool by required_capabilities (opt-in)
   └── NO_CAPABLE_MODEL error code, audit trail, 12 new tests

7. Media Generation (P7.2)
   └── New port + adapters (Ollama, OpenAI), Decision #7
   └── Depends on capability routing

8. Webhooks (P6.2)
   └── Core service, depends on HTTP API
   └── Outbound event subscriptions + inbound receivers

9. Security Scanner Plugin (P3)
   └── Runs via scheduler service
   └── Safety rail for dev agent

10. Goose Integration (P9.2) ← MOVED UP (unblocked by MCP server)
    └── MCP client connecting to OC MCP + Serena MCP
    └── No custom code — just config

11. Multimodal Conversation Input (P7.3)
    └── Vision input via asset system
    └── Depends on capability routing

12. Memory v1 — Embeddings (P8)
    └── Semantic search for memory retrieval
    └── Core enhancement to MemoryStorePort

13. Dev Agent Runner (P4.1)
    └── Uses scheduler + scanner
    └── Sandboxed execution
    └── Upgrade path: OC orchestrates Goose

14. Serena MCP in Sandbox (P4.2)
    └── Inside sandbox runner only

15. VS Code Copilot SDK (P9.1)
    └── MCP client or custom RPC

16. Private Git Server (P10)
    └── Platform infrastructure

17. Google Account Connector (P11.1)
    └── Read-only Calendar + Gmail + Drive
    └── OAuth 2.0, periodic sync via scheduler

18. Plex Media Server Connector (P11.2)
    └── Library, watch history, server monitoring
    └── Plex API, scheduler-driven sync

19. Personal Finance Connector (P11.3)
    └── Transactions, bills, investments
    └── Plaid API, encrypted credentials, strict security
```

---

## References

- **Architecture:** `docs/architecture/ARCHITECTURE.md`
- **Plugin Guide:** `docs/architecture/PLUGINS.md`
- **Plugin Roadmap:** `docs/plugins/plugin_backlog.md`
- **RPC Protocol:** `docs/protocol/stdio_rpc_v1.md`
- **Discord Contract:** `docs/integrations/discord_driver_contract.md`
- **MCP Server Spec:** `docs/integrations/mcp_server_spec.md`
- **Project Instructions:** `CLAUDE.md`
