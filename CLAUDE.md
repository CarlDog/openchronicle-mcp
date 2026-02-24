# CLAUDE.md

## Project Status File

**`docs/CODEBASE_ASSESSMENT.md`** — single source of truth for this project.

## Project-Specific Notes

- **No backwards compatibility.** Personal project, no public users, no production.
  Break whatever needs breaking.
- **`main` is v2.** The v1 codebase is archived on `archive/openchronicle.v1`.
  The `refactor/new-core-from-scratch` branch no longer exists — all development
  happens on `main`.

## Current Sprint

**Status:** Core done. Post-core features in progress. Hybrid taxonomy decided:
scheduler and Discord are core features, not plugins (Decision #4 in assessment).
See [docs/CODEBASE_ASSESSMENT.md](docs/CODEBASE_ASSESSMENT.md) for full status.

**Next action:** Enterprise tightening Passes B + C, then Memory System Phase 2
(standalone context assembly, external turn recording), media generation port,
security scanner plugin, or webhooks.
Capability-aware routing is done (`ModelConfigLoader` parses capabilities,
`RouterPolicy` filters by `required_capabilities`, `NO_CAPABLE_MODEL` error, 12 tests).
HTTP API is done (`interfaces/api/`, FastAPI, 22 REST endpoints mirroring MCP tools,
API key auth, rate limiting, shared serializers, 51+ tests, auto-starts with `oc serve`).
MoE execution strategy is done (`application/services/moe_execution.py`, Jaccard
consensus, `--moe` CLI/MCP, 32 tests).
MCP server is done (`interfaces/mcp/`, 24 tools, 37 tests + 7 posture, `oc mcp serve`
CLI, stdio + SSE transports, lazy import guard).
Asset management is done (`domain/models/asset.py`, `application/services/asset_storage.py`,
`application/use_cases/upload_asset.py`, `application/use_cases/link_asset.py`,
4 MCP tools, 4 CLI commands, SHA-256 dedup, generic linking, 40 tests).
Discord interface is done (`interfaces/discord/`, `commands.Bot` subclass, 6 slash
commands, session mapping, message splitting, 85 tests, `oc discord start` CLI).
Scheduler service is done (tick-driven, atomic claim, 53 tests, CLI + RPC).
LLMPort function calling/tool use is done (all 6 adapters, 53 contract tests).
Time context injection is done (current time, last interaction timestamp,
seconds delta — raw data in every conversation turn for bot time awareness).
File-based config is done (single `core.json`, enriched model configs, plugin
configs co-located at `plugins/<name>/config.json`).
Memory System Phase 1 is done (`memory_update` use case with `updated_at` tracking,
tag-filtered search with AND logic on `search_memory`, 19 new tests).
Memory System Phase 1.1 is done (interface parity: `memory_get`/`delete`/`stats` on MCP + API,
pagination with `offset`, source index, streaming telemetry fix, observability events
`memory.search_completed` + `context.assembly_breakdown`, 27 new tests).
Config externalization is done (conversation defaults + Discord operational
settings wired through three-layer precedence, hygiene test prevents drift).
Docker CI is done (GitHub Actions multi-arch build to `ghcr.io/openchronicle/core`,
`latest` + SHA tags, GHA cache, `.gitattributes` for LF shell scripts).
Enterprise Tightening Pass A is done (domain exceptions `NotFoundError`/`ValidationError`,
global FastAPI exception handlers, Pydantic `Field()`/`Query()` input validation,
sqlite_store rowcount checks, file path validation, ~30 use-case migration sites,
32 new tests, 1128 total).

## Build and Development

```bash
# Install in development mode
pip install -e ".[dev]"

# With optional LLM providers
pip install -e ".[openai]"    # OpenAI support
pip install -e ".[ollama]"    # Ollama support
pip install -e ".[discord]"   # Discord bot support
pip install -e ".[mcp]"      # MCP server support

# Setup pre-commit hooks
pip install pre-commit && pre-commit install
```

## Testing

```bash
# Run all tests (excludes integration tests by default)
pytest

# Run integration tests (requires OC_LLM_PROVIDER, OPENAI_API_KEY env vars)
pytest -m integration

# Run specific test file or single test
pytest tests/test_budget_gate.py
pytest tests/test_budget_gate.py::test_specific_name -v
```

## Linting and Formatting

```bash
# Format and lint with ruff
ruff format src tests plugins
ruff check --fix src tests plugins

# Type checking
mypy src tests plugins --config-file=pyproject.toml

# Markdown linting
npm run lint:md:fix

# Run all checks (what pre-commit does)
pre-commit run --all-files
```

## Architecture

Python 3.11+ project using **hexagonal architecture**: `domain/` (pure business
logic, ports) -> `application/` (use cases, policies, orchestration) ->
`infrastructure/` (LLM adapters, persistence, routing). CLI and API live in
`interfaces/`. See [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)
for the full directory tree and layer descriptions.

**Key Concepts:**

- **Ports**: Abstract interfaces in `domain/ports/` that infrastructure implements
- **Event Model**: Hash-chained events for tamper-evident task timelines (`prev_hash` -> `hash`)
- **Task Handlers**: Async functions registered by handler name (e.g., `hello.echo`, `story.draft`)
- **Plugins**: Discovered from `plugins/` directory, loaded via `importlib.util`
- **Routing**: Provider/model selection via pools (fast, quality, nsfw) with fallback support
- **Scheduler**: Core service in `application/services/scheduler.py` (not a plugin)
- **Discord**: Interfaces driver in `interfaces/discord/` (optional extra, not a plugin)
- **MCP Server**: Interfaces driver in `interfaces/mcp/` (optional extra, 24 tools, FastMCP)
- **HTTP API**: Interfaces driver in `interfaces/api/` (FastAPI, 22 REST endpoints, auto-starts with `oc serve`)
- **MoE Execution**: `application/services/moe_execution.py` — Mixture-of-Experts consensus strategy (`--moe` flag)
- **Asset Management**: `domain/models/asset.py` + `application/services/asset_storage.py` — filesystem storage, SHA-256 dedup, generic entity linking

## Conventions

**Naming:**

- Event types: dot-separated lowercase (`llm.requested`, `task.completed`)
- Task types: use `plugin.invoke` with handler in payload (not dotted task types)
- Handler names: dot-separated lowercase (`story.draft`, `hello.echo`)
- Error codes: SCREAMING_SNAKE_CASE (`INVALID_ARGUMENT`, `BUDGET_EXCEEDED`)

**Patterns:**

- All task handlers are async functions
- Strict typing enforced by mypy
- Domain models use `@dataclass`
- Tests use pytest fixtures; integration tests marked with `@pytest.mark.integration`
- Not-found conditions raise `NotFoundError` (from `domain/exceptions.py`), caught globally → HTTP 404
- Validation failures raise `ValidationError` (aliased `DomainValidationError` to avoid Pydantic collision), caught globally → HTTP 422
- Global exception handlers in `interfaces/api/app.py` eliminate per-route try/except
- Pydantic `Field()` constraints on request bodies; `Query()` constraints on query parameters

**Secrets:**

- Zero secrets in repo (enforced by `test_no_secrets_committed.py`)
- Use `.env.local` (git-ignored) or `config/` directory for secrets
- Test placeholders: `changeme`, `replace_me`, `your_key_here`, `test-key`

## Environment Variables

Most-used variables for quick reference:

| Variable | Purpose | Default |
| ---------- | --------- | --------- |
| `OC_LLM_PROVIDER` | Provider selection (`stub`, `openai`, `ollama`, `anthropic`, `groq`, `gemini`) | `stub` |
| `OPENAI_API_KEY` | OpenAI authentication | - |
| `ANTHROPIC_API_KEY` | Anthropic authentication | - |
| `GROQ_API_KEY` | Groq authentication | - |
| `GEMINI_API_KEY` | Gemini authentication (also accepts `GOOGLE_API_KEY`) | - |
| `OC_DB_PATH` | SQLite database location | `data/openchronicle.db` |

Full reference (~60 variables covering budget, rate limiting, routing, privacy,
telemetry, and more): [docs/configuration/env_vars.md](docs/configuration/env_vars.md)

## OpenChronicle Memory Integration

OC is available as an MCP server. It provides persistent memory that
survives context compression and session boundaries. **Use it.**

Context compression loses the "why" — decisions made, approaches
rejected, working state, user preferences expressed mid-session. The
status doc (`CODEBASE_ASSESSMENT.md`) tracks project-level state but
not conversational context. OC memory fills that gap.

### Setup

Configure in `.claude/settings.json` (project-level):

```json
{
  "mcpServers": {
    "openchronicle": {
      "command": "oc",
      "args": ["mcp", "serve"]
    }
  }
}
```

### Project Identity

Use `project_id: "0db2b2ff-f995-4f59-b059-0fae5c78909d"` in all `memory_save`
calls. This is a FK to the projects table — freeform strings will fail.

If the DB is recreated, create a new project with `project_create` and update
this UUID.

### Session Protocol Addition

After the standard session protocol (Serena onboarding, status doc,
CLAUDE.md sprint), add:

- Call `memory_search` with keywords relevant to the current task or
  the user's first message. Review results for prior decisions,
  rejected approaches, and working context from previous sessions.

This step is **especially critical after context compression**, where
the compression summary is a lossy snapshot. OC memory is the lossless
record.

### When to Save

Call `memory_save` when any of these happen during a session:

- **Decision made.** Architecture, design, or approach chosen. Include
  what was decided, alternatives considered, and the reasoning.
- **Approach rejected.** Something was tried and didn't work. Save what
  it was, why it failed, and what replaced it.
- **Milestone completed.** A feature or significant unit of work is done.
  Summarize what was built and any non-obvious gotchas.
- **User preference expressed.** The user states a workflow preference,
  convention, or standing instruction that isn't already in CLAUDE.md
  or working-style.md.
- **Scope change.** The user redirects mid-task. Save what changed and
  why, so future sessions don't re-tread the old path.
- **Pre-compression.** If a session is getting long (many tool calls,
  complex multi-step work), proactively save working context — what
  we're doing, where we are in it, what's left. Don't wait to be asked.
  There is no hook for compression; the only mitigation is saving early.

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
| `context_recent` | Occasionally | Catch up on prior OC activity |
| `health` | Rarely | Diagnostics only |
| `conversation_ask` | **Never** | Routes through a second LLM — you ARE the LLM |
| `conversation_*` | **No** | Not needed for Claude Code use case |

### Known Gaps

- **No compression hook.** We can't detect when compression is about to
  happen. Mitigation: save-as-you-go discipline.
- **Search is keyword-based.** Quality depends on good content and tags.
  Write memories as if future-you is searching for them with obvious
  keywords.
- **Untested in real sessions.** This integration is new. If memory
  retrieval isn't useful, or save cadence is wrong, flag it so we can
  iterate on these rules.

## Key Files

- `pyproject.toml` - Project config, dependencies, tool settings
- `docs/architecture/ARCHITECTURE.md` - Detailed architecture documentation
- `docs/architecture/PLUGINS.md` - Plugin development guide
- `docs/cli/commands.md` - CLI command reference (all `oc` subcommands)
- `docs/configuration/env_vars.md` - Full environment variables reference
- `docs/design/design_decisions.md` - Core subsystem design rationale
- `docs/protocol/stdio_rpc_v1.md` - RPC protocol specification
- `docs/integrations/mcp_server_spec.md` - OC MCP server spec (Goose/Serena triangle)
- `docs/BACKLOG.md` - Feature and implementation backlog
- `tests/test_architectural_posture.py` - Posture enforcement (core agnostic, session isolation, enqueue allowlist)
- `tests/test_hexagonal_boundaries.py` - Layer boundary enforcement (domain, application, core vs discord/mcp)
- `src/openchronicle/core/application/services/orchestrator.py` - Main orchestrator
- `src/openchronicle/interfaces/api/app.py` - HTTP API app factory (FastAPI)
- `src/openchronicle/interfaces/serializers.py` - Shared dict serializers (MCP + API)
- `src/openchronicle/interfaces/cli/main.py` - CLI entry point (`oc` command)
