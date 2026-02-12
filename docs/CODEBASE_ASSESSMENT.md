# OpenChronicle v2 — Senior Developer Codebase Assessment

**Date:** 2026-02-12
**Branch:** `refactor/new-core-from-scratch`
**Revision:** 2 (updated with full project history and Definition of Done)

---

## Executive Summary

OpenChronicle started as a solution to a real problem: chat context dies between
sessions, and there's no way to carry a narrative (or any LLM interaction) forward
durably. V1 grew into a comprehensive narrative AI engine with 13+ orchestrators,
character AI, and 15+ providers. V2 is a clean-room rebuild recognizing that the
*actual* underlying problem — durable context, explainable routing, and auditable
decisions across LLM interactions — is domain-agnostic.

The core is now in a **"foundation complete, UX incomplete"** state. The backend
pipeline works end-to-end: conversation → context assembly → memory retrieval →
provider routing → LLM call → response → turn persistence → event logging. Tests
are strong (400+), architecture is enforced, and the STDIO RPC daemon mode exists.

**What's missing for "core done"** is the user-facing experience. The CLI requires
manual UUID juggling for every turn. There's no interactive chat mode. There's no
streaming. The interface layer has God Functions that will compound as plugins
arrive. These are solvable problems, and the backend is solid enough to support
them.

**Overall: A-tier backend, C-tier UX.** The hard parts are done. What remains is
making it feel like a product you'd actually want to use.

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
  → System prompt construction with memory context
  → Interaction routing (rule-based + optional ML assist)
  → Privacy gate check (optional PII detection)
  → Provider/model selection via routing policy
  → LLM call with fallback execution
  → Response capture + metadata parsing
  → Atomic turn persistence (index, text, provider, model, routing reasons)
  → Event emission (hash-chained, tamper-evident)
  → Telemetry recording (tokens, latency, memory usage)
```

This is tested end-to-end in `test_conversation_flow.py` and `test_smoke_live.py`.

### Infrastructure Inventory

| Subsystem | Status | Evidence |
|-----------|--------|----------|
| **5 LLM providers** (OpenAI, Anthropic, Groq, Gemini, Ollama) | Working | Async-native adapters, contract tests |
| **Provider routing** (pools, fallback, NSFW, budget-aware) | Working | 1,278-line test suite |
| **SQLite persistence** (10 tables, 48 methods, WAL mode) | Working | Handles tasks, conversations, memory, events |
| **Hash-chained events** (SHA256, prev_hash → hash) | Working | Verification + replay services |
| **Privacy gate** (6 PII categories, Luhn validation) | Working | Rule-based, provider-aware |
| **Interaction routing** (rule + hybrid ML assist) | Working | NSFW scoring, mode detection |
| **Memory v0** (keyword search, pinned, tagged) | Working | Deterministic retrieval, no embeddings |
| **Budget/rate limiting** | Working | Token limits, call limits, rate gates |
| **Plugin system** (discover, load, register, invoke) | Working | 2 example plugins, collision detection |
| **STDIO RPC** (18 commands, serve + oneshot) | Working | Request dedup, telemetry, error codes |
| **CLI** (50+ subcommands) | Working | Project/task/convo/memory/diagnostics |
| **Config-driven wiring** (JSON model configs, env vars) | Working | Per-(provider, model) resolution |
| **Test suite** (400+ tests, 93 files) | Passing | 12 test categories, architecture guards |

### Architecture (Enforced and Clean)

```text
interfaces/ (CLI, RPC, API stub)
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

## Current State: What's Missing

### 1. No Interactive Chat Experience

The CLI requires this to have a conversation:

```bash
oc convo create --title "My Chat"
# → outputs conversation_id (UUID)
oc convo ask --conversation-id 550e8400-... "Hello, how are you?"
# → outputs response
oc convo ask --conversation-id 550e8400-... "Tell me more"
# → outputs response
```

**What "interact like a chatbot" requires:**

```bash
oc chat
# → enters interactive REPL
# → auto-creates or resumes conversation
You: Hello, how are you?
Assistant: I'm doing well! How can I help you today?
You: Tell me more about X
Assistant: ...
```

This is the single biggest UX gap. The backend supports it — conversations, turns,
memory all work. There's just no interactive shell wrapping it.

### 2. No Streaming Responses

`LLMPort.complete_async()` returns a complete `LLMResponse`. There's no streaming
API. For a chatbot experience, watching tokens arrive is table stakes — especially
for long responses that take 10+ seconds.

All 5 provider SDKs support streaming natively. The port interface would need a
`stream_async()` method returning an async iterator of chunks.

### 3. God Functions in Interface Layer

| Function | File | Lines | Problem |
|----------|------|-------|---------|
| `main()` | `interfaces/cli/main.py` | **1,574** | All 50+ CLI commands in one function |
| `dispatch_json_command()` | `interfaces/cli/stdio.py` | **974** | All 18 RPC commands in one function |

These make the interface layer untestable in isolation and fragile to change.
Every new command means editing a function that's already 1,000+ lines.

**This matters for "core done" because:** Plugins don't add CLI commands (they use
`plugin.invoke`), but core maintenance and future core commands (like `oc chat`)
need a clean interface layer. The God Functions also prevent proper command-level
unit testing.

### 4. Manager/Worker Methods Need Decomposition

`OrchestratorService` (831 lines) contains `_run_worker_summarize()` (339 lines)
and `_run_analysis_summary()` (119 lines). These implement the manager/worker
pattern — a core runtime capability (like multi-threading) that stays in core.

The conversation flow bypasses these methods — `ask_conversation.py` calls
`execute_with_route()` directly. But manager/worker is available for task-based
workflows and future plugins that need parallel execution.

**Resolved:** Stays in core. Methods need internal decomposition into phases
(setup, prompt building, LLM call, result parsing, worker spawning) for
readability and testability. See Resolved Decisions section.

### 5. `ask_conversation.execute()` — 444 Lines in One Function

This is the core conversation workflow. It works correctly but does too much in one
function: context assembly, memory retrieval, routing, privacy gate, LLM call,
response parsing, turn persistence, telemetry. Decomposing into 3-4 helper
functions would make it testable and readable without changing behavior.

---

## Definition of Done: Core v2

"Core done" means: a fully operational daemon that you can interact with like a
chatbot via CLI, with durable memory, explainable routing, and a stable plugin
surface. No backwards compatibility concerns. No production deployment yet.

### Must Have (Blocking for "Core Done")

| # | Item | Status | Why It's Blocking |
|---|------|--------|-------------------|
| 1 | **Interactive chat REPL** (`oc chat`) | Not started | Can't "interact like a chatbot" without it |
| 2 | **Streaming responses** (LLMPort + adapters + CLI, with `--no-stream` toggle) | Not started | Chatbot UX with 10s wait for response is broken |
| 3 | **Interface layer refactoring** (God Functions → dispatch tables) | Not started | Untestable interface layer is a stability risk |
| 4 | **Conversation UX shortcuts** (auto-create, resume latest, etc.) | Not started | UUID juggling prevents casual use |

### Should Have (Quality, Not Functionality)

| # | Item | Status | Impact |
|---|------|--------|--------|
| 5 | **Decompose `ask_conversation.execute()`** | Not started | Testability, readability |
| 6 | **Decompose orchestrator manager/worker methods** | Not started | 339+119 lines in two methods need phase separation |
| 7 | **SqliteStore row mapper extraction** | Not started | Cognitive load reduction |

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

### Phase 1: Interface Layer (Unblocks Everything Else)

**1a. Split `main()` into command functions**

Extract each CLI subcommand into its own function. Use argparse subparser callbacks
or a dispatch dict. Target: `main()` becomes ~100 lines of argument parsing +
dispatch. Each command function is independently testable.

**1b. Split `dispatch_json_command()` into handler functions**

One function per RPC command with a dispatch table mapping command names to
handlers. The STDIO RPC spec already defines clean command boundaries — the code
should match.

**1c. Build `oc chat` interactive REPL**

Wraps the existing `convo.ask` pipeline in a readline-based loop. Auto-creates
or resumes conversations. Minimal new logic — just UX wiring around existing
use cases.

### Phase 2: Streaming (Chatbot UX)

**2a. Add `stream_async()` to LLMPort**

Returns `AsyncIterator[str]` (or a richer chunk type with usage metadata on the
final chunk). Each adapter wraps its SDK's native streaming API.

**2b. Wire streaming through CLI**

`oc chat` and `oc convo ask` print tokens as they arrive. STDIO RPC gets a
`convo.ask_stream` command that emits chunks.

### Phase 3: Conversation UX Polish

**3a. Auto-create conversations** — `oc chat` with no args creates a new
conversation with an auto-generated title.

**3b. Resume latest** — `oc chat --resume` picks up the most recent conversation.

**3c. Simple conversation reference** — Allow `oc convo ask --latest "message"`
instead of requiring full UUID.

### Phase 4: Internal Quality

**4a. Decompose `ask_conversation.execute()`** — Extract context assembly, memory
retrieval, LLM interaction, and telemetry recording into helper functions.

**4b. Decide manager/worker fate** — Keep in core (cleaned up) or extract as
built-in plugin. Either way, `_run_worker_summarize()` needs decomposition.

**4c. Extract SqliteStore row mappers** — Move 11 `_row_to_*` methods to a
`row_mappers.py` module.

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

### Domain Layer (12 models, 8 ports, 3 services)

Clean and well-typed. Key models:

- **`Project`, `Agent`, `Task`, `Event`** — Core execution entities with hash chains
- **`Conversation`, `Turn`** — Chat interaction history with full metadata per turn
- **`MemoryItem`** — Persistent knowledge with tags, pinning, conversation/project scope
- **`BudgetPolicy`, `TaskRetryPolicy`** — Policy-as-data pattern
- **`InteractionHint`, `RouterAssistResult`** — Routing decision outputs

Ports define clean contracts: `StoragePort` (28+ methods), `ConversationStorePort`
(11 methods), `MemoryStorePort` (6 methods), `LLMPort` (2 methods), plus single-
method ports for routing, privacy, and plugin hosting.

**Concern:** `StoragePort` at 28+ abstract methods is doing too much. The task tree
navigation methods feel like read-model concerns that could be a separate port.

### Infrastructure Layer

**Complete:** SQLite persistence (10 tables, crash recovery, transactions), privacy
gate (6 PII categories), rule routing (NSFW + mode detection), hybrid routing
(rule + ML), linear router assist (logistic regression), event logger (hash chains),
configuration (settings dataclasses + env vars).

**Stub only:** ONNX router assist (intentional placeholder).

**Not started:** Streaming in LLM adapters.

### Test Suite (93 files, 400+ tests)

Well-organized into 12 categories: business logic (23), CLI/RPC (15), hygiene (10),
infrastructure (10), contract (8), policy (5), memory (5), architecture guard (4),
advanced (5), data format (4), plugin (2), integration (2).

**Strongest coverage:** Provider routing, budget enforcement, conversation flow,
event verification, architectural boundaries.

**Gap:** Interface layer is largely untested in isolation due to God Functions.
Splitting them would unlock proper command-level testing.

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

## Plugin Roadmap (Post Core-Done)

```text
Core Done
  → Scheduler Plugin (P0) — unlocks all downstream plugins
  → Discord Driver (P1) — first external client
  → Security Scanner (P2) — gitleaks/osv-scanner/trivy
  → Dev Agent Runner (P3) — sandboxed execution
  → Serena MCP (P3.2) — inside sandbox only
  → MoE Mode (P4) — multi-expert consensus
  → HTTP API (infra) — FastAPI/Flask
  → VS Code / Copilot SDK (P5.1)
  → Goose Integration (P5.2)
  → Private Git Server (P6)
```

Each plugin composes on core via STDIO RPC. Core stays standalone.

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

---

## Files to Know

| File | Lines | Role | Priority |
|------|-------|------|----------|
| `interfaces/cli/main.py` | 1,858 | CLI entry point | **Refactor** — God function |
| `interfaces/cli/stdio.py` | 1,842 | RPC handler | **Refactor** — God function |
| `services/orchestrator.py` | 831 | Task orchestration | **Decompose** — manager/worker methods |
| `persistence/sqlite_store.py` | 1,049 | All persistence | **Monitor** — 3 ports, 48 methods |
| `use_cases/ask_conversation.py` | 758 | Conversation logic | **Decompose** — oversized execute() |
| `infrastructure/llm/provider_facade.py` | ~291 | Provider routing | Clean |
| `application/routing/router_policy.py` | 236 | Route decisions | Clean |
| `domain/ports/llm_port.py` | 98 | LLM contract | Clean (needs streaming) |
| `application/services/llm_execution.py` | ~200 | LLM call + fallback | Clean |
| `application/runtime/container.py` | ~118 | DI container | Clean |
