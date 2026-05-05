# Connecting MCP clients to OpenChronicle v3

OpenChronicle v3 exposes its memory tools via the
[Model Context Protocol](https://modelcontextprotocol.io). The MCP
transport is mounted at `/mcp` on the same port as the HTTP REST API
(default `:8000`, host-mapped to `:18000` in the NAS Docker compose).
Any MCP-aware client speaks streamable-HTTP to that endpoint.

## Claude Code

User-scope (recommended, available in every session):

```bash
claude mcp add --scope user --transport http openchronicle \
    http://carldog-nas:18000/mcp
```

Replace `carldog-nas` with the host where OC is reachable.
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
    url: http://carldog-nas:18000/mcp
    timeout: 300
```

## Open WebUI

Open WebUI's tool-server integration speaks the OpenAI tool-server
protocol over HTTP, not native MCP. Use the REST surface instead —
register `http://carldog-nas:18000` as an OpenAPI-backed tool server
and Open WebUI will pull the spec from `/openapi.json`.

## Authenticated deployments

When `OC_API_KEY` is set, MCP clients must include the bearer token:

```bash
claude mcp add --scope user --transport http \
    --header "Authorization: Bearer $OC_API_KEY" \
    openchronicle http://carldog-nas:18000/mcp
```

Goose:

```yaml
extensions:
  openchronicle:
    type: streamable-http
    url: http://carldog-nas:18000/mcp
    headers:
      Authorization: Bearer ${OC_API_KEY}
```

## Local development

`oc serve` from a checkout binds to `127.0.0.1:8000` by default, so:

```bash
claude mcp add --scope user --transport http openchronicle \
    http://127.0.0.1:8000/mcp
```

For stdio transport (no HTTP, no networking), set
`OC_MCP_TRANSPORT=stdio` and run `oc serve` — the unified ASGI app
won't actually start; this remains as the legacy single-purpose path.
Most clients today prefer streamable-http over stdio.

## Verifying the connection

From the client side, the simplest check is to call the `health` MCP
tool. The response includes:

- `db_path`, `db_exists`, `db_modified_utc` — storage reachability
- `embedding_status.status` — `active` / `degraded` / `disabled` / `failed`
- `package_version` — confirms the version the client is talking to
- `maintenance_degraded` — `true` if the integrity-check job has
  failed since the last successful run

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
- url: http://carldog-nas:18001/mcp
+ url: http://carldog-nas:18000/mcp
```

After updating, restart the client (Claude Code caches tool
definitions on session start; a config edit alone is not enough).

## See also

- `docs/integrations/mcp_server_spec.md` — full tool surface
- `docs/api/STABILITY.md` — what's guaranteed across versions
