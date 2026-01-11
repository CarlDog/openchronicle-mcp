from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from openchronicle.core.application.runtime.handler_registry import TaskHandlerRegistry
from openchronicle.core.domain.ports.plugin_port import PluginRegistry, TaskHandler


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

    def _find_repo_root(self) -> Path:
        """Find repository root by walking up until pyproject.toml is found."""
        current = Path(__file__).resolve()
        for parent in [current] + list(current.parents):
            if (parent / "pyproject.toml").exists():
                return parent
        # Fallback: assume plugins_dir parent if pyproject.toml not found
        return self.plugins_dir.resolve().parent

    def load_plugins(self, context: dict[str, Any] | None = None) -> None:
        """Load plugins from filesystem as packages (no sys.path manipulation)."""
        repo_root = self._find_repo_root()
        plugins_root = repo_root / self.plugins_dir

        if not plugins_root.exists():
            return

        # Discover plugin candidates: directories under plugins/ with plugin.py
        for plugin_dir in plugins_root.iterdir():
            if not plugin_dir.is_dir():
                continue

            plugin_file = plugin_dir / "plugin.py"
            if not plugin_file.exists():
                continue

            # Check for __init__.py - required for package semantics
            init_file = plugin_dir / "__init__.py"
            if not init_file.exists():
                print(
                    f"ERROR: Plugin '{plugin_dir.name}' is missing __init__.py. "
                    f"Plugins must be packages to support relative imports. Skipping.",
                    file=sys.stderr,
                )
                continue

            plugin_name = plugin_dir.name
            self._load_plugin(plugin_name, plugin_dir, init_file, plugin_file, context)

    def _load_plugin(
        self, plugin_name: str, plugin_dir: Path, init_file: Path, plugin_file: Path, context: dict[str, Any] | None
    ) -> None:
        """Load a plugin as a package via file path, enabling relative imports."""
        # Step 1: Load the package (__init__.py) to establish the plugin namespace
        package_name = f"oc_plugins.{plugin_name}"

        try:
            # Create package spec with submodule_search_locations for relative imports
            package_spec = importlib.util.spec_from_file_location(
                package_name, init_file, submodule_search_locations=[str(plugin_dir)]
            )
            if package_spec is None or package_spec.loader is None:
                print(f"Failed to create package spec for plugin {plugin_name} at {init_file}", file=sys.stderr)
                return

            package_module = importlib.util.module_from_spec(package_spec)
            # Add to sys.modules so submodules can resolve relative imports
            sys.modules[package_name] = package_module
            package_spec.loader.exec_module(package_module)

        except Exception as exc:
            print(f"Failed to load plugin package {plugin_name} from {init_file}: {exc}", file=sys.stderr)
            # Clean up sys.modules on failure
            sys.modules.pop(package_name, None)
            return

        # Step 2: Load plugin.py as a submodule of the package
        plugin_module_name = f"{package_name}.plugin"

        try:
            plugin_spec = importlib.util.spec_from_file_location(plugin_module_name, plugin_file)
            if plugin_spec is None or plugin_spec.loader is None:
                print(f"Failed to create spec for plugin.py in {plugin_name} at {plugin_file}", file=sys.stderr)
                sys.modules.pop(package_name, None)
                return

            plugin_module = importlib.util.module_from_spec(plugin_spec)
            sys.modules[plugin_module_name] = plugin_module
            plugin_spec.loader.exec_module(plugin_module)

        except Exception as exc:
            print(f"Failed to load plugin.py for {plugin_name} from {plugin_file}: {exc}", file=sys.stderr)
            # Clean up sys.modules on failure
            sys.modules.pop(plugin_module_name, None)
            sys.modules.pop(package_name, None)
            return

        # Step 3: Call register function on the plugin module
        if not hasattr(plugin_module, "register"):
            print(
                f"Plugin {plugin_name} at {plugin_file} does not have a register() function",
                file=sys.stderr,
            )
            return

        try:
            plugin_module.register(self.registry, self.handler_registry, context)
        except Exception as exc:
            print(f"Failed to register plugin {plugin_name}: {exc}", file=sys.stderr)

    def registry_instance(self) -> PluginRegistry:
        return self.registry

    def handler_registry_instance(self) -> TaskHandlerRegistry:
        return self.handler_registry
