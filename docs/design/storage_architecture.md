# Storage Architecture

Design record for OpenChronicle data directory layout and multi-DB evolution.

## Current State: Single Database

16 tables in one `openchronicle.db`:

- **Conversation:** `conversations`, `turns`
- **Memory:** `memory_items`, `memory_embeddings`, `memory_turn_links`
- **Events:** `events`
- **Tasks:** `tasks`
- **Scheduling:** `scheduled_jobs`
- **LLM tracking:** `llm_usage`
- **MCP/MoE:** `mcp_tool_usage`, `moe_usage`
- **Agents:** `agents`
- **Assets:** `assets`, `asset_links`
- **Webhooks:** `webhook_subscriptions`, `webhook_deliveries`
- **Git onboarding:** `git_onboard_watermarks`

Everything is cross-queryable. Single WAL file, single backup, no coordination
overhead. This architecture is correct for the current single-project MCP use
case.

## Path Centralization (Implemented)

All data paths now flow through `RuntimePaths.resolve()` in
`application/config/paths.py`. Four-layer precedence:

1. **Constructor param** — wins unconditionally (programmatic override).
2. **Per-path env var** (e.g., `OC_DB_PATH`) — checked next.
3. **`OC_DATA_DIR` + suffix** — if `OC_DATA_DIR` is set, derives all paths.
4. **Hardcoded default** — last resort.

Seven paths are resolved:

| Path | Env Var | Default |
| ---- | ------- | ------- |
| `db_path` | `OC_DB_PATH` | `data/openchronicle.db` |
| `config_dir` | `OC_CONFIG_DIR` | `config` |
| `plugin_dir` | `OC_PLUGIN_DIR` | `plugins` |
| `output_dir` | `OC_OUTPUT_DIR` | `output` |
| `assets_dir` | `OC_ASSETS_DIR` | `data/assets` |
| `discord_session_path` | `OC_DISCORD_SESSION_STORE_PATH` | `data/discord_sessions.json` |
| `discord_pid_path` | `OC_DISCORD_PID_PATH` | `data/discord_bot.pid` |

`SqliteStore` and `AssetFileStorage` constructors no longer have default paths —
they require explicit values, preventing silent creation of files relative to cwd.

## The Problem at Scale

As OC grows to manage multiple projects (Plex connector, Google connector,
storytelling, multiple MCP clients), a single database becomes:

- **Unmanageable lifecycle.** Can't archive, delete, or backup one project
  without affecting others. A `DROP TABLE` or `DELETE FROM` is not the same as
  deleting a file.
- **Growing contention.** Concurrent writers (Discord, scheduler, MCP, API) all
  contend on one WAL. SQLite handles this with `BEGIN IMMEDIATE` and retry, but
  it's a ceiling.
- **Unclear ownership.** Which process created `openchronicle (1).db`? What can
  be safely deleted? The data directory accumulates orphaned files with no
  manifest.

## Proposed Architecture: Registry + Satellite DBs

### Registry Database (`oc_registry.db`)

Small, rarely written, fast to backup:

- `projects` table (id, name, db_path, created_at, status)
- `global_config` table
- Application-level metadata only

### Satellite Databases (`oc_proj_{slug}_{short_uuid}.db`)

Per-project, independently managed:

- `conversations`, `turns`, `events`, `memory_items`, `memory_embeddings`,
  `memory_turn_links`, `scheduled_jobs`, `llm_usage`, `assets`, `asset_links`,
  `webhook_subscriptions`, `webhook_deliveries`, `git_onboard_watermarks`
- Named with human-readable slug + UUID prefix for uniqueness
- Can be independently backed up, archived, or deleted
- Removing a project = delete its satellite DB file

### Cross-Cutting Tables (Stay in Registry)

- `mcp_tool_usage`, `moe_usage` — operational telemetry, not project-scoped
- `agents` — shared across projects

### Naming Convention

```text
data/
  oc_registry.db                           # Application registry
  projects/
    oc_proj_openchronicle_0db2b2ff.db      # Project: OpenChronicle
    oc_proj_plex-media_a1b2c3d4.db         # Project: Plex Media
    oc_proj_storytelling_e5f6a7b8.db       # Project: Storytelling
  assets/
    {project_id}/
      {asset_uuid}.ext
  discord_sessions.json
  discord_bot.pid
```

Naming rules:

- Prefix `oc_` on all OC-owned files
- `oc_registry` for the central DB
- `oc_proj_{slug}_{short_uuid}` for satellite DBs
- Slug is a sanitized project name (lowercase, hyphens, max 30 chars)
- Short UUID is first 8 chars of the project UUID

## Migration Path

1. **Path centralization** (done) — no schema changes. `RuntimePaths` centralizes
   all path resolution. When satellite DBs arrive, the path logic lives in one
   place.
2. **Add `db_path` column to `projects` table.** Stores relative path to satellite
   DB. Existing single-DB projects get `NULL` (use main DB).
3. **New `ProjectDatabaseManager` service.** Creates, opens, and closes satellite
   connections. Manages a connection pool keyed by project ID.
4. **Refactor `SqliteStore` to accept a connection (not a path).** Allows multiple
   stores pointing at different DBs. The store becomes stateless with respect to
   connection lifecycle.
5. **Split tables.** Move project-scoped tables to satellite DBs. Cross-cutting
   tables stay in the registry. Migration script copies data and drops old tables.
6. **Cross-project search.** `ATTACH DATABASE` for memory search across projects,
   or a search index in the registry. This is the hardest part and should be
   designed carefully when the need arises.

## Maintenance Operations

Future CLI commands (applicable regardless of single/multi-DB):

- **`oc data info`** — show data directory contents, sizes, last modified, which
  process owns each file.
- **`oc data gc`** — garbage collect orphaned files (WAL/SHM files without
  matching DB, asset files not in asset table, stale PID files).
- **`oc db vacuum`** — already exists. Extend to handle multiple DBs.
- **`oc db backup [--project ID]`** — backup specific project or all.
- **`oc project archive <id>`** — mark project inactive, optionally compress its
  satellite DB.

## Decision: When to Implement

**Not now.** The current single-DB architecture is correct for the current use
case (1 project, MCP-primary). Multi-DB adds complexity to every `StoragePort`
method, every query, every migration. The cost is real and the benefit is
theoretical until there are multiple active projects generating meaningful data.

**Trigger:** When OC has 3+ active projects with distinct data, or when the single
DB exceeds ~500MB and lifecycle management becomes painful.

**What path centralization does to prepare:** `RuntimePaths` centralizes all path
resolution. When satellite DBs arrive, the path logic lives in one place. The
naming convention is documented. The directory structure is clean. Nothing in the
current implementation makes multi-DB harder.
