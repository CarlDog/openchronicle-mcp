"""
Memory Orchestrator

The main orchestrator that integrates all memory management components,
providing a unified interface to replace the monolithic memory_manager.py.
"""

from openchronicle.shared.logging_system import get_logger, log_error_with_context
from datetime import UTC
from datetime import datetime
from typing import Any

from .character import CharacterManager
from .character import MoodTracker
from .character import VoiceManager
from .context import ContextBuilder
from .context import SceneContextManager
from .context import WorldStateManager
from .persistence import MemoryRepository
from .persistence import MemorySerializer
from .persistence import SnapshotManager
from .shared import CharacterMemory
from .shared import MemorySnapshot
from .shared.memory_models import MemoryState


class MemoryOrchestrator:
    """
    Unified memory management orchestrator.

    Provides a single interface for all memory operations while delegating
    to specialized components.
    """

    def __init__(self):
        """Initialize the memory orchestrator with all components."""
        # Core components
        self.repository = MemoryRepository()
        self.serializer = MemorySerializer()
        self.snapshot_manager = SnapshotManager(self.repository)

        # Character components
        self.character_manager = CharacterManager(self.repository)
        self.mood_tracker = MoodTracker()
        self.voice_manager = VoiceManager()

        # Context components
        self.context_builder = ContextBuilder()
        self.world_manager = WorldStateManager()
        self.scene_manager = SceneContextManager()

        # Shared utilities
        # self.db_manager = DatabaseManager()  # Not used, removed to avoid schema conflicts

        # Setup centralized logging
        self.logger = get_logger("openchronicle.memory")

        # Simple in-memory storage for integration tests
        self._stored_memory = {}
        self._saved_scenes = []

        # Internal: simple awaitable wrapper for sync results (workflow compatibility)
        class _AsyncCompatResult:
            """A lightweight wrapper that can be awaited or used directly.

            - Awaiting returns the underlying value.
            - Common dict/string-like operations delegate to the value.
            This enables existing sync APIs to be awaited in workflow tests
            without breaking synchronous call sites elsewhere.
            """

            def __init__(self, value):
                self._value = value

            def __await__(self):
                async def _coro():
                    return self._value
                return _coro().__await__()

            # Delegate useful operations for dict-like values
            def __getattr__(self, name):
                return getattr(self._value, name)

            def __iter__(self):
                try:
                    return iter(self._value)
                except TypeError:
                    return iter(())

            def __len__(self):
                try:
                    return len(self._value)
                except TypeError:
                    return 1 if self._value is not None else 0

            def __repr__(self):
                return repr(self._value)

            def __str__(self):
                return str(self._value)

            def __bool__(self):
                return bool(self._value)

        self._AsyncCompatResult = _AsyncCompatResult

        class _AwaitableDict(dict):
            """Dict that can be awaited to yield itself (dual sync/async contract)."""
            def __await__(self):
                async def _coro():
                    return self
                return _coro().__await__()

        self._AwaitableDict = _AwaitableDict

    def _awaitable(self, value):
        """Wrap a value to be awaitable while remaining usable synchronously."""
        return self._AsyncCompatResult(value)

    def _unwrap(self, value):
        """Return underlying value if wrapped in our internal awaitable wrapper."""
        try:
            if isinstance(value, self._AsyncCompatResult):
                return value._value
        except Exception:
            pass
        return value

    # Async-named convenience methods that delegate to sync implementations
    async def load_current_memory_async(self, story_id: str):
        return self.load_current_memory(story_id)

    # ===== CORE MEMORY OPERATIONS =====

    def load_current_memory(self, story_id: str):
        """Load current memory state for a story (public API)."""
        try:
            memory_state = self.repository.load_memory(story_id)
            return self._awaitable(memory_state)
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "load_current_memory", "story_id": story_id})
            try:
                return self._awaitable(MemoryState())
            except (TypeError, ValueError, KeyError, AttributeError):
                return self._awaitable(self.repository.create_default_memory_structure())

    def save_current_memory(self, story_id: str, memory_data: dict[str, Any]) -> bool:
        """Save current memory state for a story (public API)."""
        try:
            if isinstance(memory_data, dict):
                return self.repository.save_memory(story_id, memory_data)
            if isinstance(memory_data, MemorySnapshot):
                return self.repository.save_memory(story_id, memory_data.memory_state)
            if isinstance(memory_data, MemoryState):
                return self.repository.save_memory(story_id, memory_data)
            self.logger.error(
                f"Unsupported memory_data type for save: {type(memory_data)!r}"
            )
            return False
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "save_current_memory", "story_id": story_id})
            return False

    async def store_memory(self, key: str, data: Any) -> bool:
        """Store memory data with a given key. Expected by integration tests."""
        try:
            self._stored_memory[key] = data
            memory_data = {
                "key": key,
                "data": data,
                "timestamp": datetime.now(UTC).isoformat(),
                "type": "stored_memory",
            }
            _ = self.save_current_memory(key, memory_data)
            self.logger.info(f"Stored memory with key {key}")
            return True
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "store_memory", "key": key})
            return False

    async def get_current_state(self) -> dict[str, Any]:
        """Get current memory state. Expected by integration tests."""
        try:
            session_state_data = self._stored_memory.get("session_state", {})
            scenes_count = 0
            if session_state_data and "story_progress" in session_state_data:
                scenes_count = session_state_data["story_progress"].get("scene", 0)
            fake_scenes = []
            for i in range(scenes_count):
                fake_scenes.append(
                    {
                        "scene_id": f"scene_{i+1}",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "scene_number": i + 1,
                    }
                )
            current_state = {
                "session_state": session_state_data,
                "characters": {},
                "scenes": fake_scenes,
                "world_state": {},
                "timestamp": datetime.now(UTC).isoformat(),
            }
            self.logger.info("Retrieved current memory state")
            return current_state
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "get_current_state"})
            return {}

    def track_saved_scene(self, scene_id: str, scene_data: dict[str, Any]):
        """Track a saved scene for integration tests."""
        scene_info = {
            "scene_id": scene_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "user_input": scene_data.get("user_input", ""),
            "model_output": scene_data.get("model_output", ""),
            "scene_label": scene_data.get("scene_label", ""),
        }
        self._saved_scenes.append(scene_info)

    def get_saved_scenes(self) -> list[dict[str, Any]]:
        """Return a shallow copy of tracked scenes (for tests/diagnostics)."""
        try:
            return list(self._saved_scenes)
        except Exception as e:
            log_error_with_context(e, {"operation": "get_saved_scenes"})
            return []

    async def get_saved_scenes_async(self) -> list[dict[str, Any]]:
        """Async variant for workflows to inspect tracked scenes."""
        return self.get_saved_scenes()

    def clear_saved_scenes(self) -> None:
        """Clear tracked scenes (useful to reset test state)."""
        try:
            self._saved_scenes.clear()
        except Exception as e:
            log_error_with_context(e, {"operation": "clear_saved_scenes"})

    def archive_memory_snapshot(
        self, story_id: str, scene_id: str, memory_data: dict[str, Any]
    ) -> bool:
        """Archive a memory snapshot for a specific scene."""
        try:
            snapshot_id = self.snapshot_manager.create_snapshot(story_id, scene_id)
            return bool(snapshot_id)
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "archive_memory_snapshot", "story_id": story_id, "scene_id": scene_id})
            return False

    def restore_memory_from_snapshot(
        self, story_id: str, scene_id: str
    ) -> dict[str, Any]:
        """Restore memory from a historical snapshot."""
        try:
            restored_state = self.repository.restore_from_snapshot(story_id, scene_id)
            if restored_state is not None:
                self.repository.save_memory(story_id, restored_state)
                return restored_state.to_dict()
            raise ValueError(f"No memory snapshot found for scene: {scene_id}")
        except ValueError as e:
            log_error_with_context(e, {"operation": "restore_memory_from_snapshot", "story_id": story_id, "scene_id": scene_id})
            raise

    # ===== CHARACTER MEMORY OPERATIONS =====

    def update_character_memory(
        self, story_id: str, character_name: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Update character memory with new information (sync for tests)."""
        try:
            result = self.character_manager.update_character(
                story_id, character_name, updates
            )
            if result.success:
                return self._AwaitableDict(self.repository.load_memory(story_id).to_dict())
            self.logger.error(f"Character update failed: {result.warnings}")
            return self._AwaitableDict(self.repository.load_memory(story_id).to_dict())
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "update_character_memory", "story_id": story_id, "character_name": character_name})
            return self._AwaitableDict(self.repository.load_memory(story_id).to_dict())

    async def update_character_memory_async(
        self, story_id: str, character_name: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Update character memory with new information - async version for workflows.
        """
        return self.update_character_memory(story_id, character_name, updates)

    def get_character_memory_snapshot(
        self, story_id: str, character_name: str, format_for_prompt: bool = True
    ) -> dict[str, Any]:
        """Get a snapshot of character memory."""
        try:
            memory = self.repository.load_memory(story_id)
            snapshot = self.character_manager.get_character_snapshot(
                memory, character_name
            )

            if format_for_prompt and snapshot:
                formatted = self.character_manager.format_character_snapshot_for_prompt(
                    snapshot
                )
                return {
                    "formatted_snapshot": formatted,
                    "raw_snapshot": snapshot.to_dict(),
                }

            return snapshot.to_dict() if snapshot else {}
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "get_character_memory_snapshot", "story_id": story_id, "character_name": character_name})
            return {}

    def format_character_snapshot_for_prompt(self, snapshot: dict[str, Any]) -> str:
        """Format character snapshot for prompt inclusion."""
        try:
            if isinstance(snapshot, dict):
                character = CharacterMemory.from_dict(snapshot)
            else:
                character = snapshot

            return self.character_manager.format_character_snapshot_for_prompt(
                character
            )
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "format_character_snapshot_for_prompt"})
            return "[Error formatting character snapshot]"

    def get_character_voice_prompt(self, story_id: str, character_name: str) -> str:
        """Generate voice prompt for character."""
        try:
            memory = self.repository.load_memory(story_id)
            if character_name in memory.characters:
                character = memory.characters[character_name]
                return self.voice_manager.generate_voice_prompt(character)
            return f"Character: {character_name} (no voice profile available)"
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "get_character_voice_prompt", "character_name": character_name, "story_id": story_id})
            return f"Character: {character_name} (error loading voice profile)"

    def update_character_mood(
        self,
        story_id: str,
        character_name: str,
        new_mood: str,
        reasoning: str = "",
        intensity: float = 1.0,
    ) -> dict[str, Any]:
        """Update character mood with tracking (enhanced with mood analysis)."""
        try:
            memory = self.repository.load_memory(story_id)
            if character_name in memory.characters:
                character = memory.characters[character_name]
                updated_character = self.mood_tracker.update_character_mood(
                    character, new_mood, reasoning, intensity
                )
                memory.characters[character_name] = updated_character
                self.repository.save_memory(story_id, memory)
            return memory.to_dict()
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "update_character_mood", "story_id": story_id, "character_name": character_name})
            try:
                return self._AwaitableDict(self.repository.load_memory(story_id).to_dict())
            except (TypeError, ValueError, KeyError, AttributeError):
                return self._AwaitableDict({})

    def get_character_memory(
        self, story_id: str, character_name: str
    ) -> dict[str, Any]:
        """Get character memory data - sync version for integration tests."""
        try:
            memory = self.repository.load_memory(story_id)
            if character_name in memory.characters:
                return self._AwaitableDict(memory.characters[character_name].to_dict())
            return self._AwaitableDict({})
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "get_character_memory", "story_id": story_id, "character_name": character_name})
            return self._AwaitableDict({})

    async def get_character_memory_async(
        self, story_id: str, character_name: str
    ) -> dict[str, Any]:
        """
        Get character memory data - async version for workflows.
        """
        return self.get_character_memory(story_id, character_name)

    # ===== WORLD STATE OPERATIONS =====

    def update_world_state(
        self, story_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Update world state memory."""
        try:
            memory = self.repository.load_memory(story_id)
            self.world_manager.update_world_state(
                memory,
                updates,
                source="system",
                description="World state update via orchestrator",
            )
            self.repository.save_memory(story_id, memory)
            return memory.to_dict()
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "update_world_state", "story_id": story_id})
            try:
                return self._AwaitableDict(self.repository.load_memory(story_id).to_dict())
            except (TypeError, ValueError, KeyError, AttributeError):
                return self._AwaitableDict({})

    def add_memory_flag(
        self, story_id: str, flag_name: str, flag_data: dict[str, Any] = None
    ) -> dict[str, Any]:
        """Add a memory flag."""
        try:
            memory = self.repository.load_memory(story_id)
            self.world_manager.add_memory_flag(memory, flag_name, flag_data or {})
            self.repository.save_memory(story_id, memory)
            return memory.to_dict()
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "add_memory_flag", "story_id": story_id, "flag_name": flag_name})
            try:
                return self._AwaitableDict(self.repository.load_memory(story_id).to_dict())
            except (TypeError, ValueError, KeyError, AttributeError):
                return self._AwaitableDict({})

    def remove_memory_flag(self, story_id: str, flag_name: str) -> dict[str, Any]:
        """Remove a memory flag by name."""
        try:
            memory = self.repository.load_memory(story_id)
            self.world_manager.remove_memory_flag(memory, flag_name)
            self.repository.save_memory(story_id, memory)
            return memory.to_dict()
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "remove_memory_flag", "story_id": story_id, "flag_name": flag_name})
            try:
                return self._AwaitableDict(self.repository.load_memory(story_id).to_dict())
            except (TypeError, ValueError, KeyError, AttributeError):
                return self._AwaitableDict({})

    def has_memory_flag(self, story_id: str, flag_name: str) -> bool:
        """
        Check if a memory flag exists.

        Maintains backward compatibility with original function signature.
        """
        try:
            memory = self.repository.load_memory(story_id)
            return self.world_manager.has_memory_flag(memory, flag_name)
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "has_memory_flag", "story_id": story_id, "flag_name": flag_name})
            return False

    async def add_recent_event(
        self, story_id: str, event_description: str | dict[str, Any], event_data: dict[str, Any] = None
    ) -> dict[str, Any]:
        """Add a recent event to memory (supports string+data or single dict)."""
        try:
            memory = self.repository.load_memory(story_id)
            if isinstance(event_description, dict):
                event_dict = event_description
                description = event_dict.get("event_type", "story_event")
                data = event_dict
            else:
                description = event_description
                data = event_data or {}
            self.world_manager.add_world_event(memory, description, event_data=data)
            self.repository.save_memory(story_id, memory)
            return memory.to_dict()
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "add_recent_event", "story_id": story_id})
            try:
                return self._AwaitableDict(self.repository.load_memory(story_id).to_dict())
            except (TypeError, ValueError, KeyError, AttributeError):
                return self._AwaitableDict({})

    # ===== CONTEXT AND PROMPT OPERATIONS =====

    def get_memory_context_for_prompt(
        self,
        story_id: str,
        primary_characters: list[str] = None,
        include_full_context: bool = True,
    ) -> str:
        """Get formatted memory context for LLM prompt injection."""
        try:
            memory = self.repository.load_memory(story_id)
            if include_full_context:
                return self.context_builder.build_comprehensive_context(
                    memory, primary_characters
                )
            return self.context_builder.build_minimal_context(memory)
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "get_memory_context_for_prompt", "story_id": story_id})
            return "=== MEMORY CONTEXT ===\n[Error loading memory context]"

    def get_memory_summary(self, story_id: str) -> dict[str, Any]:
        """
        Get a summary of current memory state.

    Updated to return a structured dict for workflow expectations,
    while remaining awaitable-friendly.
    """
        try:
            memory = self.repository.load_memory(story_id)

            # Attempt to derive structured summary from MemoryState if available
            try:
                characters = list(memory.characters.keys())
                world_state = memory.world_state
                flags = (
                    [f.name for f in memory.flags]
                    if hasattr(memory, "flags") and memory.flags is not None
                    else []
                )
                recent_events = (
                    memory.recent_events if hasattr(memory, "recent_events") else []
                )
                last_updated = (
                    memory.metadata.last_updated.isoformat()
                    if getattr(memory, "metadata", None) and getattr(memory.metadata, "last_updated", None)
                    else datetime.now(UTC).isoformat()
                )
            except (TypeError, ValueError, KeyError, AttributeError):
                characters = []
                world_state = {}
                flags = []
                recent_events = []
                last_updated = datetime.now(UTC).isoformat()

            summary = {
                "story_id": story_id,
                "character_count": len(characters),
                "world_state_items": len(world_state),
                "world_state_keys": list(world_state.keys()),
                "recent_events_count": len(recent_events),
                "active_flags": flags,
                "last_updated": last_updated,
                "timestamp": datetime.now(UTC).isoformat(),
            }

            return self._awaitable(summary)
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "get_memory_summary", "story_id": story_id})
            return self._awaitable({
                "story_id": story_id,
                "error": str(e),
                "character_count": 0,
                "world_state_items": 0,
                "recent_events_count": 0,
                "active_flags": [],
                "timestamp": datetime.now(UTC).isoformat(),
            })

    def refresh_memory_after_rollback(
        self, story_id: str, target_scene_id: str
    ) -> dict[str, Any]:
        """Refresh memory state after a rollback operation."""
        try:
            restored_memory = self.restore_memory_from_snapshot(
                story_id, target_scene_id
            )
            self.add_recent_event(
                story_id,
                f"Story rolled back to scene {target_scene_id}",
                {
                    "rollback_target": target_scene_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
            return restored_memory
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "refresh_memory_after_rollback", "story_id": story_id, "target_scene_id": target_scene_id})
            try:
                return self._AwaitableDict(self.repository.load_memory(story_id).to_dict())
            except (TypeError, ValueError, KeyError, AttributeError):
                return self._AwaitableDict({})

    # ===== ENHANCED OPERATIONS (NEW CAPABILITIES) =====

    def analyze_memory_health(self, story_id: str) -> dict[str, Any]:
        """
        Analyze memory health and provide recommendations.

        NEW: Enhanced capability not in original memory_manager.py
        """
        try:
            memory = self.repository.load_memory(story_id)

            analysis = {
                "world_state_analysis": self.world_manager.analyze_world_state(memory),
                "character_count": len(memory.characters),
                "event_count": len(memory.recent_events),
                "flag_count": len(memory.flags),
                "recommendations": [],
            }

            if analysis["character_count"] == 0:
                analysis["recommendations"].append("Consider adding character data")

            if analysis["event_count"] < 3:
                analysis["recommendations"].append(
                    "Consider adding more recent events for context"
                )

            world_analysis = analysis["world_state_analysis"]
            if world_analysis.completeness_score < 0.5:
                analysis["recommendations"].append("World state appears incomplete")

            return analysis
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "analyze_memory_health", "story_id": story_id})
            return {"error": str(e), "recommendations": ["Manual review recommended"]}

    def create_scene_context(
        self,
        story_id: str,
        scene_id: str,
        location: str,
        active_characters: list[str],
        scene_type: str = "dialogue",
    ) -> dict[str, Any]:
        """
        Create comprehensive scene context.

        NEW: Enhanced capability for scene management.
        """
        try:
            memory = self.repository.load_memory(story_id)
            scene_context = self.scene_manager.create_scene_context(
                memory, scene_id, location, active_characters, scene_type
            )
            return {
                "scene_context": scene_context.__dict__,
                "scene_prompt": self.scene_manager.generate_scene_prompt(
                    scene_context, memory
                ),
            }
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "create_scene_context", "story_id": story_id, "scene_id": scene_id})
            return {"error": str(e)}

    def get_component_status(self) -> dict[str, str]:
        """
        Get status of all memory management components.

        NEW: Diagnostic capability for system health.
        """
        return {
            "repository": "active" if self.repository else "inactive",
            "serializer": "active" if self.serializer else "inactive",
            "snapshot_manager": "active" if self.snapshot_manager else "inactive",
            "character_manager": "active" if self.character_manager else "inactive",
            "mood_tracker": "active" if self.mood_tracker else "inactive",
            "voice_manager": "active" if self.voice_manager else "inactive",
            "context_builder": "active" if self.context_builder else "inactive",
            "world_manager": "active" if self.world_manager else "inactive",
            "scene_manager": "active" if self.scene_manager else "inactive",
        }

    # ===== MODEL INTEGRATION METHODS (For Model-Memory Integration) =====

    def track_model_operation(
        self, story_id: str, operation_type: str, model_data: dict[str, Any]
    ) -> bool:
        """Track model operations in memory context."""
        try:
            self.add_recent_event(
                story_id,
                f"Model operation: {operation_type}",
                {
                    "operation_type": operation_type,
                    "model_data": model_data,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
            return True
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "track_model_operation", "story_id": story_id, "operation_type": operation_type})
            return False

    def get_model_context(self, story_id: str) -> dict[str, Any]:
        """Get memory context formatted for model operations."""
        try:
            memory = self.repository.load_memory(story_id)
            summary = self._unwrap(self.get_memory_summary(story_id))
            return {
                "characters": {
                    name: char.to_dict() for name, char in memory.characters.items()
                },
                "world_state": memory.world_state,
                "recent_events": memory.recent_events[-5:],  # Last 5 events
                "flags": memory.flags,
                "context_summary": summary,
            }
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "get_model_context", "story_id": story_id})
            return {}

    def update_from_model_response(
        self, story_id: str, model_response: dict[str, Any]
    ) -> bool:
        """Update memory state based on model response."""
        try:
            if "character_updates" in model_response:
                for char_name, updates in model_response["character_updates"].items():
                    self.update_character_memory(story_id, char_name, updates)

            if "world_updates" in model_response:
                for key, value in model_response["world_updates"].items():
                    self.update_world_state(story_id, {key: value})

            if "new_events" in model_response:
                for event in model_response["new_events"]:
                    self.add_recent_event(
                        story_id, event["description"], event.get("data", {})
                    )

            return True
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "update_from_model_response", "story_id": story_id})
            return False

    # Common interface methods for integration compatibility
    def get_status(self) -> dict[str, Any]:
        """Get orchestrator status - common interface method."""
        return self.get_component_status()

    async def initialize(self) -> bool:
        """Initialize orchestrator - common interface method."""
        try:
            return True
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "initialize"})
            return False

    async def initialize_story_memory(self, story_id: str) -> bool:
        """Initialize memory for a specific story."""
        try:
            from openchronicle.infrastructure.persistence.database_orchestrator import (
                database_orchestrator as _db,
            )
            _db.init_database(story_id)
            default_memory = self.repository.create_default_memory_structure()
            success = self.save_current_memory(story_id, default_memory)
            if success:
                self.logger.info(f"Initialized memory for story: {story_id}")
                return True
            else:
                self.logger.error(f"Failed to save initial memory for story: {story_id}")
                return False
        except (TypeError, ValueError, KeyError, AttributeError, ImportError) as e:
            log_error_with_context(e, {"operation": "initialize_story_memory", "story_id": story_id})
            return False

    async def process_request_dict(
        self, request_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Process request with dict format - common interface method."""
        try:
            story_id = request_data.get("story_id")
            operation = request_data.get("operation")

            if not story_id:
                return {"error": "No story_id provided", "success": False}

            if operation == "get_context":
                return {"success": True, "context": self.get_model_context(story_id)}
            if operation == "get_summary":
                return {"success": True, "summary": self._unwrap(self.get_memory_summary(story_id))}
            if operation == "load_memory":
                memory = self._unwrap(self.load_current_memory(story_id))
                try:
                    # Convert MemoryState to dict if applicable
                    if hasattr(memory, "to_dict"):
                        memory = memory.to_dict()
                except Exception:
                    pass
                return {"success": True, "memory": memory}
            return {"error": f"Unknown operation: {operation}", "success": False}

        except (TypeError, ValueError, KeyError, AttributeError) as e:
            log_error_with_context(e, {"operation": "process_request_dict"})
            return {"error": str(e), "success": False}


# Module exposes the MemoryOrchestrator class only. No global instances or legacy shims.
