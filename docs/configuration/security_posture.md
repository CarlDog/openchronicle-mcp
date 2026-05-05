# Security posture

OpenChronicle v3 is a single-user, single-tenant memory store deployed
on the operator's own hardware. The threat model is correspondingly
narrow: lateral access from compromised LAN tools, accidental exposure
of secrets in logs, and DB corruption from operational mistakes.

## Authentication

- HTTP REST: optional bearer token via `OC_API_KEY`. When unset, the
  API is open to anything that can reach the port — fine for a
  loopback-only deployment, but anyone exposing the port to a LAN
  must set this.
- MCP: inherits the HTTP auth middleware. Clients must include
  `Authorization: Bearer <key>` (or `X-API-Key: <key>`) when the
  server is configured with a key.
- `/health` and `/openapi.json` are exempt from auth on purpose —
  liveness probes and tool discovery shouldn't require credentials.

## Transport

- The image binds the unified ASGI app to plain HTTP. TLS termination
  is the operator's job (Synology reverse proxy, Caddy, Nginx, etc.).
- The streamable-HTTP MCP transport is HTTP/1.1; if the operator wants
  WebSocket-style upgrades for an MCP client that requires them, the
  reverse proxy handles that.

## Data at rest

- The SQLite file lives in the `oc-data` named volume. Operators
  cannot bind-mount it to a host path — this is a deliberate
  protection against accidentally placing the WAL on a filesystem
  that doesn't fsync correctly (the lesson from the 2026-04-29
  bind-mount WAL incident).
- Backups go to `${OC_DATA_DIR}/backups/auto/` (also inside the
  volume). The backup module uses `sqlite3.Connection.backup()` with
  atomic `.tmp`→rename, so no half-written backup files exist on
  disk.

## Secrets in logs

- `oc config show` masks any env var whose name contains `KEY`,
  `SECRET`, `TOKEN`, or `PASSWORD` (case-insensitive) before printing.
  See `interfaces/cli/commands/system.py:_mask_secret`.
- `OC_LOG_FORMAT=json` mode includes the message verbatim — operators
  must not log raw secrets in their own code (the `logging_setup.py`
  formatter does not redact them).

## Dependencies

- v3 ships with a small dependency footprint: FastAPI, Starlette,
  uvicorn, the MCP SDK, and (for embeddings) the OpenAI / Ollama
  clients when the operator opts in. v2's anthropic / groq /
  google-generativeai / discord.py / fastmcp-tied LLM stack is gone.
- `pyproject.toml` keeps optional extras for embedding providers
  only: `[openai]`, `[ollama]`, `[mcp]`. The `[discord]` extra is
  removed.
- `pip-audit` against the runtime image catches CVEs in the slimmer
  set; run periodically.

## Container hardening

The Dockerfile keeps the v2 hardening choices that still apply:

- `python:3.11-slim` base, not `:latest`, for reproducibility.
- `--no-cache-dir` on `pip install` to avoid bloat.
- `apt-get` clean of `/var/lib/apt/lists/*` after installing `git`.
- The image runs as root by default (the same as v2). Future work:
  add a non-root `oc` user. Tracked but not in scope for v3.0.0.

## Network

- The `docker-compose.nas.yml` exposes one host port (default
  `18000:8000`). Set `HOST_HTTP_PORT` to relocate.
- `extra_hosts: host.docker.internal:host-gateway` lets the container
  reach Ollama running on the NAS host. No reverse direction.

## What we don't do (out of scope)

- **No multi-user / per-user namespacing.** Projects partition the
  keyspace, but every memory belongs to whoever has the API key.
- **No audit log / event chain.** v2 had hash-chained events; v3
  doesn't. Backups are the recovery mechanism. If audit becomes
  important, the events table from V3_PLAN open question 2 returns
  with a real consumer.
- **No rate limiting beyond the existing `OC_API_RATE_LIMIT_RPM`.**
  Ingest backpressure (V3_PLAN open question 17) is on the backlog
  but not implemented.

## Incident response

- DB corruption: the maintenance loop's `db_integrity_check` job
  detects it on a 7-day cadence, takes an emergency backup, and flips
  `/health` to `maintenance_degraded: true`. Operators restore from
  `${OC_DATA_DIR}/backups/auto/` (or a manual `oc db backup` taken
  earlier).
- Embedding provider compromise: rotate the relevant API key and
  redeploy. The degradation policy keeps search working
  (FTS5-only) until the new key is in place.
- Lost API key: read it back from `oc config show --json` (it's
  masked in human output but full in JSON) on the host, or rotate by
  setting a new `OC_API_KEY` in the Portainer stack and redeploying.

## See also

- `docs/architecture/MAINTENANCE.md` — degraded-state surfacing
- `docs/configuration/env_vars.md` — full env var inventory
- `archive/openchronicle.v2` — v2 incident notes lived here pre-rewrite
