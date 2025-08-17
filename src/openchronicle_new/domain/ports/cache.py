"""Cache port."""

from __future__ import annotations

from typing import Any, Protocol


class Cache(Protocol):
    """Abstract cache operations."""

    async def get(self, key: str) -> Any | None:
        """Retrieve a cached value."""

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store a value with optional time-to-live."""
