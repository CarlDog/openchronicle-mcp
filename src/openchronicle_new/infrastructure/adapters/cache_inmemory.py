"""In-memory cache adapter with optional TTL support."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CacheEntry:
    value: Any
    ttl: float | None = None
    created_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        return self.ttl is not None and (time.time() - self.created_at) > self.ttl


class InMemoryCache:
    """Simple async-safe in-memory cache."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._data: dict[str, CacheEntry] = {}
        self._order: list[str] = []
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            entry = self._data.get(key)
            if entry is None or entry.is_expired():
                self._data.pop(key, None)
                if key in self._order:
                    self._order.remove(key)
                return None
            if key in self._order:
                self._order.remove(key)
            self._order.append(key)
            return entry.value

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        async with self._lock:
            if key in self._data and key in self._order:
                self._order.remove(key)
            while len(self._data) >= self.max_size and self._order:
                oldest = self._order.pop(0)
                self._data.pop(oldest, None)
            self._data[key] = CacheEntry(value=value, ttl=ttl)
            self._order.append(key)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._data.pop(key, None)
            if key in self._order:
                self._order.remove(key)

    async def clear(self) -> None:
        async with self._lock:
            self._data.clear()
            self._order.clear()

    async def exists(self, key: str) -> bool:
        async with self._lock:
            entry = self._data.get(key)
            if entry is None or entry.is_expired():
                self._data.pop(key, None)
                if key in self._order:
                    self._order.remove(key)
                return False
            return True
