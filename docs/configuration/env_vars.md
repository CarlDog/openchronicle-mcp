# Environment variables

OpenChronicle v3 reads configuration from environment variables and an
optional `core.json` file. Env vars always win, then `core.json` keys,
then dataclass defaults.

The total surface is small (~15 vars). v2's LLM provider keys, MoE pool
config, Discord settings, and routing knobs are gone with the
subsystems they configured.

## Storage paths

| Var | Purpose | Default |
|---|---|---|
| `OC_DATA_DIR` | Root data directory. Per-path vars below derive from this when they're unset. | *(unset)* |
| `OC_DB_PATH` | SQLite file location | `data/openchronicle.db` |
| `OC_CONFIG_DIR` | Directory containing `core.json` | `config` |
| `OC_OUTPUT_DIR` | Directory for operator-export artifacts | `output` |

The four-layer precedence (constructor arg > per-path env > `OC_DATA_DIR`-derived > default) is implemented in
`application/config/paths.py:RuntimePaths.resolve`.

## Embeddings

| Var | Purpose | Default |
|---|---|---|
| `OC_EMBEDDING_PROVIDER` | `none` (FTS5-only), `stub`, `openai`, `ollama` | `none` |
| `OC_EMBEDDING_MODEL` | Provider-specific model name | *(provider default)* |
| `OC_EMBEDDING_DIMENSIONS` | Override dimensions (must match the model) | *(provider default)* |
| `OC_EMBEDDING_API_KEY` | Explicit override; falls back to provider-specific env | — |
| `OC_EMBEDDING_TIMEOUT` | Per-request timeout in seconds | `30.0` |
| `OPENAI_API_KEY` | Used by the OpenAI embedding adapter | — |
| `OLLAMA_HOST` | Ollama base URL (e.g. `http://localhost:11434`) | adapter default |

When the embedding provider raises during a search, `EmbeddingService`
falls back to FTS5-only and surfaces `"status": "degraded"` from
`/api/v1/health`. Backfill via the maintenance loop's
`embedding_backfill` job (default every 6 hours) catches up missing
embeddings when the provider recovers.

## HTTP API

| Var | Purpose | Default |
|---|---|---|
| `OC_API_HOST` | Bind address | `127.0.0.1` |
| `OC_API_PORT` | Listen port | `8000` |
| `OC_API_KEY` | Bearer token for auth (auth is disabled if unset) | — |
| `OC_API_RATE_LIMIT_RPM` | Per-IP request-per-minute limit | `60` |

`/health` and `/openapi.json` are exempt from auth even when
`OC_API_KEY` is set.

## MCP

| Var | Purpose | Default |
|---|---|---|
| `OC_MCP_TRANSPORT` | `stdio`, `sse`, `streamable-http` (host-mounted MCP uses streamable-http inside the unified ASGI) | `stdio` |
| `OC_MCP_HOST` | Bind address for stdio-detached MCP server | `127.0.0.1` |
| `OC_MCP_PORT` | Listen port for stdio-detached MCP server | `8080` |

Within `oc serve`, the MCP transport is mounted on the same port as
the HTTP API at `/mcp` — `OC_MCP_HOST`/`OC_MCP_PORT` are unused.

## Logging

| Var | Purpose | Default |
|---|---|---|
| `OC_LOG_FORMAT` | `human` (Python default formatter) or `json` (one JSON object per line, suitable for Loki/OpenSearch/Datadog) | `human` |
| `OC_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |

## Maintenance loop

| Var | Purpose | Default |
|---|---|---|
| `OC_MAINTENANCE_DISABLED` | `1`/`true`/`yes`/`on` short-circuits the loop entirely | unset (loop runs) |

Job-level intervals and enabled flags live in `core.json`'s
`maintenance.jobs` section. See `docs/architecture/MAINTENANCE.md`.

## Search

| Var | Purpose | Default |
|---|---|---|
| `OC_SEARCH_FTS5_ENABLED` | `0` to skip FTS5 setup (forces fallback keyword search) | `1` |

## Git onboarding

| Var | Purpose | Default |
|---|---|---|
| `OC_GIT_TOKEN` | GitHub PAT (fine-grained, `contents:read`) for the `onboard_git` MCP tool to clone private repos | — |

## See also

- `docs/configuration/config_files.md` — `core.json` schema
- `docs/architecture/MAINTENANCE.md` — maintenance loop config
- `docs/configuration/security_posture.md` — secrets handling
