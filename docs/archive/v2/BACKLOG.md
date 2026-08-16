# OpenChronicle v2 — Feature & Implementation Backlog

This document tracks planned features, implementation gaps, and future work
for OpenChronicle v2. Organized into phases based on dependencies, effort,
and value. **This is a living document** — reviewed after each phase
completion. See `docs/CODEBASE_ASSESSMENT.md` for current project status.

**Last Updated:** 2026-04-29

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
- **MCP Server** — 32 tools, stdio + SSE transports, 47 tests, optional
  `[mcp]` extra (`interfaces/mcp/`); includes `conversation_set_mode`/`get_mode`
  for storytelling/persona modes
- **HTTP API** — FastAPI, 41 REST endpoints, API key auth, rate limiting,
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

**Totals:** 1,874 tests, 32 MCP tools, 41 REST endpoints, 11 ports, 10
services, 38 use cases, 5 interfaces.

---

## Feature Taxonomy

Every feature falls into one of three categories. This determines where
code lives and what APIs it uses.

| Category | Definition | Location | API Access |
| -------- | ---------- | -------- | ---------- |
| **Core** | Stateful, needs ports/scheduler/LLM, lifecycle hooks | `application/services/`, `domain/ports/` | Full |
| **Plugin** | Behavior-modifying extension (mode prompt builder, conversation hooks) | This repo's `plugins/` | Mode dispatch, registry, event emission |
| **External MCP** | Domain integration composed via MCP | Separate repo (e.g. `plex-mcp`) | MCP tools / REST endpoints |

**Rule:** Domain integrations (Plex, banking, file indexers, security
scanners) belong as their own MCP servers, not as OC plugins. The
storytelling extension is OC's reference plugin and currently the only
one — plugins exist to alter conversational behavior in OC's pipeline,
not to import external data. The connector model was retired on
2026-04-29 along with the `OpenChronicle/plugins` repo.

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

**Status:** ✅ Implemented
**Effort:** Small
**Blocks:** Security Scanner, Dev Agent Runner, export bundles

Structured file output with timestamps and lifecycle management.

**Implemented:**

- [x] `application/services/output_manager.py` — core service
- [x] `save_report(report_type, data) → path` — timestamped JSON output
- [x] `list_outputs(report_type) → list` — enumerate outputs (newest first)
- [x] `latest_output(report_type) → path | None` — "latest" pointer
- [x] `cleanup(max_age_days) → int` — garbage collection
- [x] Config: `OC_OUTPUT_DIR` env var (wired via `RuntimePaths`)
- [x] CLI: `oc output save|list|latest|cleanup`
- [x] Path traversal validation on report_type
- [x] 14 tests

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

**Status:** ✅ Implemented
**Effort:** Medium
**Category:** Core (`application/services/webhook_service.py`)
**Depends On:** HTTP API ✅

Outbound webhook system with HMAC-SHA256 signing, background dispatcher
thread, exponential backoff retry, and fnmatch glob event filtering.

**Implemented:**

- [x] `WebhookSubscription` + `DeliveryAttempt` domain models
- [x] `WebhookStorePort` ABC with full CRUD + delivery tracking
- [x] `webhooks` + `webhook_deliveries` tables (FK CASCADE, 4 indexes)
- [x] `WebhookService` — subscription CRUD, HMAC signing, httpx delivery
- [x] `WebhookDispatcher` — background daemon thread, `queue.Queue`,
      exponential backoff retry (3 attempts, 10s/30s/90s + jitter)
- [x] Composite `emit_event` pattern (event_logger + dispatcher, zero
      existing call-site changes)
- [x] `webhook.*` event recursion prevention
- [x] 3 use cases: `register_webhook`, `list_webhooks`, `delete_webhook`
- [x] 5 REST endpoints: POST/GET/GET/{id}/DELETE/{id}/GET/{id}/deliveries
- [x] 3 MCP tools: `webhook_register`, `webhook_list`, `webhook_delete`
- [x] 4 CLI commands: `oc webhook register|list|delete|deliveries`
- [x] Events: `webhook.registered`, `webhook.deleted`
- [x] 74 new tests, 1365 total

---

## Phase 5 — Agent Automation Hooks

**Goal:** Frictionless memory flow — IDE events automatically trigger OC
memory operations without manual tool invocation.

### IDE Event-Triggered Memory

**Status:** 🟡 Prototype (Claude Code hooks only)
**Effort:** Medium
**Category:** External (config + hooks, minimal OC-side changes)
**Depends On:** MCP Server ✅, Memory Phase 2 ✅

**Prototype already shipped** for Claude Code: `PreCompact` hook injects OC
context memories before context compression, `SessionStart(compact)` hook
reloads after compression, `--full` flag on `oc memory search` for
machine-readable injection. Hooks live in `.claude/hooks/` (gitignored
since they're per-developer config). Goose and VS Code coverage still open.

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

**Status:** 🟡 V0 Complete (stub + Ollama adapters, video in contract)
**Effort:** Medium-Large
**Category:** Core (new port + adapters)
**Depends On:** Capability-Aware Routing ✅

New port for image/video generation. Different input/output types from text
completion, different routing needs, different cost model.

**Why core:** Needs its own port (`MediaGenerationPort`), adapters, routing,
and asset integration. The plugin API provides no LLM or asset access.

**Requirements:**

- [x] `MediaGenerationPort` ABC (`generate`, `supported_media_types`)
- [x] `MediaRequest` / `MediaResult` domain models (video fields included)
- [x] Stub adapter for testing (deterministic PNG from prompt hash)
- [x] Ollama media adapter (flux, sdxl, stable-diffusion via `/api/generate`)
- [ ] OpenAI media adapter (DALL-E) — deferred
- [x] `generate_media` use case (orchestrates port + asset storage + dedup)
- [x] CLI: `oc media generate`
- [x] MCP tool: `media_generate`
- [x] API route: `POST /api/v1/media/generate`
- [x] `MediaSettings` + `load_media_settings()` (three-layer precedence)
- [x] Container wiring (`_build_media_port`, graceful degradation)
- [x] 39 tests

**Remaining:**

- [ ] OpenAI adapter (DALL-E) — add when needed
- [ ] Ollama adapter API validation — Ollama's image generation API is
  experimental; adapter uses fallback extraction (images array, image
  field, base64 response). Needs testing against real Ollama diffusion
  models to confirm response format and tighten the adapter.
- [ ] `oc ollama scan` — CLI command to scan a local Ollama instance,
  discover installed models and capabilities, and auto-generate model
  config JSON files. Also serves as a concrete reference for how each
  model's API actually behaves (response format, supported params),
  informing adapter implementations.
- [ ] Capability-aware routing integration — wire `media_type` into
  `required_capabilities` for automatic model selection

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

## Phase 7 — Security Scanning

**Goal:** Periodic security scanning of OC's own repo (and any other repo
the user wires up). Reclassified to external MCP under the new architecture.

### Security Scanner

**Status:** 🔴 Not Started (Concept)
**Effort:** Medium
**Category:** External MCP candidate (separate `security-scan-mcp` repo if
pursued), or compose existing scanners directly via shell.
**Depends On:** Output Manager ✅, Shell Execution (still core, see above)

**Reclassified from core to external MCP** (2026-04-29). Same pattern as
`plex-mcp` — domain-specific glue (gitleaks, osv-scanner, trivy, semgrep)
that doesn't need to live inside OC. An external MCP can expose tools like
`scan_repo_secrets`, `scan_dependencies`, `scan_container` and OC composes
them when needed.

**Requirements (if built):**

- [ ] Integrate existing scanners (not inventing new ones): gitleaks,
      osv-scanner, trivy, semgrep
- [ ] Periodic scans via OS cron (or whatever scheduler the user prefers
      outside OC) — OC's scheduler isn't load-bearing here
- [ ] Reports stored via OC's Output Manager (or written locally and
      indexed via memory tools)
- [ ] Events surfaced via webhook subscription if the user wants alerts

**Note:** Decision #4 originally pulled this from plugin to core because
the plugin API couldn't reach scheduler/shell/output. Under the post-2026-04-29
taxonomy, neither plugin nor core is the right home — external MCP is.
Sandboxed agent execution (Dev Agent Runner, Serena-in-sandbox, private
git server integration) was dropped from this backlog: it's a different
product (sandboxed agent platform) and Claude Code/Goose already cover
that ground for the user's actual workflow.

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

### Storytelling Plugin

**Status:** ✅ Phases 1–7 Complete (text-only persona extraction; multimodal deferred)
**Effort:** Medium-Large
**Location:** `plugins/storytelling/` (this repo)
**Reference:** `archive/openchronicle.v1` branch

V1 was a comprehensive narrative AI engine. V2 stripped to domain-agnostic
core. The v1 features all live in this single plugin under
`plugins/storytelling/`, registered via the `ModePromptBuilder` protocol.

**Completed phases:**

- [x] **Phase 1: Import pipeline** — text file parsing, content classification
  (character, location, style-guide, instructions, worldbuilding), memory
  storage with structured tags, asset upload for images
- [x] **Phase 2: Scene generation** — context assembly from project memory
  (tag-filtered search), engagement modes (participant/director/audience),
  canon/sandbox, system prompt construction, LLM completion, scene persistence
- [x] **Phase 3: Conversation mode** — `ModePromptBuilder` protocol in core
  `PluginRegistry`, `prepare_ask()` delegates system prompt to active mode's
  builder, story builder assembles characters/style guides/locations/worldbuilding
  from memory, CLI convenience commands (`oc story characters|locations|search`)
- [x] **Phase 4: Game mechanics** — dice engine, resolution rules, character
  stats, narrative branching
- [x] **Phase 5: Bookmark & timeline** — scene bookmarking, auto-bookmark on
  scene save, timeline navigation
- [x] **Phase 6: Narrative engines** — LLM-based consistency checking,
  emotional arc analysis
- [x] **Phase 7: Persona extractor (text-only)** — domain models, LLM
  extraction, memory persistence

**CLI commands:** `oc story import|list|show|scene|characters|locations|search`
plus 11 additional handlers from Phases 4–7.
**Tests:** 303 across the plugin (95 from Phases 1–3 plus 208 from Phases 4–7).

**Remaining:**

- [ ] **Persona extractor — multimodal** — audio/video transcription input
  (Whisper or equivalent), behavioral analysis on transcripts. See dedicated
  section below for the long-running ingestion design.

**Data value:** Storytelling plugin generates rich, structured events
(character interactions, scene transitions, narrative decisions) that
exercise the event pipeline with diverse, non-trivial payloads. This data
is valuable for testing memory retrieval quality and event replay.

**Storage note:** Character state and scene persistence use the OC memory
system via tag-filtered search. The `ModePromptBuilder` protocol allows
the plugin to assemble custom system prompts from memory without core changes.

### Persona Extractor — Multimodal Phase

**Status:** 🟡 Text-only complete; multimodal deferred
**Effort:** Large (multimodal portion)
**Category:** Plugin (lives inside `plugins/storytelling/`)
**Depends On:** Multimodal Input (Phase 6)

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

**Downstream evolution: custom LLM personalities.** A rich enough persona
model is also a fine-tuning dataset. The same behavioral extraction that
builds a system-prompt-driven character template also produces the
training examples needed for LoRA adapters or full fine-tunes — an
actual "character model" rather than a prompted approximation. This is
downstream of downstream (extraction → persona schema → fine-tuning
pipeline), but it has architectural implications for *upstream* design
decisions made now:

- **Persona schema must be rich enough to drive fine-tuning later.**
  Speech patterns, decision heuristics, emotional response profiles,
  and conversational examples should be first-class fields, not
  collapsed into a single "description" blob. If the schema is
  expressive enough for fine-tuning, it's automatically expressive
  enough for system-prompt use.
- **Extraction should preserve raw examples alongside synthesized
  traits.** A trait summary ("Jester deflects with humor under stress")
  is useful for prompting; the source exchanges that evidence it are
  useful for few-shot examples and fine-tuning datasets. Store both.
- **Character management plugin's storage model should anticipate
  versioned, evolving personas.** As extraction refines a persona over
  time (progressive confidence), earlier versions are still valuable —
  they represent the fine-tuning curriculum (rough → refined).

None of this changes the implementation plan for the extractor itself.
It's a design constraint on the persona schema and character storage
that should be kept in mind during storytelling plugin design so we
don't have to re-extract later.

### Where Stateless Data Generators Live Now

Under the old taxonomy, ideas like daily journals, code snippet analyzers,
and habit trackers were proposed as plugins because they were stateless
input→output handlers. Under the new taxonomy (plugins are
behavior-modifying extensions only), these are not plugins. The right
shape for any of them is an **external MCP server** (separate repo, like
`plex-mcp`) that calls OC's memory tools. None are currently planned —
captured here only to document the redirect.

**Evaluation criteria for adding a new plugin in this repo:**

1. Does it modify OC's conversational behavior (mode prompt builder,
   conversation hook)?
2. Does it need to participate in the conversation pipeline directly?

If the answer to both is no, it belongs as an external MCP server, not
as a plugin.

---

## Personal Life Integrations (External MCP Servers)

Domain integrations live in their own MCP server repos and are composed
by the client (Claude Code, Goose, Open WebUI tool loop, etc.) alongside
OC. OC contributes persistent memory; the integration MCP contributes
domain data. They don't share a process.

| Integration | Where | Status |
| ----------- | ----- | ------ |
| Plex Media Server | [`CarlDog/plex-mcp`](https://github.com/CarlDog/plex-mcp) | Active |
| Servarr (Sonarr/Radarr) | [`CarlDog/servarr-mcp`](https://github.com/CarlDog/servarr-mcp) | Active |
| Downloader (qBittorrent) | [`CarlDog/downloader-mcp`](https://github.com/CarlDog/downloader-mcp) | Active |
| Portainer | [`CarlDog/portainer-mcp`](https://github.com/CarlDog/portainer-mcp) | Active |
| Google Workspace (Gmail/Calendar/Drive) | claude.ai built-in MCPs | Available out of the box |
| Personal finance (Plaid) | Not started — would be a new external MCP repo if pursued | Concept |

These don't appear elsewhere in this backlog. Cross-repo issue tracking
is the responsibility of each integration's own repo. OC's job is to
provide reliable memory + storytelling primitives that integration MCPs
compose with.

---

## Platform Infrastructure

### Performance Testing

**Status:** 🟡 Partial

- [x] Concurrency stress tests at the core level
      (`tests/integration/test_stress.py`) — hash chain integrity, turn
      index uniqueness, lost-update prevention, write lock starvation,
      scheduler atomic claim
- [ ] Load testing for rate limiting / concurrency scenarios
- [ ] Performance regression testing suite
- [ ] Benchmark tracking over time

Note: a 12-scenario OpenAI-compat API stress suite was removed alongside
`openai_compat.py` on 2026-04-29. Coverage of MCP/HTTP API concurrency
under direct-protocol traffic would be a separate follow-up.

### Plugin Integration Testing

**Status:** 🟡 Partial — applies only to behavior-modifying plugins in this repo's `plugins/`

The connector resilience criterion (rate-limit handling, retry behavior,
external I/O) no longer applies here — those tests belong in each
external MCP server's own repo. What's left is testing for plugins that
register mode prompt builders or conversation hooks.

- [ ] **Mode prompt builder tests** — given a project memory state, the
      builder produces the expected system prompt
- [ ] **Registration smoke** — plugin loads cleanly, registers its
      `ModePromptBuilder` and any handlers, emits expected events on
      first use
- [ ] **Mode dispatch end-to-end** — `conversation_set_mode` → `conversation_ask`
      uses the registered builder

(Storytelling already has 303 tests covering most of this for itself;
the open work is documenting the standard so future plugins follow it.)

---

## Memory Tooling

### Memory Validation Command (`oc memory validate`)

**Status:** 🔴 Not Started
**Effort:** Medium
**Category:** Core (CLI + use case)
**Depends On:** Memory System ✅

Validate stored memories against actual system state. Memories created
by AI agents (or humans) may contain claims about features, architecture,
or capabilities that drift from reality over time. This command would
cross-reference memory content against provable system artifacts.

**Validation sources:**

- CLI command registration (argparse subparsers) — verify claimed commands exist
- MCP tool registry — verify claimed tool counts and names
- Model config files — verify claimed provider/model support
- Test suite (`pytest --collect-only`) — verify claimed test counts
- Installed adapters — verify claimed adapter availability
- Conversation logs — verify claims against recorded interactions
- Plugin registry — verify claimed plugin capabilities

**Requirements:**

- [ ] `oc memory validate` CLI command
- [ ] Scoring model: each memory gets a confidence/validity score
- [ ] Report: validated claims, unverifiable claims, contradicted claims
- [ ] Optional `--fix` flag to update or flag stale memories
- [ ] MCP tool: `memory_validate`

**Design questions (open):**

- How to extract testable assertions from free-text memories?
- Should validation be LLM-assisted (parse claims) or rule-based (pattern match)?
- What's the right granularity — per-memory or per-claim?

---

## Memory Retrieval Improvements

### Recency-Aware Memory Retrieval

**Status:** 🔴 Not Started
**Effort:** Medium
**Category:** Core (EmbeddingService + search pipeline)
**Discovered:** 2026-03-11 — Open WebUI testing revealed stale results

Memory retrieval is purely relevance-based (keyword + semantic via RRF).
When users ask about "recent" or "latest" entries, the system returns
whatever matches the query terms best, regardless of age. A Plex entry
from March 3 ranks the same as one from today if the content similarity
is equal.

**Root causes identified:**

1. **No recency factor in RRF scoring.** The hybrid search combines
   keyword rank + semantic rank but has no time-decay component.
2. **Pinned memories crowd out search results.** With `top_k_memory=8`
   and 7+ pinned memories, zero slots remain for actual query-relevant
   results. Pinned items consume the entire budget.
3. **No temporal query detection.** Words like "recent", "latest",
   "today" are treated as search terms, not time filters.

**Proposed investigation areas:**

- Recency boost factor in RRF (time-decay weighting)
- Separate budgets for pinned vs searched memories (e.g., pinned don't
  count against `top_k`)
- Temporal keyword detection and time-window pre-filtering
- Configurable `top_k` per conversation mode (webui mode may need higher)
- Research: how do RAG systems handle recency? (hybrid time+relevance
  scoring, time-bucketed retrieval, etc.)

### Memory Injection Lacks Framing Instructions

**Status:** 🔴 Not Started
**Effort:** Small
**Category:** Core (context_builder.py)
**Discovered:** 2026-03-10

`format_memory_messages()` injects memories as raw content with no
behavioral instructions. The LLM treats injected memories as conversation
topics rather than background context — proactively summarizing Docker
workflow, Plex onboarding advice, and development decisions even when the
user just says "hi there."

**Symptoms observed:**

- User says "hi there" → LLM responds with unsolicited summaries of
  Docker setup, Plex plugin friction, and project decisions
- LLM repeatedly regurgitates the same Plex onboarding advice across
  multiple turns even after user says they've addressed it
- Memories intended as operational context are treated as active topics

**Fix:**

- Add a preamble to the memory system message: "The following are stored
  memories for reference. Use them to answer questions when relevant.
  Do not volunteer this information unprompted or treat it as the current
  conversation topic."
- Consider: separate "operational memories" (sync state, config) from
  "conversational memories" (user preferences, decisions) with different
  framing

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

## What's Left (Open Items Only)

```text
CORE INFRA GAPS                            │
└── Shell Execution ◄──────────────────── (no deps; needed if Sec Scanner is built in OC)

PHASE 5: Agent Automation Hooks            │
├── Claude Code hooks ✅ (prototype shipped)
├── Goose hook coverage ◄──────────────── MCP Server ✅
└── VS Code hook coverage ◄────────────── MCP Server ✅

PHASE 6: Media & Vision                    │
├── Media Generation polish ◄──────────── DALL-E adapter, capability routing wiring
└── Multimodal Input ◄─────────────────── Capability Routing ✅

PHASE 7: Security Scanning                 │
└── Security Scanner ◄─────────────────── External MCP candidate; Output Manager ✅

PLUGINS                                    │
└── Storytelling — Persona Multimodal ◄── Multimodal Input

MEMORY                                     │
├── Recency-aware retrieval ◄──────────── Memory Phase 3 ✅
├── Memory injection framing ◄─────────── (no deps)
└── Memory Validation Command ◄────────── Memory System ✅

PLATFORM                                   │
├── Perf Testing (post-openai_compat) ◄── (no deps)
├── Plugin Integration Test standard ◄── (no deps)
└── Docs ◄─────────────────────────────── (no deps)

EXTERNAL MCP REPOS (each owns its own backlog)
├── plex-mcp, servarr-mcp, downloader-mcp, portainer-mcp (active)
└── security-scan-mcp, plaid-mcp (concept only)
```

**Key insight:** All remaining items are parallelizable — no sequential
chain. Phase 7 sandboxed-agent items (Dev Agent Runner, Serena Sandbox,
Private Git Server) were dropped on 2026-04-29 as out-of-scope.

---

## Implementation Sequence (Recommended)

```text
1. Memory injection framing fix              [Small]    — daily impact, no deps
2. Recency-aware memory retrieval            [Medium]   — daily impact, fixes real bug
3. Memory Validation Command                 [Medium]   — useful, contained
4. Storytelling persona multimodal           [Large]    — needs Multimodal Input first
5. Multimodal Input (Phase 6)                [Medium]   — unlocks (4)
6. Goose / VS Code IDE hooks                 [Medium]   — extend Claude Code prototype
7. Plugin integration testing standard       [Small]    — doc + harness for future plugins
8. Performance testing post-openai_compat    [Medium]   — replace dropped suite
9. Documentation gaps                        [Medium]   — debugging, security hardening
```

Optimizes for daily memory impact first, then unblocks the storytelling
multimodal path, then extends IDE hooks. Security Scanner deliberately
left off the in-repo sequence — if built, it's a separate
`security-scan-mcp` repo.

---

## Story WebUI — Visual Storytelling Frontend

**Status:** 🔴 Not Started (Concept)
**Effort:** Large
**Depends On:** Storytelling Plugin ✅, Media Generation ✅, HTTP API ✅,
Asset System ✅
**Category:** Frontend (new codebase, separate repo)

A purpose-built web frontend for interactive storytelling that provides a
visual storybook experience alongside the narrative chat. Talks directly
to OC's HTTP API — no Open WebUI in the data path.

### Architecture

```text
┌───────────────────────────────────────────────┐
│           Story WebUI (custom app)            │
│  ┌──────────────┐  ┌──────────────────────┐   │
│  │  Chat Panel  │  │  Visual Panel        │   │
│  │  (player/    │  │  (generated art,     │   │
│  │   director)  │  │   scene cards,       │   │
│  │              │  │   timeline, maps)    │   │
│  └──────┬───────┘  └────────┬─────────────┘   │
│  ┌──────┴──────────────────┴──────────────┐   │
│  │  Reader Mode (storybook layout)        │   │
│  │  (full-width narrative + inline art)   │   │
│  └────────────────────────────────────────┘   │
└─────────┬─────────────────────────────────────┘
          │ OC HTTP API
          │ (POST /api/v1/conversation/{id}/ask,
          │  POST /api/v1/conversation/{id}/mode,
          │  POST /api/v1/media/generate,
          │  GET  /api/v1/asset/{id}, …)
    ┌─────┴──────┐
    │  OC Core   │ ← memory, routing, storytelling
    │  (API)     │   plugin (story mode prompt
    └────────────┘   builder), asset storage,
                     media generation
```

### Mode Mapping

The storytelling plugin's three engagement modes map to different UI
experiences:

- **Player (PARTICIPANT)** — chat-driven, real-time. User plays a
  character. Chat panel is primary; visual panel shows generated scene
  art, character portraits, location images alongside the narrative.
  Interactive — user types actions/dialogue, LLM responds with story
  continuation + media triggers.
- **Director** — chat-driven, real-time. AI performs all characters;
  user directs the narrative. Same UI layout as Player but with
  director-mode prompting. User gives stage directions rather than
  character actions.
- **Reader (AUDIENCE)** — consumption/presentation. Full-width
  storybook layout. Renders completed scenes with inline generated
  art. No chat interaction — this is the polished "read the story"
  view. Same data, different render.

### Key Components

1. **Custom Story WebUI (single component)** — purpose-built frontend that:
   - Sets `mode=story` on a conversation via `POST /api/v1/conversation/{id}/mode`
     so OC's storytelling plugin's mode prompt builder fires automatically
   - Sends user turns via `POST /api/v1/conversation/{id}/ask`
   - Triggers image generation via `POST /api/v1/media/generate` after
     scene resolution (or as part of a custom client-side trigger
     keyed off scene markers in the response)
   - Pulls assets via `GET /api/v1/asset/{id}` for the visual panel
   - Manages storylines (create, select, configure, per-story theming)
   - Renders chat + visual panel side-by-side for player/director modes
   - Renders storybook layout for reader mode
   - Applies per-storyline CSS/theming (dark gothic horror vs whimsical
     fantasy vs sci-fi etc.)

That's it. There's no middleware tier — the previous design's "Open WebUI
Pipeline Plugin" intercepting completions and triggering media generation
went away when the OpenAI-compat layer was dropped on 2026-04-29. Any
"intercept story-mode response → trigger media gen" logic now lives in
the custom UI directly (which has full visibility into what was just said
and full freedom to call `media_generate` whenever it wants).

### Design Decisions to Make

- **Media generation latency.** Image generation takes seconds. Text
  should stream back immediately with a placeholder; art appears
  asynchronously once generated. Note: OC's HTTP API doesn't yet stream
  `conversation_ask` — non-streaming response only. If progressive text
  rendering matters, a streaming variant of `/conversation/{id}/ask` is
  a prerequisite (small core change, would need its own backlog item).
- **Scene boundary detection.** How does the UI know "a scene just
  finished, time to render an image"? Options: structured markers in
  the LLM response (e.g., `<scene-end/>` tag the storytelling builder
  instructs the model to emit), explicit user-driven "render this"
  button, or scheduled scene rendering after N turns.
- **Storyline state.** Storylines map to OC `project_id` (per-storyline
  isolation of memory) and one `conversation_id` per active session.
  UI's "switch storyline" = switch project.
- **Tech stack for custom UI.** TBD — could be React/Next.js, Svelte,
  or a lightweight framework given OC's API does the heavy lifting.
  Choose based on theming/skinning requirements.

### Prerequisite that may need OC-side work

- [ ] **Streaming `/conversation/{id}/ask`** — currently non-streaming
      only. For real-time chat UX, add SSE or chunked-transfer streaming
      response. Small core change.
- [ ] **Scene boundary signal** — either a story-mode prompt convention
      ("emit `<scene-end/>` at scene transitions") or a separate
      `scene_complete` event the storytelling plugin emits that the UI
      can subscribe to via webhook.

---

## References

- **Architecture:** `docs/architecture/ARCHITECTURE.md`
- **Plugin Guide:** `docs/architecture/PLUGINS.md`
- **Plugin Roadmap:** `docs/plugins/plugin_backlog.md`
- **RPC Protocol:** `docs/protocol/stdio_rpc_v1.md`
- **Discord Contract:** `docs/integrations/discord_driver_contract.md`
- **MCP Server Spec:** `docs/integrations/mcp_server_spec.md`
- **Project Instructions:** `CLAUDE.md`
