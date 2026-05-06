# CLAUDE.md

## Project Status File

**`docs/CODEBASE_ASSESSMENT.md`** — single source of truth for this project.

## Project-Specific Notes

- **Docs + memories before every commit.** Standing rule (2026-05-05).
  Before any `git commit` on this repo, update the affected docs (at
  minimum `docs/CODEBASE_ASSESSMENT.md`; for in-flight work also
  `docs/V3_PLAN.md` status section and the CLAUDE.md "Current Sprint"
  section), and save a milestone/decision/scope memory to OC if the
  MCP server is reachable. The commit and the docs land together —
  never one without the other.
- **No backwards compatibility.** Personal project, no public users,
  no production. Break whatever needs breaking.
- **Branch state.** `main` and `archive/openchronicle.v2` are pinned
  at v2 final (`bb217d9`). v3 development happens on `v3/develop` and
  will replace `main` via force-push at Phase 8 cutover. v1 lives at
  `archive/openchronicle.v1`.
- **Post-CI redeploy convention.** Once v3 is live on the NAS, pushes
  to `main` that change anything shipping in the runtime image
  (`src/`, `pyproject.toml`, `Dockerfile`, `docker-compose.nas.yml`)
  trigger a redeploy via `portainer-mcp` once both GitHub Actions
  workflows go green (`Test` + `Build and Push Docker Image`).
  Doc-only / hook-only / workflow-only pushes don't need a redeploy.

  Lookup the stack id dynamically (don't hardcode it):

  ```text
  portainer_list_stacks → filter for name == "openchronicle-mcp" → use that .Id
  portainer_redeploy_git_stack(stack_id=<id>, confirm=true, pull_image=true)
  ```

  Verify with `mcp__openchronicle__health` — a recent `db_modified_utc`
  confirms the new container is alive.

## Current Sprint

**Status:** v3 live on NAS 2026-05-06; current image
`ghcr.io/carldog/openchronicle-mcp:v3.0.0-rc3` on stack 151 (rc1 →
rc2 → rc3 within the cutover day, see
[docs/cutover-2026-05-06-triage.md](docs/cutover-2026-05-06-triage.md)
for the full account). rc3 added the senior-dev review batch (265x
semantic-search speedup via numpy, API consistency cleanups, real
MCP smoke handshake) and cleared the 12-error ruff backlog. Cost
of cutover: 36 v2 memories not preserved through to live v3 DB; v2
DB intact on disk for forensic analysis. Canonical project_id is
`fe2ef898-0152-40a4-af97-ed97cc86ca45`.

**Phase progress:**

- ✅ **Phase 0** — `archive/openchronicle.v2` snapshot pushed,
  `v3/develop` branch created
- ✅ **Phase 1** (interfaces slimmed) — Discord/asset/conversation/
  webhook/media/hooks deletion; chat/rpc/stdio modules removed; MCP
  tool descriptions rewritten
- ✅ **Phase 2** (application slimmed) — orchestrator/scheduler/MoE/
  webhook/asset/output/llm services + routing/runtime/replay/
  observability/policies dirs deleted; ~30 use cases cut; plugins/
  removed; container reduced to memory + embedding + git-onboard
- ✅ **Phase 3+4** (infrastructure + domain slimmed) — combined
  commit; sqlite_store rewritten 1882→470 LOC; schema 18→3 tables;
  `conversation_id` dropped from MemoryItem; new `ProviderError` /
  `ConfigError` domain exceptions; git_onboard service drops LLM
  synthesis (caller-side now)
- ✅ **Phase 5** (schema migration + backup + export/import) —
  versioned `Migrator` with savepoint atomicity; `001_initial.sql`
  baseline; `infrastructure/persistence/backup.py` (atomic .tmp →
  rename via SQLite backup API); `oc memory export/import` with
  `format_version=1`; `scripts/migrate_v2_to_v3.py` and
  `scripts/verify_v3_db.py`
- ✅ **Phase 6** (ASGI unification + `OC_LOG_FORMAT`) — FastAPI host
  mounts FastMCP at `/mcp`; lifespan drives FastMCP's session_manager;
  `OC_LOG_FORMAT=human|json` (default human) via
  `interfaces/logging_setup.py`; `docker-compose.nas.yml` collapsed
  3→1 service; Dockerfile drops dead extras
- ✅ **Phase 6.5** (maintenance loop + embedding degradation) —
  asyncio `MaintenanceLoop` with per-job + global locks; 5 job
  handlers (db_backup with 7-backup retention, db_vacuum runs
  db_backup first, db_integrity_check toggles
  `container.maintenance_degraded`, embedding_backfill,
  git_onboard_resync); `/api/v1/maintenance/status` endpoint;
  `oc maintenance` CLI; `EmbeddingService.search_hybrid` falls back
  to FTS5-only on provider failure; `embedding_status_dict` reports
  `degraded`/`active`
- ✅ **Phase 7** (docs sweep + repo polish) — every doc classified
  (update / archive to `docs/archive/v2/` / delete); v3 docs
  rewritten; three new docs (api/STABILITY.md,
  configuration/security_posture.md, architecture/MAINTENANCE.md);
  README rewritten per V3_PLAN voice rules; pyproject v3.0.0.dev0;
  v2 cruft swept from configs/fixtures/CI/scripts
- ✅ **Audit pass** (post-Phase 7, commit `6a667db`) — folder-by-folder
  walk of all 187 tracked files. Dropped `application/services/context_builder.py`
  (imported deleted Conversation/Turn, zero callers), empty `domain/services/`,
  4 dead `RuntimePaths` fields, ~20 dead error codes, `load_plugin_config()`,
  v2 model + router_assist template writers, vacuous `tests/test_policies_purity.py`,
  unused `tests/helpers/subprocess_env.py`. 345 tests passing.
- ✅ **Phase 8 prep** (CI + tag flow + Dependabot + runbook
  tightening) — GHA workflows now trigger on `v3/develop` too (was
  main-only, meaning 9 commits had no CI signal); `docker-publish.yml`
  gains a `tags: ["v*"]` trigger + `type=ref,event=tag` metadata so
  `git tag v3.0.0-rc1 && git push --tags` produces the matching
  Docker tag without flipping `:latest`. New `Retag GHCR Image`
  workflow_dispatch utility for the `:v2-final` rollback target
  (and future release-alias housekeeping). New
  `.github/dependabot.yml` covering pip + github-actions + docker
  (weekly Mondays, grouped minor/patch, currently target
  `v3/develop` — flip to default branch post-cutover per the
  Phase 9 Day 0 checklist). Phase 8 runbook tightened with the
  retag command, the rc tag flow, and the force-push step.
- ✅ **Phase 8** (NAS cutover, 2026-05-06) — **shipped, with turbulence.**
  Force-push `v3/develop` → `main` succeeded; `v3.0.0-rc1` Docker image
  built and live; v3 stack deployed at `:18000/mcp`. Two unplanned
  recoveries: (1) the prior session's migrated DB was corrupt by the
  time v3 first opened it (root cause unconfirmed — likely orphan
  `-wal`/`-shm` files at the destination path; possibly compounded by
  `verify_v3_db.py` doing only superficial checks rather than
  `PRAGMA integrity_check`). Recovery: abandoned migration, restarted
  v3 against a fresh empty volume; v3 booted clean. (2) `:v2-final`
  retag failed first attempt due to lowercase IMAGE_NAME bug in the
  workflow; fixed in commit `6ae71812` and re-captured by tagging
  the v2 build SHA `bb217d9` directly. Full triage at
  [docs/cutover-2026-05-06-triage.md](docs/cutover-2026-05-06-triage.md)
  with a 12-item punch list.
- ✅ **Triage punch list closed** (rolled up 2026-05-06). All 12 original
  items + 3 post-cutover MCP-transport items are DONE, deferred to a
  separate repo (portainer-mcp 400 bug), or date-gated to Phase 9. See
  [docs/cutover-2026-05-06-triage.md](docs/cutover-2026-05-06-triage.md)
  punch list section for the per-item disposition with commit refs.
- pending: Phase 9 (decommission, Day 7+ post-cutover, earliest
  2026-05-13) — also tracks **dependency audit** as a tech-debt
  follow-up (`docs/V3_PLAN.md` "Post-cutover follow-ups").

**Locked decisions** (open questions 1, 4, 6, 13, 14, 19): drop
`memory_items.conversation_id`; unified ASGI on port `:18000`; cut
plugin system entirely; MCP tool description quality pass done; ship
`oc memory export/import` day 1; `OC_LOG_FORMAT=human|json` default
human.

See [docs/V3_PLAN.md](docs/V3_PLAN.md) for the canonical phase tracker
and [docs/CODEBASE_ASSESSMENT.md](docs/CODEBASE_ASSESSMENT.md) for the
v2 → v3 delta.

## Build and Development

```bash
# Install in development mode
pip install -e ".[dev,mcp,openai,ollama]"

# Setup pre-commit hooks
pip install pre-commit && pre-commit install
```

The optional extras are deliberately small:

- `[openai]` and `[ollama]` — embedding providers only (v3 has no LLM)
- `[mcp]` — FastMCP runtime
- `[dev]` — pytest, mypy, ruff, plus the embedding deps for tests

## Testing

```bash
# Run all tests
pytest

# Run a specific test file or single test
pytest tests/test_memory_export_import.py
pytest tests/test_maintenance_loop.py::test_overlap_skip_records_skip_and_does_not_block -v
```

There are no `@pytest.mark.integration` tests in v3 — the
`tests/integration/` directory and the `integration` marker were cut
along with the conversation engine.

## Linting and Formatting

```bash
# Format and lint with ruff
ruff format src tests scripts
ruff check --fix src tests scripts

# Type checking
mypy src tests --config-file=pyproject.toml

# Markdown linting
npm run lint:md:fix

# Run all checks (what pre-commit does)
pre-commit run --all-files
```

## Architecture

Python 3.11+ project using **hexagonal architecture**: `domain/`
(pure types + ports) → `application/` (use cases, services) →
`infrastructure/` (SQLite, embedding adapters, persistence backup,
maintenance jobs). CLI / API / MCP drivers live in `interfaces/`.
See [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)
for the full layout.

**Key Concepts:**

- **Ports**: abstract interfaces in `domain/ports/` that
  infrastructure implements. v3 has three: `StoragePort`,
  `MemoryStorePort`, `EmbeddingPort`.
- **MCP Server**: `interfaces/mcp/` — 14 tools registered via
  FastMCP, mounted at `/mcp` inside the unified ASGI app.
- **HTTP API**: `interfaces/api/` — FastAPI app factory
  (`create_app`), routes for memory + project + system, FastMCP
  mounted alongside.
- **Embedding Service**: `application/services/embedding_service.py`
  — hybrid FTS5 + cosine similarity via Reciprocal Rank Fusion.
  `EmbeddingPort` adapters: `stub` / `openai` / `ollama`. Falls back
  to FTS5-only when the provider raises (degradation policy).
- **Maintenance loop**:
  `application/services/maintenance_loop.py` — single asyncio task
  dispatches due jobs as background tasks; per-job + global locks
  give skip-on-overlap with sequential-within-process. Job handlers
  in `infrastructure/maintenance/jobs.py`. See
  [docs/architecture/MAINTENANCE.md](docs/architecture/MAINTENANCE.md).
- **Schema migration framework**:
  `infrastructure/persistence/migrator.py` reads
  `migrations/NNN_*.sql` files and applies them within savepoints.
  Idempotent re-run is a no-op. v3 baseline is `001_initial.sql`.

## Conventions

**Naming:**

- Error codes: SCREAMING_SNAKE_CASE (`INVALID_ARGUMENT`, `MEMORY_NOT_FOUND`,
  `CONFIG_ERROR`, `PROVIDER_ERROR`)
- MCP tool names: snake_case (`memory_save`, `context_recent`,
  `onboard_git`)

**Patterns:**

- Strict typing enforced by mypy
- Domain models use `@dataclass`
- Not-found conditions raise `NotFoundError` (from
  `domain/exceptions.py`), caught globally → HTTP 404
- Validation failures raise `ValidationError` (aliased
  `DomainValidationError` to avoid Pydantic collision), caught
  globally → HTTP 422
- Provider failures (embedding adapters, future external systems)
  raise `ProviderError` with `error_code`/`hint`/`details`
- Config / startup-environment failures raise `ConfigError`
- Global exception handlers in `interfaces/api/app.py` eliminate
  per-route try/except
- Pydantic `Field()` constraints on request bodies; `Query()`
  constraints on query parameters
- Use `utc_now()` from `domain/time_utils.py` for current UTC time
  (not inline `datetime.now(UTC)`)
- Use `parse_csv_tags()` from `application/config/env_helpers.py`
  for comma-separated tag parsing

**Secrets:**

- Zero secrets in repo (enforced by `test_no_secrets_committed.py`)
- Use `.env.local` (git-ignored) or `OC_CONFIG_DIR` for secrets
- Test placeholders: `changeme`, `replace_me`, `your_key_here`,
  `test-key`

**GitHub Actions hygiene:**

- "Node.js 20 actions are deprecated" warnings (and any future
  Node-version deprecation) come from an action's *bundled
  runtime*, not the workflow's `runs-on`. Fix by bumping the
  action's major version to one that ships the newer Node runtime.
  Example: `actions/setup-python@v5` → `@v6` was the bump that
  silenced Node 20 warnings.
- Verify the latest major before bumping —
  `https://github.com/<owner>/<action>/releases/latest` (e.g.
  `actions/checkout/releases/latest`,
  `docker/build-push-action/releases/latest`).
- Dependabot's `github-actions` ecosystem in
  `.github/dependabot.yml` opens weekly grouped PRs for action
  bumps automatically. If a deprecation warning fires before the
  weekly run, do a manual bump and let Dependabot pick up from
  there.
- Runtime deprecation is a *warning*, not a build failure. Don't
  treat it as a cutover blocker.

## Environment Variables

Most-used variables for quick reference:

| Variable | Purpose | Default |
| ---------- | --------- | --------- |
| `OC_DATA_DIR` | Root data directory (derives all data paths when set) | *(unset)* |
| `OC_DB_PATH` | SQLite database location | `data/openchronicle.db` |
| `OC_CONFIG_DIR` | Directory containing `core.json` | `config` |
| `OC_API_HOST` / `OC_API_PORT` | Bind address + port for the unified ASGI | `127.0.0.1` / `8000` |
| `OC_API_KEY` | Bearer token (auth disabled when empty) | — |
| `OC_EMBEDDING_PROVIDER` | `none`, `stub`, `openai`, `ollama` | `none` |
| `OC_EMBEDDING_MODEL` | Embedding model name (provider-specific default) | *(provider default)* |
| `OPENAI_API_KEY` | Used by the OpenAI embedding adapter | — |
| `OLLAMA_HOST` | Used by the Ollama embedding adapter | adapter default |
| `OC_LOG_FORMAT` | `human` or `json` | `human` |
| `OC_MAINTENANCE_DISABLED` | `1`/`true`/`yes`/`on` to short-circuit the loop | unset |

Full reference (~15 variables): [docs/configuration/env_vars.md](docs/configuration/env_vars.md)

## OpenChronicle Memory Integration

OC is available as an MCP server. It provides persistent memory that
survives context compression and session boundaries. **Use it.**

Context compression loses the "why" — decisions made, approaches
rejected, working state, user preferences expressed mid-session. The
status doc (`CODEBASE_ASSESSMENT.md`) tracks project-level state but
not conversational context. OC memory fills that gap.

### Setup

OC runs on the NAS as a Portainer stack (see `docker-compose.nas.yml`).
The MCP server is registered at user scope in `~/.claude.json` as
`openchronicle` pointing at the NAS endpoint over HTTP streamable-http
transport. No project-level setup required.

**v3 endpoint:** MCP and HTTP REST are unified on port `:18000` since the
2026-05-06 cutover. MCP at `/mcp`, REST at `/api/v1/*`, liveness at
`/health`. Each machine's `~/.claude.json` should point at
`http://carldog-nas:18000/mcp`. (Pre-cutover v2 was `:18001/mcp` for MCP
and `:18000/api/v1` for REST as separate services — that shape is gone.)

For a fresh registration:

```bash
claude mcp add --scope user --transport http openchronicle http://carldog-nas:18000/mcp
```

For local dev (without the NAS), run `oc serve` in a checkout — the
unified ASGI app binds `127.0.0.1:8000` by default, so:

```bash
claude mcp add --scope user --transport http openchronicle http://127.0.0.1:8000/mcp
```

(That uses the local OC store, which is a different memory pool than
the NAS one.)

### Project Identity

Use `project_id: "fe2ef898-0152-40a4-af97-ed97cc86ca45"` in all
`memory_save` calls on the NAS-hosted OC. This is a FK to the projects
table — freeform strings will fail. (Project name on the NAS is
`openchronicle-mcp`, created 2026-05-06 during the v3 cutover.)

**Historical project_ids (no longer valid against the live DB):**

- `87de0f7d-d6ab-4b83-8613-b2b5ff60a57b` — v2 NAS project (lost 2026-05-06
  when the v3 cutover migration produced a corrupt DB and we restarted
  v3 against a fresh empty volume; ~24 memories from v2 are unrecoverable
  from the live DB but preserved on disk for forensic analysis at
  `/volume1/@docker/volumes/openchronicle-mcp_oc-data/_data/openchronicle.db.v2-rollback`)
- `0db2b2ff-f995-4f59-b059-0fae5c78909d` — LOCAL OC (Windows machine),
  separate memory pool, never valid against NAS

If the NAS DB is recreated again in the future, create a new project
with `project_create` and update this UUID.

**Auth posture (decided 2026-05-06, post-cutover):** `OC_API_KEY` on
stack 151 resolves to empty — auth is **intentionally disabled**.
This is a single-user home-LAN deployment, the LAN is trusted, no MCP
clients are configured to send a bearer header, and the cost/benefit
of switching doesn't pay. If the trust boundary ever changes (public
exposure, untrusted LAN segment, multi-user environment), follow the
"How to enable auth on a running deployment" steps in
[docs/configuration/security_posture.md](docs/configuration/security_posture.md#authentication).

### Session Protocol Addition

After the standard session protocol (status doc, CLAUDE.md sprint),
add:

- Call `memory_search` with keywords relevant to the current task or
  the user's first message. Review results for prior decisions,
  rejected approaches, and working context from previous sessions.

This step is **especially critical after context compression**, where
the compression summary is a lossy snapshot. OC memory is the
lossless record.

### When to Save

Call `memory_save` when any of these happen during a session:

- **Decision made.** Architecture, design, or approach chosen.
  Include what was decided, alternatives considered, and the
  reasoning.
- **Approach rejected.** Something was tried and didn't work. Save
  what it was, why it failed, and what replaced it.
- **Milestone completed.** A feature or significant unit of work is
  done. Summarize what was built and any non-obvious gotchas.
- **User preference expressed.** The user states a workflow
  preference, convention, or standing instruction that isn't already
  in CLAUDE.md.
- **Scope change.** The user redirects mid-task. Save what changed
  and why, so future sessions don't re-tread the old path.
- **Pre-compression.** If a session is getting long (many tool calls,
  complex multi-step work), proactively save working context — what
  we're doing, where we are in it, what's left. There is no hook for
  compression; the only mitigation is saving early.

**Tagging convention:**

| Tag | When |
| ----- | ------ |
| `decision` | Architectural or design decisions |
| `rejected` | Approaches tried and abandoned |
| `milestone` | Completed work summaries |
| `context` | Working state snapshots (proactive saves) |
| `convention` | Patterns, preferences, recurring gotchas |
| `scope` | Scope changes and reprioritizations |

Pin memories that represent standing rules or conventions.

**Don't save:**

- Routine file edits or commands (too granular, no retrieval value)
- Anything already captured in `docs/CODEBASE_ASSESSMENT.md`
- Speculative plans that haven't been confirmed by the user

### When to Load

Call `memory_search` at these points:

- **Session start / post-compression.** Search for the current task
  topic. This is non-negotiable after compression.
- **Before starting a new area of work.** Check if prior context exists.
- **When something feels familiar.** If a problem seems like it was
  discussed before, search before re-deriving from scratch.

### Tools to Use / Avoid

| Tool | Use | Notes |
| ------ | ----- | ------- |
| `memory_save` | **Yes** | Primary persistence mechanism |
| `memory_search` | **Yes** | Primary retrieval mechanism |
| `memory_list` | Occasionally | Browse recent memories when search terms are unclear |
| `memory_pin` | Yes | Pin standing conventions and rules |
| `memory_update` | Yes | Update content/tags of existing memories |
| `context_recent` | Occasionally | Catch up on prior memory activity for a project |
| `health` | Rarely | Diagnostics only |

The v2 conversation tools (`conversation_*`, `turn_record`,
`context_assemble`, `search_turns`) are gone in v3 — Claude Code IS
the LLM, so OC's role is memory/retrieval only.

### Known Gaps

- **No compression hook.** We can't detect when compression is about
  to happen. Mitigation: save-as-you-go discipline.
- **Search is keyword-based by default.** Set `OC_EMBEDDING_PROVIDER`
  to enable hybrid semantic+keyword search. Without it, quality
  depends on good content and tags. Write memories as if future-you
  is searching for them with obvious keywords.

## Key Files

- `pyproject.toml` — Project config, dependencies, tool settings
- `docs/architecture/ARCHITECTURE.md` — v3 layout + schema + ASGI design
- `docs/architecture/MAINTENANCE.md` — maintenance loop + degradation policy
- `docs/cli/commands.md` — `oc` subcommand reference
- `docs/configuration/env_vars.md` — environment variables
- `docs/configuration/config_files.md` — `core.json` schema
- `docs/configuration/security_posture.md` — threat model + secrets handling
- `docs/integrations/mcp_server_spec.md` — MCP tool surface (14 tools)
- `docs/integrations/mcp_client_setup.md` — registering Claude Code, Goose, Open WebUI
- `docs/api/STABILITY.md` — semver + deprecation policy
- `docs/V3_PLAN.md` — full v3 plan, kill list, open questions, phase tracker
- `docs/archive/v2/` — frozen v2 docs (orchestrator, conversation engine, plugin system, etc.)
- `tests/test_architectural_posture.py` — core agnostic of MCP SDK
- `tests/test_hexagonal_boundaries.py` — domain/application/infrastructure layering
- `src/openchronicle/interfaces/api/app.py` — unified ASGI factory (FastAPI + FastMCP at /mcp)
- `src/openchronicle/interfaces/cli/main.py` — `oc` command entry point
- `src/openchronicle/core/infrastructure/wiring/container.py` — DI composition root
- `src/openchronicle/core/infrastructure/persistence/migrator.py` — schema migration runner
- `scripts/migrate_v2_to_v3.py` + `scripts/verify_v3_db.py` — one-shot cutover migration
