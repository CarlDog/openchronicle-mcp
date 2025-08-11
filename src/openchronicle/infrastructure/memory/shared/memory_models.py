"""
Memory Management Data Models

This module contains all data structures and type definitions for the OpenChronicle
memory management system.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from enum import Enum
from typing import Any


class MemoryType(Enum):
    """Types of memory components."""

    CHARACTERS = "characters"
    WORLD_STATE = "world_state"
    FLAGS = "flags"
    RECENT_EVENTS = "recent_events"
    METADATA = "metadata"


@dataclass
class MemoryFlag:
    """Represents a memory flag with associated data."""

    name: str
    created: datetime
    data: dict[str, Any] | None = None


@dataclass
class RecentEvent:
    """Represents a recent event in the story."""

    description: str
    timestamp: datetime
    data: dict[str, Any] | None = None


@dataclass
class WorldEvent:
    """Represents a significant world event."""

    description: str
    event_type: str = "general"
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    data: dict[str, Any] = field(default_factory=dict)
    characters_involved: list[str] = field(default_factory=list)
    location: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "description": self.description,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "characters_involved": self.characters_involved,
            "location": self.location,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorldEvent":
        """Create from dictionary format."""
        timestamp_str = data.get("timestamp", "")
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except:
            timestamp = datetime.now(UTC)

        return cls(
            description=data.get("description", ""),
            event_type=data.get("event_type", "general"),
            timestamp=timestamp,
            data=data.get("data", {}),
            characters_involved=data.get("characters_involved", []),
            location=data.get("location"),
        )


@dataclass
class MoodEntry:
    """Represents a character mood entry."""

    mood: str
    timestamp: datetime
    reason: str | None = None
    confidence: float = 1.0


@dataclass
class VoiceProfile:
    """Represents a character's voice profile."""

    speaking_style: str = ""
    vocabulary_level: str = "moderate"
    personality_traits: list[str] = field(default_factory=list)
    speaking_patterns: list[str] = field(default_factory=list)
    emotional_tendencies: list[str] = field(default_factory=list)


@dataclass
class CharacterMemory:
    """Complete character memory state."""

    name: str
    description: str = ""
    personality: str = ""
    background: str = ""
    current_mood: str = "neutral"
    mood_history: list[MoodEntry] = field(default_factory=list)
    voice_profile: VoiceProfile = field(default_factory=VoiceProfile)
    relationships: dict[str, str] = field(default_factory=dict)
    arc_progress: dict[str, Any] = field(default_factory=dict)
    dialogue_history: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "name": self.name,
            "description": self.description,
            "personality": self.personality,
            "background": self.background,
            "current_mood": self.current_mood,
            "mood_history": [
                entry.__dict__ if hasattr(entry, "__dict__") else entry
                for entry in self.mood_history
            ],
            "voice_profile": (
                self.voice_profile.__dict__
                if hasattr(self.voice_profile, "__dict__")
                else self.voice_profile
            ),
            "relationships": self.relationships,
            "arc_progress": self.arc_progress,
            "dialogue_history": self.dialogue_history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CharacterMemory":
        """Create CharacterMemory from dictionary data."""
        # Handle mood_history
        mood_history = []
        for entry in data.get("mood_history", []):
            if isinstance(entry, dict):
                mood_history.append(
                    MoodEntry(
                        mood=entry.get("mood", "neutral"),
                        context=entry.get("context", ""),
                        timestamp=entry.get("timestamp", datetime.now()),
                    )
                )
            else:
                mood_history.append(entry)

        # Handle voice_profile
        voice_data = data.get("voice_profile", {})
        if isinstance(voice_data, dict):
            voice_profile = VoiceProfile(
                style=voice_data.get("style", "neutral"),
                tone=voice_data.get("tone", "balanced"),
                vocabulary_complexity=voice_data.get("vocabulary_complexity", "medium"),
                sentence_structure=voice_data.get("sentence_structure", "standard"),
                emotional_range=voice_data.get("emotional_range", "moderate"),
                speaking_patterns=voice_data.get("speaking_patterns", []),
                quirks=voice_data.get("quirks", []),
            )
        else:
            voice_profile = voice_data or VoiceProfile()

        return cls(
            name=data.get("name", ""),
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


@dataclass
class MemoryMetadata:
    """Memory metadata tracking."""

    last_updated: datetime
    version: str = "1.0"
    scene_count: int = 0
    character_count: int = 0


@dataclass
class MemoryState:
    """Complete memory state structure."""

    characters: dict[str, CharacterMemory] = field(default_factory=dict)
    world_state: dict[str, Any] = field(default_factory=dict)
    flags: list[MemoryFlag] = field(default_factory=list)
    recent_events: list[RecentEvent] = field(default_factory=list)
    metadata: MemoryMetadata = field(
        default_factory=lambda: MemoryMetadata(last_updated=datetime.now(UTC))
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "characters": {
                name: char.to_dict() if hasattr(char, "to_dict") else char.__dict__
                for name, char in self.characters.items()
            },
            "world_state": self.world_state,
            "flags": [
                flag.__dict__ if hasattr(flag, "__dict__") else flag
                for flag in self.flags
            ],
            "recent_events": [
                event.__dict__ if hasattr(event, "__dict__") else event
                for event in self.recent_events
            ],
            "metadata": (
                self.metadata.__dict__
                if hasattr(self.metadata, "__dict__")
                else self.metadata
            ),
        }


@dataclass
class MemorySnapshot:
    """Memory snapshot for rollback functionality."""

    story_id: str
    scene_id: str
    memory_state: MemoryState
    created_at: datetime
    snapshot_type: str = "scene"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemorySnapshot":
        """Create MemorySnapshot from dictionary data."""
        # Handle timestamp conversion if needed
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif isinstance(created_at, (int, float)):
            created_at = datetime.fromtimestamp(created_at)
        elif created_at is None:
            created_at = datetime.now()

        # Handle memory_state - create a basic MemoryState if needed
        memory_state = data.get("memory_state")
        if isinstance(memory_state, dict):
            memory_state = MemoryState(
                characters=memory_state.get("characters", {}),
                world_state=memory_state.get("world_state", {}),
                recent_events=memory_state.get("recent_events", []),
                flags=memory_state.get("flags", []),
            )
        elif memory_state is None:
            memory_state = MemoryState(
                characters={}, world_state={}, recent_events=[], flags=[]
            )

        return cls(
            story_id=data.get("story_id", ""),
            scene_id=data.get("scene_id", ""),
            memory_state=memory_state,
            created_at=created_at,
            snapshot_type=data.get("snapshot_type", "scene"),
        )


@dataclass
class CharacterUpdates:
    """Character update specification."""

    description: str | None = None
    personality: str | None = None
    background: str | None = None
    mood: str | None = None
    voice_updates: dict[str, Any] | None = None
    relationship_updates: dict[str, str] | None = None
    arc_updates: dict[str, Any] | None = None


@dataclass
class MemoryUpdateResult:
    """Result of memory update operation."""

    success: bool
    message: str
    updated_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# Configuration Constants
MAX_RECENT_EVENTS = 20
MAX_MOOD_HISTORY = 20
MAX_MEMORY_SNAPSHOTS = 50
DEFAULT_CHARACTER_TEMPLATE = {
    "name": "",
    "description": "",
    "personality": "",
    "background": "",
    "current_mood": "neutral",
    "mood_history": [],
    "voice_profile": {
        "speaking_style": "",
        "vocabulary_level": "moderate",
        "personality_traits": [],
        "speaking_patterns": [],
        "emotional_tendencies": [],
    },
    "relationships": {},
    "arc_progress": {},
    "dialogue_history": [],
}
