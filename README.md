# OpenChronicle

<!-- markdownlint-disable MD033 -->
<!-- fleet-confidence -->
![code confidence](https://img.shields.io/badge/code_confidence-fair-orange) <sub>· claude-fable-5 · 2026-08-30 · [details](../../issues/27)</sub>
<!-- /fleet-confidence -->
<!-- markdownlint-enable MD033 -->

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-ghcr.io%2Fcarldog%2Fopenchronicle--mcp-blue?logo=docker)](https://ghcr.io/carldog/openchronicle-mcp)
[![Python 3.14+](https://img.shields.io/badge/Python-3.14%2B-blue?logo=python&logoColor=white)](https://python.org)

A memory database for LLM agents. Persistent semantic + keyword
memory, project namespacing, git-onboard, served over HTTP REST and
MCP from a single ASGI process. Runs on your hardware.

## What it does

- **Persistent memory across sessions.** Save decisions, milestones,
  and rejected approaches that survive context compression and new
  conversations. Retrieve them with hybrid full-text and semantic
  search via Reciprocal Rank Fusion.
- **Project namespacing.** Memory is scoped to projects, so context
  for one workstream doesn't leak into another.
- **Git onboarding.** Clone a repo, cluster commits by relatedness,
  return summaries ready for memory ingestion. Seeds long-term memory
  with the WHY behind existing code.
- **One process, two transports.** FastAPI hosts both the REST surface
  (`/api/v1/*`) and the MCP streamable-HTTP transport (`/mcp`) on the
  same port. Single container, single port mapping, single
  healthcheck.
- **Embedding-failure degradation.** When the embedding provider goes
  down, search degrades cleanly to FTS5-only and surfaces the
  degraded state via `/api/v1/health` and the MCP `health` tool.
  Backfill catches up when the provider returns; the static `/health`
  endpoint remains a minimal liveness probe.
- **Optional operational metrics.** The standard image includes the bounded
  Prometheus recorder and guarded `/metrics` endpoint. Enable it explicitly
  with `OC_METRICS_ENABLED=true`; it remains off by default. See the
  [metrics configuration](docs/configuration/env_vars.md) and the optional
  [local monitoring runbook](docs/monitoring/runbook.md).
- **Schema migration framework.** Versioned `.sql` migrations with
  savepoint atomicity. Re-runs are idempotent. Future schema changes
  drop in as `NNN_<slug>.sql` files.
- **Atomic online backups.** Uses SQLite's online backup API.
  Backup-before-destructive policy: vacuum runs a backup first as
  part of the same job. Integrity-check failures trigger emergency
  backups.

## What it isn't

- Not a conversation engine. v3 has no LLM. Use Claude Code, Goose,
  Open WebUI, etc. via the MCP server.
- Not multi-tenant. Single user. Bearer-token auth via `OC_API_KEY`
  is supported but optional — disabled by default for trusted-LAN
  deployments. See `docs/configuration/security_posture.md` for the
  when-to-enable guidance.
- Not a cloud sync layer. The DB lives on your hardware. Backups go
  to a directory next to it. Cross-device sync isn't built in; a
  backup-only Dropbox design is documented but not implemented in
  [`docs/design/0001-cloud-backup.md`](docs/design/0001-cloud-backup.md).

By design.

## Install

From source:

```bash
pip install -e ".[mcp,openai]"
oc init
oc serve
```

The default `oc serve` binds `127.0.0.1:8000`. Override with
`--host`/`--port` or `OC_API_HOST`/`OC_API_PORT`.

Docker (single container, NAS-friendly):

```bash
docker run --rm \
  -p 8000:8000 \
  -e OC_API_HOST=0.0.0.0 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config:/app/config \
  ghcr.io/carldog/openchronicle-mcp:latest
```

`OC_API_HOST=0.0.0.0` is required in a container — the app default
binds container-loopback, which the port mapping can't reach. To call
the server by anything other than `localhost` (a NAS hostname, a LAN
IP), also set `OC_MCP_ALLOWED_HOSTS=your-host:*` or every request gets
a 421 (see
[env_vars.md](docs/configuration/env_vars.md)).

For a Portainer stack on a NAS, use the `docker-compose.nas.yml` at
the repo root.

## Quickstart

```bash
# Bootstrap the runtime tree
oc init

# Create a project
PROJECT_ID=$(oc init-project "my-project")

# Save your first memory
oc memory add "Decision: SQLite for storage; AGPL for license" \
    --project-id $PROJECT_ID --tags decision

# Search it
oc memory search "storage decision" --project-id $PROJECT_ID
```

Or do the same via MCP — register the server with Claude Code:

```bash
claude mcp add --scope user --transport http openchronicle \
    http://127.0.0.1:8000/mcp
```

Then ask Claude to call `memory_save` and `memory_search`.

## Architecture

Hexagonal: `domain/` (pure types + ports) → `application/` (use cases,
services) → `infrastructure/` (SQLite, embedding adapters, the
maintenance loop). Driver-side adapters in `interfaces/` host the
HTTP, MCP, and CLI surfaces.

See `docs/architecture/ARCHITECTURE.md` for the full layout.

## Documentation

- [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md) — layout, schema, ASGI design
- [`docs/architecture/MAINTENANCE.md`](docs/architecture/MAINTENANCE.md) — maintenance loop + degradation policy
- [`docs/cli/commands.md`](docs/cli/commands.md) — `oc` subcommand reference
- [`docs/configuration/env_vars.md`](docs/configuration/env_vars.md) — environment variables
- [`docs/configuration/config_files.md`](docs/configuration/config_files.md) — `core.json` schema
- [`docs/configuration/security_posture.md`](docs/configuration/security_posture.md) — security model
- [`docs/integrations/mcp_client_setup.md`](docs/integrations/mcp_client_setup.md) — register the MCP server
- [`docs/integrations/mcp_server_spec.md`](docs/integrations/mcp_server_spec.md) — MCP tool surface
- [`docs/api/STABILITY.md`](docs/api/STABILITY.md) — versioning + deprecation policy
- [`docs/design/README.md`](docs/design/README.md) — proposed designs and comparative repository reviews

## Development

```bash
pip install -e ".[dev,mcp,openai,ollama]"
pre-commit install
pytest
```

The architecture is enforced by tests:

- `tests/test_hexagonal_boundaries.py` — domain/application/infrastructure layering
- `tests/test_architectural_posture.py` — core agnostic of MCP SDK
- `tests/test_no_secrets_committed.py`, `tests/test_no_soft_deprecation.py` — repo hygiene

## License

Copyright (C) 2025-2026 CarlDog

[AGPL-3.0](LICENSE). This program is free software: you can redistribute
it and/or modify it under the terms of the GNU Affero General Public
License as published by the Free Software Foundation, either version 3
of the License, or (at your option) any later version. It is distributed
WITHOUT ANY WARRANTY; see the license for details.

The copyright line lives here rather than inside `LICENSE`: that file is
the AGPL text verbatim, and the `<year> <name of author>` placeholders in
its closing appendix are the license's own *instructions* for what to put
in your source files — not blanks to fill in. Editing them would modify
the license text itself.
