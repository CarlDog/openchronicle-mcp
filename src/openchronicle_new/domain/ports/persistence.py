"""Persistence port definitions."""

from __future__ import annotations

from typing import Any, Protocol


class Persistence(Protocol):
    """Abstract persistence operations."""

    async def save(self, obj: Any) -> None:
        """Persist an object."""

    async def load(self, identifier: Any) -> Any:
        """Retrieve an object by its identifier."""
