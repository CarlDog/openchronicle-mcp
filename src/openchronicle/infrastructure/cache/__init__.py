"""
Infrastructure layer caching implementations for OpenChronicle.

This module provides various caching strategies for improving performance
of frequently accessed data like model responses, character states, and
narrative context.
"""

import json
import asyncio
import hashlib
import time
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from abc import ABC, abstractmethod
import aiofiles


class CacheEntry:
    """Represents a cached entry with metadata."""

    def __init__(self, key: str, value: Any, ttl: Optional[int] = None):
        self.key = key
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl  # Time to live in seconds
        self.access_count = 0
        self.last_accessed = self.created_at

    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    def access(self) -> Any:
        """Access the cached value and update metadata."""
        self.access_count += 1
        self.last_accessed = time.time()
        return self.value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at,
            "ttl": self.ttl,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """Create from dictionary."""
        entry = cls(data["key"], data["value"], data.get("ttl"))
        entry.created_at = data.get("created_at", time.time())
        entry.access_count = data.get("access_count", 0)
        entry.last_accessed = data.get("last_accessed", entry.created_at)
        return entry


class BaseCache(ABC):
    """Abstract base class for cache implementations."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value by key."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set key-value pair with optional TTL."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete key."""
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """Clear all cached entries."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass


class InMemoryCache(BaseCache):
    """Simple in-memory cache with LRU eviction."""

    def __init__(self, max_size: int = 1000, default_ttl: Optional[int] = None):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: List[str] = []  # For LRU tracking
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Get value by key."""
        async with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]

            # Check expiration
            if entry.is_expired():
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                return None

            # Update LRU order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

            return entry.access()

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set key-value pair with optional TTL."""
        async with self._lock:
            # Use default TTL if not specified
            if ttl is None:
                ttl = self.default_ttl

            # Create cache entry
            entry = CacheEntry(key, value, ttl)

            # Remove existing entry if present
            if key in self._cache:
                if key in self._access_order:
                    self._access_order.remove(key)

            # Evict if at capacity
            while len(self._cache) >= self.max_size and self._access_order:
                oldest_key = self._access_order.pop(0)
                del self._cache[oldest_key]

            # Add new entry
            self._cache[key] = entry
            self._access_order.append(key)

            return True

    async def delete(self, key: str) -> bool:
        """Delete key."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                return True
            return False

    async def clear(self) -> bool:
        """Clear all cached entries."""
        async with self._lock:
            self._cache.clear()
            self._access_order.clear()
            return True

    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        async with self._lock:
            if key not in self._cache:
                return False

            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                return False

            return True

    async def cleanup_expired(self):
        """Remove expired entries."""
        async with self._lock:
            expired_keys = []
            for key, entry in self._cache.items():
                if entry.is_expired():
                    expired_keys.append(key)

            for key in expired_keys:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hit_rate": self._calculate_hit_rate(),
            "oldest_entry": min(
                (entry.created_at for entry in self._cache.values()), default=None
            ),
            "most_accessed": max(
                self._cache.items(),
                key=lambda x: x[1].access_count,
                default=(None, None),
            )[0],
        }

    def _calculate_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if not self._cache:
            return 0.0

        total_accesses = sum(entry.access_count for entry in self._cache.values())
        return total_accesses / len(self._cache) if self._cache else 0.0


class FileSystemCache(BaseCache):
    """File-based cache with persistence."""

    def __init__(self, cache_dir: str = "storage/cache", max_files: int = 10000):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_files = max_files
        self._lock = asyncio.Lock()

    def _get_cache_path(self, key: str) -> Path:
        """Get file path for cache key."""
        # Hash the key to create a safe filename
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"

    async def get(self, key: str) -> Optional[Any]:
        """Get value by key."""
        cache_file = self._get_cache_path(key)

        if not cache_file.exists():
            return None

        try:
            async with aiofiles.open(cache_file, "r", encoding="utf-8") as f:
                content = await f.read()
                entry_data = json.loads(content)

            entry = CacheEntry.from_dict(entry_data)

            # Check expiration
            if entry.is_expired():
                await self.delete(key)
                return None

            # Update access metadata and save
            value = entry.access()

            # Save updated metadata
            async with aiofiles.open(cache_file, "w", encoding="utf-8") as f:
                await f.write(json.dumps(entry.to_dict(), indent=2))

            return value

        except Exception as e:
            print(f"Error reading cache file {cache_file}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set key-value pair with optional TTL."""
        async with self._lock:
            try:
                # Check if we need to evict old files
                await self._evict_if_needed()

                cache_file = self._get_cache_path(key)
                entry = CacheEntry(key, value, ttl)

                async with aiofiles.open(cache_file, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(entry.to_dict(), indent=2, default=str))

                return True

            except Exception as e:
                print(f"Error writing cache file for key {key}: {e}")
                return False

    async def delete(self, key: str) -> bool:
        """Delete key."""
        cache_file = self._get_cache_path(key)

        try:
            if cache_file.exists():
                cache_file.unlink()
                return True
            return False
        except Exception as e:
            print(f"Error deleting cache file {cache_file}: {e}")
            return False

    async def clear(self) -> bool:
        """Clear all cached entries."""
        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                cache_file.unlink()
            return True
        except Exception as e:
            print(f"Error clearing cache: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        cache_file = self._get_cache_path(key)

        if not cache_file.exists():
            return False

        # Check if expired
        try:
            async with aiofiles.open(cache_file, "r", encoding="utf-8") as f:
                content = await f.read()
                entry_data = json.loads(content)

            entry = CacheEntry.from_dict(entry_data)

            if entry.is_expired():
                await self.delete(key)
                return False

            return True

        except Exception:
            return False

    async def _evict_if_needed(self):
        """Evict old files if cache is at capacity."""
        cache_files = list(self.cache_dir.glob("*.cache"))

        if len(cache_files) >= self.max_files:
            # Sort by modification time and remove oldest
            cache_files.sort(key=lambda f: f.stat().st_mtime)
            files_to_remove = cache_files[: len(cache_files) - self.max_files + 1]

            for file_to_remove in files_to_remove:
                try:
                    file_to_remove.unlink()
                except Exception as e:
                    print(f"Error removing cache file {file_to_remove}: {e}")


class ModelResponseCache(BaseCache):
    """Specialized cache for model responses with content-aware keys."""

    def __init__(self, base_cache: BaseCache):
        self.base_cache = base_cache

    def _create_cache_key(self, prompt: str, model_name: str, **kwargs) -> str:
        """Create a deterministic cache key for model responses."""
        # Include relevant parameters in the key
        key_data = {
            "prompt": prompt,
            "model": model_name,
            "params": sorted(kwargs.items()),
        }

        key_string = json.dumps(key_data, sort_keys=True)
        return f"model_response:{hashlib.sha256(key_string.encode()).hexdigest()}"

    async def get_response(
        self, prompt: str, model_name: str, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Get cached model response."""
        cache_key = self._create_cache_key(prompt, model_name, **kwargs)
        return await self.base_cache.get(cache_key)

    async def set_response(
        self,
        prompt: str,
        model_name: str,
        response_data: Dict[str, Any],
        ttl: Optional[int] = 3600,  # 1 hour default
        **kwargs,
    ) -> bool:
        """Cache model response."""
        cache_key = self._create_cache_key(prompt, model_name, **kwargs)
        return await self.base_cache.set(cache_key, response_data, ttl)

    # Delegate other methods to base cache
    async def get(self, key: str) -> Optional[Any]:
        return await self.base_cache.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        return await self.base_cache.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        return await self.base_cache.delete(key)

    async def clear(self) -> bool:
        return await self.base_cache.clear()

    async def exists(self, key: str) -> bool:
        return await self.base_cache.exists(key)


# Factory function for creating caches
def create_cache(cache_type: str = "memory", **kwargs) -> BaseCache:
    """Factory function to create cache instances."""
    if cache_type == "memory":
        return InMemoryCache(**kwargs)
    elif cache_type == "filesystem":
        return FileSystemCache(**kwargs)
    else:
        raise ValueError(f"Unknown cache type: {cache_type}")


# Export cache implementations
__all__ = [
    "CacheEntry",
    "BaseCache",
    "InMemoryCache",
    "FileSystemCache",
    "ModelResponseCache",
    "create_cache",
]
