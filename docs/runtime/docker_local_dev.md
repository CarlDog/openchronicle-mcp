# Docker Local Development Workflow

Build and run OpenChronicle from source using Docker Compose.

## Prerequisites

- Docker and Docker Compose v2 installed
- External config directory with model configs and API keys
  (e.g., `C:\Docker\openchronicle\config\` on Windows)

## Quick Start

```bash
# Build from source, tagged :dev
docker compose -f docker-compose.yml -f docker-compose.dev.yml build

# Start the HTTP API server
docker compose -f docker-compose.yml -f docker-compose.dev.yml up serve
```

The API server listens on `http://localhost:8000`.

## Services

| Service | Command | Use |
|---|---|---|
| `serve` | `oc serve --http-only` | HTTP API + daemon (default) |
| `openchronicle` | `oc <command>` | One-shot CLI commands |
| `discord` | `oc discord start` | Discord bot (long-running) |
| `mcp` | `oc mcp serve` | MCP server (stdio) |

## External Config

Mount your config directory (containing `core.json` and `models/*.json`)
into the container:

```bash
# Override config volume with a bind mount
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
  run -v /path/to/config:/config serve
```

Or set `OC_CONFIG_DIR` in a `.env` file (git-ignored):

```env
OC_LLM_PROVIDER=openai
```

## Running CLI Commands

```bash
# Run any oc command via the openchronicle service
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
  run --rm openchronicle version

docker compose -f docker-compose.yml -f docker-compose.dev.yml \
  run --rm openchronicle selftest --json
```

## Rebuild After Changes

```bash
# Rebuild and restart
docker compose -f docker-compose.yml -f docker-compose.dev.yml build
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d serve
```

## Data Persistence

Named volumes persist data across restarts:

| Volume | Container path | Content |
|---|---|---|
| `oc-data` | `/data` | SQLite database |
| `oc-config` | `/config` | Configuration files |
| `oc-output` | `/output` | Report output files |
| `oc-assets` | `/assets` | Asset file storage |

The `plugins/` directory is bind-mounted from the repo.

## Troubleshooting

**Image not found:** Make sure you ran the build step with both
compose files specified.

**Config directory not found:** The container expects `/config` to
exist. Either use the named volume or bind-mount your config directory.

**Database locked:** Only one service should write to the database at a
time. Stop other services before running CLI commands that write.

## Related

- [Docker MVP runtime](docker_mvp.md) — single-container quick start
- [CLI command reference](../cli/commands.md) — all `oc` subcommands
