"""In-memory plugin registry."""

from __future__ import annotations

from typing import Any


class Registry:
    """Store facades for registered plugins."""

    def __init__(self) -> None:
        self._facades: dict[str, Any] = {}

    def register(self, plugin_id: str, facade: Any) -> None:
        """Register a plugin facade under its identifier."""
        self._facades[plugin_id] = facade

    def get(self, plugin_id: str) -> Any | None:
        """Retrieve a facade by plugin identifier."""
        return self._facades.get(plugin_id)

    def list_all(self) -> list[str]:
        """List all registered plugin identifiers."""
        return sorted(self._facades)
