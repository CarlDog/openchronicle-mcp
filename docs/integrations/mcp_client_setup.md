# Connecting MCP clients to OpenChronicle v3

OpenChronicle v3 exposes its memory tools via the
[Model Context Protocol](https://modelcontextprotocol.io). The MCP
transport is mounted at `/mcp` on the same port as the HTTP REST API
(default `:8000`, host-mapped to `:18000` in the NAS Docker compose).
Any MCP-aware client speaks streamable-HTTP to that endpoint.

## Prerequisite for a non-loopback server

If clients reach OpenChronicle by anything other than `localhost` /
`127.0.0.1`, the server must allow that hostname or **every request
returns 421**. The MCP transport validates the `Host` header as a
DNS-rebinding defense, and an operator allowlist **replaces** the
default loopback set rather than adding to it — so keep the loopback
entries or you trade a 421 for remote clients for a 421 on localhost
(which also breaks the container healthcheck):

```bash
OC_MCP_ALLOWED_HOSTS=your-nas:*,127.0.0.1:*,localhost:*
```

See [env_vars.md](../configuration/env_vars.md) for the matching rules.

## Claude Code

User-scope (recommended, available in every session):

```bash
claude mcp add --scope user --transport http openchronicle \
    http://your-nas:18000/mcp
```

Replace `your-nas` with the host where OC is reachable.
`localhost:18000/mcp` for a same-machine deployment.

The config ends up in `~/.claude.json` under `mcpServers`. To verify
it's wired up, ask Claude Code to call `health` and look at the OC
runtime status that comes back.

## Goose

```yaml
# ~/.config/goose/config.yaml
extensions:
  openchronicle:
    type: streamable-http
    url: http://your-nas:18000/mcp
    timeout: 300
```

## Open WebUI

Open WebUI v0.6.31 and later speaks native MCP over Streamable HTTP,
so it can use `http://your-nas:18000/mcp` directly. It supports MCP
tools but not MCP prompts. The OpenAPI tool-server route still works
too: register `http://your-nas:18000` and Open WebUI pulls the spec
from `/openapi.json`.

## Authenticated deployments

When `OC_API_KEY` is set, MCP clients must include the bearer token:

```bash
claude mcp add --scope user --transport http \
    --header "Authorization: Bearer $OC_API_KEY" \
    openchronicle http://your-nas:18000/mcp
```

Goose:

```yaml
extensions:
  openchronicle:
    type: streamable-http
    url: http://your-nas:18000/mcp
    headers:
      Authorization: Bearer ${OC_API_KEY}
```

### Other clients (verified 2026-09-28)

Production has required the key since 2026-09-25. Each client below was
configured on a second workstation and passed OpenChronicle's `health` tool
(ROADMAP OPS-06). Formats were checked against each client's documentation on
that date; re-check a client's docs if one stops connecting after an update.
Use the hostname `your-nas` (or `your-nas.local`), never the NAS's IP address:
the Host-header allowlist answers anything else with 421. A 401 means the key
is not being sent.

- **Claude Desktop.** Custom connectors connect from Anthropic's cloud, which
  cannot reach a LAN host, so use the `mcp-remote` bridge (needs Node.js) in
  `%APPDATA%\Claude\claude_desktop_config.json`. Keep `Authorization:${AUTH_HEADER}`
  without a space after the colon: passing the value through an env var is how
  mcp-remote's docs avoid a Windows argument-quoting bug. Fully restart after editing.

  ```json
  {"mcpServers":{"openchronicle":{"command":"npx","args":["-y","mcp-remote","http://your-nas:18000/mcp","--allow-http","--transport","http-only","--header","Authorization:${AUTH_HEADER}"],"env":{"AUTH_HEADER":"Bearer YOUR_KEY_HERE"}}}}
  ```

- **OpenAI Codex** (`%USERPROFILE%\.codex\config.toml`). The key stays in an
  environment variable (`setx OC_API_KEY "..."`, then a new shell):

  ```toml
  [mcp_servers.openchronicle]
  url = "http://your-nas:18000/mcp"
  bearer_token_env_var = "OC_API_KEY"
  ```

- **Gemini CLI.** `httpUrl` is Streamable HTTP; `url` means SSE.

  ```bash
  gemini mcp add --transport http -H "Authorization: Bearer YOUR_KEY_HERE" openchronicle http://your-nas:18000/mcp
  ```

- **Google Antigravity** (`%USERPROFILE%\.gemini\config\mcp_config.json`, a
  different file and key from Gemini CLI):

  ```json
  {"mcpServers":{"openchronicle":{"serverUrl":"http://your-nas:18000/mcp","headers":{"Authorization":"Bearer YOUR_KEY_HERE"}}}}
  ```

- **VS Code** (*MCP: Open User Configuration*). The top-level key is
  `servers`, and the key is prompted for once and masked:

  ```json
  {"inputs":[{"type":"promptString","id":"oc-key","description":"OpenChronicle API key","password":true}],
   "servers":{"openchronicle":{"type":"http","url":"http://your-nas:18000/mcp","headers":{"Authorization":"Bearer ${input:oc-key}"}}}}
  ```

- **Visual Studio 2022 17.14+ / 2026** (`%USERPROFILE%\.mcp.json`). Its docs
  do not mention `headers`, but it reads the VS Code format, and this worked.
  Enable the tools afterwards in Chat → Agent → Tools; they start disabled.

  ```json
  {"servers":{"openchronicle":{"type":"http","url":"http://your-nas:18000/mcp","headers":{"Authorization":"Bearer YOUR_KEY_HERE"}}}}
  ```

Claude Desktop, Antigravity and Visual Studio hold the key in plain text in
their config files; Codex (environment variable) and VS Code (masked prompt)
do not. After a key rotation, update every one of these.

## Local development

`oc serve` from a checkout binds to `127.0.0.1:8000` by default, so:

```bash
claude mcp add --scope user --transport http openchronicle \
    http://127.0.0.1:8000/mcp
```

For stdio transport (no HTTP, no networking), set
`OC_MCP_TRANSPORT=stdio python -m openchronicle.interfaces.mcp`. Note that
`oc serve` does **not** read `OC_MCP_TRANSPORT` — it always builds the
unified ASGI app and binds a port, mounting `/mcp` regardless — so the
module entry point above is the only one that honours the variable.
Most clients today prefer streamable-http over stdio.

## Verifying the connection

From the client side, the simplest check is to call the `health` MCP
tool. The response includes:

- `db_path`, `db_exists`, `db_modified_utc` — storage reachability
- `embedding_status.status` — `active` / `degraded` / `disabled` / `failed`; `degraded` also while the model revision is unverified
- `embedding_status.unembeddable` — rows parked as permanently
  over-length for the current model (ADR 0009); parked rows are not
  failures and do not make `status` read `degraded`
- `embedding_status.model_revision_state` — `known`, `none` or
  `unknown`; while `unknown`, no embedding is written (ADR 0005 §7)
- `package_version` — confirms the version the client is talking to
- `maintenance_degraded` — `true` if the integrity-check job has
  failed since the last successful run (the database may be corrupt)
- `backup_last_run_failed` — `true` if the last scheduled backup failed.
  Usually the backup root needs attention, and that is not a reason to
  restore. But if the maintenance status error names `integrity_check`,
  `foreign_key_check` or `quick_check`, the live database failed its checks:
  run the integrity check before anything else (see
  [security_posture.md](../configuration/security_posture.md#incident-response)).

From the server side:

```bash
curl -fsS http://127.0.0.1:8000/health
# {"status": "ok"}

curl -fsS http://127.0.0.1:8000/api/v1/health | jq .embedding_status
```

## Migrating from v2

v2 clients pointed at `:18001/mcp` (the separate MCP service). v3
collapses MCP onto the HTTP port. Update each client's config:

```diff
- url: http://your-nas:18001/mcp
+ url: http://your-nas:18000/mcp
```

After updating, restart the client (Claude Code caches tool
definitions on session start; a config edit alone is not enough).

## See also

- `docs/integrations/mcp_server_spec.md` — full tool surface
- `docs/api/STABILITY.md` — what's guaranteed across versions
