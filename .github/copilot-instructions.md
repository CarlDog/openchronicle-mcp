# Copilot Instructions — OpenChronicle MCP

`AGENTS.md` (root) is the canonical, exhaustive instruction set for this repo — read
it for full project history, sprint status, and NAS/deploy operational rules.
`CLAUDE.md` is a byte-identical mirror enforced by a repo-hygiene test. This file is
a shorter, code-focused companion for Copilot sessions.

## Project Overview

OpenChronicle is a persistent memory database for LLM agents: keyword (SQLite FTS5)
plus optional hybrid semantic search, served over HTTP REST and MCP from one unified
ASGI process. It is a solo-maintained personal project (`CONTRIBUTING.md`: PRs from
outsiders are not accepted) distributed as a single Python package (`oc` CLI +
importable `openchronicle` package) and as a GHCR Docker image, deployed as a
Portainer stack on a home NAS. There is no LLM inside the service — the calling
agent (Claude Code, etc.) is the LLM; OpenChronicle only stores and retrieves.

## Tech Stack

| Area | Technology | Version |
| --- | --- | --- |
| Language | Python | `>=3.14` (`pyproject.toml`) |
| Web/ASGI | FastAPI + uvicorn[standard] | `fastapi>=0.110.0`, `uvicorn>=0.52.4` |
| MCP protocol | `mcp` (FastMCP) | `>=1.30.0,<2` — **never bump past 2.x**, see Gotchas |
| Storage | SQLite (stdlib) + FTS5, WAL mode | n/a |
| Embeddings (optional) | OpenAI SDK / Ollama via httpx + numpy | `openai>=3.16.2`, `httpx>=0.25.0`, `numpy>=2.5.3` |
| Metrics (optional, off by default) | `prometheus-client` | `>=0.23.1` |
| Lint/format | ruff | `>=0.16.8,<0.17` (minor-pinned deliberately) |
| Type checking | mypy | `>=1.8`, strict via `pyproject.toml` config |
| Tests | pytest + pytest-asyncio | `asyncio_mode = "auto"` |
| Markdown lint | markdownlint-cli2 (via npm) | see `package.json` |
| Container base | `python:3.14-slim` | multi-stage `Dockerfile`, amd64 only |
| Build backend | setuptools | `>=84.0.0` (CVE-pinned floor, do not lower) |

## Repository Structure

```text
src/openchronicle/
  core/
    domain/            # pure types + ports: StoragePort, MemoryStorePort, EmbeddingPort
      errors/error_codes.py   # canonical error code string constants — no inline literals
      exceptions.py           # NotFoundError, ValidationError (DomainValidationError), ProviderError, ConfigError
      time_utils.py           # utc_now() — use instead of datetime.now(UTC)
    application/
      services/embedding_service.py   # hybrid FTS5 + cosine similarity via Reciprocal Rank Fusion
      services/maintenance_loop.py    # single asyncio task dispatching due background jobs
      use_cases/                      # request-driven business logic, calls domain ports
      config/env_helpers.py           # parse_csv_tags() etc.
    infrastructure/
      persistence/sqlite_store.py     # StoragePort/MemoryStorePort impl, WAL journal mode
      persistence/migrator.py         # applies migrations/NNN_*.sql within savepoints, idempotent
      persistence/migrations/         # 001_initial.sql, 002_embedding_identity.sql, 004_embedding_status.sql
      embedding/                      # stub / openai / ollama EmbeddingPort adapters
      maintenance/jobs.py             # job handlers: db_vacuum, db_backup, embedding_backfill, etc.
      wiring/container.py             # DI composition root (CoreContainer)
  interfaces/
    api/app.py            # create_app() FastAPI factory, global exception handlers, mounts FastMCP at /mcp
    api/routes/           # memory.py, project.py, system.py
    mcp/server.py          # create_server() — FastMCP instance
    mcp/tools/             # memory.py, project.py, context.py, onboard.py, backup.py, system.py
    cli/main.py            # `oc` entrypoint; cli/commands/ subcommands (db, config, etc.)
tests/                    # pytest, one test_*.py per concern, mirrors src topics not 1:1 files
migrations = src/openchronicle/core/infrastructure/persistence/migrations/  (NOT top-level)
scripts/                  # one-shot ops scripts: migrate_v2_to_v3.py, verify_v3_db.py, benchmark_embeddings.py, offline_restore.py
docs/CODEBASE_ASSESSMENT.md  # single source of truth for project status — update before every commit
docs/V3_PLAN.md              # phase tracker / open questions
docs/architecture/ARCHITECTURE.md  # full layout + schema + ASGI design
config/core.json.example     # copy to config/core.json for local overrides
docker-compose.yml            # local dev (builds from Dockerfile)
docker-compose.nas.yml        # Portainer/NAS deployment shape (healthcheck, named volumes, OC_TAG pin)
```

Layering rule (hexagonal architecture, enforced by tests): `domain` → `application` →
`infrastructure`, with `interfaces/` as drivers on top. `domain/` must not import
infrastructure or the `mcp`/`fastapi` packages — enforced by
`tests/test_hexagonal_boundaries.py` and `tests/test_core_agnosticism.py`.

## Essential Commands

```bash
# Setup (editable install with all extras used by CI/dev)
pip install -e ".[dev,mcp,openai,ollama,metrics]"

# Pre-commit hooks (run once per clone)
pip install pre-commit && pre-commit install
# After bumping any hook `rev:` in .pre-commit-config.yaml, refresh the env
# BEFORE committing, from a plain shell (not inside the commit itself):
pre-commit install-hooks

# Run local dev server (binds 127.0.0.1:8000, REST at /api/v1/*, MCP at /mcp)
oc serve

# Full test suite
pytest

# Single test file / single test
pytest tests/test_memory_export_import.py
pytest tests/test_maintenance_loop.py::test_overlap_skip_records_skip_and_does_not_block -v

# Lint / format / typecheck (what pre-commit + CI's `quality` job run)
ruff check src tests scripts
ruff format --check src tests scripts   # or without --check to auto-fix
mypy src tests --config-file=pyproject.toml

# Everything pre-commit runs, in one shot
pre-commit run --all-files

# Markdown lint
npm run lint:md:fix

# Docker (local)
docker compose build
docker compose up oc
```

There is no separate "migrate" command — `sqlite_store.py` calls
`migrator.apply_pending(conn)` automatically on every startup; it is idempotent.
`oc db info` / `oc db vacuum` / `oc db backup` / `oc db stats` are the CLI's
database-maintenance surface (`interfaces/cli/commands/db.py`).

## Architecture & Key Patterns

- **Unified ASGI process.** One FastAPI app (`interfaces/api/app.py: create_app`)
  serves REST at `/api/v1/*` and mounts a FastMCP streamable-HTTP app at `/mcp` on
  the same port. The FastAPI lifespan drives the FastMCP session manager so its
  background tasks join host startup/shutdown. `mount_mcp=False` exists for tests
  that want the REST surface in isolation.
- **Ports & adapters.** Three ports in `domain/ports/`: `StoragePort`,
  `MemoryStorePort`, `EmbeddingPort`. `infrastructure/` provides the only concrete
  implementations (SQLite store, stub/openai/ollama embedding adapters). Never let
  `application/` or `domain/` import a concrete infrastructure module directly.
- **DI composition root.** `core/infrastructure/wiring/container.py` (`CoreContainer`)
  builds and wires everything; both CLI and ASGI entrypoints construct one
  `CoreContainer` and pass it down.
- **Hybrid search.** `application/services/embedding_service.py` combines SQLite FTS5
  keyword search with cosine similarity over embeddings using Reciprocal Rank Fusion,
  and degrades to FTS5-only if the embedding provider raises.
- **Maintenance loop.** `application/services/maintenance_loop.py` runs one asyncio
  task that dispatches due jobs (`infrastructure/maintenance/jobs.py`) as background
  tasks; per-job + global locks give skip-on-overlap with sequential-within-process
  execution. See `docs/architecture/MAINTENANCE.md`.
- **Schema migrations.** `infrastructure/persistence/migrator.py` reads
  `migrations/NNN_*.sql` files and applies each inside a savepoint; re-running on an
  up-to-date DB is a no-op. Baseline is `001_initial.sql`.
- **MCP tool surface.** 18 tools registered via FastMCP in `interfaces/mcp/tools/`
  (`memory.py`, `project.py`, `context.py`, `onboard.py`, `backup.py`, `system.py`).
  Backup tools are conditionally registered only if `OC_BACKUP_MCP_ENABLED=true`,
  `OC_API_KEY` is set, and `OC_BACKUP_DIR` is explicit (`app.py: _backup_tools_enabled`)
  — a bad setting logs an error and disables the tools rather than crash-looping.

## Coding Conventions

**Enforced by tooling:**

- ruff lint + format (`ruff check`, `ruff format --check`) — CI's `quality` job fails
  the build otherwise.
- mypy strict typing on `src` and `tests` (`pyproject.toml` config).
- `tests/test_error_codes_canonical.py` — every error response must use a constant
  from `domain/errors/error_codes.py`, never an inline string literal (checks both
  `code=` kwargs and `"code":` dict keys).
- `tests/test_hexagonal_boundaries.py` / `test_core_agnosticism.py` — layering and
  MCP-SDK-agnosticism of `core/`.
- `tests/test_no_secrets_committed.py` — no committed secrets; use placeholders
  `changeme`, `replace_me`, `your_key_here`, `test-key`.
- `.githooks/check-identity-and-pii.sh` (via pre-commit `check-identity-and-pii`) —
  author identity + PII checks on staged content.
- markdownlint-cli2 on all `*.md`.

**Team conventions (not tool-enforced):**

- Error codes: SCREAMING_SNAKE_CASE (`INVALID_ARGUMENT`, `MEMORY_NOT_FOUND`).
- MCP tool names: snake_case (`memory_save`, `context_recent`, `onboard_git`).
- Domain models use `@dataclass`.
- `NotFoundError` → HTTP 404, `ValidationError`/`DomainValidationError` → HTTP 422,
  `ProviderError` (with `error_code`/`hint`/`details`) for embedding/external-provider
  failures, `ConfigError` for startup/env failures — all caught by global handlers in
  `interfaces/api/app.py`; don't add local per-route try/except for these.
  <!-- TODO: verify -->  (global handler file location confirmed; exact handler function names not individually inspected)
- Pydantic `Field()` for request-body constraints, `Query()` for query-param
  constraints.
- Always use `utc_now()` from `domain/time_utils.py`, never inline
  `datetime.now(UTC)`.
- Use `parse_csv_tags()` from `application/config/env_helpers.py` for CSV tag
  parsing rather than hand-rolled `.split(",")`.

## Testing Guidelines

- Framework: pytest + pytest-asyncio, `asyncio_mode = "auto"` (async test functions
  need no `@pytest.mark.asyncio` decorator), `pythonpath = ["src"]` so tests import
  `openchronicle` without an install step.
- All tests live flat in `tests/`, one `test_<topic>.py` file per concern (not
  strictly mirrored to `src/` paths) — e.g. `test_embedding_service.py`,
  `test_maintenance_loop.py`, `test_mcp_tool_schema_snapshot.py`.
- No `integration` marker and no `tests/integration/` directory — both were
  deliberately removed in v3. Do not reintroduce an integration-test marker; CI
  validates unit + functional tests only (`pytest -v`, no `-m` filter).
- Shared fixtures live in `tests/conftest.py`. There is deliberately **no** shared
  `store` fixture — six local per-file fixtures diverge in seeded data and close
  behavior; pytest's nearest-fixture resolution would make a shared one a silent
  seventh shape, not a replacement (documented rejected-refactor in `AGENTS.md`).
- Windows and Ubuntu both run in CI (`.github/workflows/test.yml`); macOS was
  dropped as a leg (never caught anything Ubuntu didn't).
- "Done" for a change = `pytest` full suite green, `ruff check`/`ruff format --check`
  clean, `mypy` clean, and (if `*.md` touched) `npm run lint:md:fix` clean.

## Git & PR Conventions

- Commit prefixes seen in history: `feat:`, `fix:`, `docs:`, `release:` (Conventional
  Commits style, not strictly enforced by tooling). <!-- TODO: verify: no commit-msg
  hook found; convention is by observation of `git log`, not codified. -->
- Feature branches are named `<agent>/<topic>` (e.g. `claude/0019-llm-cost-north-star`,
  `codex/exposed-backup-tools`) — reflects that this repo's contributors are
  autonomous coding agents directed by the operator, not humans opening PRs cold.
- **This project does not accept outside pull requests** (`CONTRIBUTING.md`). Use
  issues for bugs/feature requests/questions instead.
- Work lands via PR so CI actually runs; a pushed branch alone gets no test run
  (`AGENTS.md` "Rules for autonomous agents"). Nothing is "shipped" until it's in a
  tagged release and CI passed on that exact commit.
- `main` is the v3.x production line; `v4/develop` is where MAJOR-breaking work
  (ADR 0008 etc.) lands; merge `main` → `v4/develop` regularly. CI runs
  test+quality on both, but only `main` pushes and `v*` tags trigger
  `build-and-push` (image publish) — see `.github/workflows/test.yml`.
- A `v*` tag's version must exactly match `pyproject.toml`'s `[project].version`
  (normalized, e.g. `v3.0.0-rc6` ↔ `3.0.0rc6`) — CI's `quality` job fails the tag
  build otherwise.

## Configuration & Environment

- Config precedence: environment variables override `config/core.json` (copy from
  `config/core.json.example`); `OC_CONFIG_DIR` selects the config directory
  (default `config`). Full schema: `docs/configuration/config_files.md`.
- Key env vars (full reference: `docs/configuration/env_vars.md`):

  | Variable | Purpose | Default |
  | --- | --- | --- |
  | `OC_DB_PATH` | SQLite database file | `data/openchronicle.db` |
  | `OC_CONFIG_DIR` | Directory containing `core.json` | `config` |
  | `OC_API_HOST` / `OC_API_PORT` | Bind address/port | `127.0.0.1` / `8000` |
  | `OC_API_KEY` | Bearer token; auth disabled when empty | *(unset)* |
  | `OC_EMBEDDING_PROVIDER` | `none`/`stub`/`openai`/`ollama` | `none` |
  | `OC_METRICS_ENABLED` | Expose `/metrics` | `false` |
  | `OC_LOG_FORMAT` | `human` or `json` | `human` |
  | `OC_BACKUP_MCP_ENABLED` / `OC_BACKUP_DIR` | Enable backup MCP tools | disabled |

- **Never commit secrets.** No `OPENAI_API_KEY`, `OC_API_KEY`, `OC_GIT_TOKEN`, etc. in
  tracked files. Use a git-ignored `.env.local` or `OC_CONFIG_DIR`-mounted secrets.
  `tests/test_no_secrets_committed.py` and the gitleaks pre-commit hook both gate this.

## Do / Don't

**Do:**

- Update `docs/CODEBASE_ASSESSMENT.md` (and `docs/V3_PLAN.md` + AGENTS.md "Current
  Sprint" for in-flight work) in the *same commit* as any source change.
- Keep `AGENTS.md` and `CLAUDE.md` byte-identical — there is a hygiene test for it.
- Use the canonical error code constants (`domain/errors/error_codes.py`) for every
  new error path.
- Run `pre-commit run --all-files` (or the individual ruff/mypy/pytest commands)
  before committing.
- Treat `docs/CODEBASE_ASSESSMENT.md` as the single source of truth for "what's
  actually shipped" — cross-check before claiming something is released/deployed.

**Don't:**

- Don't bump the `mcp` package past `<2` without reading the V3_PLAN "mcp 2.x
  migration" entry first — `mcp.server.fastmcp` is a tombstone module in 2.x
  (`ModuleNotFoundError` at import), so an unpinned bump ships a container that dies
  on startup.
- Don't add an ARM/`linux/arm64` build platform — every deploy target is amd64; it
  was explicitly rejected as wasted CI time.
- Don't reintroduce the `integration` pytest marker or a `tests/integration/`
  directory — deliberately cut in v3.
- Don't add a shared `store` fixture to `tests/conftest.py` — it would silently
  shadow the six existing local fixtures rather than replace them.
- Don't treat `db_modified_utc` (health/API field) as a liveness signal — SQLite is
  in WAL mode, so writes land in the `-wal` sidecar and the main DB's mtime only
  advances on checkpoint.
- Don't scrub the NAS LAN hostname if you see it in tracked files, and don't
  re-raise the historical author-email-in-history finding — both are permanently
  closed decisions recorded in `AGENTS.md`'s phase-end audit checklist.
- Don't open a pull request from an external contributor workflow expectation —
  this repo doesn't accept them; direct users to file an issue instead.
- Don't assume a green CI run means the change is live in production — the NAS
  stack is tag-pinned (`OC_TAG`); a push to `main` only moves the `:latest` tag,
  which the pinned stack doesn't track.

## Common Tasks

**Add a new MCP tool:**

1. Add the handler function in the relevant module under
   `src/openchronicle/interfaces/mcp/tools/` (e.g. `memory.py` for memory-related
   tools), following the snake_case naming convention.
2. Register it in `interfaces/mcp/server.py: create_server`.
3. Add/extend the schema-snapshot test coverage
   (`tests/test_mcp_tool_schema_snapshot.py`) and error-shape coverage
   (`tests/test_mcp_error_shape.py`).
4. Update `docs/integrations/mcp_server_spec.md` (tool count/spec is versioned there).

**Add a new REST route:**

1. Add the route function to the matching file in
   `src/openchronicle/interfaces/api/routes/` (`memory.py`, `project.py`,
   `system.py`).
2. Raise `NotFoundError` / `ValidationError` / `ProviderError` / `ConfigError` from
   `domain/exceptions.py` for error cases — do not hand-roll try/except + JSONResponse;
   the global handlers in `app.py` do that.
3. Use canonical error codes from `domain/errors/error_codes.py`.
4. Add a test in `tests/test_http_api.py` (or a topic-specific test file).

**Add a schema migration:**

1. Add a new `NNN_description.sql` file to
   `src/openchronicle/core/infrastructure/persistence/migrations/` with the next
   sequential number.
2. If it changes the table list, update `_TABLE_NAMES` in
   `interfaces/cli/commands/db.py` (`cmd_db_info`) to match.
3. The migrator (`infrastructure/persistence/migrator.py`) applies it automatically
   and idempotently on next startup — no manual "run migration" command exists.

**Add a new embedding provider:**

1. Implement `EmbeddingPort` in `core/infrastructure/embedding/` alongside the
   existing `stub`/`openai`/`ollama` adapters.
2. Wire the new provider name into `OC_EMBEDDING_PROVIDER` handling in the
   config/wiring layer (`core/infrastructure/wiring/container.py`).
3. Add it as an optional extra in `pyproject.toml` `[project.optional-dependencies]`
   if it needs new third-party deps, and to the Dockerfile's
   `pip install ".[openai,ollama,mcp,metrics]"` line if it should ship in the
   standard image.
4. Add adapter tests alongside `tests/test_embedding_adapters.py`.

**Run before opening a PR / calling a task done:**

```bash
ruff format src tests scripts
ruff check --fix src tests scripts
mypy src tests --config-file=pyproject.toml
pytest
npm run lint:md:fix   # if markdown changed
```

## Gotchas

- **WAL mode + `db_modified_utc`.** SQLite runs `PRAGMA journal_mode = WAL`; writes
  land in the `-wal` sidecar and the main DB file's mtime only advances on
  checkpoint. A memory saved seconds ago can still show an old `db_modified_utc` —
  it's a checkpoint clock, not a freshness signal.
- **Tag-pinned NAS deploy.** `docker-compose.nas.yml` requires `OC_TAG` explicitly
  (`${OC_TAG:?...}`); a push to `main` only refreshes the `:latest` GHCR tag, which
  the pinned Portainer stack does not pull. Runtime changes ship with the next
  tagged release, not the next push.
- **`build-and-push` gating.** It only runs on push to `main` or a `v*` tag, and
  only after both `test` and `quality` succeed (`needs: [test, quality]`), and it
  now also builds locally and runs `tools/ci/smoke-image.sh` before pushing
  (verifies `oc version` reports the build SHA, extras import, and `/health`
  responds) — an image that can't start never reaches `:latest`.
- **CI path filters.** Doc-only / `package.json` / `.pre-commit-config.yaml` /
  `.githooks/**` changes are in `test.yml`'s `paths-ignore` and don't trigger a
  build — don't expect a doc PR to publish an image.
- **`mypy` additional_dependencies drift.** The pre-commit mypy hook pins its own
  `additional_dependencies` list (fastapi/uvicorn/mcp/prometheus-client versions)
  separately from `pyproject.toml`'s `[dev]` extra — keep both in step manually when
  bumping a floor.
- **ruff is minor-pinned** (`>=0.16.8,<0.17`) deliberately: the formatter's output
  changes across minor versions, so an open floor can make CI's `ruff format --check`
  fail on code the local pinned pre-commit hook happily passed.
- No conversation-engine tools exist in v3 (`conversation_*`, `turn_record`,
  `context_assemble`, `search_turns` are gone) — OpenChronicle's MCP role is purely
  memory storage/retrieval; the calling agent is the LLM.

## Glossary

- **OC** — OpenChronicle (also the `oc` CLI command name).
- **MCP** — Model Context Protocol; the tool-calling transport OpenChronicle exposes
  at `/mcp` alongside its REST API.
- **FTS5** — SQLite's full-text search extension; backs keyword search.
- **RRF** — Reciprocal Rank Fusion; the algorithm combining FTS5 and embedding
  similarity rankings in hybrid search.
- **ADR** — Architecture Decision Record (`docs/design/000N-*.md`).
- **v2 / v3 / v4** — major generational cuts of the project; v2 had a conversation
  engine and separate MCP/REST ports, v3 (current `main`) unified them and dropped
  the LLM, v4 (`v4/develop`) is in-progress MAJOR-breaking work (pins-as-ranking-prior).

