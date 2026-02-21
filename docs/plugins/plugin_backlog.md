# OpenChronicle v2 — Plugins & Extensions Roadmap (Backlog)

This document captures all known plugin/extension ideas discussed to date, ordered by user value and near-term leverage. It is intentionally implementation-light: the goal is clarity, sequencing, and minimum standards — not design-by-document.

## Guiding principles

- **Core stays hardcore.** Core must remain fully usable standalone via CLI/RPC, with no dependency on any plugin to function.
- **Plugins add capabilities, not stability.** If a feature is required for basic reliability, it belongs in core (e.g., deterministic persistence, RPC, audit logs).
- **Determinism and explainability are non-negotiable.** Plugins must emit explainable outcomes and stable ordering where it matters.
- **Explicit network policy.** Anything that talks to the internet must be opt-in, logged, and explainable.
- **Security posture: pragmatic, not government-grade.** Prefer integrating existing open-source scanners over inventing new ones.

---

## Priority 0 — Foundation enhancers (plugin-facing, but core-agnostic)

These provide immediate leverage for all other plugins and should be implemented early.

### 0.1 Scheduler / Background Jobs ✅ (Moved to Core)

**Status:** Implemented as a core service in `application/services/scheduler.py`
per Decision #4 (hybrid taxonomy). The scheduler needs persistent storage,
lifecycle hooks, and direct service access — all of which the plugin API lacks.

**What was built (52+ tests, 6 CLI + 6 RPC commands):**

- Job store in core SQLite (`scheduled_jobs` table)
- One-shot + recurring jobs (interval-based)
- Deterministic ordering: `next_due_at ASC`, `created_at ASC`, `id ASC`
- `scheduler.tick(now, max_jobs)` — atomic claim via `BEGIN IMMEDIATE`
- `scheduler.serve()` — async polling loop with clean shutdown
- Events: `scheduler.job_created/paused/resumed/cancelled/fired/tick_completed`

See `docs/BACKLOG.md` section 0.1 for full details.

---

## Priority 1 — Front-end / Client integrations (core remains standalone)

### 1.1 Discord Integration ✅ (Moved to Core)

**Status:** Implemented as a core interfaces driver in `interfaces/discord/`
per Decision #4 (hybrid taxonomy). Discord is an interface like CLI or STDIO
RPC — it needs the same level of access as core services.

**What was built (60 unit tests + 7 integration tests):**

- `commands.Bot` subclass with message handling
- 6 slash commands: `/newconvo`, `/remember`, `/forget`, `/explain`, `/mode`, `/history`
- Session-to-conversation mapping (file-backed, multi-user)
- Message splitting for Discord's 2000-char limit
- Config from `core.json` + env vars (three-layer precedence)
- `oc discord start` CLI command with lazy import guard
- Optional `[discord]` extra — core runs without discord.py installed

**Posture enforcement:** `test_architectural_posture.py` + `test_hexagonal_boundaries.py`
verify core agnosticism, no inward imports, and session isolation.

See `docs/BACKLOG.md` section 1.1 for full details.

---

## Priority 2 — Safety, security, and trust tooling

### 2.1 Dev Folder Security Scanner (Background Task Plugin)

**Problem:** Add an “extra set of eyes” for codebases touched by AI assistants — detect secrets, malware, suspicious dependencies, risky patterns.

**Approach:** Integrate existing scanners; do not reinvent.

- Secrets scanning: (e.g., gitleaks/trufflehog)
- Dependency vuln scanning: (e.g., osv-scanner)
- Container/image scanning (optional): (e.g., trivy)
- Static code scanning (optional): (e.g., semgrep rules)

**Minimum capability:**

- Configured scan targets (folders).
- Deterministic scan runs:
  - stable tool versions
  - stable output schema
- Reports stored under output directory with timestamps and a stable “latest” pointer.
- Alert channels:
  - CLI/RPC retrieval
  - optionally Discord (if installed), but do not depend on it.

**Why high priority:** High confidence, low regret, and aligns with your workflow.

---

## Priority 3 — Workflow automation and “assistant goes to work” mode

### 3.1 Controlled “Dev Agent Runner” (MCP-style) Plugin

**Problem:** You want the ability to build a plan and let the app execute dev tasks in the background — safely.

**Non-goals (early):**

- No autonomous pushing to external repos.
- No unrestricted internet access.

**Minimum capability:**

- A “job” is a plan + constraints + workspace + tool permissions.
- Execution happens in a sandboxed environment:
  - ideally a dedicated container image with locked-down permissions
  - explicit mounts (read-only vs read-write)
  - optional: no network by default
- Every action is logged (command, files touched, outputs, errors).
- The product outputs are a patch/branch or artifact bundle, never directly pushed upstream.

**Security baseline:**

- Default deny:
  - network
  - secrets access
  - external repo push
- Explicit allow-lists for:
  - commands
  - directories
  - time/resource limits

**Why medium priority:** Huge value, but the highest security risk. Build once the “scheduler + scanner” ecosystem is in place.

### 3.2 Serena MCP Capabilities Integration (Optional)

**Problem:** Serena is open source and useful for codebase navigation/refactoring workflows.

**Plan (lightweight evaluation):**

- Start with “compatibility mode”:
  - allow plugin to invoke Serena-like flows only inside the sandbox runner container
- Integrate only after:
  - sandbox runner is stable
  - network policy is explicit
  - scanning pipeline exists for outputs

**Why medium priority:** Leverage is high, but we should absorb risk carefully.

---

## Priority 4 — Multi-LLM orchestration features (advanced, optional)

### 4.1 Mixture-of-Experts Mode ✅ (Moved to Core)

**Status:** Reclassified as a core execution strategy in
`application/services/` per Decision #4 taxonomy review (2026-02-20).

MoE needs `LLMPort` to make N expert calls with explicit model selection,
`RouterPolicy` / `ProviderFacade` to route each expert to a different
provider/model, and response aggregation logic. The plugin API provides
`(task, context) → result` with no LLM access — MoE cannot work within
those constraints.

MoE is an **execution strategy** (like streaming vs non-streaming), not a
stateless handler. It belongs in `application/services/`, not `plugins/`.

See `docs/BACKLOG.md` section 5.1 for full requirements.

---

## Priority 5 — V1 Feature Rebuilds (Plugins)

### 5.1 Storytelling Plugin Suite

**Status:** 🔴 Not Started (demo handler exists in `plugins/storytelling/`)
**Effort:** Large
**Reference:** `v1.reference/` directory contains the full v1 implementation

V1 was a comprehensive narrative AI engine. V2 stripped to domain-agnostic core.
The v1 features belong in a plugin suite built on v2's stable foundation.

**V1 features to rebuild as plugins:**

- **Character management** — entity tracking, stats, behavior engine, interaction dynamics
- **Scene/timeline management** — scene persistence, timeline navigation, rollback
- **Narrative engines** — consistency checker, emotional analyzer, response planner
- **Game mechanics** — dice engine, narrative branching
- **Content analysis** — detection, extraction, classification (NLP pipeline)
- **Image generation** — multi-provider orchestrator, style presets, character portraits
- **Import system** — storypack orchestrator, multi-phase import with AI-assisted analysis
- **Bookmark system** — scene bookmarking, chapters, navigation

**Approach:** Each subsystem can be an independent plugin or grouped into a
storytelling suite. The `v1.reference/` directory serves as both design reference
and implementation roadmap. Rebuild incrementally — character + scene management
first (highest user value), then narrative engines, then image generation.

**Plugin API note:** Some of these (character memory, scene state) need persistent
storage beyond what the current plugin API provides. Options: use OC's memory
system for persistence, extend the plugin context, or promote to core services
if the plugin API proves insufficient (same pattern as scheduler/Discord).

---

## Priority 6 — IDE / Developer platform integrations

### 6.1 VS Code / Copilot SDK Integration (MCP Client — Not a Plugin)

**Status:** Reclassified per Decision #5 (MCP-first integration strategy,
2026-02-20). VS Code supports MCP servers natively. Primary integration path
is OC MCP server — no plugin code needed.

**Approach:** VS Code connects to `oc mcp serve` as an MCP server, gaining
access to OC's persistent memory and conversation capabilities. Same mechanism
as the Goose integration. A custom Copilot SDK integration is a secondary
option only if deeper IDE-specific features are needed.

See `docs/BACKLOG.md` section 7.1 for requirements.

### 6.2 Goose Integration (MCP Client — Not a Plugin)

**Status:** Reclassified per Decision #5 (MCP-first integration strategy,
2026-02-20). Goose supports MCP servers natively. No custom Goose extension
or OC plugin needed.

**Approach:** Goose connects to both OC MCP server and Serena MCP server,
forming the triangle: persistent memory (OC) + code understanding (Serena) +
agent execution (Goose). Zero custom glue code.

See `docs/BACKLOG.md` section 7.2 and `docs/integrations/mcp_server_spec.md`
for full details.

---

## Priority 7 — Platform infrastructure (optional, enabling)

### 7.1 Private Git Server (External Infrastructure)

**Problem:** Keep code “off the net” while enabling safe automated tooling to work on repos.

**Scope note:** This is not a core feature; it’s platform infrastructure.

- Candidate solutions: self-hosted Git (e.g., Gitea/GitLab) behind your network.
- Integrate later via plugins/drivers:
  - clone/pull in sandbox
  - produce branches/patch bundles
  - manual human review gate before any upstream push

**Why optional:** Useful for security posture, but not required to ship plugins.

---

## Already implemented / belongs in Core (for reference)

These were discussed as plugin candidates but were (correctly) handled in core
because they are foundational:

- **Scheduler service** — `application/services/scheduler.py` (52+ tests)
- **Discord interface** — `interfaces/discord/` (60 tests, optional extra)
- **OC MCP server** — `interfaces/mcp/` (Decision #5, 14 tools, stdio + SSE)
- **MoE mode** — `application/services/moe_execution.py` (Jaccard consensus, 32 tests)
- **Router assist seam + local classifier baseline**
- **Privacy gate / PII controls + override**
- **Deterministic metrics surface + telemetry hooks**
- **Daemon-friendly STDIO RPC + oneshot RPC**
- **Acceptance harness (`oc init`, `oc acceptance`)**

External clients (not plugins, not core — compose via MCP or RPC):

- **Goose** — MCP client connecting to OC MCP + Serena MCP (Decision #5)
- **VS Code / Copilot SDK** — MCP client connecting to OC MCP
- **Claude Desktop** — MCP client connecting to OC MCP

---

## Implementation sequencing recommendation (high-level)

1. ~~**Scheduler service**~~ ✅ (core — `application/services/scheduler.py`)
2. ~~**Discord interface**~~ ✅ (core — `interfaces/discord/`)
3. ~~**OC MCP server**~~ ✅ (core — `interfaces/mcp/`, 14 tools)
4. ~~**Mixture-of-experts mode**~~ ✅ (core — `application/services/moe_execution.py`)
5. **Security scanner plugin** (runs via scheduler service)
6. **Goose integration** (MCP client — unblocked by #3, config only)
7. **Storytelling plugin suite** (rebuild v1 features as plugins)
8. **Sandbox dev-agent runner** (uses scheduler + scanner as safety rails)
9. **Serena MCP capabilities inside sandbox runner**
10. **VS Code / Copilot SDK** (MCP client — unblocked by #3)
11. **Private Git server integration** (platform + sandbox workflows)

See `docs/BACKLOG.md` for the authoritative sequence with full details.

---

## Minimum standards for all plugins

- Must load/unload cleanly (no side effects at import time).
- Deterministic ordering wherever selection happens (jobs, tasks, scans).
- Outputs are structured and auditable:
  - stable JSON envelopes preferred
  - errors carry canonical `error_code` and actionable hints
- Network usage:
  - explicit config flag
  - logged endpoints / rationale
- No secrets in logs.
- Tests:
  - unit tests for handlers
  - at least one docker harness execution path for “happy path” plugin.invoke (where practical)

End of document.
