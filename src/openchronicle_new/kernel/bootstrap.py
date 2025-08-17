"""Core bootstrap functions."""

from __future__ import annotations

from ..infrastructure.adapters.config_env import ConfigEnv
from ..infrastructure.adapters.kv_inmemory import InMemoryKV
from ..infrastructure.adapters.scheduler_asyncio import AsyncIOScheduler
from .container import Container


class PluginRegistry:
    """Minimal plugin registry placeholder."""

    def list_all(self) -> list[str]:
        return []


_container: Container | None = None
_plugin_registry: PluginRegistry | None = None


def create_core() -> None:
    """Initialize the core container and services."""
    global _container, _plugin_registry
    if _container is not None:
        return
    _container = Container()
    _container.set("config", ConfigEnv())
    _container.set("kv", InMemoryKV())
    _container.set("scheduler", AsyncIOScheduler())
    _plugin_registry = PluginRegistry()


def get_container() -> Container:
    """Retrieve the initialized container."""
    if _container is None:
        create_core()
    return _container


def get_plugin_registry() -> PluginRegistry:
    """Retrieve the plugin registry."""
    if _plugin_registry is None:
        create_core()
    return _plugin_registry
