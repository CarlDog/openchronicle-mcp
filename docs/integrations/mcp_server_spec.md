# OpenChronicle MCP Server Interface

**Status:** Implemented
**Last Updated:** 2026-02-20

---

## Motivation

OpenChronicle's core value proposition is **durable memory and context across
sessions**. Today that value is accessible via CLI and STDIO RPC. An MCP server
interface exposes the same capabilities to any MCP-compatible agent — Goose,
Claude Desktop, VS Code Copilot, or any future client — without custom
integration code per client.

One build, multiple integrations unblocked.

## The Triangle: OC + Serena + Goose

The natural synergy between three tools:

| Tool | Role | What it knows | Persistence |
| ------ | ------ | --------------- | ------------- |
| **Serena** | Eyes | What the code **is** — symbols, references, structure | Stateless (LSP on demand) |
| **OpenChronicle** | Long-term memory | What was **decided** and **why** — memory, history, audit | Persistent (core purpose) |
| **Goose** | Hands | How to **act** — edit files, run commands, iterate | Ephemeral (session-scoped) |

```text
Goose (orchestrating agent)
  ├── Serena MCP server  →  code understanding (what IS)
  └── OC MCP server      →  persistent memory (what WAS and WHY)
```

A coding agent with architectural understanding (Serena) and institutional
memory (OC) in every session. Neither tool alone provides both.

**Upgrade path:** Eventually OC can orchestrate Goose (flip the control). That's
the Dev Agent Runner on the roadmap. The MCP server is a prerequisite either way.

---

## MCP Tools (Minimal Viable Surface)

Design principle: expose OC's existing capabilities through MCP tool semantics.
No new domain logic — this is a new interface to existing use cases, like Discord
and CLI before it.

### Project Tools

| Tool | Description | Maps to |
| ------ | ------------- | --------- |
| `project_create` | Create a new project (top-level organizer for conversations and memories) | `create_project.execute()` |
| `project_list` | List all projects | `list_projects.execute()` |

### Memory Tools

| Tool | Description | Maps to |
| ------ | ------------- | --------- |
| `memory_search` | Keyword search across memory items | `MemoryStorePort.search()` |
| `memory_save` | Store a memory item (tagged, optionally pinned) | `MemoryStorePort.save()` |
| `memory_list` | List memories (by conversation, project, or all) | `MemoryStorePort.list()` |
| `memory_pin` | Pin/unpin a memory for persistent retrieval | `MemoryStorePort.set_pinned()` |
| `memory_update` | Update content and/or tags of an existing memory | `MemoryStorePort.update_memory()` |

### Conversation Tools

| Tool | Description | Maps to |
| ------ | ------------- | --------- |
| `conversation_ask` | Send a message through OC's full pipeline (routing, memory, privacy, telemetry) | `AskConversation.execute()` |
| `conversation_history` | Retrieve recent turns for a conversation | `ConversationStorePort.get_turns()` |
| `conversation_list` | List conversations (with optional filters) | `ConversationStorePort.list()` |
| `conversation_create` | Create a new conversation | `ConversationStorePort.create()` |

### Context Tools

| Tool | Description | Maps to |
| ------ | ------------- | --------- |
| `context_recent` | Summary of recent activity on a topic/conversation — "what happened last session" | Conversation turns + memory search composite |

### System Tools

| Tool | Description | Maps to |
| ------ | ------------- | --------- |
| `health` | Health check (storage reachable, config valid) | `system.health` RPC |
| `tool_stats` | Per-tool MCP call statistics (count, latency, errors) | `SqliteStore.get_mcp_tool_stats()` |
| `moe_stats` | MoE consensus run statistics (per provider/model) | `SqliteStore.get_moe_stats()` |
| `search_turns` | Full-text search across conversation turns | `SqliteStore.search_turns()` |

### Onboarding Tools

| Tool | Description | Maps to |
| ------ | ------------- | --------- |
| `onboard_git` | Analyze git history, return commit clusters for host LLM synthesis | `git_onboard` service |

### Asset Tools

| Tool | Description | Maps to |
| ------ | ------------- | --------- |
| `asset_upload` | Upload a file as an asset (SHA-256 dedup) | `upload_asset.execute()` |
| `asset_list` | List assets in a project | `AssetStorePort.list_assets()` |
| `asset_get` | Get asset metadata and links | `AssetStorePort.get_asset()` |
| `asset_link` | Link an asset to any entity | `link_asset.execute()` |

### Tool Count

21 tools. Each maps directly to an existing port method or use case — no new
domain logic required.

---

## MCP Resources (Optional, Phase 2)

Resources provide read-only structured data that clients can subscribe to.
Lower priority than tools — tools alone are sufficient for the triangle.

| Resource URI | Description |
| --- | --- |
| `openchronicle://memory/{id}` | Individual memory item |
| `openchronicle://conversation/{id}/turns` | Conversation turn history |
| `openchronicle://events/recent` | Recent event chain entries |

---

## Architecture

### Location

```text
src/openchronicle/interfaces/mcp/
  __init__.py
  server.py          # MCP server setup, tool registration
  config.py          # MCP server configuration
  tracking.py        # Tool call statistics persistence
  tools/
    __init__.py
    memory.py         # memory_* tool handlers
    conversation.py   # conversation_* tool handlers
    context.py        # context_recent tool handler
    system.py         # health, tool_stats, moe_stats, search_turns tools
    project.py        # project_* tool handlers
    onboard.py        # onboard_git tool handler
    asset.py          # asset_* tool handlers
```

Same tier as `interfaces/cli/`, `interfaces/discord/`, `interfaces/api/`.

### Wiring

Two operational modes:

1. **In-process** (primary) — MCP server instantiates `CoreContainer` directly.
   Same pattern as the Discord driver. Lowest latency, simplest deployment.

2. **RPC proxy** (optional, later) — MCP server forwards to a running
   `oc serve` instance via STDIO RPC. Enables remote operation. Every MCP tool
   maps 1:1 to an existing RPC command.

Start with in-process. RPC proxy is a convenience for deployment scenarios where
core runs as a separate daemon.

### Dependencies

- `mcp` Python SDK (new optional extra: `pip install -e ".[mcp]"`)
- No changes to domain or application layers
- No changes to existing interfaces

### CLI Integration

```bash
# Start OC as an MCP server (stdio transport)
oc mcp serve

# Start OC as an MCP server (SSE transport, for network clients)
oc mcp serve --transport sse --port 8080
```

### Posture (Enforced by Tests)

Same rules as Discord:

- Core must remain fully functional without MCP SDK installed
- No `core.*` module imports `interfaces.mcp`
- MCP is an optional extra, all MCP imports are lazy
- Add to `test_architectural_posture.py` and `test_hexagonal_boundaries.py`

---

## Security

- **Privacy gate honored.** All `conversation_ask` calls go through the full
  pipeline including PII detection. No bypass path.
- **No secret exposure.** Memory search results never include API keys or
  credentials. Same sanitization as CLI/RPC.
- **Auth boundary.** The MCP server itself runs locally (stdio transport).
  Network transports (SSE) require explicit opt-in and should enforce
  authentication (deferred to HTTP API work).

---

## Goose Configuration (End State)

Once the MCP server exists, a user configures Goose with both servers:

```yaml
# ~/.config/goose/profiles/openchronicle.yaml (illustrative)
extensions:
  serena:
    type: stdio
    command: uvx
    args: ["serena", "start-mcp-server"]

  openchronicle:
    type: stdio
    command: oc
    args: ["mcp", "serve"]
```

Goose then has access to both code understanding and persistent memory in every
session. No custom Goose extension code required.

---

## What This Replaces

The original Goose integration spec (Backlog 5.2) assumed Goose as a sandboxed
worker orchestrated by OC. That approach requires the Dev Agent Runner to exist
first (large effort, many dependencies).

The MCP approach inverts the relationship: Goose orchestrates, OC serves. This:

- Removes the Dev Agent Runner as a prerequisite for Goose integration
- Removes the Security Scanner as a prerequisite (OC serves read/write memory,
  not executing arbitrary code)
- Unblocks value immediately after the MCP server ships
- Preserves the Dev Agent Runner as an upgrade path (OC orchestrates Goose
  later, with full audit trail)

---

## Implementation Sequence

1. Scaffold `interfaces/mcp/` with server setup and tool registration
2. Implement memory tools (highest standalone value)
3. Implement conversation tools
4. Implement context and system tools
5. CLI command (`oc mcp serve`)
6. Posture tests
7. Manual validation with Goose + Serena triangle
8. Optional: MCP resources (phase 2)

---

## Open Questions

- **Streaming.** MCP supports streaming for long-running tools.
  `conversation_ask` should stream. Confirm MCP Python SDK streaming support
  at implementation time.
- **Tool naming.** MCP tool names are flat strings. Using underscores
  (`memory_search`) vs dots (`memory.search`). Underscores are more common in
  MCP ecosystem — confirm convention.
- **Session identity.** When Goose calls `conversation_ask`, which conversation
  does it target? Options: explicit conversation ID per call, or a session
  concept where OC auto-creates/resumes. Recommend explicit ID (matches RPC
  pattern) with a `conversation_get_or_create` convenience tool.
