"""
Async Memory Repository

Async version of memory repository using the new async database operations.
Provides non-blocking memory persistence with caching and performance optimization.
"""

import asyncio
import logging
from datetime import UTC
from datetime import datetime
from functools import lru_cache
from typing import Any

from cachetools import TTLCache
from src.openchronicle.infrastructure.persistence.async_database_orchestrator import (
    AsyncDatabaseOrchestrator,
)
from src.openchronicle.shared.json_utilities import JSONUtilities


# Setup logging
logger = logging.getLogger("openchronicle.async_memory_repository")


class AsyncMemoryRepository:
    """Async memory data persistence and retrieval with caching."""

    def __init__(self, cache_size: int = 256, cache_ttl: int = 300):
        """Initialize async memory repository with caching."""
        self.json_util = JSONUtilities()
        self.db_orchestrator = AsyncDatabaseOrchestrator()

        # Performance caches
        self.memory_cache = TTLCache(maxsize=cache_size, ttl=cache_ttl)
        self.character_cache = TTLCache(maxsize=cache_size * 2, ttl=cache_ttl)
        self.world_state_cache = TTLCache(maxsize=128, ttl=cache_ttl)

        # Cache stats for monitoring
        self.cache_stats = {"hits": 0, "misses": 0, "evictions": 0}

        # Locks for concurrent operation safety
        self._story_locks = {}
        self._lock_lock = asyncio.Lock()  # Lock to manage the locks dict

    async def _get_story_lock(self, story_id: str) -> asyncio.Lock:
        """Get or create a lock for a specific story."""
        async with self._lock_lock:
            if story_id not in self._story_locks:
                self._story_locks[story_id] = asyncio.Lock()
            return self._story_locks[story_id]

    async def load_memory(self, story_id: str) -> dict[str, Any]:
        """Load complete memory state for story with caching."""
        cache_key = f"memory_{story_id}"

        # Check cache first
        if cache_key in self.memory_cache:
            self.cache_stats["hits"] += 1
            return self.memory_cache[cache_key]

        try:
            self.cache_stats["misses"] += 1

            # Initialize database first if needed
            await self.db_orchestrator.init_database(story_id, is_test=False)

            # Query all memory types from database asynchronously
            rows = await self.db_orchestrator.execute_query(
                story_id,
                """
                SELECT type, key, value FROM memory
                WHERE story_id = ? AND key = "current"
                ORDER BY updated_at DESC
            """,
                (story_id,),
                is_test=False,
            )

            if not rows:
                # No data found, return default memory structure
                default_memory = self._get_default_memory()
                self.memory_cache[cache_key] = default_memory
                return default_memory

            memory_data = {}
            for row in rows:
                memory_type = row["type"]
                value = self.json_util.safe_loads(row["value"])
                if value:
                    memory_data[memory_type] = value

            # If we still don't have data, use defaults
            if not memory_data:
                default_memory = self._get_default_memory()
                self.memory_cache[cache_key] = default_memory
                return default_memory

            memory_state = self._deserialize_memory(memory_data)

            # Cache the result
            self.memory_cache[cache_key] = memory_state

            return memory_state

        except Exception as e:
            print(f"Error loading memory: {e}")
            import traceback

            traceback.print_exc()
            # Return default memory structure if loading fails
            return self._get_default_memory()

    async def save_memory(self, story_id: str, memory: dict[str, Any]) -> bool:
        """Save memory state with automatic timestamping and cache invalidation."""
        try:
            # Initialize database first if needed
            await self.db_orchestrator.init_database(story_id, is_test=False)

            serialized_data = self._serialize_memory(memory)
            timestamp = datetime.now(UTC).isoformat()

            # Prepare async database operations
            operations = []
            for memory_type, data in serialized_data.items():
                json_data = self.json_util.safe_dumps(data)
                operations.append((memory_type, json_data))

            # Execute all saves concurrently
            tasks = []
            for memory_type, json_data in operations:
                task = self.db_orchestrator.execute_update(
                    story_id,
                    """
                    INSERT OR REPLACE INTO memory (story_id, type, key, value, updated_at)
                    VALUES (?, ?, "current", ?, ?)
                """,
                    (story_id, memory_type, json_data, timestamp),
                    is_test=False,
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks)
            success = all(results)

            if success:
                # Invalidate caches
                self._invalidate_cache(story_id)
                logger.info(f"Successfully saved memory for story {story_id}")
            else:
                logger.error(
                    f"Failed to save memory for story {story_id}: some operations failed"
                )
                logger.error(f"Memory data type: {type(memory)}")
                logger.error(f"Memory data: {str(memory)[:500]}")

            return success

        except Exception as e:
            print(f"Error saving memory: {e}")
            import traceback

            traceback.print_exc()
            return False

    @lru_cache(maxsize=512)
    def get_character_memory_cached(
        self, story_id: str, character_name: str
    ) -> dict[str, Any] | None:
        """LRU cached character memory lookup (for frequently accessed characters)."""
        # This is a synchronous cache for the most frequently accessed character data
        # The actual database fetch will be async
        return None  # Placeholder - actual data fetched async and cached here

    async def load_character_memory(
        self, story_id: str, character_name: str
    ) -> dict[str, Any] | None:
        """Load character memory with lazy loading and caching."""
        cache_key = f"char_{story_id}_{character_name}"

        # Check cache first
        if cache_key in self.character_cache:
            self.cache_stats["hits"] += 1
            return self.character_cache[cache_key]

        try:
            self.cache_stats["misses"] += 1

            # Lazy load only this character's data
            rows = await self.db_orchestrator.execute_query(
                story_id,
                """
                SELECT value FROM memory
                WHERE story_id = ? AND type = "characters" AND key = "current"
            """,
                (story_id,),
                is_test=False,
            )

            if not rows:
                return None

            characters_data = self.json_util.safe_loads(rows[0]["value"])
            if not characters_data or character_name not in characters_data:
                return None

            character_memory = characters_data[character_name]

            # Cache the result
            self.character_cache[cache_key] = character_memory

            return character_memory

        except Exception:
            return None

    async def update_character_memory(
        self, story_id: str, character_name: str, updates: dict[str, Any]
    ) -> bool:
        """Update character memory with cache invalidation and concurrency protection."""
        # Use per-story locking to prevent race conditions in concurrent updates
        story_lock = await self._get_story_lock(story_id)

        async with story_lock:
            try:
                # Load current memory state
                memory = await self.load_memory(story_id)

                # Ensure character exists
                if "characters" not in memory:
                    memory["characters"] = {}

                if character_name not in memory["characters"]:
                    memory["characters"][character_name] = {
                        "traits": {},
                        "relationships": {},
                        "history": [],
                        "current_state": {},
                        "voice_profile": {},
                        "mood": "neutral",
                    }

                # Apply updates
                character_data = memory["characters"][character_name]
                for key, value in updates.items():
                    if key in character_data:
                        if isinstance(character_data[key], dict) and isinstance(
                            value, dict
                        ):
                            character_data[key].update(value)
                        else:
                            character_data[key] = value
                    else:
                        character_data[key] = value

                # Save updated memory
                success = await self.save_memory(story_id, memory)

                if success:
                    # Invalidate character-specific cache
                    cache_key = f"char_{story_id}_{character_name}"
                    if cache_key in self.character_cache:
                        del self.character_cache[cache_key]

                return success

            except Exception as e:
                logger.error(f"Error updating character memory: {e}")
                return False

    async def load_world_state(self, story_id: str) -> dict[str, Any]:
        """Load world state with caching."""
        cache_key = f"world_{story_id}"

        # Check cache first
        if cache_key in self.world_state_cache:
            self.cache_stats["hits"] += 1
            return self.world_state_cache[cache_key]

        try:
            self.cache_stats["misses"] += 1

            rows = await self.db_orchestrator.execute_query(
                story_id,
                """
                SELECT value FROM memory
                WHERE story_id = ? AND type = "world_state" AND key = "current"
            """,
                (story_id,),
                is_test=False,
            )

            if not rows:
                return {}

            world_state = self.json_util.safe_loads(rows[0]["value"]) or {}

            # Cache the result
            self.world_state_cache[cache_key] = world_state

            return world_state

        except Exception:
            return {}

    async def save_world_state(
        self, story_id: str, world_state: dict[str, Any]
    ) -> bool:
        """Save world state with cache invalidation."""
        try:
            # Ensure database is initialized first
            await self.db_orchestrator.init_database(story_id, is_test=False)

            json_data = self.json_util.safe_dumps(world_state)
            timestamp = datetime.now(UTC).isoformat()

            success = await self.db_orchestrator.execute_update(
                story_id,
                """
                INSERT OR REPLACE INTO memory (story_id, type, key, value, updated_at)
                VALUES (?, "world_state", "current", ?, ?)
            """,
                (story_id, json_data, timestamp),
                is_test=False,
            )

            if success:
                # Invalidate world state cache
                cache_key = f"world_{story_id}"
                if cache_key in self.world_state_cache:
                    del self.world_state_cache[cache_key]

            return success

        except Exception as e:
            logger.error(f"Error saving world state: {e}")
            return False

    async def create_memory_snapshot(self, story_id: str, scene_id: str) -> bool:
        """Create memory snapshot for rollback capability."""
        try:
            # Load current memory
            memory = await self.load_memory(story_id)

            # Serialize snapshot
            snapshot_data = self._serialize_memory(memory)
            json_data = self.json_util.safe_dumps(snapshot_data)
            timestamp = datetime.now(UTC).isoformat()

            success = await self.db_orchestrator.execute_update(
                story_id,
                """
                INSERT INTO memory_snapshots (story_id, scene_id, snapshot_data, created_at)
                VALUES (?, ?, ?, ?)
            """,
                (story_id, scene_id, json_data, timestamp),
                is_test=False,
            )

            return success

        except Exception:
            return False

    async def restore_memory_snapshot(self, story_id: str, scene_id: str) -> bool:
        """Restore memory from snapshot with cache invalidation."""
        try:
            # Get snapshot data
            rows = await self.db_orchestrator.execute_query(
                story_id,
                """
                SELECT snapshot_data FROM memory_snapshots
                WHERE story_id = ? AND scene_id = ?
                ORDER BY created_at DESC LIMIT 1
            """,
                (story_id, scene_id),
                is_test=False,
            )

            if not rows:
                return False

            snapshot_data = self.json_util.safe_loads(rows[0]["snapshot_data"])
            if not snapshot_data:
                return False

            # Restore memory state
            memory = self._deserialize_memory(snapshot_data)
            success = await self.save_memory(story_id, memory)

            return success

        except Exception:
            return False

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache performance statistics."""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = (
            (self.cache_stats["hits"] / total_requests * 100)
            if total_requests > 0
            else 0
        )

        return {
            "hit_rate_percent": round(hit_rate, 2),
            "total_hits": self.cache_stats["hits"],
            "total_misses": self.cache_stats["misses"],
            "total_requests": total_requests,
            "memory_cache_size": len(self.memory_cache),
            "character_cache_size": len(self.character_cache),
            "world_cache_size": len(self.world_state_cache),
        }

    def clear_cache(self, story_id: str | None = None):
        """Clear caches, optionally for specific story."""
        if story_id:
            # Clear specific story caches
            keys_to_remove = []
            for key in self.memory_cache:
                if key.endswith(story_id):
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self.memory_cache[key]

            # Similar for other caches...
            keys_to_remove = []
            for key in self.character_cache:
                if story_id in key:
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self.character_cache[key]

            keys_to_remove = []
            for key in self.world_state_cache:
                if key.endswith(story_id):
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self.world_state_cache[key]
        else:
            # Clear all caches
            self.memory_cache.clear()
            self.character_cache.clear()
            self.world_state_cache.clear()

        # Reset stats
        self.cache_stats = {"hits": 0, "misses": 0, "evictions": 0}

    def _invalidate_cache(self, story_id: str):
        """Invalidate all caches for a story."""
        self.clear_cache(story_id)

    def _get_default_memory(self) -> dict[str, Any]:
        """Get default memory structure."""
        return {
            "characters": {},
            "world_state": {},
            "flags": {},
            "recent_events": [],
            "metadata": {
                "last_updated": datetime.now(UTC).isoformat(),
                "version": "1.0",
            },
        }

    def _serialize_memory(self, memory: dict[str, Any]) -> dict[str, Any]:
        """Serialize memory state to dictionary."""
        return {
            "characters": memory.get("characters", {}),
            "world_state": memory.get("world_state", {}),
            "flags": memory.get("flags", {}),
            "recent_events": memory.get("recent_events", []),
            "metadata": memory.get(
                "metadata",
                {"last_updated": datetime.now(UTC).isoformat(), "version": "1.0"},
            ),
        }

    def _deserialize_memory(self, data: dict[str, Any]) -> dict[str, Any]:
        """Deserialize dictionary to memory state."""
        if not data:
            return self._get_default_memory()

        return {
            "characters": data.get("characters", {}),
            "world_state": data.get("world_state", {}),
            "flags": data.get("flags", {}),
            "recent_events": data.get("recent_events", []),
            "metadata": data.get(
                "metadata",
                {"last_updated": datetime.now(UTC).isoformat(), "version": "1.0"},
            ),
        }
