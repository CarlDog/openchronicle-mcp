# OpenChronicle Core v2

An orchestration core for a manager/supervisor/worker LLM system, built with
hexagonal architecture in Python 3.11+.

- Source root: `src/openchronicle/`
- Plugins: `plugins/`
- Docker: `ghcr.io/openchronicle/core`

## Installation

```bash
pip install -e .                # Base install (includes stub provider)
pip install -e ".[openai]"      # OpenAI support
pip install -e ".[ollama]"      # Ollama local inference
pip install -e ".[dev]"         # Development dependencies
```

Use `oc --help` to explore the CLI.

## Provider Selection

Control which LLM provider to use via `OC_LLM_PROVIDER`:

- **`stub` (default)**: Deterministic stub for testing/demos
- **`openai`**: OpenAI API (requires `OPENAI_API_KEY`)
- **`ollama`**: Local Ollama instance
- **`anthropic`**: Anthropic Claude API

```bash
# Use local Ollama
export OC_LLM_PROVIDER=ollama
oc demo-summary <project_id> "Your text here"

# Use OpenAI
export OC_LLM_PROVIDER=openai
export OPENAI_API_KEY=your_key_here
oc demo-summary <project_id> "Your text here"
```

For the full list of environment variables (budget, rate limiting, routing,
privacy, telemetry, and more), see
[docs/configuration/env_vars.md](docs/configuration/env_vars.md).

## Secret Management

OpenChronicle follows a **zero-secrets-in-repo** policy enforced by
`tests/test_no_secrets_committed.py`.

- Use `.env.local` (git-ignored) or `config/` directory for secrets
- Use obvious placeholders in examples: `changeme`, `replace_me`,
  `your_key_here`, `test-key`

## Docker

The Docker setup separates **immutable core** (application code baked into the
image) from **persistent userland** (data, config, plugins, outputs mounted on
the host).

```bash
# Quick start
docker compose run --rm openchronicle --help
docker compose run --rm openchronicle smoke-live "Hello" --provider stub
```

Persistent volumes:

- `/data` -- SQLite DB
- `/config` -- Optional config files
- `/plugins` -- Plugin packages
- `/output` -- Artifact exports

## Documentation

| Document | Description |
| -------- | ----------- |
| [Architecture](docs/architecture/ARCHITECTURE.md) | Hexagonal architecture, layers, event model |
| [Plugin Guide](docs/architecture/PLUGINS.md) | Full plugin development guide |
| [Plugin Contract](docs/plugins/plugin_contract.md) | Plugin guarantees and requirements |
| [Plugin Quickstart](docs/plugins/plugin_quickstart.md) | Get a plugin running fast |
| [Environment Variables](docs/configuration/env_vars.md) | All ~60 configuration variables |
| [Design Decisions](docs/design/design_decisions.md) | Rationale for core subsystems |
| [RPC Protocol](docs/protocol/stdio_rpc_v1.md) | JSON-RPC stdio protocol spec |
| [Backlog](docs/BACKLOG.md) | Feature and implementation backlog |
| [CLAUDE.md](CLAUDE.md) | AI assistant instructions for this repo |

## License

[AGPL-3.0](LICENSE) — free to use, modify, and share. If you run a modified
version as a network service, you must publish your source under the same
license.
