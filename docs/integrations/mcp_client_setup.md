# OC MCP Server — Client Setup Guide

OpenChronicle exposes persistent memory and conversation capabilities via
[Model Context Protocol](https://modelcontextprotocol.io/). Any
MCP-compatible agent can connect to OC without custom integration code.

**Prerequisites:**

- OC installed: `pip install -e ".[mcp]"`
- `oc mcp serve` runs without errors

---

## Claude Code

Claude Code is already configured in this repository. The config lives in
`.claude/settings.json`:

```json
{
  "mcpServers": {
    "openchronicle": {
      "command": "oc",
      "args": ["mcp", "serve"]
    }
  }
}
```

No additional setup needed. OC tools appear automatically in Claude Code
sessions when working in this repo.

---

## Goose

[Goose](https://github.com/block/goose) is an open-source AI agent with
native MCP support. Add OC as a stdio extension in your Goose config.

**Config file:** `~/.config/goose/config.yaml`

Add to the `extensions` section:

```yaml
extensions:
  openchronicle:
    type: stdio
    command: "oc"
    args: ["mcp", "serve"]
    timeout: 300
```

To use OC alongside Serena for the full triangle (memory + code
understanding + agent execution):

```yaml
extensions:
  openchronicle:
    type: stdio
    command: "oc"
    args: ["mcp", "serve"]
    timeout: 300
  serena:
    type: stdio
    command: "serena"
    args: ["--config", "/path/to/serena/config.yaml"]
    timeout: 300
```

**Verify:** Start a Goose session and run a memory operation:

```text
> save a memory: "Goose integration is working"
> search memories for "Goose"
```

---

## VS Code

VS Code supports MCP servers natively via Copilot. Add OC as a local
stdio server.

**Option 1 — Workspace config** (shared via source control):

Create `.vscode/mcp.json` in your project:

```json
{
  "servers": {
    "openchronicle": {
      "command": "oc",
      "args": ["mcp", "serve"]
    }
  }
}
```

**Option 2 — User config** (global, all projects):

Run the command palette action `MCP: Open User Configuration` and add the
same server block.

**Verify:** Open the Copilot chat and confirm OC tools are listed.

---

## SSE Transport (Remote / Multi-Client)

For scenarios where multiple clients need to share one OC instance (e.g.,
running OC on a server), use SSE transport instead of stdio:

```bash
oc mcp serve --transport sse --port 8080
```

Then configure clients to connect via HTTP:

**Goose (SSE):**

```yaml
extensions:
  openchronicle:
    type: sse
    uri: "http://localhost:8080/sse"
```

**VS Code (HTTP):**

```json
{
  "servers": {
    "openchronicle": {
      "type": "http",
      "url": "http://localhost:8080/sse"
    }
  }
}
```

---

## Available Tools

Once connected, MCP clients have access to all 26 OC tools:

| Category | Tools |
| -------- | ----- |
| Memory | `memory_save`, `memory_search`, `memory_list`, `memory_pin`, `memory_update`, `memory_get`, `memory_delete`, `memory_stats` |
| Conversation | `conversation_create`, `conversation_list`, `conversation_history`, `conversation_ask`, `turn_record`, `context_assemble` |
| Context | `context_recent`, `search_turns` |
| Project | `project_create`, `project_list` |
| Asset | `asset_upload`, `asset_list`, `asset_get`, `asset_link` |
| System | `health`, `tool_stats`, `moe_stats` |
| Onboard | `onboard_git` |

See [`mcp_server_spec.md`](mcp_server_spec.md) for full tool documentation.

---

## Troubleshooting

**"command not found: oc"** — Ensure OC is installed and `oc` is on your
PATH. If installed in a virtualenv, use the full path:

```json
{
  "command": "/path/to/venv/bin/oc",
  "args": ["mcp", "serve"]
}
```

**Tools not appearing** — Check that the `[mcp]` extra is installed:
`pip install -e ".[mcp]"`. The MCP server requires `mcp>=1.0.0`.

**Connection timeout** — Increase the timeout in your client config.
Default Goose timeout is 300s. For SSE, ensure the port is not blocked.
