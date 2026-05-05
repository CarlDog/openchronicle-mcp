# OpenChronicle v3 Architecture

A memory database for LLM agents. SQLite-backed, FTS5 + embeddings for
hybrid search, project namespacing, served over HTTP REST and MCP
streamable-http from a single ASGI process.

## Layers (hexagonal, slimmed)

```text
interfaces/                 CLI + ASGI app (FastAPI host with /mcp mount)
  ↓
application/                use cases + embedding service + git-onboard +
                            maintenance loop orchestration
  ↓
domain/                     MemoryItem, Project, ports
  ↑
infrastructure/             SQLite store + embedding adapters + persistence
                            backup + migration framework + maintenance jobs
```

The v2 orchestrator/scheduler/router/MoE/webhook/asset/media/plugin
stack is gone. Look in `archive/openchronicle.v2` if you need it.

## Layer responsibilities

### Domain (`src/openchronicle/core/domain/`)

Pure business types. No imports of `application/` or `infrastructure/`.

- `models/`: `MemoryItem`, `Project`, `GitCommit` / `CommitCluster`
- `ports/`: `MemoryStorePort`, `StoragePort`, `EmbeddingPort`
- `exceptions.py`: `NotFoundError`, `ValidationError`, `ConfigError`,
  `ProviderError`, `BudgetExceededError`
- `errors/error_codes.py`: SCREAMING_SNAKE_CASE error codes
- `time_utils.py`: `utc_now()`

### Application (`src/openchronicle/core/application/`)

Use cases orchestrate domain operations against ports. No infrastructure
imports — anything reaching outside the process goes through a port.

- `services/embedding_service.py`: hybrid FTS5 + cosine-similarity
  search via Reciprocal Rank Fusion. Falls back to FTS5-only on
  embedding provider failure (the embedding-degradation policy).
- `services/git_onboard.py`: clone-and-cluster a remote git repo into
  memory candidates. No LLM call — synthesis is the caller's job.
- `services/maintenance_loop.py`: in-process asyncio loop that runs
  scheduled jobs (per-job lock for cross-tick overlap detection,
  global lock so jobs never run concurrently in this process).
- `services/context_builder.py`: helpers shared between use cases.
- `use_cases/`: `add_memory`, `delete_memory`, `list_memory`,
  `pin_memory`, `search_memory`, `update_memory`, `show_memory`,
  `create_project`, `list_projects`, `init_runtime`, `init_config`,
  `diagnose_runtime`, `export_memory`, `import_memory`
- `config/`: runtime path resolution (`paths.py`), embedding settings,
  env-var helpers
- `models/diagnostics_report.py`: shape returned by `oc health` /
  `/api/v1/health`

### Infrastructure (`src/openchronicle/core/infrastructure/`)

Adapters that implement ports + cross-cutting infra (SQLite, embedding
HTTP clients, the wiring container).

- `persistence/`:
  - `sqlite_store.py`: SQLite-backed implementation of
    `StoragePort` + `MemoryStorePort`.
  - `migrator.py`: versioned schema migration runner. Reads
    `migrations/NNN_*.sql`, applies pending versions in order with
    savepoint atomicity, records `schema_version` rows.
  - `migrations/001_initial.sql`: v3 baseline schema.
  - `backup.py`: atomic online backup module via
    `sqlite3.Connection.backup()` (writes to `.tmp` → `os.replace`).
  - `row_mappers.py`: row → domain model conversion.
- `embedding/`: stub, OpenAI, Ollama adapters implementing
  `EmbeddingPort`. Adapters never crash startup —
  `_build_embedding_port` catches and falls back to FTS5-only.
- `maintenance/jobs.py`: handler implementations for the maintenance
  loop's job registry (db_backup, db_vacuum, db_integrity_check,
  embedding_backfill, git_onboard_resync).
- `wiring/container.py`: composition root. Builds the SQLite store,
  optional embedding service, runtime paths. The container lifecycle
  (`__enter__`/`__exit__`/`close`) closes the DB connection cleanly.
- `config/config_loader.py`: `core.json` reader.

### Interfaces (`src/openchronicle/interfaces/`)

Driver-side adapters: HTTP, MCP, CLI.

- `api/`: FastAPI app with FastMCP mounted at `/mcp`. Lifespan starts
  FastMCP's session manager and the maintenance loop together.
  - Routes: `system` (health, maintenance/status), `project`, `memory`
  - Middleware: API key auth, rate limit
- `mcp/`: FastMCP server + tool modules
  - Tools: `memory_save`, `memory_search`, `memory_list`, `memory_get`,
    `memory_update`, `memory_delete`, `memory_pin`, `memory_stats`,
    `memory_embed`, `project_create`, `project_list`, `context_recent`,
    `health`, `onboard_git`
- `cli/`: argparse-based command tree (`oc <command>`)
  - `oc serve` runs the unified ASGI app
  - `oc memory ...`, `oc project ...`, `oc db ...`, `oc onboard git`,
    `oc maintenance ...`, `oc init`, `oc config show`, `oc version`
- `serializers.py`: shared dict serializers (project, memory) used by
  both API routes and MCP tools
- `logging_setup.py`: `OC_LOG_FORMAT=human|json` configuration

## Single-process ASGI

`oc serve` launches one uvicorn process serving everything:

```text
HTTP REST   →  /api/v1/{health,maintenance/status,project,memory,...}
MCP         →  /mcp/* (streamable-http transport, mounted Starlette app)
Liveness    →  /health  (no auth, no DB work)
```

The lifespan inside `interfaces/api/app.py` drives both subsystems:

```python
async with AsyncExitStack() as stack:
    if mcp_server is not None:
        await stack.enter_async_context(mcp_server.session_manager.run())
    if maintenance is not None:
        await maintenance.start()
        stack.push_async_callback(maintenance.stop)
    yield
```

uvicorn shutdown drains both cleanly.

## Schema

Three tables (plus the FTS5 virtual table and `schema_version`):

```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    metadata TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE memory_items (
    id         TEXT PRIMARY KEY,
    content    TEXT NOT NULL,
    tags       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    pinned     INTEGER NOT NULL,
    project_id TEXT,
    source     TEXT NOT NULL,
    updated_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE memory_embeddings (
    memory_id    TEXT PRIMARY KEY,
    embedding    BLOB NOT NULL,
    model        TEXT NOT NULL,
    dimensions   INTEGER NOT NULL,
    generated_at TEXT NOT NULL,
    FOREIGN KEY (memory_id) REFERENCES memory_items(id) ON DELETE CASCADE
);
```

`memory_fts` is an FTS5 contentless virtual table mirroring
`memory_items.content` and `tags`, kept in sync via triggers. FTS5
support is runtime-detected; SqliteStore degrades to a
keyword-fallback path if the SQLite build lacks FTS5.

`memory_items.conversation_id` from v2 is gone (locked Q1).

## Storage path resolution

`application/config/paths.py:RuntimePaths.resolve()` follows a
four-layer precedence:

1. constructor arg
2. per-path env var (`OC_DB_PATH`, `OC_CONFIG_DIR`, `OC_OUTPUT_DIR`)
3. `OC_DATA_DIR`-derived (`<dir>/openchronicle.db`, `<dir>/config`, …)
4. defaults (`data/openchronicle.db`, `config`, `output`)

The Docker entrypoint exports the per-path vars from `OC_DATA_DIR`
when set so operators can move everything with a single env tweak.

## See also

- `docs/cli/commands.md` — `oc` subcommand reference
- `docs/configuration/env_vars.md` — environment variables
- `docs/configuration/config_files.md` — `core.json` schema
- `docs/integrations/mcp_client_setup.md` — registering the MCP server
- `docs/integrations/mcp_server_spec.md` — full MCP tool surface
- `docs/api/STABILITY.md` — API + MCP tool stability promise
- `docs/architecture/MAINTENANCE.md` — maintenance loop reference
- `docs/configuration/security_posture.md` — container hardening posture
