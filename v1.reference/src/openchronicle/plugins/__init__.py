from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Protocol


class Registers(Protocol):
    def register(self, container: Dict[str, Any]) -> None: ...


class RegistersCLI(Protocol):
    def register_cli(self, app: Any) -> None: ...


class Plugin(Protocol):
    """Protocol for OpenChronicle plugins with optional CLI registration."""

    def metadata(self) -> Dict[str, Any]: ...

    def register(self, container: Dict[str, Any]) -> None: ...

    # Optional CLI registration
    def register_cli(self, app: Any) -> None: ...


def load_plugin(mode: str):
    """Load a single plugin by mode."""
    if mode == "storytelling":
        # import deferred to avoid hard dependency if plugin is missing
        try:
            from .storytelling import plugin as storytelling_plugin  # type: ignore
        except Exception:
            return None
        else:
            return storytelling_plugin
    return None


def discover_plugins(mode: Optional[str] = None) -> List[Any]:
    """
    Discover available plugins.

    Args:
        mode: If specified, load only that plugin. If None, discover all.

    Returns:
        List of plugin modules that have register and/or register_cli methods.
    """
    plugins = []

    # For now, we only have the storytelling plugin
    # In the future, this could scan for installed plugins
    available_plugins = ["storytelling"]

    if mode:
        # Load specific plugin
        plugin = load_plugin(mode)
        if plugin:
            plugins.append(plugin)
    else:
        # Load all available plugins
        for plugin_name in available_plugins:
            plugin = load_plugin(plugin_name)
            if plugin:
                plugins.append(plugin)

    return plugins
