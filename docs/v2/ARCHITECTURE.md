# OpenChronicle v2 Architecture (Clean Slate)

## Goals

- Manager/supervisor/worker-ready orchestration core.
- Strongly typed task/event/resource model with hash-chained events.
- Pluggable task handlers and agent templates via simple registry/loader.
- No runtime dependency on v1; v1 is preserved under `v1.reference/`.

## Layout

```text
src/openchronicle_core/
  core/
    domain/ (models, ports, services)
    application/ (use cases, runtime wiring)
    infrastructure/ (llm adapters, persistence, logging)
  interfaces/
    cli/ (argparse-based CLI)
    api/ (HTTP stub)
plugins/
  storytelling/ (example plugin registering a task handler)
```

## Key Components

- **Domain models**: Project, Agent, Task, Event, Resource with `TaskStatus` and event hash chaining.
- **Ports**: `LLMPort`, `StoragePort`, `PluginRegistry`/`PluginPort` abstractions.
- **OrchestratorService**: coordinates projects, agents, task submission/execution, and resource recording.
- **Persistence**: `SqliteStore` with minimal schema and JSON payload storage.
- **Logging**: `EventLogger` computes `prev_hash`/`hash` and persists via storage.
- **LLM adapters**: mock OpenAI/Anthropic/Ollama adapters implementing `LLMPort`.
- **Plugins**: discovered under `plugins/`, each exporting `register(registry)` to add task handlers and agent templates.
- **CLI**: `oc` entrypoint supporting project creation, agent registration, task submission/execution, and timeline display.

## Event Model

Events link via `prev_hash` → `hash`, enabling tamper-evident timelines per task. `EventLogger.append` fetches the latest event for a task, sets `prev_hash`, computes the hash, and persists.

## Next Steps

- Add real LLM integrations and provider selection.
- Introduce supervisor/worker scheduling queues.
- Extend plugin metadata (manifests, capabilities, tool registration).
- Build HTTP API with auth and streaming.
- Replace mock adapters with real clients and config-driven routing.
