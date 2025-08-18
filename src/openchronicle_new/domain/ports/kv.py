"""Key-value store port."""

from __future__ import annotations

from typing import Any, Protocol


class KeyValueStore(Protocol):
    """Abstract key-value operations."""

    async def get(self, key: str) -> Any | None:
        """Retrieve a value by key."""

    async def set(self, key: str, value: Any) -> None:
        """Store a value by key."""

    async def delete(self, key: str) -> None:
        """Remove a key."""
