# `core.json`

OpenChronicle v3 reads exactly one config file: `${OC_CONFIG_DIR}/core.json`.
v2's per-section files (model configs, router configs, plugin configs)
are gone with the subsystems they configured.

The file is optional. When absent, every section uses dataclass
defaults; env vars still apply.

## Schema

```json
{
  "embedding": {
    "provider": "openai",
    "model": "text-embedding-3-small",
    "dimensions": 1536,
    "timeout": 30.0
  },
  "api": {
    "host": "0.0.0.0",
    "port": 8000,
    "api_key": ""
  },
  "mcp": {
    "transport": "streamable-http",
    "host": "0.0.0.0",
    "port": 8080,
    "server_name": "openchronicle"
  },
  "maintenance": {
    "jobs": [
      {"name": "db_vacuum",          "interval_seconds": 604800, "enabled": true},
      {"name": "db_integrity_check", "interval_seconds": 604800, "enabled": true},
      {"name": "embedding_backfill", "interval_seconds": 21600,  "enabled": true},
      {"name": "db_backup",          "interval_seconds": 86400,  "enabled": true},
      {"name": "git_onboard_resync", "interval_seconds": 3600,   "enabled": false}
    ]
  }
}
```

Every key is optional. Env vars override individual values:
`OC_EMBEDDING_PROVIDER`, `OC_API_PORT`, `OC_MCP_HOST`, etc. — see
`docs/configuration/env_vars.md`.

## Sections

### `embedding`

Configures the embedding provider for hybrid memory search. When
`provider` is `none` (the default), search is FTS5-only.

| Key | Type | Default |
|---|---|---|
| `provider` | `none` / `stub` / `openai` / `ollama` | `none` |
| `model` | string | provider default |
| `dimensions` | int | provider default |
| `timeout` | float | `30.0` |
| `api_key` | string | (env var) |

### `api`

HTTP REST surface configuration.

| Key | Type | Default |
|---|---|---|
| `host` | bind address | `127.0.0.1` |
| `port` | int | `8000` |
| `api_key` | bearer token (auth disabled when unset/empty) | — |
| `allowed_hosts` | list of `Host:` patterns for the DNS-rebinding allowlist; `OC_API_ALLOWED_HOSTS` overrides it | loopback only |

### `mcp`

MCP server configuration. Within `oc serve` the streamable-HTTP MCP
transport is mounted into the FastAPI app at `/mcp` and shares the
`api.port`; this section is for the standalone-MCP code path used by
older clients pinning `:8080`.

It also reads `allowed_hosts` (same shape and purpose as `api.allowed_hosts`,
overridden by `OC_MCP_ALLOWED_HOSTS`). Both loaders read the key from the
file, so the rebinding allowlist is configurable without an env var —
which was not discoverable from this document before 2026-08-28.

### `maintenance`

Maintenance loop schedule. The `jobs` list **merges onto the built-in
defaults** — an entry overrides the matching default by name, and any job
it omits keeps its default rather than being dropped. Omitting a job does
not disable it; set `"enabled": false` explicitly. Unknown job names are
skipped with a warning. See `docs/architecture/MAINTENANCE.md`.

## See also

- `docs/configuration/env_vars.md`
- `docs/architecture/MAINTENANCE.md`
