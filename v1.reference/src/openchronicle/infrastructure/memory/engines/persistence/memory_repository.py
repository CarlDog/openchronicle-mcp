"""
Memory Repository

Handles all database operations and persistence for memory data.
Consolidates all database access patterns from the original memory_manager.py.
"""

import json
import sqlite3
from datetime import UTC
from datetime import datetime
from typing import Any

from openchronicle.infrastructure.persistence.database_orchestrator import database_orchestrator
from openchronicle.shared.json_utilities import JSONUtilities
from openchronicle.shared.logging_system import log_error
from openchronicle.shared.logging_system import log_info
from openchronicle.shared.logging_system import log_warning

from ...shared.memory_models import MemoryState


class MemoryRepository:
    """Handles memory data persistence and retrieval."""

    def __init__(self):
        """Initialize memory repository."""
        self.json_util = JSONUtilities()

    def load_memory(self, story_id: str) -> MemoryState:
        """Load complete memory state for unit (compat identifier retained)."""
        try:
            # Ensure database is initialized (auto-detect test context)
            database_orchestrator.init_database(story_id)
            # Query all memory types from database
            rows = database_orchestrator.execute_query(
                story_id,
                """
                SELECT type, key, value FROM memory
                WHERE story_id = ? AND key = "current"
                ORDER BY updated_at DESC
            """,
                (story_id,),
            )

            memory_data = {}
            for row in rows:
                memory_type = row["type"]
                value = self.json_util.safe_loads(row["value"])
                if value:
                    memory_data[memory_type] = value

            return self._deserialize_memory(memory_data)

        except (sqlite3.Error, TypeError, ValueError, KeyError, AttributeError) as e:
            log_error(
                f"Failed to load memory for unit {story_id}: {e}",
                context_tags=["memory", "load", "error"],
            )
            return MemoryState()

    def save_memory(self, story_id: str, memory: MemoryState | dict[str, Any]) -> bool:
        """Save memory state with automatic timestamping.

        Accepts either a MemoryState instance or a plain dict that follows the
        serialized memory structure. Dicts will be converted to MemoryState first
        to normalize shapes before serialization.
        """
        try:
            # Ensure database is initialized (auto-detect test context)
            database_orchestrator.init_database(story_id)
            # Normalize input to MemoryState
            if isinstance(memory, dict):
                memory = self._deserialize_memory(memory)

            serialized_data = self._serialize_memory(memory)

            # Update timestamp
            serialized_data["metadata"]["last_updated"] = datetime.now(UTC).isoformat()

            # Save each memory type to database
            for memory_type in [
                "characters",
                "world_state",
                "flags",
                "recent_events",
                "metadata",
            ]:
                if memory_type in serialized_data:
                    database_orchestrator.execute_update(
                        story_id,
                        """
                        INSERT OR REPLACE INTO memory
                        (story_id, type, key, value, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (
                            story_id,
                            memory_type,
                            "current",
                            self.json_util.safe_dumps(serialized_data[memory_type]),
                            datetime.now(UTC).isoformat(),
                        ),
                    )
        except (sqlite3.Error, TypeError, ValueError, KeyError, AttributeError) as e:
            log_error(
                f"Failed to save memory for unit {story_id}: {e}",
                context_tags=["memory", "save", "error"],
            )
            return False
        else:
            return True

    def load_memory_section(self, story_id: str, section: str) -> dict[str, Any]:
        """Load specific memory section efficiently."""
        try:
            # Ensure database is initialized (auto-detect test context)
            database_orchestrator.init_database(story_id)
            rows = database_orchestrator.execute_query(
                story_id,
                """
                SELECT value FROM memory
                WHERE story_id = ? AND type = ? AND key = "current"
            """,
                (story_id, section),
            )

            if rows:
                return self.json_util.safe_loads(rows[0]["value"]) or {}
        except (sqlite3.Error, TypeError, ValueError) as e:
            log_error(
                f"Failed to load memory section {section} for unit {story_id}: {e}",
                context_tags=["memory", "section", "error"],
            )
            return {}
        else:
            return {}

    def update_memory_section(self, story_id: str, section: str, data: dict[str, Any]) -> bool:
        """Update specific memory section efficiently."""
        try:
            # Ensure database is initialized (auto-detect test context)
            database_orchestrator.init_database(story_id)
            database_orchestrator.execute_update(
                story_id,
                """
                INSERT OR REPLACE INTO memory
                (story_id, type, key, value, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    story_id,
                    section,
                    "current",
                    self.json_util.safe_dumps(data),
                    datetime.now(UTC).isoformat(),
                ),
            )
        except (sqlite3.Error, TypeError, ValueError) as e:
            log_error(
                f"Failed to update memory section {section} for unit {story_id}: {e}",
                context_tags=["memory", "update", "error"],
            )
            return False
        else:
            return True

    def create_snapshot(self, story_id: str, scene_id: str, memory: MemoryState) -> str:
        """Create memory snapshot linked to frame (legacy id name retained)."""
        try:
            # Ensure database is initialized (auto-detect test context)
            database_orchestrator.init_database(story_id)
            serialized_memory = self._serialize_memory(memory)
            snapshot_id = f"{story_id}_{scene_id}_{datetime.now(UTC).isoformat()}"

            database_orchestrator.execute_update(
                story_id,
                """
                INSERT INTO memory_history (story_id, scene_id, timestamp, value)
                VALUES (?, ?, ?, ?)
            """,
                (
                    story_id,
                    scene_id,
                    datetime.now(UTC).isoformat(),
                    self.json_util.safe_dumps(serialized_memory),
                ),
            )

            # Keep only last 50 snapshots to prevent database bloat
            self._cleanup_old_snapshots(story_id)

        except (sqlite3.Error, TypeError, ValueError) as e:
            log_error(
                f"Failed to create snapshot for unit {story_id} frame {scene_id}: {e}",
                context_tags=["memory", "snapshot", "error"],
            )
            return ""
        else:
            return snapshot_id

    def restore_from_snapshot(self, story_id: str, scene_id: str) -> MemoryState | None:
        """Restore memory from a specific snapshot point."""
        try:
            # Ensure database is initialized (auto-detect test context)
            database_orchestrator.init_database(story_id)
            rows = database_orchestrator.execute_query(
                story_id,
                """
                SELECT value FROM memory_history
                WHERE story_id = ? AND scene_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """,
                (story_id, scene_id),
            )

            if rows:
                snapshot_data = self.json_util.safe_loads(rows[0]["value"])
                if snapshot_data:
                    result = self._deserialize_memory(snapshot_data)
                else:
                    result = None
            else:
                result = None

        except (sqlite3.Error, TypeError, ValueError) as e:
            log_error(
                f"Failed to restore snapshot for unit {story_id} frame {scene_id}: {e}",
                context_tags=["memory", "snapshot", "error"],
            )
            return None
        else:
            return result

    def get_snapshot_metadata(self, story_id: str) -> list[dict[str, Any]]:
        """Get metadata for all snapshots."""
        try:
            # Ensure database is initialized (auto-detect test context)
            database_orchestrator.init_database(story_id)
            rows = database_orchestrator.execute_query(
                story_id,
                """
                SELECT scene_id, timestamp FROM memory_history
                WHERE story_id = ?
                ORDER BY timestamp DESC
            """,
                (story_id,),
            )

            return [{"scene_id": row["scene_id"], "timestamp": row["timestamp"]} for row in rows]

        except (sqlite3.Error, TypeError, ValueError) as e:
            log_error(
                f"Failed to load snapshot metadata for unit {story_id}: {e}",
                context_tags=["memory", "snapshot", "error"],
            )
            return []

    def _serialize_memory(self, memory: MemoryState) -> dict[str, Any]:
        """Convert MemoryState to dictionary for storage.

        Robust to lists containing either dataclass instances or dicts for
        flags/recent_events.
        """

        def _serialize_flag(flag_obj: Any) -> dict[str, Any]:
            if isinstance(flag_obj, dict):
                name = flag_obj.get("name", "")
                created = flag_obj.get("created")
                # Normalize created to isoformat string
                if hasattr(created, "isoformat"):
                    created_str = created.isoformat()
                elif isinstance(created, str):
                    created_str = created
                else:
                    created_str = datetime.now(UTC).isoformat()
                return {
                    "name": name,
                    "created": created_str,
                    "data": flag_obj.get("data"),
                }
            # Dataclass-like
            return {
                "name": getattr(flag_obj, "name", ""),
                "created": getattr(flag_obj, "created", datetime.now(UTC)).isoformat(),
                "data": getattr(flag_obj, "data", None),
            }

        def _serialize_event(event_obj: Any) -> dict[str, Any]:
            if isinstance(event_obj, dict):
                description = event_obj.get("description", "")
                ts = event_obj.get("timestamp")
                if hasattr(ts, "isoformat"):
                    ts_str = ts.isoformat()
                elif isinstance(ts, str):
                    ts_str = ts
                else:
                    ts_str = datetime.now(UTC).isoformat()
                data = event_obj.get("data", {})
                return {"description": description, "timestamp": ts_str, "data": data}
            # Dataclass-like
            description = getattr(event_obj, "description", "")
            ts = getattr(event_obj, "timestamp", datetime.now(UTC))
            data = getattr(event_obj, "data", {})
            return {"description": description, "timestamp": ts.isoformat(), "data": data}

        return {
            "characters": {name: self._serialize_character(char) for name, char in memory.characters.items()},
            "world_state": memory.world_state,
            "flags": [_serialize_flag(flag) for flag in memory.flags],
            "recent_events": [_serialize_event(evt) for evt in memory.recent_events],
            "metadata": {
                "last_updated": memory.metadata.last_updated.isoformat(),
                "version": memory.metadata.version,
                "scene_count": memory.metadata.scene_count,
                "character_count": memory.metadata.character_count,
            },
        }

    def _deserialize_memory(self, data: dict[str, Any]) -> MemoryState:
        """Convert dictionary to MemoryState."""
        from ...shared.memory_models import MemoryFlag
        from ...shared.memory_models import MemoryMetadata
        from ...shared.memory_models import MemoryState
        from ...shared.memory_models import RecentEvent

        memory = MemoryState()

        # Characters
        if "characters" in data:
            for name, char_data in data["characters"].items():
                memory.characters[name] = self._deserialize_character(name, char_data)

        # World state
        if "world_state" in data:
            memory.world_state = data["world_state"]

        # Flags
        if "flags" in data:
            memory.flags = [
                MemoryFlag(
                    name=flag["name"],
                    created=datetime.fromisoformat(flag["created"]),
                    data=flag.get("data"),
                )
                for flag in data["flags"]
            ]

        # Recent events
        if "recent_events" in data:
            memory.recent_events = [
                RecentEvent(
                    description=event["description"],
                    timestamp=datetime.fromisoformat(event["timestamp"]),
                    data=event.get("data"),
                )
                for event in data["recent_events"]
            ]

        # Metadata
        if "metadata" in data:
            meta = data["metadata"] or {}
            last_updated = meta.get("last_updated")
            if isinstance(last_updated, str):
                try:
                    last_updated_dt = datetime.fromisoformat(last_updated)
                except (ValueError, TypeError):
                    last_updated_dt = datetime.now(UTC)
            elif hasattr(last_updated, "isoformat"):
                last_updated_dt = last_updated
            else:
                last_updated_dt = datetime.now(UTC)

            memory.metadata = MemoryMetadata(
                last_updated=last_updated_dt,
                version=meta.get("version", "1.0"),
                scene_count=meta.get("scene_count", 0),
                character_count=meta.get("character_count", 0),
            )

        return memory

    def _serialize_character(self, character) -> dict[str, Any]:
        """Serialize entity to dictionary."""
        return {
            "name": character.name,
            "description": character.description,
            "personality": character.personality,
            "background": character.background,
            "current_mood": character.current_mood,
            "mood_history": [
                {
                    "mood": mood.mood,
                    "timestamp": mood.timestamp.isoformat(),
                    "reason": mood.reason,
                    "confidence": mood.confidence,
                }
                for mood in character.mood_history
            ],
            "voice_profile": {
                "speaking_style": character.voice_profile.speaking_style,
                "vocabulary_level": character.voice_profile.vocabulary_level,
                "personality_traits": character.voice_profile.personality_traits,
                "speaking_patterns": character.voice_profile.speaking_patterns,
                "emotional_tendencies": character.voice_profile.emotional_tendencies,
            },
            "relationships": character.relationships,
            "arc_progress": character.arc_progress,
            "dialogue_history": character.dialogue_history,
        }

    def _deserialize_character(self, name: str, data: dict[str, Any]):
        """Deserialize entity from dictionary."""
        from ...shared.memory_models import CharacterMemory
        from ...shared.memory_models import MoodEntry
        from ...shared.memory_models import VoiceProfile

        # Mood history
        mood_history = []
        for mood_data in data.get("mood_history", []):
            mood_history.append(
                MoodEntry(
                    mood=mood_data["mood"],
                    timestamp=datetime.fromisoformat(mood_data["timestamp"]),
                    reason=mood_data.get("reason"),
                    confidence=mood_data.get("confidence", 1.0),
                )
            )

        # Voice profile
        voice_data = data.get("voice_profile", {})
        voice_profile = VoiceProfile(
            speaking_style=voice_data.get("speaking_style", ""),
            vocabulary_level=voice_data.get("vocabulary_level", "moderate"),
            personality_traits=voice_data.get("personality_traits", []),
            speaking_patterns=voice_data.get("speaking_patterns", []),
            emotional_tendencies=voice_data.get("emotional_tendencies", []),
        )

        return CharacterMemory(
            name=name,
            description=data.get("description", ""),
            personality=data.get("personality", ""),
            background=data.get("background", ""),
            current_mood=data.get("current_mood", "neutral"),
            mood_history=mood_history,
            voice_profile=voice_profile,
            relationships=data.get("relationships", {}),
            arc_progress=data.get("arc_progress", {}),
            dialogue_history=data.get("dialogue_history", []),
        )

    def _cleanup_old_snapshots(self, story_id: str, max_snapshots: int = 50) -> None:
        """Clean up old snapshots based on retention policy."""
        try:
            # Ensure database is initialized (auto-detect test context)
            database_orchestrator.init_database(story_id)
            database_orchestrator.execute_update(
                story_id,
                """
                DELETE FROM memory_history
                WHERE id NOT IN (
                    SELECT id FROM memory_history
                    WHERE story_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                )
            """,
                (story_id, max_snapshots),
            )
        except sqlite3.Error as e:
            log_warning(
                "Snapshot cleanup failed for st" + f"ory {story_id}: {e}",
                context_tags=["memory", "snapshot", "cleanup"],
            )  # Non-critical

    def create_default_memory_structure(self) -> dict[str, Any]:
        """Create default memory structure for backward compatibility."""
        return {
            "characters": {},
            "world_state": {},
            "flags": [],
            "recent_events": [],
            "metadata": {
                "last_updated": datetime.now(UTC).isoformat(),
                "version": "1.0",
                "scene_count": 0,
                "character_count": 0,
            },
        }
