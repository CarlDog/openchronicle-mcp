"""
Memory Serializer

Handles memory serialization, deserialization, and validation.
Consolidates JSON handling patterns from the original memory_manager.py.
"""

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from typing import Any

from openchronicle.shared.json_utilities import JSONUtilities

from ..shared.memory_models import CharacterMemory
from ..shared.memory_models import MemoryFlag
from ..shared.memory_models import MemoryMetadata
from ..shared.memory_models import MemoryState
from ..shared.memory_models import MoodEntry
from ..shared.memory_models import RecentEvent
from ..shared.memory_models import VoiceProfile


@dataclass
class ValidationResult:
    """Result of memory validation."""

    valid: bool
    errors: list[str]
    warnings: list[str]
    corrected_fields: list[str]


class MemorySerializer:
    """Handles memory serialization and deserialization with validation."""

    def __init__(self):
        """Initialize memory serializer."""
        self.json_util = JSONUtilities()

    def serialize_memory(self, memory: MemoryState) -> dict[str, Any]:
        """Serialize memory to database-ready format."""
        try:
            return {
                "characters": self._serialize_characters(memory.characters),
                "world_state": memory.world_state,
                "flags": self._serialize_flags(memory.flags),
                "recent_events": self._serialize_events(memory.recent_events),
                "metadata": self._serialize_metadata(memory.metadata),
            }
        except Exception:
            # Return minimal valid structure on error
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

    def deserialize_memory(self, data: dict[str, Any]) -> MemoryState:
        """Deserialize memory from database format with validation."""
        try:
            # Validate and correct data structure
            validated_data = self._validate_and_correct_structure(data)

            memory = MemoryState()

            # Deserialize characters
            if "characters" in validated_data:
                memory.characters = self._deserialize_characters(
                    validated_data["characters"]
                )

            # Deserialize world state
            if "world_state" in validated_data:
                memory.world_state = validated_data["world_state"]

            # Deserialize flags
            if "flags" in validated_data:
                memory.flags = self._deserialize_flags(validated_data["flags"])

            # Deserialize recent events
            if "recent_events" in validated_data:
                memory.recent_events = self._deserialize_events(
                    validated_data["recent_events"]
                )

            # Deserialize metadata
            if "metadata" in validated_data:
                memory.metadata = self._deserialize_metadata(validated_data["metadata"])

            return memory

        except Exception:
            # Return default memory on deserialization error
            return MemoryState()

    def validate_memory_structure(self, memory: MemoryState) -> ValidationResult:
        """Validate memory structure integrity."""
        errors = []
        warnings = []
        corrected_fields = []

        # Validate characters
        for char_name, character in memory.characters.items():
            if not isinstance(character.name, str) or not character.name:
                errors.append(f"Character {char_name} has invalid name")

            if not isinstance(character.current_mood, str):
                warnings.append(f"Character {char_name} has invalid mood type")
                character.current_mood = "neutral"
                corrected_fields.append(f"{char_name}.current_mood")

            # Validate mood history length
            if len(character.mood_history) > 20:
                warnings.append(
                    f"Character {char_name} mood history too long, truncating"
                )
                character.mood_history = character.mood_history[-20:]
                corrected_fields.append(f"{char_name}.mood_history")

        # Validate recent events length
        if len(memory.recent_events) > 20:
            warnings.append("Recent events list too long, truncating")
            memory.recent_events = memory.recent_events[-20:]
            corrected_fields.append("recent_events")

        # Validate metadata
        if not isinstance(memory.metadata.last_updated, datetime):
            errors.append("Invalid metadata timestamp")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            corrected_fields=corrected_fields,
        )

    def _serialize_characters(
        self, characters: dict[str, CharacterMemory]
    ) -> dict[str, Any]:
        """Serialize characters dictionary."""
        result = {}
        for name, character in characters.items():
            result[name] = {
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
        return result

    def _deserialize_characters(
        self, data: dict[str, Any]
    ) -> dict[str, CharacterMemory]:
        """Deserialize characters with error handling."""
        characters = {}
        for name, char_data in data.items():
            try:
                characters[name] = self._deserialize_single_character(name, char_data)
            except Exception:
                # Create minimal character on error
                characters[name] = CharacterMemory(name=name)
        return characters

    def _deserialize_single_character(
        self, name: str, data: dict[str, Any]
    ) -> CharacterMemory:
        """Deserialize single character with validation."""
        # Mood history
        mood_history = []
        for mood_data in data.get("mood_history", []):
            try:
                mood_history.append(
                    MoodEntry(
                        mood=mood_data.get("mood", "neutral"),
                        timestamp=datetime.fromisoformat(mood_data["timestamp"]),
                        reason=mood_data.get("reason"),
                        confidence=mood_data.get("confidence", 1.0),
                    )
                )
            except Exception:
                # Skip invalid mood entries
                continue

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

    def _serialize_flags(self, flags: list[MemoryFlag]) -> list[dict[str, Any]]:
        """Serialize memory flags."""
        return [
            {"name": flag.name, "created": flag.created.isoformat(), "data": flag.data}
            for flag in flags
        ]

    def _deserialize_flags(self, data: list[dict[str, Any]]) -> list[MemoryFlag]:
        """Deserialize memory flags with error handling."""
        flags = []
        for flag_data in data:
            try:
                flags.append(
                    MemoryFlag(
                        name=flag_data["name"],
                        created=datetime.fromisoformat(flag_data["created"]),
                        data=flag_data.get("data"),
                    )
                )
            except Exception:
                # Skip invalid flags
                continue
        return flags

    def _serialize_events(self, events: list[RecentEvent]) -> list[dict[str, Any]]:
        """Serialize recent events."""
        return [
            {
                "description": event.description,
                "timestamp": event.timestamp.isoformat(),
                "data": event.data,
            }
            for event in events
        ]

    def _deserialize_events(self, data: list[dict[str, Any]]) -> list[RecentEvent]:
        """Deserialize recent events with error handling."""
        events = []
        for event_data in data:
            try:
                events.append(
                    RecentEvent(
                        description=event_data["description"],
                        timestamp=datetime.fromisoformat(event_data["timestamp"]),
                        data=event_data.get("data"),
                    )
                )
            except Exception:
                # Skip invalid events
                continue
        return events

    def _serialize_metadata(self, metadata: MemoryMetadata) -> dict[str, Any]:
        """Serialize memory metadata."""
        return {
            "last_updated": metadata.last_updated.isoformat(),
            "version": metadata.version,
            "scene_count": metadata.scene_count,
            "character_count": metadata.character_count,
        }

    def _deserialize_metadata(self, data: dict[str, Any]) -> MemoryMetadata:
        """Deserialize memory metadata with defaults."""
        try:
            return MemoryMetadata(
                last_updated=datetime.fromisoformat(data["last_updated"]),
                version=data.get("version", "1.0"),
                scene_count=data.get("scene_count", 0),
                character_count=data.get("character_count", 0),
            )
        except Exception:
            return MemoryMetadata(last_updated=datetime.now(UTC))

    def _validate_and_correct_structure(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate and correct data structure."""
        # Ensure all required sections exist
        required_sections = [
            "characters",
            "world_state",
            "flags",
            "recent_events",
            "metadata",
        ]
        for section in required_sections:
            if section not in data:
                if section in ["characters", "world_state"]:
                    data[section] = {}
                elif section in ["flags", "recent_events"]:
                    data[section] = []
                else:  # metadata
                    data[section] = {
                        "last_updated": datetime.now(UTC).isoformat(),
                        "version": "1.0",
                        "scene_count": 0,
                        "character_count": 0,
                    }

        return data
