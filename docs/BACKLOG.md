# OpenChronicle v2 - Feature & Implementation Backlog

This document tracks planned features, implementation gaps, and future work for the OpenChronicle v2 project.

**Last Updated:** 2026-02-04

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Implemented |
| 🟡 | In Progress |
| 🔴 | Not Started |
| ⚪ | Stubbed/Placeholder |
| ⏸️ | Deferred |

---

## Priority 0 — Foundation (Blocking)

### 0.1 Scheduler / Background Jobs Plugin

**Status:** 🔴 Not Started
**Effort:** Medium
**Rationale:** Enables scheduled responses, periodic scans, metrics snapshots without daemon in core. Unlocks downstream plugins (Discord, security scanner, dev agent runner).

**Requirements:**

- [ ] Job store (plugin-local SQLite)
- [ ] One-shot scheduled tasks
- [ ] Recurring jobs (cron-like)
- [ ] Deterministic execution order (`due_at ASC`, `created_at ASC`, `job_id ASC`)
- [ ] `scheduler.tick(now, max_jobs)` to enqueue tasks
- [ ] Optional long-running `scheduler.serve` loop

**Acceptance Criteria:**

- Jobs persist across restarts
- Deterministic ordering verified by tests
- Integration with task.submit RPC

---

## Priority 1 — Client Integrations

### 1.1 Discord Driver Plugin

**Status:** 🔴 Not Started
**Effort:** Medium
**Depends On:** Scheduler (recommended, not required)
**Documentation:** `docs/integrations/discord_driver_contract.md`

**Requirements:**

- [ ] Discord bot receiving messages
- [ ] Map to `convo.ask` / `convo.ask_async` RPC
- [ ] Honor conversation modes
- [ ] Honor privacy gates and NSFW filtering
- [ ] Explicit network and credential configuration
- [ ] Rate limiting + retry policy with clear logs
- [ ] Sync mode (simple) and Async mode (recommended)

**Constraints:**

- Core must remain fully functional without Discord
- Integrate via STDIO RPC, not by importing core internals
- Explicit PII handling with allow_pii bypass confirmation

---

## Priority 2 — Safety & Security

### 2.1 Dev Folder Security Scanner Plugin

**Status:** 🔴 Not Started
**Effort:** Medium
**Depends On:** Scheduler Plugin

**Requirements:**

- [ ] Integrate existing scanners (not inventing new ones):
  - [ ] Secrets scanning: gitleaks or trufflehog
  - [ ] Dependency vulnerability: osv-scanner
  - [ ] Container scanning: trivy (optional)
  - [ ] Static analysis: semgrep rules (optional)
- [ ] Deterministic scan runs with stable tool versions
- [ ] Reports stored in output directory with timestamps + "latest" pointer
- [ ] Alert channels: CLI/RPC retrieval
- [ ] Optional Discord alerts (if Discord plugin installed)

**Acceptance Criteria:**

- Scans run on schedule via scheduler plugin
- Reports are JSON-serializable and timestamped
- No false positives in baseline scan of clean repo

---

## Priority 3 — Workflow Automation

### 3.1 Dev Agent Runner (Sandboxed)

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

### 3.2 Serena MCP Capabilities Integration

**Status:** ⏸️ Deferred
**Depends On:** Dev Agent Runner (stable)

**Approach:**

- Start with "compatibility mode": allow Serena-like flows only inside sandbox runner container
- Integrate only after sandbox runner is stable, network policy is explicit, scanning pipeline exists

---

## Priority 4 — Advanced LLM Features

### 4.1 Mixture-of-Experts Mode

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

## Priority 5 — IDE Integrations

### 5.1 VS Code Copilot SDK Integration

**Status:** 🔴 Not Started
**Effort:** Medium
**Depends On:** Dev Agent Runner (recommended)

**Requirements:**

- [ ] Authenticate explicitly (user-managed)
- [ ] Submit request payload, return structured output + logs
- [ ] Explicit opt-in network policy with full audit logging
- [ ] Sanitize payloads / respect PII gate

---

## Priority 6 — Platform Infrastructure

### 6.1 Private Git Server Integration

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

| Issue | Location | Priority |
|-------|----------|----------|
| ~~Unicode encoding on Windows CLI~~ | `interfaces/cli/main.py` | ✅ Fixed |
| ~~Test subprocess PATH issue~~ | `tests/test_task_submit_rpc.py` | ✅ Fixed |
| ~~Docker acceptance JSON escaping~~ | `tools/docker/acceptance.ps1` | ✅ Fixed |
| ~~docker-compose .env required~~ | `docker-compose.yml` | ✅ Fixed |
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
1. Scheduler Plugin (P0)
   └── Foundation for all plugins

2. Security Scanner Plugin (P2)
   └── Runs via scheduler
   └── Safety rail for dev agent

3. Discord Driver Plugin (P1)
   └── Uses core via RPC
   └── Can use scheduler for async

4. HTTP API (Infrastructure)
   └── Web integrations
   └── External tool access

5. Dev Agent Runner (P3)
   └── Uses scheduler + scanner
   └── Sandboxed execution

6. Serena MCP Integration (P3.2)
   └── Inside sandbox runner only

7. VS Code Copilot SDK (P5)
   └── After sandbox exists

8. Mixture-of-Experts (P4)
   └── Optional advanced feature

9. Private Git Server (P6)
   └── Platform infrastructure
```

---

## References

- **Architecture:** `docs/v2/ARCHITECTURE.md`
- **Plugin Guide:** `docs/v2/PLUGINS.md`
- **Plugin Roadmap:** `docs/plugins/plugin_backlog.md`
- **RPC Protocol:** `docs/protocol/stdio_rpc_v1.md`
- **Discord Contract:** `docs/integrations/discord_driver_contract.md`
- **Project Instructions:** `CLAUDE.md`
