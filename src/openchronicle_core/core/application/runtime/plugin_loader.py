from __future__ import annotations

import importlib
import pkgutil
import sys
from pathlib import Path
from typing import Any

from openchronicle_core.core.application.runtime.task_handler_registry import TaskHandlerRegistry
from openchronicle_core.core.domain.ports.plugin_port import PluginRegistry, TaskHandler


class InMemoryPluginRegistry(PluginRegistry):
    def __init__(self) -> None:
        self._task_handlers: dict[str, TaskHandler] = {}
        self._agent_templates: list[dict[str, Any]] = []

    def register_task_handler(self, task_type: str, handler: TaskHandler) -> None:
        self._task_handlers[task_type] = handler

    def get_task_handler(self, task_type: str) -> TaskHandler | None:
        return self._task_handlers.get(task_type)

    def register_agent_template(self, agent: dict[str, Any]) -> None:
        self._agent_templates.append(agent)

    def list_agent_templates(self) -> list[dict[str, Any]]:
        return list(self._agent_templates)


class PluginLoader:
    def __init__(self, plugins_dir: str = "plugins", handler_registry: TaskHandlerRegistry | None = None) -> None:
        self.plugins_dir = Path(plugins_dir)
        self.registry = InMemoryPluginRegistry()
        self.handler_registry = handler_registry or TaskHandlerRegistry()

    def load_plugins(self, context: dict[str, Any] | None = None) -> None:
        if not self.plugins_dir.exists():
            return
        project_root = str(self.plugins_dir.resolve().parent)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        for module_info in pkgutil.iter_modules([str(self.plugins_dir)]):
            if module_info.ispkg:
                module_name = f"plugins.{module_info.name}.plugin"
                try:
                    module = importlib.import_module(module_name)
                except Exception as exc:
                    print(f"Failed to import plugin {module_name}: {exc}", file=sys.stderr)
                    continue
                if hasattr(module, "register"):
                    try:
                        module.register(self.registry, self.handler_registry, context)
                    except Exception as exc:
                        # Do not crash core if plugin fails, but surface the failure
                        print(f"Failed to register plugin {module_name}: {exc}", file=sys.stderr)
                        continue

    def registry_instance(self) -> PluginRegistry:
        return self.registry

    def handler_registry_instance(self) -> TaskHandlerRegistry:
        return self.handler_registry
