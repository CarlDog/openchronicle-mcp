# `oc` CLI reference

All subcommands of the `oc` entry point. Run any with `--help` for the
full argparse output.

## Server

### `oc serve`

Launch the unified ASGI app. One uvicorn process serves the HTTP REST
surface at `/api/v1/*` and the MCP streamable-HTTP transport at `/mcp`.
The maintenance loop runs in the same process.

```bash
oc serve --host 0.0.0.0 --port 8000
```

`OC_LOG_FORMAT=json` switches log output to one JSON object per line.

## Memory

### `oc memory add CONTENT`

Save a memory item. `--project-id` is required. `--tags`, `--pin`,
`--source` map to MemoryItem fields.

```bash
oc memory add "Decision: use SQLite for storage" \
    --project-id $PROJECT_ID --tags decision,architecture --pin
```

### `oc memory list`

Browse memory items newest-first, with pinned items floated to the top.
`--limit`, `--offset`, `--pinned-only`, and `--project-id` for filtering.

`--project-id` is strict: it excludes global (project-less) items. Note
that ordering is by `created_at`, which `oc memory add` and the git
onboarder can backdate, so a small `--limit` is not a reliable way to see
"everything recent in this project" — pass `--project-id` and no limit.

### `oc memory show MEMORY_ID`

Print a single memory item.

### `oc memory pin MEMORY_ID --on|--off`

Toggle pin state.

### `oc memory search QUERY`

Hybrid FTS5 + semantic search via Reciprocal Rank Fusion. `--top-k`,
`--project-id`, `--tags` (comma-separated, AND logic),
`--include-pinned`/`--no-include-pinned`, `--offset`, `--full` (print
full content for context injection).

Search-surface v2 (Q20/Q21):

- `--mode hybrid|keyword|semantic` picks the retrieval channel per
  call. `keyword` never touches the embedding provider; `semantic`
  requires one and fails loudly (exit 1) instead of silently degrading.
- `--phrase` matches the whole query as one adjacent-token phrase on
  the keyword channel ("does content literally contain this").
- `--pinned-limit N` caps how many *matching* pins float above the
  ranked results (best-matching first; default 10). `0` means "don't
  float" — the pins still rank; `--no-include-pinned` is what hides
  them. Use `oc memory list --pinned-only` to enumerate every pin.
- Each result line carries a bracketed relevance column — the channel
  that surfaced it (`pinned` / `keyword` / `semantic` / `hybrid`) plus
  `sim=` cosine similarity when the semantic channel contributed.

### `oc memory update MEMORY_ID`

Edit content or tags in place. `--content NEW`, `--tags "a,b,c"`.
Preserves identity (id, created_at), bumps `updated_at`.

### `oc memory delete MEMORY_ID [--confirm]`

Without `--confirm`, prints a deletion preview and leaves the memory
unchanged. Re-run with `--confirm` for the hard delete. There is no
soft-delete recovery; backups are the recovery path.

### `oc memory embed`

Generate embeddings for memories that lack them. `--force` regenerates
all (use after switching `OC_EMBEDDING_MODEL`). `--status` reports
coverage without doing work.

### `oc memory export [--out FILE] [--project-id ID]`

Dump projects + memory items as a portable JSON envelope. Embeddings
are excluded (regenerable). Cross-version-portable disaster recovery
surface.

The envelope carries `exported_at` (import reads it for a staleness
warning). It does **not** bump `format_version` — an envelope written
before that field existed still imports, and one carrying it still
imports into an older build.

The git-onboard watermark (this device's git resume point, see below)
is never included — it's device-local state, not portable content.

### `oc memory import FILE [--mode merge|replace]`

Read an envelope produced by `oc memory export` and apply it.

- `merge` (default): inserts items whose IDs aren't already present
- `replace`: refuses if the destination has any project or memory rows

**`merge` is a union by id, not a sync.** There is no update branch, so
it has two lossy edges, both silent in the data:

- a **collision keeps the destination's copy** — an edit made on the
  other device (content, tags, pin) is discarded
- an item **deleted here since the export is re-inserted** — the
  envelope has no way to know it was deleted

For an exact restore, import into a fresh DB with `--mode replace`.

Import **reports** over-cap content rather than rejecting it. New content is
capped at 100,000 characters on every write surface, but a restore is not new
input — a store can already hold a longer row, and failing the recovery path on
data the operator already owns would be worse than accepting it. Such rows are
imported intact, counted, and named in a stderr warning.

A git-onboard watermark carried by an envelope written before the export
fix above is dropped on import too, in both modes, and reported
separately (`Dropped N git-onboard watermark(s)...`) — not counted as a
skip, since it isn't a collision. Re-run `oc onboard git` on this device
afterward to re-anchor its own resume point.

Merge prints both counts (`added` and `skipped`, for projects and memory
items alike) and logs two warnings to stderr: one unconditional, naming
both edges with the counts, and one that fires only when the envelope's
`exported_at` predates the destination's newest **memory-item**
`updated_at` — i.e. this store has edits the envelope cannot contain.

The staleness signal is narrower than the hazard, deliberately. It reads
`updated_at`, never `created_at`: `onboard_git` sets cluster `created_at`
from the commit author date, so one future-dated commit would otherwise
make every legitimate envelope read as stale forever. That leaves three
local edits it cannot see — a project rename or metadata change (the
`projects` table has no `updated_at` column at all), a pin/unpin
(`set_pinned` does not bump it), and a store nobody has edited since
creation (every `updated_at` is null). It is a signal, not a guarantee;
the unconditional warning is the one that always holds.

## Project

### `oc init-project NAME`

Create a project; prints the new id (UUID).

### `oc list-projects`

Tab-separated `id\tname` per line, newest first. `--name-contains` is a
case-insensitive substring filter, matched literally — a project named
`100%` matches only itself.

There is no bulk-delete CLI command. The MCP `project_delete_bulk` tool
exists because 46 projects cost 92 MCP round-trips; in a shell that is a
`for` loop over `oc delete-project`, so a twin would add parsing and a new
output format to relieve nothing.

### `oc show-project PROJECT_ID`

Project metadata. `--json` for structured output.

### `oc update-project PROJECT_ID`

Rename or replace metadata. Set at least one of `--name` / `--metadata`;
whichever you omit is left untouched. Pass `--metadata '{}'` to clear.

### `oc delete-project PROJECT_ID`

Preview by default — prints the project name and how many memories would
go with it. Add `--confirm` to actually delete. The cascade takes the
project row, its memories, and their embeddings in one transaction. There
is no soft-delete; `oc db backup` is the only recovery path.

## Database

### `oc db info`

File sizes, row counts (projects / memory_items / memory_embeddings),
SQLite pragmas, integrity check.

### `oc db vacuum`

`PRAGMA wal_checkpoint(TRUNCATE)` + `VACUUM`. Note: this command does
NOT auto-backup; the maintenance loop's `db_vacuum` job DOES. Take a
manual backup first if you're running this ad-hoc.

### `oc db backup PATH [--force]`

Online backup via the SQLite backup API; atomic `.tmp` → rename. Safe
to run while writes are in flight.

### `oc db stats`

Project / memory / pinned / embedding counts. `--json` available.

## Onboarding

### `oc onboard git --project-id ID --repo-path .`

Bootstrap memories from local git history. `--max-commits` (default
500), `--max-memories` (clusters; default 15), `--force` (delete prior
git-onboard memories **and the watermark**, then re-run from scratch),
`--dry-run` (print clusters without saving; touches nothing).

Shares its orchestration with the `onboard_git` MCP tool since
2026-08-16, so the semantics match: runs are **incremental** past a
stored watermark (re-running only walks new commits), the resolved
branch + head SHA are printed, and an unreachable watermark (history
rewrite / force-push) automatically falls back to a full walk with a
duplicate-memories warning instead of erroring.

For remote repos, use the `onboard_git` MCP tool — that path clones
shallow into a tmpdir on the server side.

## Maintenance

### `oc maintenance list [--json]`

Show configured jobs and their schedules. Surfaces
`OC_MAINTENANCE_DISABLED` state.

### `oc maintenance run-once JOB_NAME`

Manually invoke a single maintenance handler. Useful at cutover time
(`oc maintenance run-once embedding_backfill` after migrating).

Job names: `db_backup`, `db_vacuum`, `db_integrity_check`,
`embedding_backfill`, `git_onboard_resync`.

## Operator

### `oc init`

Create the runtime directory tree. The command is idempotent and does
not create or overwrite configuration templates. Add the global
`--json` flag for machine-readable output.

### `oc config show [--json]`

Print effective configuration: paths, `core.json` contents, and masked
`OC_*` secret env vars. Names containing KEY/SECRET/TOKEN/PASSWORD are
masked in both human and JSON output.

### `oc version [--json]`

Package version + Python version.

## Removed in v3

These v2 commands were dropped along with their subsystems:

| Command | Replacement |
|---|---|
| `oc chat` / `oc convo` | OC has no LLM in v3. Use Claude Code, Goose, etc. via the MCP server. |
| `oc init-config` (removed 2026-08-16) | Was a v2 leftover: it scaffolded LLM model configs and a `core.json` whose every key v3 ignores, while writing none of the sections v3 reads. `core.json` is optional — create it by hand per [config_files.md](../configuration/config_files.md). |
| `oc story <subcmd>` | Storytelling plugin archived on `archive/openchronicle.v2`. |
| `oc task` / `oc run-task` / `oc list-tasks` | Orchestrator gone. |
| `oc scheduler add/list/...` | Replaced by the in-process maintenance loop. |
| `oc discord start` | Discord interface archived. |
| `oc mcp serve` | MCP is mounted into `oc serve` now. |
| `oc asset` / `oc media` / `oc webhook` | Subsystems archived. |
| `oc rpc` / stdio JSON-RPC | RPC layer archived. |
| `oc selftest` / `oc smoke-live` / `oc demo-summary` / `oc acceptance` | Test entry points only. |
| `oc ollama` / `oc openwebui` | Provider tooling archived. |
| `oc provider list/setup/custom` | LLM providers gone. |

## See also

- `docs/architecture/ARCHITECTURE.md` — high-level layout
- `docs/configuration/env_vars.md` — environment variables
- `docs/integrations/mcp_client_setup.md` — register the MCP server
  with Claude Code
