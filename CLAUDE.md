# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working Style

**Read these first every session:**

- This file (always loaded automatically)
- `docs/CODEBASE_ASSESSMENT.md` — the project bible. Contains current state,
  Definition of Done, resolved decisions, and refactoring priorities. Read it
  before proposing or starting any work.

**How the owner works:**

- **Discuss before implementing.** Always talk through the approach before writing
  code. The owner wants to understand and approve the direction, not just see a PR.
- **No backwards compatibility.** This is a personal project with no public users
  and no production deployment. Break whatever needs breaking.
- **Push back on scope creep.** The owner self-describes as having "a tendency to
  wander." If a request is drifting away from the current sprint or the Definition
  of Done, say so directly. Be a guardrail, not a yes-man.
- **Be direct.** The owner responds well to honest technical opinions and pushback.
  Don't hedge or soften assessments. Say what you think.
- **Don't over-engineer.** This is a personal project. Solve the problem in front
  of you. Don't add abstraction layers for hypothetical future requirements.

**Session discipline:**

- If a session is getting long or complex, proactively offer to write a handoff
  note (update Current Sprint below + MEMORY.md) before context compression hits.
- When starting a new session after compression, read the assessment document
  before doing anything else.

## Current Sprint

**Objective:** Get core to "done" — a fully operational daemon you can interact
with like a chatbot via CLI, with durable memory, explainable routing, and a
stable plugin surface.

**Definition of Done (4 must-haves):**

1. Interactive chat REPL (`oc chat`) — auto-create/resume conversations, no UUIDs
2. Streaming responses (`stream_async()` on LLMPort + all 5 adapters + CLI, with
   `--no-stream` opt-out toggle)
3. Interface layer refactoring — split God Functions into dispatch tables
4. Conversation UX shortcuts — `--latest`, `--resume`, auto-create

**Current status:** Planning phase. Assessment complete (rev 2), all three open
decisions resolved, CLAUDE.md and MEMORY.md updated with working style and sprint
context. No code changes pending — clean working tree except docs.

**Next action:** Commit the assessment + CLAUDE.md + MEMORY.md updates, then plan
Phase 1 (interface layer refactoring — split God Functions in main.py and stdio.py
into dispatch tables). This unblocks everything else.

**Important:** docs/CODEBASE_ASSESSMENT.md, CLAUDE.md, and MEMORY.md all have
uncommitted changes from this session. Commit these first.

**Recently completed:**

- All 5 LLM adapters built out (OpenAI, Anthropic, Groq, Gemini, Ollama)
- Codebase assessment written with full project history context
- Three open decisions resolved (manager/worker, streaming, memory self-report)

**Resolved decisions (see assessment for full rationale):**

- Manager/worker stays in core (runtime capability, not domain feature)
- Streaming is must-have with `--no-stream` opt-out
- Memory self-report: keep lenient, remove strict mode

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
- `docs/configuration/env_vars.md` - Full environment variables reference
- `docs/design/design_decisions.md` - Core subsystem design rationale
- `docs/protocol/stdio_rpc_v1.md` - RPC protocol specification
- `docs/BACKLOG.md` - Feature and implementation backlog
- `src/openchronicle/core/application/services/orchestrator.py` - Main orchestrator
- `src/openchronicle/interfaces/cli/main.py` - CLI entry point (`oc` command)
