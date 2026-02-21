# OpenChronicle v2 - Feature & Implementation Backlog

This document tracks planned features, implementation gaps, and future work for the OpenChronicle v2 project.

**Last Updated:** 2026-02-20

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
- [x] 52+ tests (28 service, 13 storage, 11 CLI)

---

## Priority 1 — Client Integrations

### 1.1 Discord Interface (Core Driver)

**Status:** ✅ Implemented
**Location:** `src/openchronicle/interfaces/discord/` (optional `[discord]` extra)
**Tests:** 60 unit tests (`test_discord_*.py`) + 7 integration tests

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

**Status:** 🔴 Not Started
**Location:** `src/openchronicle/interfaces/mcp/` (optional `[mcp]` extra)
**Effort:** Medium
**Spec:** [`docs/integrations/mcp_server_spec.md`](integrations/mcp_server_spec.md)

Exposes OC's persistent memory and conversation capabilities via Model Context
Protocol. Enables any MCP-compatible agent (Goose, Claude Desktop, VS Code) to
use OC without custom integration code. See Decision #5 in assessment.

**Key insight — the OC + Serena + Goose triangle:**

- Serena MCP = code understanding (what the code IS)
- OC MCP = persistent memory (what was DECIDED and WHY)
- Goose = agent execution (hands that do the work)

**MCP Tools (10):**

- [ ] `memory_search` — keyword search across memory items
- [ ] `memory_save` — store a memory item (tagged, optionally pinned)
- [ ] `memory_list` — list memories (by conversation, project, or all)
- [ ] `memory_pin` — pin/unpin a memory for persistent retrieval
- [ ] `conversation_ask` — send a message through full OC pipeline
- [ ] `conversation_history` — retrieve recent turns
- [ ] `conversation_list` — list conversations
- [ ] `conversation_create` — create a new conversation
- [ ] `context_recent` — recent activity summary for a topic/conversation
- [ ] `health` — health check

**Infrastructure:**

- [ ] `oc mcp serve` CLI command (stdio transport)
- [ ] Optional SSE transport (`--transport sse --port 8080`)
- [ ] Posture tests (core runs without MCP SDK, no inward imports)

**Acceptance Criteria:**

- All 10 tools map to existing ports/use cases (no new domain logic)
- Privacy gate honored on all conversation tools
- Core functional without `mcp` extra installed
- Manual validation with Goose + Serena triangle

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

### 5.1 Mixture-of-Experts Mode

**Status:** 🔴 Not Started (Optional)
**Effort:** Medium
**Priority:** Low — may not be required for core usefulness

**Requirements:**

- [ ] Run N experts (default 3)
- [ ] Select output via agreement rules
- [ ] Produce aggregator decision with explainability:
  - Which experts agreed
  - Conflict summary
  - Why final output was chosen
- [ ] Deterministic selection rules with stable tie-breakers

**Constraints:**

- Must be optional, not default UX
- Clear cost implications documented

---

## Priority 6 — IDE / Developer Platform Integrations

### 6.1 VS Code Copilot SDK Integration

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

### 6.2 Goose (Block) Integration (MCP Client)

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

## Priority 7 — Platform Infrastructure

### 7.1 Private Git Server Integration

**Status:** 🔴 Not Started
**Effort:** Medium
**Depends On:** Dev Agent Runner

**Approach:**

- Self-hosted Git (Gitea/GitLab) behind network
- Clone/pull in sandbox, produce branches/patches
- Manual human review gate before any upstream push

---

## Infrastructure Gaps

### HTTP API

**Status:** ⚪ Stubbed
**File:** `src/openchronicle/interfaces/api/http_api.py`
**Effort:** Medium

**Requirements:**

- [ ] FastAPI or Flask wiring
- [ ] Authentication layer
- [ ] Streaming response support
- [ ] OpenAPI documentation
- [ ] Rate limiting middleware

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

---

## Technical Debt

### Known Issues

| Issue                               | Location                               | Priority |
| ----------------------------------- | -------------------------------------- | -------- |
| ~~Unicode encoding on Windows CLI~~ | `interfaces/cli/main.py`               | ✅ Fixed |
| ~~Test subprocess PATH issue~~      | `tests/test_task_submit_rpc.py`        | ✅ Fixed |
| ~~Docker acceptance JSON escaping~~ | `tools/docker/acceptance.ps1`          | ✅ Fixed |
| ~~docker-compose .env required~~    | `docker-compose.yml`                   | ✅ Fixed |
| ~~Smoke test assertion too strict~~ | `tests/integration/test_smoke_live.py` | ✅ Fixed |

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

3. OC MCP Server (P2) ← NEW (Decision #5)
   └── Core interface in interfaces/mcp/
   └── 10 tools, maps to existing ports/use cases
   └── Unblocks: Goose, VS Code, Claude Desktop, any MCP client

4. Security Scanner Plugin (P3)
   └── Runs via scheduler service
   └── Safety rail for dev agent

5. Goose Integration (P6.2) ← MOVED UP (unblocked by MCP server)
   └── MCP client connecting to OC MCP + Serena MCP
   └── No custom code — just config

6. HTTP API (Infrastructure)
   └── Web integrations
   └── External tool access

7. Dev Agent Runner (P4.1)
   └── Uses scheduler + scanner
   └── Sandboxed execution
   └── Upgrade path: OC orchestrates Goose

8. Serena MCP in Sandbox (P4.2)
   └── Inside sandbox runner only

9. VS Code Copilot SDK (P6.1)
   └── MCP client or custom RPC

10. Mixture-of-Experts (P5)
    └── Optional advanced feature

11. Private Git Server (P7)
    └── Platform infrastructure
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
