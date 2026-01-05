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

from ....shared.exceptions import CacheConnectionError
from ....shared.exceptions import CacheError
from ....shared.exceptions import InfrastructureError
from ....shared.exceptions import MemoryError as MemorySystemError  # Avoid conflict with built-in MemoryError
from ..engines.character import CharacterManager
from ..engines.character import MoodTracker
from ..engines.character import VoiceManager
from ..engines.context import ContextBuilder
from ..engines.context import SceneContextManager
from ..engines.context import WorldStateManager
from ..engines.persistence.async_memory_repository import AsyncMemoryRepository


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
        except (CacheError, CacheConnectionError, InfrastructureError) as e:
            self.logger.exception("Error loading memory for story")
            return self._get_default_memory()
        except Exception as e:
            # Unexpected error - log and convert to infrastructure error
            self.logger.exception("Unexpected error loading memory for story")
            return self._get_default_memory()
        else:
            return result

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

    async def save_current_memory(self, story_id: str, memory_data: dict[str, Any]) -> bool:
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
                    self.performance_stats["average_response_time"] * 0.9 + operation_time * 0.1
                )
        except (CacheError, CacheConnectionError, InfrastructureError) as e:
            self.logger.exception("Error saving memory for story")
            return False
        except Exception as e:
            # Unexpected error - log and convert to infrastructure error
            self.logger.exception("Unexpected error saving memory for story")
            return False
        else:
            return result

    async def update_character_memory(self, story_id: str, character_name: str, updates: dict[str, Any]) -> bool:
        """Update character memory with optimized caching."""
        start_time = asyncio.get_event_loop().time()

        try:
            success = await self.repository.update_character_memory(story_id, character_name, updates)

            # Update performance stats
            end_time = asyncio.get_event_loop().time()
            self._update_performance_stats(end_time - start_time)
        except (CacheError, CacheConnectionError, InfrastructureError) as e:
            self.logger.exception(f"Error updating character {character_name} memory")
            return False
        except Exception as e:
            # Unexpected error - log and convert to infrastructure error
            self.logger.exception(f"Unexpected error updating character {character_name} memory")
            return False
        else:
            return success

    async def get_character_memory_snapshot(
        self, story_id: str, character_name: str, format_for_prompt: bool = True
    ) -> dict[str, Any] | None:
        """Get character memory with lazy loading."""
        start_time = asyncio.get_event_loop().time()

        try:
            character_memory = await self.repository.load_character_memory(story_id, character_name)

            if not character_memory:
                return None

            if format_for_prompt:
                # Format for prompt (this could be optimized with caching too)
                formatted = self._format_character_snapshot_for_prompt(character_memory)

                # Update performance stats
                end_time = asyncio.get_event_loop().time()
                self._update_performance_stats(end_time - start_time)

                result = formatted
            else:
                # Update performance stats
                end_time = asyncio.get_event_loop().time()
                self._update_performance_stats(end_time - start_time)

                result = character_memory
        except (CacheError, CacheConnectionError, InfrastructureError) as e:
            self.logger.exception(f"Error getting character {character_name} snapshot")
            return None
        except Exception as e:
            # Unexpected error - log and convert to infrastructure error
            self.logger.exception(f"Unexpected error getting character {character_name} snapshot")
            return None
        else:
            return result

    async def update_world_state(self, story_id: str, updates: dict[str, Any]) -> bool:
        """Update world state asynchronously."""
        start_time = asyncio.get_event_loop().time()

        try:
            # Load current world state
            current_world_state = await self.repository.load_world_state(story_id)

            # Apply updates
            current_world_state.update(updates)

            # Save updated world state
            success = await self.repository.save_world_state(story_id, current_world_state)

            # Update performance stats
            end_time = asyncio.get_event_loop().time()
            self._update_performance_stats(end_time - start_time)
        except (CacheError, CacheConnectionError, InfrastructureError) as e:
            self.logger.exception("Error updating world state")
            return False
        except Exception as e:
            # Unexpected error - log and convert to infrastructure error
            self.logger.exception("Unexpected error updating world state")
            return False
        else:
            return success

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
        except (CacheError, CacheConnectionError, InfrastructureError) as e:
            self.logger.exception("Error creating memory snapshot")
            return False
        except Exception as e:
            # Unexpected error - log and convert to infrastructure error
            self.logger.exception("Unexpected error creating memory snapshot")
            return False
        else:
            return success

    async def refresh_memory_after_rollback(self, story_id: str, target_scene_id: str) -> bool:
        """Restore memory from snapshot asynchronously."""
        start_time = asyncio.get_event_loop().time()

        try:
            success = await self.repository.restore_memory_snapshot(story_id, target_scene_id)

            # Update performance stats
            end_time = asyncio.get_event_loop().time()
            self._update_performance_stats(end_time - start_time)
        except (CacheError, CacheConnectionError, InfrastructureError) as e:
            self.logger.exception("Error restoring memory snapshot")
            return False
        except Exception as e:
            # Unexpected error - log and convert to infrastructure error
            self.logger.exception("Unexpected error restoring memory snapshot")
            return False
        else:
            return success

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

    # ===== ASYNC FLAG AND EVENT OPERATIONS =====

    async def add_memory_flag(self, story_id: str, flag_name: str, flag_data: Any = None) -> bool:
        """Add or update a memory flag asynchronously."""
        try:
            memory = await self.repository.load_memory(story_id)
            if "flags" not in memory:
                memory["flags"] = {}
            memory["flags"][flag_name] = flag_data or True
            return await self.repository.save_memory(story_id, memory)
        except (CacheError, CacheConnectionError, InfrastructureError) as e:
            self.logger.exception("Error adding memory flag")
            return False
        except Exception as e:
            # Unexpected error - log and convert to infrastructure error
            self.logger.exception("Unexpected error adding memory flag")
            return False

    async def remove_memory_flag(self, story_id: str, flag_name: str) -> bool:
        """Remove a memory flag asynchronously."""
        try:
            memory = await self.repository.load_memory(story_id)
            if "flags" in memory and flag_name in memory["flags"]:
                del memory["flags"][flag_name]
                result = await self.repository.save_memory(story_id, memory)
            else:
                result = True
        except (CacheError, CacheConnectionError, InfrastructureError) as e:
            self.logger.exception("Error removing memory flag")
            return False
        except Exception as e:
            # Unexpected error - log and convert to infrastructure error
            self.logger.exception("Unexpected error removing memory flag")
            return False
        else:
            return result

    async def has_memory_flag(self, story_id: str, flag_name: str) -> bool:
        """Check if a memory flag exists asynchronously."""
        try:
            memory = await self.repository.load_memory(story_id)
            return "flags" in memory and flag_name in memory["flags"]
        except (CacheError, CacheConnectionError, InfrastructureError) as e:
            return False
        except (AttributeError, KeyError) as e:
            # Data structure error in memory format
            return False
        except Exception as e:
            # Unexpected error - silently return False for flag check
            return False

    async def add_recent_event(self, story_id: str, event_description: str, event_data: Any = None) -> bool:
        """Append a recent event entry asynchronously."""
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
            self.logger.exception("Error adding recent event")
            return False

    # ===== PRIVATE HELPER METHODS =====

    def _update_performance_stats(self, operation_time: float):
        """Update performance statistics."""
        self.performance_stats["operations_count"] += 1
        count = self.performance_stats["operations_count"]
        current_avg = self.performance_stats["average_response_time"]

        # Calculate rolling average
        self.performance_stats["average_response_time"] = (current_avg * (count - 1) + operation_time) / count

    def _get_default_memory(self) -> dict[str, Any]:
        """Get default memory structure."""
        return {
            "characters": {},
            "world_state": {},
            "flags": {},
            "recent_events": [],
            "metadata": {"created_at": datetime.now(UTC).isoformat(), "version": "1.0"},
        }

    def _format_character_snapshot_for_prompt(self, snapshot: dict[str, Any]) -> dict[str, Any]:
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
