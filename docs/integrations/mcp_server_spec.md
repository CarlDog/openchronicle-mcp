# MCP server tool surface (v3)

OpenChronicle's MCP server exposes 14 tools. They map 1:1 with the
HTTP REST surface (same use cases under both transports). All tools
return JSON-safe Python dicts; the FastMCP runtime handles
serialization to MCP's wire format.

For client setup see `docs/integrations/mcp_client_setup.md`. For
stability guarantees see `docs/api/STABILITY.md`.

## Memory

| Tool | Purpose |
|---|---|
| `memory_save` | Persist a memory item that should outlive the current session. `project_id` required. |
| `memory_search` | Hybrid FTS5 + semantic search via RRF, scoped optionally by `project_id` and `tags`. |
| `memory_list` | Browse memory items in reverse-chronological order (unfiltered pagination). |
| `memory_get` | Fetch one memory by ID. |
| `memory_update` | Edit content/tags in place; preserves identity. |
| `memory_delete` | Hard delete. |
| `memory_pin` | Toggle pin state. |
| `memory_stats` | Counts + per-tag/per-source breakdown. |
| `memory_embed` | Generate missing (or all, with `force=true`) embeddings. |

The `memory_save` tool's input schema is the canonical "what does an
LLM need to write a memory" shape:

```json
{
  "content": "string, 1-100000 chars",
  "project_id": "string, required",
  "tags": ["decision", "rejected", "milestone", "context", "convention", "scope"],
  "pinned": false,
  "created_at": "ISO datetime, optional (for backdated imports)"
}
```

## Project

| Tool | Purpose |
|---|---|
| `project_create` | Create a new project namespace. |
| `project_list` | List every project. |

## Context

| Tool | Purpose |
|---|---|
| `context_recent` | Catch-up on prior context for a project. Returns recent memory items, optionally filtered by a `query` keyword. Use at session start (especially post-compression). |

## Onboarding

| Tool | Purpose |
|---|---|
| `onboard_git` | Clone a remote git repo shallow into a server-side tmpdir, cluster commits, and return per-cluster summaries the caller synthesizes into memories. |

## System

| Tool | Purpose |
|---|---|
| `health` | Probe server state: DB reachability, config, embedding subsystem status, maintenance degraded flag, package version. |

## Tool design philosophy

Each tool's docstring answers "when would I call this vs the others?"
not "what does this do?" — the LLM's tool selection improves
dramatically when descriptions discriminate the choice. Concretely:

- `memory_search` vs `memory_list`: search when you have keywords;
  list for unfiltered pagination.
- `memory_search` vs `context_recent`: search for specific keywords;
  context_recent for "what was I working on last?"
- `memory_save` vs `memory_update`: save creates a new ID + timestamp;
  update preserves identity. Edits revise in place.
- `memory_delete` vs `memory_update`: delete is permanent; update
  revises. Don't use delete-then-save when revising — that loses the
  original `created_at`.
- `memory_pin`: changes pin state only; doesn't touch content/tags
  (use `memory_update` for those).

## Cut from v2

These v2 MCP tools were dropped along with their subsystems:

- `conversation_create` / `conversation_list` / `conversation_history`
  / `conversation_ask` / `conversation_set_mode` /
  `conversation_get_mode` — conversation engine archived.
- `turn_record` / `context_assemble` — depended on conversation/turn
  storage.
- `search_turns` — turns table is gone.
- `tool_stats` / `moe_stats` — telemetry archived (V3_PLAN Q8).
- `asset_*` / `webhook_*` / `media_generate` — subsystems archived.

If a future project needs any of these, copy from
`archive/openchronicle.v2`.

## See also

- `docs/integrations/mcp_client_setup.md` — wiring up Claude Code,
  Goose, etc.
- `docs/cli/commands.md` — CLI commands that mirror these tools
- `docs/api/STABILITY.md` — what's stable across versions
