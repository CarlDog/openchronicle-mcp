# Plugin System

> **Related Plugin Documentation:**
> [Plugin Contract](../plugins/plugin_contract.md) |
> [Plugin Quickstart](../plugins/plugin_quickstart.md)

OpenChronicle uses a file-based plugin system for **extensions that modify
OC's conversational behavior** — primarily mode prompt builders, system
prompt augmenters, and conversation-lifecycle handlers. Domain integrations
that import external data (Plex, Plaid, etc.) belong as their own MCP
servers, not as OC plugins. Plugins live in this repo's `plugins/` directory
(or wherever `OC_PLUGIN_DIR` points). The current extension is
`storytelling`.

## Plugin Structure

Each plugin must follow this structure:

```text
<plugin_dir>/
  <plugin_name>/
    __init__.py     # Required: makes the plugin a Python package
    plugin.py       # Required: contains register() function
    ... other files ...
```

### Required: `plugin.py`

Each plugin must have a `plugin.py` file that exports a `register()` function with this signature:

```python
from openchronicle.core.application.runtime.task_registry import TaskHandlerRegistry
from openchronicle.core.domain.ports.plugin_port import PluginRegistry

def register(
    registry: PluginRegistry,
    handler_registry: TaskHandlerRegistry,
    context: dict[str, Any] | None = None
) -> None:
    # Register task handlers by handler name (namespace.action)
    handler_registry.register("my.task.type", my_handler_function)

    # Optionally register agent templates
    registry.register_agent_template({
        "role": "my_role",
        "description": "Description of what this agent does"
    })
```

## Plugin Discovery and Loading

The `PluginLoader` automatically discovers and loads plugins:

1. **Discovery**: Scans the plugin directory (`OC_PLUGIN_DIR`, default `plugins/`) for subdirectories containing `plugin.py`
2. **Loading**: Loads each plugin module by **file path** using `importlib.util` (NOT by import path)
3. **Registration**: Calls the plugin's `register()` function to register handlers and capabilities
4. **Error Handling**: Plugin load failures are logged but don't crash the system

### Package-Based Loading

Plugins are loaded as Python packages under the `oc_plugins` namespace:

- Plugins are registered as `oc_plugins.<plugin_name>` in `sys.modules`
- This enables relative imports within plugin directories
- Each plugin must have `__init__.py` to support package semantics

### Handler Collision Detection

By default, the plugin system prevents handler name collisions:

- If two plugins register the same handler name, a `PluginCollisionError` is raised
- Set `OC_PLUGIN_ALLOW_COLLISIONS=1` to allow later plugins to override earlier ones
- Collision checking applies to both plugin IDs and handler names

## Creating a New Plugin

To add a new plugin:

1. Create a directory in the plugin directory:

   ```bash
   mkdir plugins/my_plugin
   ```

2. Create `plugin.py` with a `register()` function:

   ```python
   from typing import Any
   from openchronicle.core.application.runtime.task_registry import TaskHandlerRegistry
   from openchronicle.core.domain.models.project import Task
   from openchronicle.core.domain.ports.plugin_port import PluginRegistry

   async def my_handler(task: Task, context: dict[str, Any] | None = None) -> dict[str, Any]:
       # Your handler logic here
       return {"result": "success"}

   def register(
       registry: PluginRegistry,
       handler_registry: TaskHandlerRegistry,
       context: dict[str, Any] | None = None
   ) -> None:
       handler_registry.register("my.task.type", my_handler)
   ```

3. Your plugin will be automatically discovered and loaded when the application starts

## Task Handlers

Task handlers are async functions that process tasks:

```python
async def my_handler(task: Task, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Handle a task via handler name "my.task.type".

    Args:
        task: The task to process (includes payload, project_id, etc.)
        context: Optional runtime context (emit_event, agent_id, etc.)

    Returns:
        Dictionary with task results
    """
    # Access task data
    prompt = task.payload.get("prompt")

    # Emit events if needed
    emit_event = context.get("emit_event") if context else None
    if emit_event:
        from openchronicle.core.domain.models.project import Event
        emit_event(Event(
            project_id=task.project_id,
            task_id=task.id,
            agent_id=context.get("agent_id"),
            type="my.event.type",
            payload={"status": "processing"}
        ))

    # Return results
    return {"output": "processed"}
```

## Example: Storytelling Plugin

The `storytelling` plugin demonstrates full plugin capabilities including task
handlers, agent templates, mode prompt builders, and CLI commands:

```text
plugins/
  storytelling/
    __init__.py
    plugin.py              # Registration: handlers + agent template + mode builder
    cli.py                 # CLI commands (oc story import|list|show|scene|characters|locations|search)
    importer.py            # Project import pipeline (text file parsing + classification)
    helpers.py             # Shared utilities
    application/
      context_assembler.py # Tag-filtered memory retrieval for scene/conversation context
      scene_handler.py     # Scene generation orchestration
      conversation_mode.py # Story mode prompt builder for conversation integration
    domain/
      modes.py             # Engagement modes (participant/director/audience), system prompt builder
      models.py            # Domain models (ImportResult, SceneResult, StoryContext)
    resources/             # Static prompt templates
```

Key parts of `plugin.py`:

```python
from .application.conversation_mode import story_prompt_builder

def register(registry, handler_registry, context=None):
    handler_registry.register("story.draft", _story_draft_handler)
    handler_registry.register("story.import", _story_import_handler)
    handler_registry.register("story.scene", _story_scene_handler)
    registry.register_agent_template({
        "role": "storyteller",
        "description": "Imports and manages narrative content, generates scenes."
    })
    registry.register_mode_prompt_builder("story", story_prompt_builder)
```

## Using Plugin Task Handlers

Once registered, plugin handlers are executed via task_type = plugin.invoke with a payload specifying the handler.
Dotted task_type strings (for example, story.draft) are invalid and return INVALID_TASK_TYPE.

```bash
# Create a project
PROJECT_ID=$(oc init-project "plugin-demo")

# Submit plugin invocation
TASK_ID=$(oc rpc --request '{"protocol_version":"1","command":"task.submit","args":{"project_id":"'"$PROJECT_ID"'","task_type":"plugin.invoke","payload":{"handler":"story.draft","input":{"prompt":"Write a sci-fi story"}}}}' | jq -r '.result.task_id')

# Execute queued tasks
oc rpc --request '{"protocol_version":"1","command":"task.run_many","args":{"limit":5,"type":"plugin.invoke","max_seconds":0}}'

# Show result
oc show-task --result "$TASK_ID"

# List all registered handlers (including plugin handlers)
oc list-handlers
```

## Testing Plugins

Test your plugin by:

1. Creating a test that loads the plugin:

   ```python
   from openchronicle.core.application.runtime.plugin_loader import PluginLoader
   from openchronicle.core.application.runtime.task_registry import TaskHandlerRegistry

   def test_my_plugin():
       registry = TaskHandlerRegistry()
       loader = PluginLoader(plugins_dir="plugins", handler_registry=registry)
       loader.load_plugins()

    handler = registry.get("my.task.type")
       assert handler is not None
   ```

2. Running integration tests with the orchestrator:

   ```python
   import pytest
   from openchronicle.core.application.services.orchestrator import OrchestratorService

   @pytest.mark.asyncio
   async def test_plugin_integration():
       # Set up orchestrator with plugin loader
       orchestrator = OrchestratorService(...)

    # Submit task that routes to your plugin via plugin.invoke
    task = orchestrator.submit_task(project_id, "plugin.invoke", {"handler": "my.task.type", "input": {...}})
    result = await orchestrator.execute_task(task.id)

       assert result["output"] == "expected"
   ```

## Mode Prompt Builders

Plugins can register **mode prompt builders** to customize the system prompt
for conversations in a specific mode. When a conversation's `mode` matches a
registered builder, `prepare_ask()` delegates system prompt construction to the
builder instead of using the default `"You are a helpful assistant."` prompt.

### Registering a Mode Prompt Builder

```python
from openchronicle.core.domain.ports.plugin_port import PluginRegistry

def my_mode_builder(
    prompt_text: str,
    *,
    memory_search,       # Callable for tag-filtered memory search
    project_id=None,     # Conversation's project ID
) -> str:
    """Build a custom system prompt for 'my_mode' conversations."""
    # Use memory_search to retrieve mode-specific context
    items = memory_search("relevant query", top_k=50, tags=["my-tag"])
    # Assemble and return the system prompt string
    return f"You are a specialized assistant.\n\nContext:\n{items}"

def register(registry: PluginRegistry, handler_registry, context=None):
    # Register task handlers as usual...
    handler_registry.register("my.handler", my_handler)

    # Register the mode prompt builder
    registry.register_mode_prompt_builder("my_mode", my_mode_builder)
```

### How It Works

1. User sets `mode` on a conversation (e.g., `oc convo mode <id> story`)
2. On each `prepare_ask()` call, the system checks for a registered builder
   matching the conversation's `effective_mode`
3. If a builder exists and the conversation has a `project_id`:
   - The builder receives a pre-bound `memory_search` closure and the user's prompt
   - The builder returns the complete system prompt
   - Generic keyword-based memory retrieval is **skipped** (the builder does its own)
   - Pinned memories are still included
4. If no builder matches, the default system prompt and memory retrieval are used

### ModePromptBuilder Protocol

```python
class ModePromptBuilder(Protocol):
    def __call__(
        self,
        prompt_text: str,
        *,
        memory_search: Callable[..., list[Any]],
        project_id: str | None = None,
    ) -> str: ...
```

The `memory_search` closure has the signature:
`(query: str, top_k: int = 8, tags: list[str] | None = None) -> list[MemoryItem]`

### Example: Storytelling Plugin

The `storytelling` plugin registers a `"story"` mode builder that assembles
characters, style guides, locations, worldbuilding, and scene context from
project memory using tag-filtered search:

```python
from .application.context_assembler import assemble_story_context
from .domain.modes import EngagementMode, build_system_prompt

def story_prompt_builder(prompt_text, *, memory_search, project_id=None):
    ctx = assemble_story_context(memory_search, prompt_text)
    return build_system_prompt(
        EngagementMode.DIRECTOR,
        instructions=ctx.instructions,
        style_guide=ctx.style_guide,
        characters=ctx.characters,
        locations=ctx.locations,
        scenes=ctx.scenes,
        worldbuilding=ctx.worldbuilding,
        canon=True,
    )
```

## Plugin Repository Root Resolution

The plugin loader automatically finds the repository root by walking up the directory tree until it finds `pyproject.toml`. This ensures plugins are discovered correctly regardless of where the code is installed.

If `pyproject.toml` is not found, it falls back to the parent directory of the configured `plugins_dir`.

## Error Handling

Plugin errors are handled gracefully:

- **Load Errors**: If a plugin fails to load, an error is printed to stderr and the plugin is skipped
- **Missing register()**: If `plugin.py` doesn't have a `register()` function, an error is logged
- **Registration Errors**: If `register()` throws an exception, the error is logged and other plugins continue loading

The core system continues to function even if individual plugins fail.
