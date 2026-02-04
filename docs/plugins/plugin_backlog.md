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

### 0.1 Scheduler / Background Jobs Plugin

**Problem:** We want scheduled tasks/responses and periodic background work without baking a daemon scheduler into core.

**Minimum capability:**

- Define a job store (plugin-local SQLite under runtime directory).
- Job types:
  - one-shot at timestamp
  - recurring (interval or cron-like later)
- Deterministic selection/order:
  - `due_at ASC`, `created_at ASC`, `job_id ASC`
- Execution is explicit and auditable:
  - `scheduler.tick(now, max_jobs)` -> enqueues tasks via core (`task.submit`), returns run metadata
- No threads required to start:
  - Initial version can be “tick-driven” (via `oc rpc` or external driver).
  - Optional later: long-running `scheduler.serve` loop (still plugin-side).

**Why high priority:** It unlocks scheduled responses, scans, metrics snapshots, and future automation with minimal core impact.

---

## Priority 1 — Front-end / Client integrations (core remains standalone)

### 1.1 Discord Integration (Driver Plugin)

**Problem:** Provide a real “app feel” by letting Discord act as a UI client.

**Minimum capability:**

- Discord bot that:
  - receives messages
  - maps them to `convo.ask` (RPC)
  - posts responses back
- Must honor:
  - conversation modes
  - privacy gate / PII checks
  - routing decisions (NSFW-capable model selection)
- Explicit network and credential configuration.
- Rate limiting + retry policy (plugin-side), with clear logs.

**Notes:**

- Core must remain fully functional without Discord.
- Prefer integrating via STDIO RPC process orchestration; do not import core internals directly unless we explicitly allow it.

**Why high priority:** Most visible UX win once core is stable.

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

### 4.1 Mixture-of-Experts Mode (Manager/Worker Future)

**Problem:** Improve answer quality and reliability by asking 3 models and selecting output via agreement rules.

**Minimum capability:**

- A “consensus run” mode:
  - run N experts (default 3)
  - produce an aggregator decision with explainability:
    - which experts agreed
    - conflict summary
    - why final output was chosen
- Deterministic selection rules:
  - exact match or structured rubric
  - tie-breakers are stable and logged
- Must be optional and not the default UX.

**Why later:** Powerful, but not required for core usefulness; adds complexity.

---

## Priority 5 — IDE / Developer platform integrations

### 5.1 VS Code Copilot SDK Integration (Plugin)

**Problem:** Use Copilot SDK capabilities to enhance coding workflows (especially for MCP plugins).

**Minimum capability:**

- A plugin that can:
  - authenticate explicitly (user-managed)
  - submit a request payload
  - return structured output + logs
- Must obey network policy:
  - explicit opt-in
  - full audit logging of endpoints contacted
  - sanitize payloads / respect PII gate

**Why later:** High value, but external API surface + auth + policy complexity. Better once sandbox runner exists.

---

## Priority 6 — Platform infrastructure (optional, enabling)

### 6.1 Private Git Server (External Infrastructure)

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

These were discussed as plugin candidates but were (correctly) handled in core because they are foundational:

- **Router assist seam + local classifier baseline**
- **Privacy gate / PII controls + override**
- **Deterministic metrics surface + telemetry hooks**
- **Daemon-friendly STDIO RPC + oneshot RPC**
- **Acceptance harness (`oc init`, `oc acceptance`)**

---

## Implementation sequencing recommendation (high-level)

1. **Scheduler plugin MVP**
2. **Security scanner plugin** (runs via scheduler)
3. **Discord driver plugin** (uses core via RPC; can also schedule via scheduler)
4. **Sandbox dev-agent runner** (uses scheduler + scanner as safety rails)
5. **Serena MCP capabilities inside sandbox runner**
6. **Mixture-of-experts mode** (optional advanced UX)
7. **Copilot SDK plugin** (networked, opt-in)
8. **Private Git server integration** (platform + sandbox workflows)

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
