# CLAUDE.md

## Project Status File

**`docs/CODEBASE_ASSESSMENT.md`** — single source of truth for this project.

## Project-Specific Notes

- **No backwards compatibility.** Personal project, no public users, no production.
  Break whatever needs breaking.

## Current Sprint

**Status:** Core done. All must-haves and should-have refactoring complete.
Plugin phase starting. See
[docs/CODEBASE_ASSESSMENT.md](docs/CODEBASE_ASSESSMENT.md) for full status.

**Next action:** Scheduler Plugin (P0) — design and implement.

## Build and Development

```bash
# Install in development mode
pip install -e ".[dev]"

# With optional LLM providers
pip install -e ".[openai]"    # OpenAI support
pip install -e ".[ollama]"    # Ollama support

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

**Secrets:**

- Zero secrets in repo (enforced by `test_no_secrets_committed.py`)
- Use `.env.local` (git-ignored) or `config/` directory for secrets
- Test placeholders: `changeme`, `replace_me`, `your_key_here`, `test-key`

## Environment Variables

Most-used variables for quick reference:

| Variable | Purpose | Default |
|----------|---------|---------|
| `OC_LLM_PROVIDER` | Provider selection (`stub`, `openai`, `ollama`, `anthropic`) | `stub` |
| `OPENAI_API_KEY` | OpenAI authentication | - |
| `OC_DB_PATH` | SQLite database location | `data/openchronicle.db` |

Full reference (~60 variables covering budget, rate limiting, routing, privacy,
telemetry, and more): [docs/configuration/env_vars.md](docs/configuration/env_vars.md)

## Key Files

- `pyproject.toml` - Project config, dependencies, tool settings
- `docs/architecture/ARCHITECTURE.md` - Detailed architecture documentation
- `docs/architecture/PLUGINS.md` - Plugin development guide
- `docs/cli/commands.md` - CLI command reference (all `oc` subcommands)
- `docs/configuration/env_vars.md` - Full environment variables reference
- `docs/design/design_decisions.md` - Core subsystem design rationale
- `docs/protocol/stdio_rpc_v1.md` - RPC protocol specification
- `docs/BACKLOG.md` - Feature and implementation backlog
- `src/openchronicle/core/application/services/orchestrator.py` - Main orchestrator
- `src/openchronicle/interfaces/cli/main.py` - CLI entry point (`oc` command)
