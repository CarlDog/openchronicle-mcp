"""
Async Memory Orchestrator

Async version of the memory orchestrator with performance optimizations.
Provides lazy loading, caching, and non-blocking memory operations.
"""

import asyncio
import logging
from datetime import UTC
from datetime import datetime
from typing import Any

from .character import CharacterManager
from .character import MoodTracker
from .character import VoiceManager
from .context import ContextBuilder
from .context import SceneContextManager
from .context import WorldStateManager
from .persistence.async_memory_repository import AsyncMemoryRepository


class AsyncMemoryOrchestrator:
    """
    Async memory management orchestrator with performance optimization.

    Provides non-blocking memory operations with caching and lazy loading
    for improved performance with large datasets.
    """

    def __init__(self, cache_size: int = 256, cache_ttl: int = 300):
        """Initialize the async memory orchestrator with caching."""
        # Core async components
        self.repository = AsyncMemoryRepository(cache_size, cache_ttl)

        # Character components (will be made async later)
        self.character_manager = CharacterManager(self.repository)
        self.mood_tracker = MoodTracker()
        self.voice_manager = VoiceManager()

        # Context components (will be made async later)
        self.context_builder = ContextBuilder()
        self.world_manager = WorldStateManager()
        self.scene_manager = SceneContextManager()

        # Performance monitoring
        self.performance_stats = {
            "operations_count": 0,
            "average_response_time": 0.0,
            "cache_effectiveness": 0.0,
        }

        # Setup logging
        self.logger = logging.getLogger("openchronicle.async_memory")

    # ===== ASYNC CORE MEMORY OPERATIONS =====

    async def load_current_memory(self, story_id: str) -> dict[str, Any]:
        """Load complete memory state asynchronously."""
        start_time = asyncio.get_event_loop().time()

        try:
            memory_state = await self.repository.load_memory(story_id)

            # Memory state is already a dictionary, return it directly
            result = memory_state

            # Update performance stats
            end_time = asyncio.get_event_loop().time()
            self._update_performance_stats(end_time - start_time)

            return result

        except Exception as e:
            self.logger.error(f"Error loading memory for story {story_id}: {e}")
            return self._get_default_memory()

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

    async def save_current_memory(
        self, story_id: str, memory_data: dict[str, Any]
    ) -> bool:
        """Save memory state asynchronously."""
        start_time = asyncio.get_event_loop().time()

        try:
            # Pass dictionary directly to repository (no conversion needed)
            result = await self.repository.save_memory(story_id, memory_data)

            # Update performance statistics
            end_time = asyncio.get_event_loop().time()
            operation_time = end_time - start_time
            self.performance_stats["operations_count"] += 1

            # Update rolling average response time
            if self.performance_stats["average_response_time"] == 0:
                self.performance_stats["average_response_time"] = operation_time
            else:
                self.performance_stats["average_response_time"] = (
                    self.performance_stats["average_response_time"] * 0.9
                    + operation_time * 0.1
                )

            return result

        except Exception as e:
            self.logger.error(f"Error saving memory for story {story_id}: {e}")
            return False

    async def update_character_memory(
        self, story_id: str, character_name: str, updates: dict[str, Any]
    ) -> bool:
        """Update character memory with optimized caching."""
        start_time = asyncio.get_event_loop().time()

        try:
            success = await self.repository.update_character_memory(
                story_id, character_name, updates
            )

            # Update performance stats
            end_time = asyncio.get_event_loop().time()
            self._update_performance_stats(end_time - start_time)

            return success

        except Exception as e:
            self.logger.error(f"Error updating character {character_name} memory: {e}")
            return False

    async def get_character_memory_snapshot(
        self, story_id: str, character_name: str, format_for_prompt: bool = True
    ) -> dict[str, Any] | None:
        """Get character memory with lazy loading."""
        start_time = asyncio.get_event_loop().time()

        try:
            character_memory = await self.repository.load_character_memory(
                story_id, character_name
            )

            if not character_memory:
                return None

            if format_for_prompt:
                # Format for prompt (this could be optimized with caching too)
                formatted = self._format_character_snapshot_for_prompt(character_memory)

                # Update performance stats
                end_time = asyncio.get_event_loop().time()
                self._update_performance_stats(end_time - start_time)

                return formatted

            # Update performance stats
            end_time = asyncio.get_event_loop().time()
            self._update_performance_stats(end_time - start_time)

            return character_memory

        except Exception as e:
            self.logger.error(f"Error getting character {character_name} snapshot: {e}")
            return None

    async def update_world_state(self, story_id: str, updates: dict[str, Any]) -> bool:
        """Update world state asynchronously."""
        start_time = asyncio.get_event_loop().time()

        try:
            # Load current world state
            current_world_state = await self.repository.load_world_state(story_id)

            # Apply updates
            current_world_state.update(updates)

            # Save updated world state
            success = await self.repository.save_world_state(
                story_id, current_world_state
            )

            # Update performance stats
            end_time = asyncio.get_event_loop().time()
            self._update_performance_stats(end_time - start_time)

            return success

        except Exception as e:
            self.logger.error(f"Error updating world state: {e}")
            return False

    async def archive_memory_snapshot(
        self, story_id: str, scene_id: str, memory_data: dict[str, Any] | None = None
    ) -> bool:
        """Create memory snapshot for rollback capability."""
        start_time = asyncio.get_event_loop().time()

        try:
            success = await self.repository.create_memory_snapshot(story_id, scene_id)

            # Update performance stats
            end_time = asyncio.get_event_loop().time()
            self._update_performance_stats(end_time - start_time)

            return success

        except Exception as e:
            self.logger.error(f"Error creating memory snapshot: {e}")
            return False

    async def refresh_memory_after_rollback(
        self, story_id: str, target_scene_id: str
    ) -> bool:
        """Restore memory from snapshot asynchronously."""
        start_time = asyncio.get_event_loop().time()

        try:
            success = await self.repository.restore_memory_snapshot(
                story_id, target_scene_id
            )

            # Update performance stats
            end_time = asyncio.get_event_loop().time()
            self._update_performance_stats(end_time - start_time)

            return success

        except Exception as e:
            self.logger.error(f"Error restoring memory snapshot: {e}")
            return False

    # ===== PERFORMANCE MONITORING =====

    def get_performance_stats(self) -> dict[str, Any]:
        """Get performance statistics including cache effectiveness."""
        cache_stats = self.repository.get_cache_stats()

        return {
            "memory_operations": self.performance_stats,
            "cache_stats": cache_stats,
            "cache_effectiveness_percent": cache_stats["hit_rate_percent"],
        }

    def clear_cache(self, story_id: str | None = None):
        """Clear memory caches."""
        self.repository.clear_cache(story_id)
        self.logger.info(f"Cache cleared for story: {story_id or 'all stories'}")

    # ===== BACKWARDS COMPATIBILITY METHODS =====

    async def add_memory_flag(
        self, story_id: str, flag_name: str, flag_data: Any = None
    ) -> bool:
        """Add memory flag asynchronously."""
        try:
            memory = await self.repository.load_memory(story_id)
            if "flags" not in memory:
                memory["flags"] = {}
            memory["flags"][flag_name] = flag_data or True
            return await self.repository.save_memory(story_id, memory)
        except Exception as e:
            self.logger.error(f"Error adding memory flag: {e}")
            return False

    async def remove_memory_flag(self, story_id: str, flag_name: str) -> bool:
        """Remove memory flag asynchronously."""
        try:
            memory = await self.repository.load_memory(story_id)
            if "flags" in memory and flag_name in memory["flags"]:
                del memory["flags"][flag_name]
                return await self.repository.save_memory(story_id, memory)
            return True
        except Exception as e:
            self.logger.error(f"Error removing memory flag: {e}")
            return False

    async def has_memory_flag(self, story_id: str, flag_name: str) -> bool:
        """Check if memory flag exists asynchronously."""
        try:
            memory = await self.repository.load_memory(story_id)
            return "flags" in memory and flag_name in memory["flags"]
        except Exception:
            return False

    async def add_recent_event(
        self, story_id: str, event_description: str, event_data: Any = None
    ) -> bool:
        """Add recent event asynchronously."""
        try:
            memory = await self.repository.load_memory(story_id)

            if "recent_events" not in memory:
                memory["recent_events"] = []

            event = {
                "description": event_description,
                "data": event_data,
                "timestamp": datetime.now(UTC).isoformat(),
            }

            memory["recent_events"].append(event)

            # Keep only last 50 events (configurable)
            if len(memory["recent_events"]) > 50:
                memory["recent_events"] = memory["recent_events"][-50:]

            return await self.repository.save_memory(story_id, memory)

        except Exception as e:
            self.logger.error(f"Error adding recent event: {e}")
            return False

    # ===== PRIVATE HELPER METHODS =====

    def _update_performance_stats(self, operation_time: float):
        """Update performance statistics."""
        self.performance_stats["operations_count"] += 1
        count = self.performance_stats["operations_count"]
        current_avg = self.performance_stats["average_response_time"]

        # Calculate rolling average
        self.performance_stats["average_response_time"] = (
            current_avg * (count - 1) + operation_time
        ) / count

    def _get_default_memory(self) -> dict[str, Any]:
        """Get default memory structure."""
        return {
            "characters": {},
            "world_state": {},
            "flags": {},
            "recent_events": [],
            "metadata": {"created_at": datetime.now(UTC).isoformat(), "version": "1.0"},
        }

    def _format_character_snapshot_for_prompt(
        self, snapshot: dict[str, Any]
    ) -> dict[str, Any]:
        """Format character snapshot for LLM prompt."""
        # This could be optimized with caching for frequently accessed characters
        formatted = {
            "name": snapshot.get("name", "Unknown"),
            "traits": snapshot.get("traits", {}),
            "current_mood": snapshot.get("mood", "neutral"),
            "relationships": snapshot.get("relationships", {}),
            "recent_history": snapshot.get("history", [])[-5:],  # Last 5 history items
            "current_state": snapshot.get("current_state", {}),
        }

        return formatted
