# Security posture

OpenChronicle v3 is a single-user, single-tenant memory store deployed
on the operator's own hardware. The threat model is correspondingly
narrow: lateral access from compromised LAN tools, accidental exposure
of secrets in logs, and DB corruption from operational mistakes.

## Authentication

OC supports bearer-token auth via `OC_API_KEY` but does not require it.
Whether to enable it is an operator decision, deliberately deferred to
deployment context.

**Defaults:**

- HTTP REST: optional bearer token via `OC_API_KEY`. When unset (or
  empty), the API is open to anything that can reach the port.
- MCP: inherits the HTTP auth middleware. Clients must include
  `Authorization: Bearer <key>` (or `X-API-Key: <key>`) when the server
  is configured with a key.
- Auth-exempt paths, deliberately: `/health` and `/api/v1/health`
  (liveness + diagnostics probes), plus the OpenAPI surface (`/docs`,
  `/redoc`, `/openapi.json` — tool discovery shouldn't require
  credentials). Everything else, including the mounted `/mcp`
  transport, requires the key when one is configured. Caveat worth
  knowing: `/api/v1/health` includes absolute filesystem paths
  (`db_path`, `config_dir`) — acceptable on the trusted LAN, worth
  revisiting if the port is ever exposed.

**When to leave auth disabled (`OC_API_KEY` empty):**

- Loopback-only (`127.0.0.1`) deployments.
- Single-user home-LAN deployments where the LAN is trusted (no guest
  network with NAS visibility, no untrusted IoT VLAN with reachable
  routes, no cohabitating users you don't want reading your memory).
  This is the original target use case and is acceptable when the
  trust boundary genuinely matches the network boundary.

**When to enable auth (set `OC_API_KEY`):**

- Any deployment reachable from beyond the trusted LAN — public
  internet, reverse-proxied through a public hostname, exposed via a
  port-forward.
- Multi-user environments (even cohabitating-but-different-trust users
  on the same LAN).
- Anywhere "anyone who can reach the port can read/write all your
  memories" is unacceptable.

**How to enable auth on a running deployment:**

1. Generate a key (don't reuse an existing secret):

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. Set it on the Portainer stack (this triggers a redeploy):

   ```text
   Stacks → openchronicle-mcp → Environment variables → OC_API_KEY
   ```

   Or programmatically via portainer-mcp:
   `portainer_set_stack_env(stack_id=151, set=[{name:"OC_API_KEY", value:"<key>"}], confirm=true)`.

3. Update every client to send the bearer header. For MCP clients
   that don't natively support custom headers, prefer placing the OC
   server behind a reverse proxy that injects the header on their
   behalf, or accept that those clients won't work auth-enabled.

4. Rotate by setting a new value and redeploying; old keys are
   invalidated immediately on container restart (no in-DB key
   storage; the env var is the source of truth).

**Current stable deployment:** the NAS stack at `your-nas:18000`
is configured with `OC_API_KEY` empty (auth disabled) — single-user
home-LAN deployment, intentional, documented per the lessons from the
2026-05-06 cutover. If that trust boundary changes, follow the steps
above.

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
- Backups go to the resolved DB path's directory + `/backups/auto/`
  (`/data/backups/auto/` on the NAS deployment, which sets
  `OC_DB_PATH=/data/openchronicle.db`; also inside the volume). The backup module uses `sqlite3.Connection.backup()` with
  atomic `.tmp`→rename, so no half-written backup files exist on
  disk.

## Secrets in logs

- `oc config show` inspects `OC_*` env vars and masks any whose name
  contains `KEY`, `SECRET`, `TOKEN`, or `PASSWORD` (case-insensitive)
  before printing in either human or JSON form. See
  `interfaces/cli/commands/system.py:_mask_secret`.
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

Hardened 2026-07-30 (the review-driven CI batch):

- `python:3.14-slim` base, not `:latest`, for reproducibility.
- Multi-stage build — the runtime stage copies only the venv, never
  pip caches or build tooling.
- **Runs as the non-root `oc` user** (uid 1000): the entrypoint starts
  as root only long enough to chown the mount points (self-healing
  volumes that predate this change), then drops via `gosu`.
- `HEALTHCHECK` probes `/health` from inside the container.
- `--no-cache-dir` on `pip install`; `apt-get` lists cleaned after
  installing `git` + `gosu`.

## Network

- The `docker-compose.nas.yml` exposes one host port (default
  `18000:8000`). Set `HOST_HTTP_PORT` to relocate.
- `extra_hosts: host.docker.internal:host-gateway` lets the container
  reach Ollama running on the NAS host. No reverse direction.
- **DNS-rebinding defense: Host-header allowlists on both surfaces.**
  A containerized service can't be secured by its bind address (it
  binds `0.0.0.0` to be reachable at all), and a malicious web page
  can reach it via DNS rebinding — which makes the request same-origin
  in the browser, so CORS never applies. Both transports validate the
  `Host:` header instead: FastMCP's transport security guards `/mcp`
  (`OC_MCP_ALLOWED_HOSTS`), and `HostAllowlistMiddleware` guards the
  REST surface (`OC_API_ALLOWED_HOSTS`, falling back to
  `OC_MCP_ALLOWED_HOSTS` so the one stack variable protects both).
  Defaults are loopback-only; rejections are 421. Loopback hosts are
  always allowed on the REST side so the container-internal
  HEALTHCHECK survives any operator allowlist. Added 2026-08-16 —
  before that the REST surface had no Host validation at all.

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

## Author email in commit metadata — CLOSED, do not re-raise

**Decided 2026-08-28. This is settled. It is not an open item, not a
backlog entry, and not an audit finding. Do not surface it again.**

540 of 779 commits reachable from `main` carry a personal-domain email in
their author and/or committer fields, spanning 2025-07-15 to 2026-07-07,
on a public repository. A further 162 entries carry a corporate domain.
This is accurate and was verified directly against `git log`.

**It will not be remediated.** The reasoning, recorded once so it never
needs re-deriving:

- **A force-push does not remove it.** Rewritten-away commits become
  unreferenced, not deleted, and stay retrievable at
  `/commit/<old-sha>` indefinitely. Every affected SHA is written down in
  this repo's own CHANGELOG, status doc, and OC memories. Actually
  deleting them needs a manual GitHub Support garbage-collection request.
- **It would not retract the past regardless.** The address has been
  public since 2025-07-15, GitHub associates it with the account
  independently of any commit, and forks, mirrors, and the commit-search
  index are all outside our reach.
- **The cost is severe and certain.** ~1,700 commits across five refs;
  every SHA reference in our docs and memories invalidated; the
  "frozen at `bb217d9`" guarantee that is the entire purpose of the
  `archive/*` branches broken; the deployed container's
  `org.opencontainers.image.revision` provenance orphaned; every clone
  re-cloned.

A large, irreversible, self-inflicted breakage that does not solve the
problem is not a fix. **Accepted as-is.**

### What actually protects us, and is already working

The pre-commit author-identity check (`.githooks/check-identity-and-pii.sh`,
added 2026-05-01) blocks any commit whose configured author matches a
personal-domain pattern, and `test_no_secrets_committed.py` backstops the
PII half in CI where a local hook can be bypassed. Both verified green
across every commit made on 2026-08-28. Nothing new is accumulating —
that is the part that matters, and it is handled.

## Incident response

- DB corruption: the maintenance loop's `db_integrity_check` job
  detects it on a 7-day cadence, takes an emergency backup, and flips
  `/api/v1/health` to `maintenance_degraded: true`. Operators restore
  from the resolved DB path's `backups/auto/` directory
  (`/data/backups/auto/` on the NAS; or a manual `oc db backup` taken
  earlier).
- Embedding provider compromise: rotate the relevant API key and
  redeploy. The degradation policy keeps search working
  (FTS5-only) until the new key is in place.
- Lost API key: retrieve it from Portainer or the original secret store.
  `oc config show` masks it in both human and JSON output. If the
  original value is unavailable, set a new `OC_API_KEY` in the
  Portainer stack and redeploy.

## See also

- `docs/architecture/MAINTENANCE.md` — degraded-state surfacing
- `docs/configuration/env_vars.md` — full env var inventory
- `archive/openchronicle.v2` — v2 incident notes lived here pre-rewrite

## Embedding content egress

A cloud embedding provider sends every saved memory's full content and
every semantic search query off this host — the same corpus the backup
design age-encrypts against a different cloud. Since 2026-08-29 that
choice is surfaced rather than silent: startup logs a WARNING whenever
the configured embedding endpoint is not clearly LAN-local (fail-safe:
ambiguous hosts warn), and `/api/v1/health` + the MCP `health` tool
report `content_egress: "remote" | "local"`. The warning is a notice,
not a control; the mitigation is a LAN-local provider
(`OC_EMBEDDING_PROVIDER=ollama` pointed at a LAN host). Operator
direction (2026-08-29): local embedding is the priority path — see
[design/0006](../design/0006-embedding-provider-review.md).
