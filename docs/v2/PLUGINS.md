# Plugin System

OpenChronicle v2 uses a file-based plugin system that allows contributors to extend functionality by adding plugins to the `plugins/` directory.

## Plugin Structure

Plugins live in the root-level `plugins/` directory. Each plugin must follow this structure:

```text
plugins/
  <plugin_name>/
    plugin.py       # Required: contains register() function
    __init__.py     # Optional
    ... other files ...
```

### Required: `plugin.py`

Each plugin must have a `plugin.py` file that exports a `register()` function with this signature:

```python
from openchronicle.core.application.runtime.task_handler_registry import TaskHandlerRegistry
from openchronicle.core.domain.ports.plugin_port import PluginRegistry

def register(
    registry: PluginRegistry,
    handler_registry: TaskHandlerRegistry,
    context: dict[str, Any] | None = None
) -> None:
    # Register task handlers
    handler_registry.register("my.task.type", my_handler_function)

    # Optionally register agent templates
    registry.register_agent_template({
        "role": "my_role",
        "description": "Description of what this agent does"
    })
```

## Plugin Discovery and Loading

The `PluginLoader` automatically discovers and loads plugins:

1. **Discovery**: Scans the `plugins/` directory for subdirectories containing `plugin.py`
2. **Loading**: Loads each plugin module by **file path** using `importlib.util` (NOT by import path)
3. **Registration**: Calls the plugin's `register()` function to register handlers and capabilities
4. **Error Handling**: Plugin load failures are logged but don't crash the system

### No sys.path Manipulation

The plugin system does **NOT** modify `sys.path`. Plugins are loaded directly by file path, ensuring:

- Clean isolation between plugins
- No import path conflicts
- Predictable module loading behavior

## Creating a New Plugin

To add a new plugin:

1. Create a directory under `plugins/`:

   ```bash
   mkdir plugins/my_plugin
   ```

2. Create `plugin.py` with a `register()` function:

   ```python
   from typing import Any
   from openchronicle.core.application.runtime.task_handler_registry import TaskHandlerRegistry
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
    Handle a task of type "my.task.type".

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

The built-in `storytelling` plugin demonstrates the plugin structure:

```text
plugins/
  storytelling/
    plugin.py           # Main plugin file
    __init__.py
    application/        # Optional: organized code
    domain/
    resources/
```

Key parts of `plugin.py`:

```python
async def _story_draft_handler(task: Task, context: dict[str, Any] | None = None) -> dict[str, str]:
    prompt = task.payload.get("prompt") or "Tell a short story."
    draft = f"[storytelling draft] {prompt}"
    return {"draft": draft}

def register(
    registry: PluginRegistry,
    handler_registry: TaskHandlerRegistry,
    context: dict[str, Any] | None = None
) -> None:
    handler_registry.register("story.draft", _story_draft_handler)
    registry.register_agent_template({
        "role": "storyteller",
        "description": "Generates narrative drafts."
    })
```

## Using Plugin Task Handlers

Once registered, plugin task handlers can be invoked via the CLI or API:

```bash
# Via CLI
oc run-task <project_id> story.draft '{"prompt": "Write a sci-fi story"}'

# List all registered handlers (including plugin handlers)
oc list-handlers
```

## Testing Plugins

Test your plugin by:

1. Creating a test that loads the plugin:

   ```python
   from openchronicle.core.application.runtime.plugin_loader import PluginLoader
   from openchronicle.core.application.runtime.task_handler_registry import TaskHandlerRegistry

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

       # Submit task that routes to your plugin
       task = orchestrator.submit_task(project_id, "my.task.type", {...})
       result = await orchestrator.execute_task(task.id)

       assert result["output"] == "expected"
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
