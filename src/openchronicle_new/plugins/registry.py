"""Thread-safe in-memory plugin registry."""

from __future__ import annotations

from threading import Lock
from typing import Any


class Registry:
    """Store facades for registered plugins."""

    def __init__(self) -> None:
        self._facades: dict[str, Any] = {}
        self._lock = Lock()

    def register(self, plugin_id: str, facade: Any) -> None:
        """Register a plugin facade under its identifier."""
        with self._lock:
            self._facades[plugin_id] = facade

    def get(self, plugin_id: str) -> Any | None:
        """Retrieve a facade by plugin identifier."""
        with self._lock:
            return self._facades.get(plugin_id)

    def list_all(self) -> list[str]:
        """List all registered plugin identifiers."""
        with self._lock:
            return sorted(self._facades)
