from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from openchronicle.core.application.runtime.task_registry import HandlerCollisionError, TaskHandlerRegistry
from openchronicle.core.domain.errors import PLUGIN_COLLISION, PLUGIN_ID_COLLISION
from openchronicle.core.domain.ports.plugin_port import PluginRegistry, TaskHandler
from openchronicle.core.infrastructure.config.config_loader import load_plugin_config


class PluginCollisionError(Exception):
    """Raised when duplicate plugin IDs or handler names are detected."""

    def __init__(
        self,
        collision_type: str,
        key: str,
        sources: list[str] | None = None,
        existing_source: str | None = None,
        new_source: str | None = None,
        error_code: str = PLUGIN_COLLISION,
    ) -> None:
        self.collision_type = collision_type
        self.key = key
        self.existing_source = existing_source
        self.new_source = new_source
        self.error_code = error_code
        if sources is None:
            sources = []
            if existing_source is not None:
                sources.append(existing_source)
            if new_source is not None:
                sources.append(new_source)
        self.sources = sources
        sources_str = "\n  - ".join(sources) if sources else "(unknown sources)"
        super().__init__(
            "Plugin collision detected: "
            f"collision_type='{collision_type}', key='{key}', "
            f"existing_source='{existing_source}', new_source='{new_source}', error_code='{error_code}'. "
            f"Sources:\n  - {sources_str}"
        )


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
    def __init__(
        self,
        plugins_dir: str = "plugins",
        handler_registry: TaskHandlerRegistry | None = None,
        config_dir: str | None = None,
    ) -> None:
        self.plugins_dir = Path(plugins_dir)
        self.config_dir = config_dir
        self.registry = InMemoryPluginRegistry()
        self.allow_collisions = os.getenv("OC_PLUGIN_ALLOW_COLLISIONS", "0") == "1"
        # Create handler registry with collision checking enabled (unless collisions are allowed)
        self.handler_registry = handler_registry or TaskHandlerRegistry(check_collisions=not self.allow_collisions)
        self._plugin_sources: dict[str, str] = {}  # plugin_name -> source_path

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

            # Check for plugin ID collision
            if plugin_name in self._plugin_sources and not self.allow_collisions:
                existing_source = self._plugin_sources[plugin_name]
                new_source = str(plugin_dir)
                raise PluginCollisionError(
                    collision_type="plugin_id",
                    key=plugin_name,
                    existing_source=existing_source,
                    new_source=new_source,
                    sources=[existing_source, new_source],
                    error_code=PLUGIN_ID_COLLISION,
                )
            # With collisions allowed, later plugins override earlier ones (deterministic)

            self._plugin_sources[plugin_name] = str(plugin_dir)

            # Inject per-plugin JSON config into context
            plugin_context = dict(context) if context else {}
            if self.config_dir:
                plugin_cfg = load_plugin_config(self.config_dir, plugin_name)
                if plugin_cfg:
                    plugin_context["config"] = plugin_cfg

            self._load_plugin(plugin_name, plugin_dir, init_file, plugin_file, plugin_context or None)

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

        # Set current source for collision tracking
        self.handler_registry.set_current_source(plugin_name)

        try:
            plugin_module.register(self.registry, self.handler_registry, context)
        except HandlerCollisionError as exc:
            raise PluginCollisionError(
                collision_type="handler_name",
                key=exc.handler_name,
                existing_source=exc.existing_source,
                new_source=exc.new_source,
                sources=[f"plugin '{exc.existing_source}'", f"plugin '{exc.new_source}'"],
                error_code=exc.error_code,
            ) from None
        finally:
            # Clear current source after registration
            self.handler_registry.set_current_source(None)

    def registry_instance(self) -> PluginRegistry:
        return self.registry

    def handler_registry_instance(self) -> TaskHandlerRegistry:
        return self.handler_registry
