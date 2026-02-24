# OpenChronicle

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-ghcr.io%2Fopenchronicle%2Fcore-blue?logo=docker)](https://ghcr.io/openchronicle/core)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://python.org)
[![CI](https://github.com/OpenChronicle/core/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/OpenChronicle/core/actions/workflows/docker-publish.yml)

**Persistent memory and context for LLM conversations.**

Chat context dies between sessions. OpenChronicle fixes that — it's an
orchestration core that gives any LLM durable memory, explainable routing,
and auditable decision history across conversations, sessions, and tools.

## Features

- **Persistent memory** — full-text search (FTS5) with deterministic
  fallback, pinning, tagging; conversations resume where you left off
- **Multi-provider routing** — OpenAI, Anthropic, Groq, Gemini, Ollama with
  pool-based selection and automatic fallback
- **Mixture-of-Experts** — consensus answers from multiple models via
  `--moe` flag
- **Streaming responses** — token-by-token output with `--no-stream` opt-out
- **Hash-chained event log** — tamper-evident audit trail for every decision
- **MCP server** — 20 tools exposing memory, conversation, and context to
  any MCP-compatible client (Claude Code, Goose, VS Code)
- **HTTP API** — 20 REST endpoints mirroring MCP tools, API key auth, rate
  limiting, auto-starts with `oc serve`
- **Discord bot** — slash commands, session mapping, multi-user isolation
- **Scheduler** — tick-driven job execution with atomic claim and drift
  prevention
- **Asset management** — file storage with SHA-256 dedup and generic linking
- **Plugin system** — extend with stateless task handlers
- **Privacy gate** — PII detection (6 categories, Luhn validation) before
  data leaves your machine
- **Hexagonal architecture** — enforced by tests, not convention

## Quick Start

```bash
pip install -e ".[openai]"
oc init
export OPENAI_API_KEY=your_key_here
oc chat
```

That's it. You're in a persistent conversation with memory, streaming, and
full audit trail.

## Quick Start (Docker)

```bash
docker pull ghcr.io/openchronicle/core:latest
docker compose run --rm openchronicle chat
```

Persistent volumes: `/data` (SQLite DB), `/config`, `/plugins`, `/output`.

## Interfaces

| Interface | Entry point | Use case |
| ----------- | ------------- | ---------- |
| **CLI** | `oc chat`, `oc convo ask` | Interactive and scripted use |
| **STDIO RPC** | `oc serve` / `oc rpc` | Programmatic integration |
| **HTTP API** | Auto-starts with `oc serve` | REST clients, webhooks, web UIs |
| **MCP Server** | `oc mcp serve` | Agent interop (Goose, Claude Code) |
| **Discord** | `oc discord start` | Chat bot with slash commands |

## Supported Providers

| Provider | Extra | Streaming | Tool Use |
| ---------- | ------- | ----------- | ---------- |
| OpenAI | `.[openai]` | Yes | Yes |
| Anthropic | `.[anthropic]` | Yes | Yes |
| Groq | `.[groq]` | Yes | Yes |
| Gemini | `.[gemini]` | Yes | Yes |
| Ollama | `.[ollama]` | Yes | Yes |
| Stub | *(built-in)* | Yes | Yes |

## Documentation

| Document | Description |
| ---------- | ------------- |
| [Architecture](docs/architecture/ARCHITECTURE.md) | Hexagonal layers, event model, directory tree |
| [CLI Commands](docs/cli/commands.md) | Full `oc` command reference |
| [Environment Variables](docs/configuration/env_vars.md) | All ~60 configuration knobs |
| [MCP Server Spec](docs/integrations/mcp_server_spec.md) | Tool list, transports, integration guide |
| [Plugin Guide](docs/architecture/PLUGINS.md) | Build and register task handlers |
| [Design Decisions](docs/design/design_decisions.md) | Rationale for core subsystems |
| [RPC Protocol](docs/protocol/stdio_rpc_v1.md) | JSON-RPC stdio protocol spec |
| [Backlog](docs/BACKLOG.md) | Roadmap and feature backlog |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md).

## License

[AGPL-3.0](LICENSE) — free to use, modify, and share. Network service use
requires publishing source under the same license.
