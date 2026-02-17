# OpenChronicle v2 — Senior Developer Codebase Assessment

**Date:** 2026-02-16
**Branch:** `refactor/new-core-from-scratch`
**Revision:** 16 (Discord interface — driving adapter)

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
Tests are strong (680+ unit/functional, 13 real-world integration, 6 concurrency
stress), architecture is enforced, and the STDIO RPC daemon mode exists. Integration
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
`busy_timeout` expires. Connection setup uses `autocommit=True` to bypass
Python's legacy `isolation_level` transaction handling, which silently undermined
explicit `BEGIN IMMEDIATE` in multi-threaded scenarios.

Six operational CLI utilities were added to close day-one gaps: `oc version`,
`oc db info|vacuum|backup|stats`, `oc config show`, `oc show-project`,
`oc events`, and `oc convo delete` + `oc memory delete`. These required two
domain port additions (`delete_conversation`, `delete_memory`) with cascade
logic in SqliteStore. CLI command reference documented in `docs/cli/commands.md`.

**What's next:** Discord driver done. Next: security scanner plugin or dev agent runner.

**Overall: Core feature-complete, Discord interface operational, concurrency-safe for multi-process deployment.**

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
|-----------|--------|----------|
| **5 LLM providers** (OpenAI, Anthropic, Groq, Gemini, Ollama) | Working | Async-native adapters, contract tests |
| **Provider routing** (pools, fallback, NSFW, budget-aware) | Working | 1,278-line test suite |
| **SQLite persistence** (11 tables, 58 methods, WAL mode) | Working | Handles tasks, conversations, memory, events, scheduled jobs, delete + cascade operations |
| **Hash-chained events** (SHA256, prev_hash → hash) | Working | Verification + replay services |
| **Privacy gate** (6 PII categories, Luhn validation) | Working | Rule-based, provider-aware |
| **Interaction routing** (rule + hybrid ML assist) | Working | NSFW scoring, mode detection |
| **Memory v0** (keyword search, pinned, tagged) | Working | Deterministic retrieval, no embeddings |
| **Budget/rate limiting** | Working | Token limits, call limits, rate gates |
| **Plugin system** (discover, load, register, invoke) | Working | 2 example plugins, collision detection |
| **Scheduler** (tick-driven, atomic claim, drift prevention) | Working | Core service, 6 CLI + 6 RPC commands, 52+ tests |
| **STDIO RPC** (24 commands, serve + oneshot) | Working | Request dedup, telemetry, error codes |
| **CLI** (76+ subcommands) | Working | Project/task/convo/memory/diagnostics/db maintenance/config/version/events/delete/scheduler |
| **File-based configuration** (single `core.json`, three-layer precedence) | Working | `config/core.json` + enriched `models/*.json` (limits, capabilities, cost, performance) + per-plugin JSON + env var overrides |
| **Config-driven wiring** (JSON model configs, env vars) | Working | Per-(provider, model) resolution |
| **Time context** (current time, last interaction, seconds delta) | Working | Injected in `prepare_ask()`, raw ISO + integer data, 5 tests |
| **Discord interface** (bot, slash commands, session, formatting) | Working | `commands.Bot` subclass, 6 slash commands, session mapping, message splitting, 60 tests |
| **Test suite** (740+ unit/functional, 13 real-world integration, 6 concurrency stress) | Passing | 13 test categories + Discord, architecture guards, live provider validation, concurrency race proofs, auto-detecting conftest |

### Architecture (Enforced and Clean)

```text
interfaces/ (CLI, RPC, Discord, API stub)
    ↓ calls
application/ (use cases, orchestrator, policies, routing)
    ↓ depends on
domain/ (models, ports, services)
    ↑ implements
infrastructure/ (LLM adapters, SQLite, privacy, router assist)
```

Enforced by: `test_hexagonal_boundaries.py`, `test_core_agnosticism.py`,
`test_policies_purity.py`. Domain has zero infrastructure imports. Application has
zero SDK imports. This is genuinely enforced, not aspirational.

---

## Core Gaps (All Resolved)

The following gaps were identified at the start of the v2 rebuild and have all
been closed. Kept here for architectural context — see Definition of Done and
Refactoring Priorities sections for implementation details.

| # | Gap | Resolution |
|---|-----|------------|
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
|---|-------|-----|--------|
| 1 | **Hash chain fork** — `EventLogger.append()` read-compute-write race | Wrapped in `BEGIN IMMEDIATE` transaction + timestamp refresh under lock | **Fixed** |
| 2 | **Duplicate turn index** — `next_turn_index()` reads MAX in deferred BEGIN | `BEGIN IMMEDIATE` serializes all write transactions | **Fixed** |
| 3 | **Lost memory link** — `link_memory_to_turn()` JSON read-modify-write race | Wrapped in `BEGIN IMMEDIATE` transaction | **Fixed** |
| 4 | **Write lock starvation** — long transaction blocks all writers | Short transactions + application-level retry with exponential backoff in `transaction()` | **Fixed** |

Additional fixes applied during implementation:

- **`autocommit=True`** on connection setup — Python's legacy `isolation_level`
  handling silently undermined explicit `BEGIN IMMEDIATE` in multi-threaded
  scenarios. Explicit `COMMIT`/`ROLLBACK` via `execute()` instead of
  `conn.commit()`/`conn.rollback()`.
- **Timestamp refresh under lock** — events constructed before lock acquisition
  had `created_at` timestamps that didn't match serialization order, causing
  `ORDER BY created_at` to return stale `prev_hash` values.

**Multi-process safe.** Scheduler plugin, Discord driver, and concurrent
processes can now share the database.

---

## Definition of Done: Core v2

"Core done" means: a fully operational daemon that you can interact with like a
chatbot via CLI, with durable memory, explainable routing, and a stable plugin
surface. No backwards compatibility concerns. No production deployment yet.

### Must Have (Blocking for "Core Done")

| # | Item | Status | Why It's Blocking |
|---|------|--------|-------------------|
| 1 | **Interactive chat REPL** (`oc chat`) | Done (e368db4) | Can't "interact like a chatbot" without it |
| 2 | **Streaming responses** (LLMPort + adapters + CLI, with `--no-stream` toggle) | Done (6416c76) | Chatbot UX with 10s wait for response is broken |
| 3 | **Interface layer refactoring** (God Functions → dispatch tables) | Done (e368db4) | Untestable interface layer is a stability risk |
| 4 | **Conversation UX shortcuts** (auto-create, resume latest, etc.) | Done (a946e7c) | UUID juggling prevents casual use |

### Should Have (Quality, Not Functionality)

| # | Item | Status | Impact |
|---|------|--------|--------|
| 5 | **Decompose `ask_conversation.execute()`** | Done | Testability, readability |
| 6 | **Decompose orchestrator manager/worker methods** | Done | Phase-separated into 6 private helpers + dataclass |
| 7 | **SqliteStore row mapper extraction** | Done | Cognitive load reduction |

### Defer to Plugin Phase

| Item | Reason |
|------|--------|
| HTTP API | CLI + RPC cover the chatbot use case |
| ONNX router assist | Linear model works; ONNX is a performance optimization |
| Embeddings / vector memory search | Keyword search works for v0; embeddings are a plugin concern |
| Docker hardening | Not needed until deployment |
| Scheduler plugin | First plugin after core done |
| Discord driver | Needs scheduler first |

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
- **`v1.reference/` directory** — Keep as design reference and plugin feature roadmap

---

## Subsystem Detail

### Use Case Layer (27 files, ~2,924 lines)

The use case layer has a healthy distribution: 16 thin wrappers (~328 lines total)
that forward to ports, and 8 complex orchestration files (~2,393 lines) with real
business logic. This is correct architecture — not everything needs to be complex.

**Heavyweights:**

| File | Lines | Complexity |
|------|-------|------------|
| `ask_conversation.py` | 758 | Full conversation turn orchestration |
| `smoke_live.py` | 360 | End-to-end provider testing |
| `task_once.py` | 333 | Task execution with error handling |
| `selftest_run.py` | 330 | Comprehensive workflow testing |
| `replay_project.py` | 283 | Event replay engine |
| `diagnose_runtime.py` | 283 | Runtime diagnostics |
| `explain_turn.py` | 267 | Turn analysis via event correlation |
| `resume_project.py` | 160 | Orphaned task recovery |

**Concern:** The boundary between "what belongs in a use case" vs "what belongs in
the orchestrator" is unclear. `run_task.py` is 28 lines (pure forwarding) while
`ask_conversation.py` is 758 lines (full orchestration). The orchestrator also owns
built-in handler logic that could be use cases.

### Domain Layer (13 models, 8 ports, 3 services)

Clean and well-typed. Key models:

- **`Project`, `Agent`, `Task`, `Event`** — Core execution entities with hash chains
- **`Conversation`, `Turn`** — Chat interaction history with full metadata per turn
- **`MemoryItem`** — Persistent knowledge with tags, pinning, conversation/project scope
- **`BudgetPolicy`, `TaskRetryPolicy`** — Policy-as-data pattern
- **`InteractionHint`, `RouterAssistResult`** — Routing decision outputs

Ports define clean contracts: `StoragePort` (34+ methods), `ConversationStorePort`
(12 methods, including cascade delete), `MemoryStorePort` (7 methods, including
delete with turn reference cleanup), `LLMPort` (2 methods), plus single-method
ports for routing, privacy, and plugin hosting.

**Concern:** `StoragePort` at 28+ abstract methods is doing too much. The task tree
navigation methods feel like read-model concerns that could be a separate port.

### Infrastructure Layer

**Complete:** SQLite persistence (10 tables, crash recovery, transactions), privacy
gate (6 PII categories), rule routing (NSFW + mode detection), hybrid routing
(rule + ML), linear router assist (logistic regression), event logger (hash chains),
file-based configuration (single `core.json` with three-layer precedence:
dataclass defaults → JSON file → env var override; enriched model configs with
limits, capabilities, cost tracking, and performance metadata; per-plugin JSON config).

**Stub only:** ONNX router assist (intentional placeholder).

### Test Suite (118 files, 670+ unit/functional + 13 real-world integration + 6 concurrency stress)

Well-organized into 12 categories: business logic (23), CLI/RPC (23), hygiene (10),
infrastructure (11), contract (8), policy (5), memory (5), architecture guard (4),
advanced (5), data format (4), plugin (2), integration (3 + conftest).

**Real-world integration** (`test_real_world.py`): 13 scenarios exercising the
full stack against live LLM providers — single/multi-turn, memory save/recall,
pinned memory, hash chain verification, token tracking, event chain completeness,
privacy gate PII detection, conversation resume, export with verify/explain,
streaming vs non-streaming, and conversation mode. Validated against OpenAI
(gpt-4o-mini) and Anthropic (Claude Sonnet 4). Manual checklist covers
interactive features (streaming visual, chat resume, quit, diagnose).

**Integration test auto-detection** (`tests/integration/conftest.py`): Session-scoped
conftest auto-detects the application's config directory (well-known deployment paths
with `models/*.json`, e.g. `C:\Docker\openchronicle\config`), LLM provider (from env
vars or model config scan), and credentials (embedded in model config JSON files).
Only `OC_INTEGRATION_TESTS=1` is needed to run — no manual `OC_CONFIG_DIR` or
`OC_LLM_PROVIDER` setup. Explicit env vars always take precedence. Smoke tests
(`test_smoke_live.py`) adapted to handle config-embedded credentials (skip
credential-removal tests when keys aren't in env vars).

**Concurrency stress tests** (`test_stress.py`): 5 threading-based tests using
separate `SqliteStore` connections to the same database file (simulating
multi-process access). Each thread gets its own `sqlite3.Connection` with
independent locks and WAL snapshots. Results:

| Test | Target | Outcome |
|------|--------|---------|
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
|------------|-----------|-------|
| 13+ orchestrators | 1 orchestrator + use cases | Intentional simplification |
| 15+ LLM providers | 5 providers (async-native) | OpenAI, Anthropic, Groq, Gemini, Ollama |
| Character AI | Not ported | Plugin territory |
| Timeline rollback | Hash-chained events | Cryptographic > database integrity |
| Multi-tier memory (Redis + SQLite) | Single-tier SQLite | Simpler, may need tiers later |
| Content analysis (two-tier LLM) | Router assist (linear/ONNX) | Lighter weight |
| Scene management, narrative engines | Not ported | Plugin territory |
| Image generation | Not ported | Plugin territory |
| Plugin: full domain/app/infra per plugin | Plugin: handler + register() | Intentionally simpler |
| Web UI templates | Not ported | HTTP API deferred |
| CLI commands only | CLI + STDIO RPC daemon | Headless operation enabled |
| Database integrity | Cryptographic integrity | Hash-chained events are the upgrade |

**The v2 strategy is correct:** Build a hardcore core with clean boundaries, then
re-implement v1 features as plugins. The `v1.reference/` directory is both
historical context and a feature roadmap for the plugin phase.

---

## Post-Core Roadmap

A plugin-readiness audit (2026-02-13) identified that the plugin system works for
stateless task handlers but cannot support stateful, long-running, or
service-dependent features. See Decision #4 below for the architectural response.

```text
Core Done
  ✓ LLMPort: function calling / tool use (done)
  ✓ Scheduler (core — application/services)
  ✓ Discord Driver (core — interfaces/)
  → Security Scanner (plugin — stateless handler)
  → Dev Agent Runner (core — needs LLM + sandbox)
  → Serena MCP (core — inside sandbox only)
  → MoE Mode (plugin — stateless handler)
  → HTTP API (core — interfaces/)
  → VS Code / Copilot SDK (external client via RPC)
  → Goose Integration (external client via RPC)
  → Private Git Server (plugin or external)
```

**Taxonomy:** Features that need persistent state, lifecycle hooks, or direct
service access are core features (in `application/` or `interfaces/`). Stateless
input→output handlers remain plugins. External clients compose via STDIO RPC.

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
|------------------|-------------|----------|
| Persistent state, lifecycle, service access | Core (`application/` or `interfaces/`) | Scheduler, Discord, HTTP API, Dev Agent Runner |
| Stateless input→output processing | Plugin (`plugins/`) | Story generation, analysis, formatting, security scan |
| External process composing via RPC | External client | VS Code extension, Goose, CI integrations |

**Action:** Build scheduler in `application/services/`, Discord driver in
`interfaces/discord/`. Keep the plugin system for what it's good at. Close one
core gap first: add function calling / tool use to LLMPort (done — ToolDefinition,
ToolCall, tool_calls on LLMResponse/StreamChunk, tools/tool_choice params on all
6 adapters + facade + execution layer, 30 contract tests).

---

## Files to Know

| File | Lines | Role | Status |
|------|-------|------|--------|
| `interfaces/cli/main.py` | ~400 | CLI entry point | Clean (dispatch tables) |
| `interfaces/cli/commands/db.py` | ~170 | DB maintenance CLI | New (info, vacuum, backup, stats) |
| `interfaces/cli/stdio.py` | ~200 | RPC dispatch | Clean (handlers extracted) |
| `services/orchestrator.py` | 927 | Task orchestration | Clean (phases decomposed) |
| `persistence/sqlite_store.py` | ~1,150 | All persistence | Clean (mappers extracted, delete + cascade, scheduled jobs) |
| `persistence/row_mappers.py` | ~180 | Row → domain model | Clean |
| `use_cases/ask_conversation.py` | 832 | Conversation logic | Clean (prepare/finalize pipeline) |
| `infrastructure/llm/provider_facade.py` | ~291 | Provider routing | Clean |
| `application/routing/router_policy.py` | 236 | Route decisions | Clean |
| `domain/ports/llm_port.py` | 146 | LLM contract | Clean (includes streaming) |
| `application/services/llm_execution.py` | ~200 | LLM call + fallback | Clean |
| `services/scheduler.py` | ~250 | Tick-driven scheduler | New (core service) |
| `interfaces/discord/bot.py` | ~130 | Discord bot | New (commands.Bot, on_message, streaming pipeline) |
| `interfaces/discord/commands.py` | ~170 | Slash commands | New (6 commands, Cog pattern) |
| `application/runtime/container.py` | ~189 | DI container | Clean (file-based config, scheduler wired) |
