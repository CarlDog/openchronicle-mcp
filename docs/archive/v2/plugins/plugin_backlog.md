# OpenChronicle v2 — Plugins & Extensions Roadmap

**Authoritative backlog:** [`docs/BACKLOG.md`](../BACKLOG.md) — this document
covers plugin-specific standards and the taxonomy boundary.

**Last Updated:** 2026-04-29

---

## Feature Taxonomy

Every feature falls into one of three categories:

| Category | Definition | Location | API Access |
| -------- | ---------- | -------- | ---------- |
| **Core** | Stateful, needs ports/scheduler/LLM, lifecycle hooks | `application/services/`, `domain/ports/` | Full |
| **Plugin** | Behavior-modifying extension (mode prompt builder, conversation hooks) | This repo's `plugins/` | Mode dispatch, registry, event emission |
| **External** | Composes via MCP or HTTP API | Outside OC repo | MCP tools / REST endpoints |

**The plugin API is complete.** No extension planned. Complex features belong
in core. The boundary is intentional:

- If it needs LLM access → core
- If it needs persistent storage → core
- If it needs scheduler integration → core
- If it needs shell execution → core
- If it's a stateless handler → plugin

---

## Plugin API Surface

What plugins receive at invocation:

```python
async def handler(task: Task, context: dict[str, Any] | None = None) -> dict:
    # context contains:
    #   "agent_id": str           — which agent invoked
    #   "attempt_id": str         — execution attempt ID
    #   "emit_event": Callable    — emit audit trail events
    #   "config": dict            — per-plugin config from config.json
    pass
```

What plugins **cannot** do:

- Access LLMPort (no LLM calls)
- Access StoragePort (no persistent state)
- Access MemoryStorePort (no memory read/write)
- Access scheduler (no job scheduling)
- Run shell commands (no subprocess)
- Call other plugins (no cross-plugin deps)

---

## Plugin Standards

- Must load/unload cleanly (no side effects at import time)
- Deterministic ordering wherever selection happens
- Outputs are structured and auditable (stable JSON envelopes)
- Errors carry canonical `error_code` and actionable hints
- Network usage: explicit config flag, logged endpoints
- No secrets in logs
- Tests: unit tests for handlers, integration test for `plugin.invoke`

---

## Plugins as Pipeline Validators

Plugins serve a dual purpose beyond user-facing functionality: every plugin
execution generates events, produces results, and flows through the task
lifecycle. More diverse workloads = better observability data, better
stress-testing of the event system, and earlier discovery of core gaps.

**Evaluation criteria for new plugins:**

1. Does it generate diverse, realistic data through the pipeline?
2. Does it exercise a core capability that needs validation?
3. Can it be implemented as a stateless handler? (If not → core)
4. Is it independent of all other plugins?

---

## Existing Plugins

### `storytelling`

Reference extension. Registers narrative-mode prompt builder and story
handlers (draft/scene/import/persona/consistency/emotion/bookmark/timeline/dice).
Phases 1–7 complete; persona-extractor multimodal phase deferred. See
`docs/BACKLOG.md` for the open work.

---

## Where Things Don't Belong (Reference)

Three categories of work that were once discussed as plugins but live
elsewhere:

**Implemented as core services** (correct under any taxonomy — needed
deep core access from day one):

- **Scheduler** — `application/services/scheduler.py` (persistent
  storage, lifecycle hooks)
- **Discord** — `interfaces/discord/` (interface like CLI, full core access)
- **MoE** — `application/services/moe_execution.py` (needs LLMPort)

**Reclassified to external MCP** (under the post-2026-04-29 taxonomy,
domain integrations live in their own MCP servers):

- **Security Scanner** — `security-scan-mcp` candidate (separate repo)
  if pursued
- **Plex / Servarr / qBittorrent / Portainer** — already exist as
  `plex-mcp`, `servarr-mcp`, `downloader-mcp`, `portainer-mcp`
- **Personal finance** — `plaid-mcp` candidate if pursued
- **Google Workspace** — claude.ai built-in MCPs cover this

**Dropped as out-of-scope** (sandboxed agent platform; different product):

- Dev Agent Runner
- Serena MCP in Sandbox
- Private Git Server Integration

---

## References

- **Main Backlog:** `docs/BACKLOG.md`
- **Plugin Guide:** `docs/architecture/PLUGINS.md`
- **Architecture:** `docs/architecture/ARCHITECTURE.md`
