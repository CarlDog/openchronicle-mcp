"""
Redis Caching Infrastructure
Week 16: Performance Optimization Advanced

Provides multi-tier caching (Memory → Redis → Database) for OpenChronicle.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable


if TYPE_CHECKING:
    import redis.asyncio as redis

try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from ...core.memory_interfaces import CharacterMemory
from ...core.memory_interfaces import MemorySnapshot


class CacheConfig:
    """Configuration for Redis caching system."""

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_password: str | None = None,
        default_ttl: int = 3600,  # 1 hour
        character_ttl: int = 7200,  # 2 hours
        memory_ttl: int = 1800,  # 30 minutes
        scene_ttl: int = 3600,  # 1 hour
        enable_local_cache: bool = True,
        local_cache_size: int = 1000,
    ):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.redis_password = redis_password
        self.default_ttl = default_ttl
        self.character_ttl = character_ttl
        self.memory_ttl = memory_ttl
        self.scene_ttl = scene_ttl
        self.enable_local_cache = enable_local_cache
        self.local_cache_size = local_cache_size


class CacheMetrics:
    """Track cache performance metrics."""

    def __init__(self):
        self.reset_metrics()

    def reset_metrics(self):
        """Reset all metrics."""
        self.hits = 0
        self.misses = 0
        self.redis_hits = 0
        self.redis_misses = 0
        self.local_hits = 0
        self.local_misses = 0
        self.cache_operations = 0
        self.redis_response_times = []
        self.start_time = time.time()

    def record_hit(self, cache_type: str):
        """Record a cache hit."""
        self.hits += 1
        if cache_type == "local":
            self.local_hits += 1
        elif cache_type == "redis":
            self.redis_hits += 1

    def record_miss(self, cache_type: str):
        """Record a cache miss."""
        self.misses += 1
        if cache_type == "local":
            self.local_misses += 1
        elif cache_type == "redis":
            self.redis_misses += 1

    def record_redis_time(self, response_time: float):
        """Record Redis response time."""
        self.redis_response_times.append(response_time)
        # Keep only last 1000 measurements
        if len(self.redis_response_times) > 1000:
            self.redis_response_times = self.redis_response_times[-1000:]

    @property
    def hit_rate(self) -> float:
        """Calculate overall hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def redis_hit_rate(self) -> float:
        """Calculate Redis hit rate."""
        total = self.redis_hits + self.redis_misses
        return self.redis_hits / total if total > 0 else 0.0

    @property
    def local_hit_rate(self) -> float:
        """Calculate local cache hit rate."""
        total = self.local_hits + self.local_misses
        return self.local_hits / total if total > 0 else 0.0

    @property
    def avg_redis_time(self) -> float:
        """Calculate average Redis response time."""
        return sum(self.redis_response_times) / len(self.redis_response_times) if self.redis_response_times else 0.0

    def get_summary(self) -> dict[str, Any]:
        """Get comprehensive metrics summary."""
        uptime = time.time() - self.start_time
        return {
            "uptime_seconds": uptime,
            "overall_hit_rate": self.hit_rate,
            "redis_hit_rate": self.redis_hit_rate,
            "local_hit_rate": self.local_hit_rate,
            "total_operations": self.hits + self.misses,
            "avg_redis_response_ms": self.avg_redis_time * 1000,
            "operations_per_second": ((self.hits + self.misses) / uptime if uptime > 0 else 0),
        }


class MultiTierCache:
    """
    Multi-tier caching system: Memory → Redis → Database

    Provides high-performance caching with fallback layers and automatic
    cache warming/invalidation strategies.
    """

    def __init__(self, config: CacheConfig | None = None):
        self.config = config or CacheConfig()
        self.logger = logging.getLogger("openchronicle.cache")
        self.metrics = CacheMetrics()

        # Local memory cache
        if self.config.enable_local_cache:
            from cachetools import TTLCache

            self.local_cache = TTLCache(
                maxsize=self.config.local_cache_size,
                ttl=300,  # 5 minutes local TTL
            )
        else:
            self.local_cache = None

        # Redis client (initialized lazily)
        self._redis_client = None
        self._redis_available = REDIS_AVAILABLE

    async def _get_redis_client(self) -> Any | None:
        """Get or create Redis client."""
        if not self._redis_available or redis is None:
            return None

        if self._redis_client is None:
            try:
                self._redis_client = redis.Redis(
                    host=self.config.redis_host,
                    port=self.config.redis_port,
                    db=self.config.redis_db,
                    password=self.config.redis_password,
                    decode_responses=True,
                )
                # Test connection
                await self._redis_client.ping()
                self.logger.info("Redis connection established")
            except (ConnectionError, TimeoutError) as e:
                self.logger.warning(f"Redis network error: {e}")
                self._redis_available = False
                return None
            except (ImportError, ModuleNotFoundError) as e:
                self.logger.warning(f"Redis module not available: {e}")
                self._redis_available = False
                return None
            except Exception as e:
                self.logger.warning(f"Redis unavailable: {e}")
                self._redis_available = False
                return None

        return self._redis_client

    def _make_key(self, prefix: str, story_id: str, identifier: str) -> str:
        """Create standardized cache key."""
        return f"oc:{prefix}:{story_id}:{identifier}"

    async def get(
        self,
        key: str,
        fallback_func: Callable[..., Any] | None = None,
        ttl: int | None = None,
    ) -> Any | None:
        """
        Get value from cache with multi-tier fallback.

        Args:
            key: Cache key
            fallback_func: Function to call if not in cache
            ttl: TTL for storing result if fetched from fallback

        Returns:
            Cached or fallback value
        """
        start_time = time.time()

        # Tier 1: Local memory cache
        if self.local_cache is not None and key in self.local_cache:
            self.metrics.record_hit("local")
            self.logger.debug(f"Local cache hit: {key}")
            return self.local_cache[key]

        if self.local_cache is not None:
            self.metrics.record_miss("local")

        # Tier 2: Redis cache
        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                redis_start = time.time()
                redis_value = await redis_client.get(key)
                redis_time = time.time() - redis_start
                self.metrics.record_redis_time(redis_time)

                if redis_value is not None:
                    self.metrics.record_hit("redis")
                    self.logger.debug(f"Redis cache hit: {key}")

                    # Deserialize and store in local cache
                    try:
                        value = json.loads(redis_value)
                        if self.local_cache is not None:
                            self.local_cache[key] = value
                    except json.JSONDecodeError:
                        self.logger.exception("Failed to deserialize Redis value for key")
                    else:
                        return value
                else:
                    self.metrics.record_miss("redis")
            except (ConnectionError, TimeoutError) as e:
                self.logger.exception("Redis network error for key")
            except (AttributeError, KeyError) as e:
                self.logger.exception("Redis data structure error for key")
            except Exception as e:
                self.logger.exception("Redis error for key")

        # Tier 3: Fallback function (usually database)
        if fallback_func:
            self.logger.debug(f"Cache miss, calling fallback for: {key}")
            value = await fallback_func() if asyncio.iscoroutinefunction(fallback_func) else fallback_func()

            if value is not None:
                # Store in both caches
                await self.set(key, value, ttl or self.config.default_ttl)

            return value

        return None

    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """
        Set value in all cache tiers.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds

        Returns:
            True if successfully cached
        """
        ttl = ttl or self.config.default_ttl
        success = True

        # Store in local cache
        if self.local_cache is not None:
            try:
                self.local_cache[key] = value
            except Exception as e:
                self.logger.exception("Local cache error for key")
                success = False

        # Store in Redis
        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                serialized = json.dumps(value, default=str)
                await redis_client.setex(key, ttl, serialized)
                self.logger.debug(f"Cached in Redis: {key} (TTL: {ttl}s)")
            except (ConnectionError, TimeoutError) as e:
                self.logger.exception("Redis network error caching key")
                success = False
            except (TypeError, ValueError) as e:
                self.logger.exception("JSON serialization error for key")
                success = False
            except Exception as e:
                self.logger.exception("Redis cache error for key")
                success = False

        return success

    async def delete(self, key: str) -> bool:
        """Delete from all cache tiers."""
        success = True

        # Delete from local cache
        if self.local_cache is not None:
            self.local_cache.pop(key, None)

        # Delete from Redis
        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                await redis_client.delete(key)
                self.logger.debug(f"Deleted from Redis: {key}")
            except Exception as e:
                self.logger.exception("Redis delete error for key")
                success = False

        return success

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern."""
        deleted = 0

        # Clear local cache (simple approach - clear all)
        if self.local_cache is not None:
            self.local_cache.clear()

        # Clear Redis pattern
        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                keys = await redis_client.keys(pattern)
                if keys:
                    deleted = await redis_client.delete(*keys)
                    self.logger.info(f"Invalidated {deleted} keys matching pattern: {pattern}")
            except Exception as e:
                self.logger.exception("Redis pattern invalidation error")

        return deleted

    async def close(self):
        """Close Redis connection."""
        if self._redis_client:
            await self._redis_client.close()

    def get_metrics(self) -> dict[str, Any]:
        """Get cache performance metrics."""
        return self.metrics.get_summary()


class CachedCharacterManager:
    """Character manager with Redis caching."""

    def __init__(self, cache: MultiTierCache, original_manager):
        self.cache = cache
        self.original_manager = original_manager
        self.logger = logging.getLogger("openchronicle.cache.character")

    async def get_character_memory(self, story_id: str, character_name: str) -> CharacterMemory | None:
        """Get character memory with caching."""
        cache_key = self.cache._make_key("char", story_id, character_name)

        async def fallback():
            return self.original_manager.get_character_memory(story_id, character_name)

        result = await self.cache.get(cache_key, fallback, ttl=self.cache.config.character_ttl)

        return result

    async def update_character(self, story_id: str, character_name: str, updates: dict[str, Any]) -> bool:
        """Update character and invalidate cache."""
        # Update in original manager
        success = self.original_manager.update_character(story_id, character_name, updates)

        if success:
            # Invalidate cache
            cache_key = self.cache._make_key("char", story_id, character_name)
            await self.cache.delete(cache_key)
            self.logger.debug(f"Invalidated character cache: {character_name}")

        return success

    async def invalidate_story_characters(self, story_id: str):
        """Invalidate all character caches for a story."""
        pattern = self.cache._make_key("char", story_id, "*")
        deleted = await self.cache.invalidate_pattern(pattern)
        self.logger.info(f"Invalidated {deleted} character caches for story: {story_id}")


class CachedMemoryOrchestrator:
    """Memory orchestrator with Redis caching."""

    def __init__(self, original_orchestrator, cache_config: CacheConfig | None = None):
        self.original = original_orchestrator
        self.cache = MultiTierCache(cache_config)
        self.cached_character_manager = CachedCharacterManager(self.cache, original_orchestrator.character_manager)
        self.logger = logging.getLogger("openchronicle.cache.memory")

    async def get_memory_snapshot(self, story_id: str) -> MemorySnapshot | None:
        """Get memory snapshot with caching."""
        cache_key = self.cache._make_key("snapshot", story_id, "current")

        async def fallback():
            return self.original.load_current_memory(story_id)

        return await self.cache.get(cache_key, fallback, ttl=self.cache.config.memory_ttl)

    async def save_memory(self, story_id: str, memory_data: dict[str, Any]) -> bool:
        """Save memory and invalidate related caches."""
        success = self.original.save_current_memory(story_id, memory_data)

        if success:
            # Invalidate memory snapshot cache
            cache_key = self.cache._make_key("snapshot", story_id, "current")
            await self.cache.delete(cache_key)
            self.logger.debug(f"Invalidated memory snapshot cache for story: {story_id}")

        return success

    async def get_cache_metrics(self) -> dict[str, Any]:
        """Get comprehensive cache performance metrics."""
        return self.cache.get_metrics()

    async def close(self):
        """Close cache connections."""
        await self.cache.close()


# Convenience function for easy integration
def create_cached_memory_orchestrator(
    original_orchestrator, redis_host: str = "localhost", redis_port: int = 6379
) -> CachedMemoryOrchestrator:
    """Create a cached memory orchestrator with default config."""
    config = CacheConfig(redis_host=redis_host, redis_port=redis_port)
    return CachedMemoryOrchestrator(original_orchestrator, config)
