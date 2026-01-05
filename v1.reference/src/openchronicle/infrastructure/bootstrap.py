from __future__ import annotations

from typing import Any
from typing import Optional


def build_container() -> dict[str, Any]:
    """Build and configure the application's DI container.

    This function constructs the application's dependency injection container
    by setting up domain services, infrastructure adapters, and other components
    that plugins will use to wire their facades.
    """
    container = {}

    # TODO: In a full implementation, this would set up:
    # - Domain services (story_service, character_service, etc.)
    # - Infrastructure adapters (database connections, etc.)
    # - Model orchestrator
    # - Logging and cache services

    # For now, provide minimal placeholder services to avoid breaking the plugin
    # The actual wiring will be implemented when the full bootstrap is created
    container["story_service"] = None  # Placeholder
    container["character_service"] = None  # Placeholder
    container["scene_service"] = None  # Placeholder
    container["memory_service"] = None  # Placeholder
    container["model_orchestrator"] = None  # Placeholder
    container["logging_service"] = None  # Placeholder
    container["cache_service"] = None  # Placeholder

    # Core facade placeholder (would be set by core plugin if it existed)
    container["core_facade"] = None

    return container


def build_facade():
    container = build_container()
    # Core doesn't register plugins; return core facade or container
    return container.get("core_facade") or container


def get_facade(name: str = "core") -> Optional[Any]:
    """Get a facade by name from the core container (plugin-agnostic)."""
    container = build_container()
    if name == "core":
        return container.get("core_facade")
    return None
