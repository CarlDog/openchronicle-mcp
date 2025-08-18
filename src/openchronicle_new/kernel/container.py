"""Simple dependency injection container."""

from __future__ import annotations

from typing import Any, Dict


class Container:
    """Stores service instances by key."""

    def __init__(self) -> None:
        self._services: Dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._services[key] = value

    def get(self, key: str) -> Any:
        return self._services[key]
