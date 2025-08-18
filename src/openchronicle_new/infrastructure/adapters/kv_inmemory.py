"""In-memory key-value adapter."""

from __future__ import annotations

from typing import Any


class InMemoryKV:
    """Simple in-memory key-value storage."""

    # TODO: add persistence or eviction strategy if needed

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def get(self, key: str) -> Any | None:
        return self._data.get(key)

    async def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)
