# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

This is a Python 3.11+ project using **hexagonal architecture** with three layers:

```text
src/openchronicle/
├── core/
│   ├── domain/           # Pure business logic, models, ports (no external deps)
│   │   ├── models/       # Task, Project, Agent, Event, Conversation, Memory dataclasses
│   │   ├── ports/        # Abstract interfaces (LLMPort, StoragePort, PluginPort, etc.)
│   │   ├── services/     # Domain services (replay, verification, usage_tracker)
│   │   └── errors/       # Error codes and exceptions
│   ├── application/      # Use cases, orchestration, policies
│   │   ├── policies/     # BudgetGate, RateLimiter, RetryController
│   │   ├── routing/      # RouterPolicy, PoolConfig, FallbackExecutor
│   │   ├── runtime/      # Container, PluginLoader, TaskHandlerRegistry
│   │   ├── services/     # OrchestratorService, LLMExecution
│   │   ├── use_cases/    # All application use cases (ask_conversation, smoke_live, etc.)
│   │   ├── replay/       # Project state replay and usage derivation
│   │   └── observability/# Execution index and telemetry
│   └── infrastructure/   # Technical implementations
│       ├── llm/          # Provider adapters (OpenAI, Anthropic, Ollama, Stub)
│       ├── persistence/  # SqliteStore
│       ├── privacy/      # Privacy gate implementation
│       ├── routing/      # Rule-based and hybrid routers
│       └── router_assist/# NSFW classification (linear, ONNX)
└── interfaces/
    ├── cli/              # CLI via argparse, JSON-RPC stdio protocol
    └── api/              # HTTP API stub
```

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

### Core Paths

| Variable | Purpose | Default |
|----------|---------|---------|
| `OC_DB_PATH` | SQLite database location | `data/openchronicle.db` |
| `OC_CONFIG_DIR` | Configuration directory | `config` |
| `OC_PLUGIN_DIR` | Plugin directory | `plugins` |
| `OC_OUTPUT_DIR` | Output/export directory | `output` |

### LLM Provider Selection

| Variable | Purpose | Default |
|----------|---------|---------|
| `OC_LLM_PROVIDER` | Provider selection (`stub`, `openai`, `ollama`, `anthropic`) | `stub` |
| `OPENAI_API_KEY` | OpenAI authentication | - |
| `OPENAI_MODEL` | OpenAI model override | `gpt-4o-mini` |
| `OC_LLM_MODEL_FAST` | Model for fast pool | - |
| `OC_LLM_MODEL_QUALITY` | Model for quality pool | - |
| `OC_LLM_DEFAULT_MODE` | Default routing mode (`fast`, `quality`) | `fast` |

### Budget and Rate Limiting

| Variable | Purpose | Default |
|----------|---------|---------|
| `OC_MAX_TOKENS_PER_TASK` | Budget limit per task | - |
| `OC_MAX_OUTPUT_TOKENS_PER_CALL` | Max output tokens per LLM call | - |
| `OC_LLM_RPM_LIMIT` | Rate limit (requests/minute) | - |
| `OC_LLM_TPM_LIMIT` | Rate limit (tokens/minute) | - |
| `OC_LLM_MAX_WAIT_MS` | Max wait for rate limiting | `5000` |
| `OC_LLM_MAX_RETRIES` | Max retry attempts | `2` |
| `OC_LLM_MAX_RETRY_SLEEP_MS` | Max sleep per retry | `2000` |

### Routing and Pools

| Variable | Purpose | Default |
|----------|---------|---------|
| `OC_LLM_FAST_POOL` | Providers for fast pool | - |
| `OC_LLM_QUALITY_POOL` | Providers for quality pool | - |
| `OC_LLM_POOL_NSFW` | Provider for NSFW content | - |
| `OC_LLM_MAX_FALLBACKS` | Max fallback attempts | `1` |
| `OC_LLM_PROVIDER_WEIGHTS` | Provider weights for selection | `ollama:100,openai:20` |

### Privacy

| Variable | Purpose | Default |
|----------|---------|---------|
| `OC_PRIVACY_OUTBOUND_MODE` | Privacy mode (`off`, `warn`, `block`, `redact`) | `off` |
| `OC_PRIVACY_OUTBOUND_EXTERNAL_ONLY` | Only apply to external providers | `true` |
| `OC_PRIVACY_OUTBOUND_CATEGORIES` | PII categories to detect | - |

### Telemetry

| Variable | Purpose | Default |
|----------|---------|---------|
| `OC_TELEMETRY_ENABLED` | Enable telemetry | `true` |
| `OC_TELEMETRY_PERF_ENABLED` | Enable performance metrics | `true` |
| `OC_TELEMETRY_USAGE_ENABLED` | Enable usage tracking | `true` |

## Key Files

- `pyproject.toml` - Project config, dependencies, tool settings
- `docs/v2/ARCHITECTURE.md` - Detailed architecture documentation
- `docs/v2/PLUGINS.md` - Plugin development guide
- `docs/protocol/stdio_rpc_v1.md` - RPC protocol specification
- `docs/BACKLOG.md` - Feature and implementation backlog
- `src/openchronicle/core/application/services/orchestrator.py` - Main orchestrator
- `src/openchronicle/interfaces/cli/main.py` - CLI entry point (`oc` command)
