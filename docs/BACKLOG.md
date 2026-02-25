# OpenChronicle v2 — Feature & Implementation Backlog

This document tracks planned features, implementation gaps, and future work
for OpenChronicle v2. Organized into phases based on dependencies, effort,
and value. **This is a living document** — reviewed after each phase
completion. See `docs/CODEBASE_ASSESSMENT.md` for current project status.

**Last Updated:** 2026-02-24

---

## Review Protocol

This backlog is re-evaluated after each phase completion. The goal is to
capture what we learned during implementation and adjust course — not to
re-plan from scratch every time.

**Trigger:** Completing any numbered phase or significant milestone.

**Review checklist:**

1. Did implementation reveal a missing core capability? → Add to Core
   Infrastructure Gaps.
2. Did effort estimates prove wrong? → Update remaining estimates.
3. Did a "later" item become urgent (e.g., daily-use connector)? → Move
   it up in the implementation sequence.
4. Did a planned item turn out to be unnecessary? → Remove or defer it.
5. Did a plugin candidate need core access? → Reclassify to core and
   document why.
6. Any new items discovered during implementation? → Add to the right
   phase.

**What changes:** Ordering, effort estimates, new items, removed items.

**What doesn't change:** The taxonomy (plugin/core/external), the
dependency graph (unless a real dependency is discovered), and completed
work.

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

## Completed Work (Reference)

Everything below is implemented, tested, and merged to `main`. Collapsed
for reference — see `docs/CODEBASE_ASSESSMENT.md` for full details.

<details>
<summary><strong>Foundation & Core Services</strong></summary>

- **Scheduler Service** — tick-driven, atomic claim, 53 tests, CLI + RPC
  (`application/services/scheduler.py`)
- **Mixture-of-Experts** — Jaccard consensus, quality pool, `--moe` flag,
  32 tests (`application/services/moe_execution.py`)
- **Capability-Aware Routing** — `ModelConfigLoader` parses capabilities,
  `RouterPolicy` filters by `required_capabilities`, 12 tests
- **Asset Management** — filesystem storage, SHA-256 dedup, generic linking,
  4 MCP tools, 4 CLI commands, 40 tests
- **Time Context Injection** — current time, last interaction, seconds delta
- **File-Based Config** — single `core.json`, three-layer precedence
- **Config Externalization** — conversation defaults + Discord settings wired
- **Enterprise Tightening** — Passes A/B/C: domain exceptions, input
  validation, DRY extraction, timeouts, container lifecycle, error codes,
  API/MCP parity, 102 new tests across 3 passes

</details>

<details>
<summary><strong>Interfaces</strong></summary>

- **CLI** — 76+ subcommands via dispatch tables, streaming support
- **STDIO RPC** — 24 commands, async, daemon mode (`oc serve`)
- **Discord Interface** — 6 slash commands, session mapping, 85 tests,
  optional `[discord]` extra (`interfaces/discord/`)
- **MCP Server** — 27 tools, stdio + SSE transports, 44 tests, optional
  `[mcp]` extra (`interfaces/mcp/`)
- **HTTP API** — FastAPI, 25 REST endpoints, API key auth, rate limiting,
  CORS, 54+ tests (`interfaces/api/`)
- **Docker CI** — GitHub Actions multi-arch build, GHA cache

</details>

<details>
<summary><strong>Memory System</strong></summary>

- **Phase 1** — `memory_update` use case, tag-filtered AND-logic search,
  schema migration, 19 tests
- **Phase 1.1** — Interface parity (`get`/`delete`/`stats` on MCP + API),
  pagination, source index, observability events, 27 tests
- **Phase 2** — External turn recording, standalone context assembly,
  incremental `onboard_git` with watermark tracking, `context_builder`
  service extracted from `prepare_ask()`, 39 tests
- **Phase 3 (Memory v1)** — Embedding-based semantic search, `EmbeddingPort`
  ABC (stub/OpenAI/Ollama adapters), `EmbeddingService` with hybrid FTS5+cosine
  retrieval via RRF, `memory_embeddings` table, backfill CLI/MCP/API,
  backwards-compatible default, 54 new tests

</details>

**Totals:** 1,291 tests, 27 MCP tools, 26 REST endpoints, 10 ports, 8
services, 35 use cases, 5 interfaces.

---

## Feature Taxonomy

Every feature falls into one of three categories. This determines where
code lives and what APIs it uses.

| Category | Definition | Location | API Access |
| -------- | ---------- | -------- | ---------- |
| **Core** | Stateful, needs ports/scheduler/LLM, lifecycle hooks | `application/services/`, `domain/ports/` | Full |
| **Plugin** | Stateless `(task, context) → result` handler | `plugins/<name>/` | Task payload + event emission |
| **External** | Composes via MCP or HTTP API | Outside OC repo | MCP tools / REST endpoints |

**Rule:** If a feature needs LLM access, persistent storage, scheduler
integration, or shell execution, it is core — not a plugin. Plugins are
independent, stateless, and never depend on other plugins. If a plugin
candidate reveals a need for core capabilities, the missing capability
is added to core first.

---

## Quick Wins (Trivial, Unblocked Now)

### Goose MCP Integration

**Status:** ✅ Implemented
**Effort:** Trivial (config only)
**Category:** External

Goose connects to OC as an MCP server. No custom code — just a Goose
profile config pointing to `oc mcp serve` alongside Serena MCP.

```text
Goose (orchestrating agent)
  ├── Serena MCP server  →  code understanding (what IS)
  └── OC MCP server      →  persistent memory (what WAS and WHY)
```

**MVP:**

- [x] Goose profile config pointing to both OC and Serena MCP servers
- [ ] Manual validation: save memory → exit → new session retrieves it

### VS Code MCP Integration

**Status:** ✅ Implemented
**Effort:** Trivial (config only)
**Category:** External

VS Code supports MCP servers natively. Primary integration is `oc mcp serve`
in VS Code's MCP config. Custom Copilot SDK integration is secondary — only
if deeper IDE features are needed later.

- [x] VS Code MCP config pointing to `oc mcp serve`
- [ ] Manual validation: memory save/search works from VS Code

---

## Core Infrastructure Gaps (Blockers)

These are small but foundational services that multiple downstream features
depend on. They should be built before the features that need them.

### Output Manager

**Status:** 🔴 Not Started
**Effort:** Small
**Blocks:** Security Scanner, Dev Agent Runner, export bundles

Expose `OC_OUTPUT_DIR` through a proper core service for structured file
output with timestamps and lifecycle management.

**Requirements:**

- [ ] `application/services/output_manager.py` — core service
- [ ] `save_report(report_type, data) → path` — timestamped JSON output
- [ ] `list_outputs(report_type) → list` — enumerate outputs
- [ ] `latest_output(report_type) → path | None` — "latest" pointer
- [ ] `cleanup(max_age_days) → int` — garbage collection
- [ ] Config: `OC_OUTPUT_DIR` env var (existing, currently unused)

### Controlled Shell Execution

**Status:** 🔴 Not Started
**Effort:** Small-Medium
**Blocks:** Security Scanner, Dev Agent Runner

Subprocess execution with timeout, permission enforcement, and audit
logging. Required by any core service that runs external tools.

**Requirements:**

- [ ] `application/services/shell_runner.py` — core service
- [ ] Execute command with timeout and resource limits
- [ ] Allowlist enforcement (permitted commands/paths)
- [ ] Structured result capture (stdout, stderr, exit code, duration)
- [ ] Event emission: `shell.command_executed` with audit trail
- [ ] No network access by default (configurable per invocation)

---

## Phase 3 — Smarter Memory

**Goal:** Upgrade memory retrieval from keyword matching to semantic search.
Highest daily impact — every OC session touches memory.

### Memory v1: Embeddings / Semantic Search

**Status:** ✅ Implemented
**Effort:** Medium-Large
**Category:** Core (new `EmbeddingPort`, enhances memory search pipeline)

Provider-agnostic embedding-based semantic search behind the existing
`search_memory()` interface. Hybrid FTS5 keyword + cosine similarity combined
via Reciprocal Rank Fusion (RRF). No new heavy dependencies.

**Implemented:**

- [x] `EmbeddingPort` ABC — provider abstraction (`embed`, `embed_batch`, `dimensions`, `model_name`)
- [x] Stub adapter (deterministic hash-based vectors for testing)
- [x] OpenAI adapter (`text-embedding-3-small`, 1536 dims)
- [x] Ollama adapter (`nomic-embed-text`, `/api/embed` endpoint)
- [x] `EmbeddingService` — generation, backfill, hybrid search orchestration
- [x] Hybrid search: FTS5 (list A) + cosine similarity (list B) → RRF merge (k=60)
- [x] `memory_embeddings` table (BLOB storage, FK CASCADE to `memory_items`)
- [x] Auto-generate on memory save, force-regenerate on content update
- [x] Backfill CLI (`oc memory embed`), MCP tool (`memory_embed`), API endpoint
- [x] Backwards-compatible: `OC_EMBEDDING_PROVIDER=none` (default) = FTS5-only
- [x] 54 new tests (port, adapters, storage, service, backfill, wiring)

**Decisions made:**

- Embedding provider: API-based (OpenAI + Ollama), not local `sentence-transformers`
- Storage: BLOB in SQLite (`struct.pack`), no `sqlite-vec` extension needed
- Retrieval: Hybrid scoring (keyword + semantic via RRF), not either/or
- Cosine similarity via dot product of pre-normalized unit vectors (pure Python)

---

## Phase 4 — Reactive Eventing

**Goal:** Make OC event-driven. External systems can subscribe to OC events
and push events into OC.

### Webhook Service

**Status:** 🔴 Not Started
**Effort:** Medium
**Category:** Core (`application/services/webhook_service.py`)
**Depends On:** HTTP API ✅

**Requirements:**

- [ ] **Outbound:** Event listener → filter by subscription → HTTP POST
      with retry + HMAC signing
- [ ] **Inbound:** Receive POST → validate signature → transform payload →
      emit internal event
- [ ] **Storage:** `webhooks` table in SQLite (endpoint, event_types,
      secret, active)
- [ ] **Retry:** Existing `RetryController` pattern (exponential backoff
      with jitter)
- [ ] **Routes:** CRUD for webhook subscriptions + inbound receiver
  - `POST /api/v1/webhooks` (register)
  - `GET /api/v1/webhooks` (list)
  - `DELETE /api/v1/webhooks/{id}` (remove)
  - `POST /api/v1/webhooks/inbound/{source}` (receive)
- [ ] MCP tools: `webhook_register`, `webhook_list`, `webhook_delete`
- [ ] Events: `webhook.registered`, `webhook.delivered`, `webhook.failed`

---

## Phase 5 — Agent Automation Hooks

**Goal:** Frictionless memory flow — IDE events automatically trigger OC
memory operations without manual tool invocation.

### IDE Event-Triggered Memory

**Status:** 🔴 Not Started
**Effort:** Medium
**Category:** External (config + hooks, minimal OC-side changes)
**Depends On:** MCP Server ✅, Memory Phase 2 ✅

Configure MCP so that IDE events (session start, file save, commit, context
compression) automatically trigger OC memory operations.

**Target IDEs:**

- [ ] **Claude Code** — hooks system (`user_prompt_submit`, session
      start/end) for auto-save/load of working context
- [ ] **Goose** — MCP event subscriptions for auto-memory on session
      boundaries
- [ ] **VS Code** — extension events (workspace open, file save) mapped
      to OC memory operations via MCP

**Requirements:**

- [ ] Define event-to-action mapping (which IDE events → which OC ops)
- [ ] Auto-context injection on session start (load relevant memories)
- [ ] Auto-save working context on session end / context compression
- [ ] User-configurable triggers (enable/disable per event type)
- [ ] Documentation: hook config examples for each IDE

**OC-side changes (if any):**

- [ ] MCP server-side event subscription capability (or SSE push)
- [ ] Batch memory operations for efficiency (save multiple in one call)

---

## Phase 6 — Media & Vision

**Goal:** Image generation and vision input. These share capability-aware
routing infrastructure (already implemented).

### Media Generation Port

**Status:** 🔴 Not Started
**Effort:** Medium-Large
**Category:** Core (new port + adapters)
**Depends On:** Capability-Aware Routing ✅

New port for image/video generation. Different input/output types from text
completion, different routing needs, different cost model.

**Why core:** Needs its own port (`MediaGenerationPort`), adapters, routing,
and asset integration. The plugin API provides no LLM or asset access.

**Requirements:**

- [ ] `MediaGenerationPort` ABC (`generate_async`, `supported_media_types`)
- [ ] `MediaRequest` / `MediaResult` domain models
- [ ] Stub adapter for testing
- [ ] Ollama media adapter (flux, sdxl, stable-diffusion via Ollama API)
- [ ] OpenAI media adapter (DALL-E)
- [ ] `generate_media` use case (orchestrates port + asset storage)
- [ ] CLI: `oc media generate`
- [ ] MCP tool: `media_generate`
- [ ] API route: `POST /api/v1/media/generate`

### Multimodal Conversation Input

**Status:** 🔴 Not Started
**Effort:** Medium
**Category:** Core (LLM port + adapter enhancement)
**Depends On:** Capability-Aware Routing ✅

Send images to vision-capable models via the conversation pipeline.

**Requirements:**

- [ ] Extend message format to include `image_url` content blocks
- [ ] Wire asset IDs → base64 or URL in `prepare_ask()`
- [ ] Add `asset_ids` parameter to `ask_conversation.execute()`
- [ ] Route to vision-capable models when images present
- [ ] Adapter support in OpenAI, Anthropic, Ollama (vision models)

---

## Phase 7 — Security & Automation

**Goal:** Safety rails for autonomous agent execution. Sequential dependency
chain — each item depends on the one before it.

**Dependency chain:**

```text
Core Infra (Output Manager + Shell Execution)
  └── Security Scanner ──→ Dev Agent Runner ──→ Serena in Sandbox
```

### Security Scanner (Core Service)

**Status:** 🔴 Not Started
**Effort:** Medium
**Category:** Core (`application/services/security_scanner.py`)
**Depends On:** Scheduler ✅, Output Manager, Shell Execution

**Reclassified from plugin to core service.** Needs scheduler integration,
controlled shell execution, output directory access, and event emission —
none of which the plugin API provides. Per Decision #4 (hybrid taxonomy).

**Requirements:**

- [ ] Integrate existing scanners (not inventing new ones):
  - [ ] Secrets scanning: gitleaks or trufflehog
  - [ ] Dependency vulnerability: osv-scanner
  - [ ] Container scanning: trivy (optional)
  - [ ] Static analysis: semgrep rules (optional)
- [ ] Scheduled scan runs via scheduler service
- [ ] Reports stored via output manager with timestamps + "latest" pointer
- [ ] Alert channels: CLI/RPC retrieval
- [ ] Optional Discord alerts (via event → webhook or direct interface)
- [ ] Events: `security.scan_started`, `security.scan_completed`,
      `security.finding_detected`

**Acceptance Criteria:**

- Deterministic scan runs with stable tool versions
- Reports are JSON-serializable and timestamped
- No false positives in baseline scan of clean repo

### Dev Agent Runner (Sandboxed)

**Status:** 🔴 Not Started
**Effort:** Large (3+ weeks)
**Category:** Core (`application/services/sandbox_runner.py`)
**Depends On:** Scheduler ✅, Security Scanner, Shell Execution
**Risk:** High — requires careful security design

**Requirements:**

- [ ] Sandboxed execution environment (dedicated container image)
- [ ] Plan + constraints + workspace + tool permissions model
- [ ] Explicit mounts (read-only vs read-write)
- [ ] Network restrictions (no network by default)
- [ ] Complete audit logging (commands, files touched, outputs, errors)
- [ ] Outputs: patch/branch or artifact bundle (never direct upstream push)
- [ ] Security scanner runs on all outputs before they leave sandbox

**Security Baseline (non-negotiable):**

- [ ] Default deny: network, secrets access, external repo push
- [ ] Explicit allow-lists for commands, directories
- [ ] Time/resource limits enforced
- [ ] Human review gate before any upstream push

### Serena MCP in Sandbox

**Status:** ⏸️ Deferred
**Depends On:** Dev Agent Runner (stable)

Allow Serena-like code navigation flows only inside the sandbox runner
container. Integrate only after sandbox runner is stable, network policy
is explicit, and scanning pipeline exists for outputs.

---

## Plugins

Plugins are **independent, stateless handlers** that register via the plugin
API: `(task, context) → result`. They never depend on other plugins. They
never access LLM, storage, or scheduler directly. If a plugin candidate
needs core capabilities, the capability is added to core first.

**Plugins serve a dual purpose:**

1. **User-facing functionality** — domain-specific task handlers
2. **Pipeline exercise** — every plugin execution generates events, produces
   results, and flows through the task lifecycle. More diverse workloads
   improve observability data, stress-test the event system, and validate
   retrieval quality when memory embeddings land. Plugins are the best way
   to generate realistic, varied datapoints through the core pipeline.

### Plugin Standards

- Must load/unload cleanly (no side effects at import time)
- Deterministic ordering where selection matters
- Structured, auditable outputs (stable JSON envelopes)
- Errors carry canonical `error_code` and actionable hints
- Network usage: explicit config flag, logged endpoints
- No secrets in logs
- Tests: unit tests for handlers, integration test for `plugin.invoke`

### Storytelling Plugin Suite

**Status:** 🔴 Not Started (demo handler exists in `plugins/storytelling/`)
**Effort:** Medium-Large
**Reference:** `archive/openchronicle.v1` branch

V1 was a comprehensive narrative AI engine. V2 stripped to domain-agnostic
core. The v1 features belong in a plugin suite. Each subsystem is an
independent plugin — no cross-plugin dependencies.

**Candidate plugins (each independent):**

- [ ] **Character management** — entity tracking, stats, behavior
- [ ] **Scene/timeline management** — scene persistence, navigation
- [ ] **Narrative engines** — consistency checker, emotional analyzer
- [ ] **Game mechanics** — dice engine, narrative branching
- [ ] **Bookmark system** — scene bookmarking, chapters
- [ ] **Persona extractor** — see dedicated section below

**Data value:** Storytelling plugins generate rich, structured events
(character interactions, scene transitions, narrative decisions) that
exercise the event pipeline with diverse, non-trivial payloads. This data
is valuable for testing memory retrieval quality and event replay.

**Storage note:** Character state and scene persistence need structured
storage. Options: (a) serialize state in task payloads (stateless), (b) use
OC memory system via the conversation pipeline, (c) if the plugin API proves
insufficient, promote storage-heavy features to core services. Evaluate at
implementation time — don't over-engineer the plugin API preemptively.

### Persona Extractor (Storytelling Extension)

**Status:** 🔴 Not Started
**Effort:** Large
**Category:** Plugin (stateless extraction pipeline)
**Depends On:** Storytelling Plugin Suite (character management), Multimodal
Input (Phase 6)

Extract personality models from performance content (video, audio,
transcripts). Target use case: analyzing actors' live interpretations of
characters — speech patterns, decision-making tendencies, emotional
responses, humor style, conflict resolution approach — and producing
structured persona templates for use in OC's character management system.

**Pipeline:**

```text
Video/Audio source
  → Transcription (Whisper or equivalent)
  → Behavioral analysis (LLM-driven extraction)
  → Persona schema (structured JSON: traits, speech patterns, values, quirks)
  → Character template (feeds into storytelling character management)
```

**Key insight: volume is the feature, not the problem.** Thousands of
hours of source material (e.g., Critical Role's full catalog) makes this
an ideal long-running background workload. The extraction job runs for
hours, days, or weeks via the scheduler — progressively building a
persona model with increasing confidence. This is the single best
stress test for sustained scheduler operation, event pipeline throughput,
memory accumulation, and embedding search at scale. Nothing else in the
backlog exercises these systems at this sustained load.

**Progressive confidence model:** The extractor doesn't process
everything — it processes *enough*. Early passes build a rough persona
from sampled scenes. Subsequent passes refine, confirm, or revise trait
assessments. A confidence score tracks convergence per trait. When the
delta between iterations drops below a threshold, extraction stops for
that trait (or the whole persona). This means a well-defined character
might converge in hours; a nuanced one might take longer. The system
decides, not the operator.

**Requirements:**

- [ ] Persona schema definition (structured JSON for personality traits,
      speech patterns, behavioral tendencies, values, quirks, each with
      confidence scores)
- [ ] Transcription ingestion (accept pre-transcribed text, or invoke
      transcription service for audio/video)
- [ ] Scene sampling strategy (smart selection of character-defining
      moments, not exhaustive sequential processing)
- [ ] Multi-pass LLM extraction (behavioral analysis, speech pattern
      identification, trait synthesis)
- [ ] Confidence tracking and convergence detection (per-trait confidence
      scores, iteration delta threshold, automatic completion)
- [ ] Actor/character separation (context-aware extraction — distinguish
      performer from role, especially for DMs voicing multiple NPCs)
- [ ] Persona validation (consistency checks, completeness scoring)
- [ ] Export as character template (compatible with character management
      plugin)
- [ ] Long-running job support (scheduler integration, progress
      tracking, resumable after interruption)

**Licensing considerations:** Source material (e.g., Critical Role,
actual-play content) is copyrighted. The extraction tool itself is
general-purpose, but character models derived from specific IP require
licensing agreements. Strategy: build the tool as a general-purpose
persona extractor, demonstrate with a proof-of-concept on licensed
content, then pursue licensing for distribution of derived character
models. The demo proves technical viability; the license enables
sharing.

**Scope honesty:** This is a large, ambitious idea. The effort estimate
above is likely an understatement. Capturing it now to preserve the
concept; feasibility assessment happens when dependencies are met.

**Why this is interesting beyond storytelling:** A general-purpose persona
extractor has applications beyond fictional characters — interview
analysis, communication style profiling, user preference modeling. The
storytelling use case is the most compelling demo, but the underlying
capability is broadly useful.

### Future Plugin Candidates

Plugin ideas that would generate valuable pipeline data:

- **Daily journal / reflection** — scheduled via core, generates structured
  memory entries. Exercises scheduler→task→event→memory flow.
- **Code snippet analyzer** — processes code payloads, emits structured
  analysis events. Exercises task handler + event emission.
- **Habit tracker** — periodic tasks with time-series data. Exercises
  scheduler integration and event aggregation.

**Evaluation criteria for new plugins:**

1. Does it generate diverse, realistic data through the pipeline?
2. Does it exercise a core capability that needs validation?
3. Can it be implemented as a stateless handler? (If not → core service)
4. Is it independent of all other plugins?

---

## Personal Life Connectors

These extend OC beyond developer tooling into personal AI assistant
territory. All connectors are **read-only by default** — OC observes and
advises, it does not impersonate or take actions on the user's behalf.

Each connector is independent. Classification (plugin vs core driver) is
TBD at implementation time based on how deeply it needs core access.
Connectors that need scheduler integration for periodic sync are likely
core services.

**Connectors as continuous integration tests:** A connector used daily is
worth more than a feature used occasionally. Daily-use connectors produce a
steady stream of real-world data through the entire pipeline — scheduler
ticks, memory population, event emission, retrieval quality — exercising
code paths that synthetic tests can't reach. Edge cases surface naturally
under sustained real load. Prioritize connectors that will see daily use
over those that are architecturally interesting but rarely exercised.

### Google Account Connector

**Status:** 🔴 Not Started
**Effort:** Medium-Large
**Depends On:** Scheduler ✅, Asset System ✅ (for Drive file references)

Read-only integration with Google Workspace. OC becomes a time-aware
assistant that knows your schedule, can summarize emails, and has context
from your documents.

**Scope (read-only, no impersonation):**

- [ ] **Google Calendar** — event awareness, schedule context, reminders
- [ ] **Gmail** — email summaries, search, thread context
- [ ] **Google Drive** — file listing, document context, search

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

### Plex Media Server Connector

**Status:** 🔴 Not Started
**Effort:** Medium
**Depends On:** Scheduler ✅
**Daily use:** Yes — highest-value connector for pipeline validation

Integration with a local Plex Media Server for library awareness, watch
history tracking, and server health monitoring. Daily use makes this the
best candidate for sustained pipeline stress-testing: scheduler-driven
sync, memory-backed watch history, event-logged library changes.

**Scope:**

- [ ] **Library management** — browse, search, metadata access
- [ ] **Watch history / recommendations** — track viewed content, suggest
      unwatched items based on preferences
- [ ] **Server monitoring** — transcoding status, storage usage, health

**Technical approach:**

- [ ] Plex API via `plexapi` Python library (or direct REST)
- [ ] Plex token authentication
- [ ] Periodic library/watch-history sync via scheduler
- [ ] MCP tools: `plex_search`, `plex_recently_watched`,
      `plex_server_status` (tentative)
- [ ] Memory integration: watch history as OC memories for cross-session
      recommendations

### Personal Finance Connector

**Status:** 🔴 Not Started
**Effort:** Large
**Depends On:** Scheduler ✅
**Risk:** Medium — financial data requires careful security handling

Transaction tracking, spending categorization, bill/subscription
monitoring, and investment overview.

**Decision:** Use Plaid directly for bank aggregation, not Quicken Simplifi.
Simplifi has no public API (only an unmaintained unofficial library and
manual CSV export). Simplifi's own bank links are unreliable. Plaid is the
aggregator Simplifi uses under the hood anyway — going direct is more
reliable and gives richer data.

**Scope:**

- [ ] **Transaction aggregation** — bank accounts via Plaid, spending
      categorization, budget tracking
- [ ] **Bill / subscription tracking** — recurring charges, due dates,
      unusual amounts
- [ ] **Investment tracking** — portfolio overview, market data, basic
      performance

**Technical approach:**

- [ ] Plaid API for bank/transaction aggregation (`plaid-python`)
- [ ] Plaid Link flow for account authorization (one-time browser setup)
- [ ] Market data API (Alpha Vantage, Yahoo Finance, or similar)
- [ ] Encrypted credential storage (separate from general config)
- [ ] Periodic transaction sync via scheduler
- [ ] Spending categorization (rule-based initially, LLM-assisted later)

**Security constraints (non-negotiable):**

- All financial credentials encrypted at rest
- No financial data in event trail or general logs
- PII gate enforced on all financial content
- No write/transfer capabilities (read-only aggregation)
- Audit log for every data access

---

## Platform Infrastructure

### Private Git Server Integration

**Status:** 🔴 Not Started
**Effort:** Medium
**Depends On:** Dev Agent Runner

Self-hosted Git (Gitea/GitLab) behind network. Clone/pull in sandbox,
produce branches/patches. Manual human review gate before any upstream push.

### Performance Testing

**Status:** 🔴 Not Started

- [ ] Load testing for rate limiting / concurrency scenarios
- [ ] Performance regression testing suite
- [ ] Benchmark tracking over time

### Plugin Integration Testing

**Status:** 🟡 Partial

- [ ] Standardized plugin test harness
- [ ] Mock core for plugin unit tests
- [ ] Integration test templates

---

## Documentation Gaps

- [ ] **Plugin development entry point** — consolidate plugin docs into a
      single learning path with end-to-end tutorial
- [ ] **Docker minimal build guide** — provider-specific images, size
      optimization
- [ ] **Performance/Optimization Guide** — scaling, caching, perf tuning
- [ ] **Debugging Guide** — troubleshooting procedures, common issues
- [ ] **Security Hardening Guide** — production hardening beyond privacy gate

---

## Technical Debt

### Known Issues

| Issue                             | Location                                                    | Priority |
| --------------------------------- | ----------------------------------------------------------- | -------- |
| FTS5 rebuild on every startup     | `infrastructure/persistence/sqlite_store.py _ensure_fts5()` | Low      |
| Ollama token counts are estimates | `infrastructure/llm/ollama_adapter.py`                      | Low      |

### Code Quality Enforcement

All enforced via CI/tests:

- ✅ No tech debt marker comments (`test_no_soft_deprecation.py`)
- ✅ No secrets committed (`test_no_secrets_committed.py`)
- ✅ Strict mypy typing required
- ✅ Ruff formatting + linting required

---

## Dependency Graph

```text
COMPLETED (all ✅)
├── Scheduler ──────────────────────────────┐
├── Discord ────────────────────────────────│
├── MCP Server ─────────────────────────────│
├── HTTP API ───────────────────────────────│
├── MoE ────────────────────────────────────│
├── Capability-Aware Routing ───────────────│
├── Asset Management ───────────────────────│
├── Memory Phase 1 / 1.1 / 2 ──────────────│
└── Enterprise Tightening A/B/C ────────────┘

QUICK WINS (done)                           │
├── Goose MCP config ✅ ◄──────────────── MCP Server ✅
└── VS Code MCP config ✅ ◄────────────── MCP Server ✅

CORE INFRA GAPS (small, enable downstream)  │
├── Output Manager ◄───────────────────── (no deps)
└── Shell Execution ◄──────────────────── (no deps)

PHASE 3: Smarter Memory ✅                  │
└── Memory Embeddings ✅ ◄─────────────── (no deps)

PHASE 4: Reactive Eventing                 │
└── Webhooks ◄─────────────────────────── HTTP API ✅

PHASE 5: Agent Automation Hooks            │
└── IDE Event-Triggered Memory ◄───────── MCP Server ✅ + Memory Phase 2 ✅

PHASE 6: Media & Vision                    │
├── Media Generation ◄─────────────────── Capability Routing ✅
└── Multimodal Input ◄─────────────────── Capability Routing ✅

PHASE 7: Security & Automation (sequential chain)
├── Security Scanner ◄─────────────────── Scheduler ✅ + Output Mgr + Shell Exec
├── Dev Agent Runner ◄─────────────────── Security Scanner
└── Serena in Sandbox ◄───────────────── Dev Agent Runner

PLUGINS (all independent, no cross-deps)
├── Storytelling suite ◄───────────────── (no deps)
├── Daily journal ◄────────────────────── (no deps)
└── Future plugins ◄───────────────────── (no deps)

PERSONAL CONNECTORS (each independent)
├── Google ◄───────────────────────────── Scheduler ✅
├── Plex ◄─────────────────────────────── Scheduler ✅
└── Finance ◄──────────────────────────── Scheduler ✅

PLATFORM
├── Private Git ◄──────────────────────── Dev Agent Runner
├── Perf Testing ◄─────────────────────── (no deps)
└── Docs ◄─────────────────────────────── (no deps)
```

**Key insight:** Phases 3-6, Plugins, and Personal Connectors are all
parallelizable — they share no dependencies. The only sequential chain is
Phase 7 (Security & Automation), which depends on the Core Infrastructure
Gaps being filled first.

---

## Implementation Sequence (Recommended)

```text
 1. Quick Wins: Goose + VS Code MCP config          [Trivial] ✅
 2. Core Infra: Output Manager + Shell Execution     [Small]
 3. Phase 3: Memory Embeddings                       [Medium-Large] ✅
 4. Phase 4: Webhooks                                [Medium]
 5. Phase 5: IDE Event-Triggered Memory              [Medium]
 6. Plugins: Storytelling suite (pipeline exercise)   [Medium]
 7. Connector: Plex (daily-use pipeline validator)   [Medium]
 8. Phase 6: Media Generation + Multimodal           [Large]
 9. Phase 7: Security Scanner                        [Medium]
10. Phase 7: Dev Agent Runner                        [Large]
11. Connectors: Google, Finance                      [Large each]
12. Platform: Private Git, Perf Testing, Docs        [Medium]
```

Phases 3-6, Plugins, and daily-use Connectors can be interleaved based on
interest. The sequence above optimizes for daily impact first (memory,
webhooks, automation hooks), then pipeline validation via real workloads
(plugins, Plex connector), then new capabilities (media, security), then
expansion (remaining connectors).

---

## References

- **Architecture:** `docs/architecture/ARCHITECTURE.md`
- **Plugin Guide:** `docs/architecture/PLUGINS.md`
- **Plugin Roadmap:** `docs/plugins/plugin_backlog.md`
- **RPC Protocol:** `docs/protocol/stdio_rpc_v1.md`
- **Discord Contract:** `docs/integrations/discord_driver_contract.md`
- **MCP Server Spec:** `docs/integrations/mcp_server_spec.md`
- **Project Instructions:** `CLAUDE.md`
