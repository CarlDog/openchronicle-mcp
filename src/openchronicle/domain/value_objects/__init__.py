"""
Value objects for OpenChronicle domain.

Value objects are immutable objects that represent concepts without identity.
They encapsulate related data and behavior that doesn't belong to entities.
"""

import json
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from enum import Enum
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple


@dataclass(frozen=True)
class MemoryState:
    """
    Immutable snapshot of story memory at a point in time.

    This value object represents the complete state of story memory including
    character states, world information, and narrative context.
    """

    story_id: str
    timestamp: datetime

    # Character memory states
    character_memories: dict[str, dict[str, Any]] = field(default_factory=dict)

    # World state
    world_state: dict[str, Any] = field(default_factory=dict)
    active_flags: dict[str, Any] = field(default_factory=dict)

    # Recent events for context
    recent_events: list[dict[str, Any]] = field(default_factory=list)

    # Metadata
    version: int = 1
    checksum: str | None = None

    def get_character_state(self, character_id: str) -> dict[str, Any] | None:
        """Get memory state for a specific character."""
        return self.character_memories.get(character_id)

    def get_world_value(self, key: str, default: Any = None) -> Any:
        """Get a world state value with optional default."""
        return self.world_state.get(key, default)

    def has_flag(self, flag_name: str) -> bool:
        """Check if a specific flag is active."""
        return flag_name in self.active_flags

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "story_id": self.story_id,
            "timestamp": self.timestamp.isoformat(),
            "character_memories": self.character_memories,
            "world_state": self.world_state,
            "active_flags": self.active_flags,
            "recent_events": self.recent_events,
            "version": self.version,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryState":
        """Create from dictionary representation."""
        timestamp = datetime.fromisoformat(data["timestamp"])
        return cls(
            story_id=data["story_id"],
            timestamp=timestamp,
            character_memories=data.get("character_memories", {}),
            world_state=data.get("world_state", {}),
            active_flags=data.get("active_flags", {}),
            recent_events=data.get("recent_events", []),
            version=data.get("version", 1),
            checksum=data.get("checksum"),
        )


class ContextPriority(Enum):
    """Priority levels for narrative context elements."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class NarrativeContext:
    """
    Immutable context for narrative generation.

    This value object assembles all relevant context for AI model generation
    including character information, world state, and user input.
    """

    story_id: str
    user_input: str
    assembled_at: datetime = field(default_factory=datetime.now)

    # Context components
    characters: dict[str, Any] = field(default_factory=dict)
    memory_state: Optional["MemoryState"] = None
    scene_type: str = "narrative"
    participant_ids: list[str] = field(default_factory=list)
    location: str = ""
    additional_context: dict[str, Any] = field(default_factory=dict)

    # Legacy fields for compatibility
    character_context: dict[str, dict[str, Any]] = field(default_factory=dict)
    world_context: dict[str, Any] = field(default_factory=dict)
    recent_history: list[str] = field(default_factory=list)

    # Context metadata
    priority_elements: dict[ContextPriority, list[str]] = field(default_factory=dict)
    token_estimate: int = 0
    generation_hints: list[str] = field(default_factory=list)

    def get_primary_characters(self) -> list[str]:
        """Get list of primary character IDs in this context."""
        return self.participant_ids or list(self.characters.keys())

    def get_context_summary(self) -> str:
        """Generate a human-readable context summary."""
        chars = len(self.characters)
        world_keys = len(self.additional_context)
        history_items = len(self.recent_history)

        return (
            f"Context for {self.story_id}: "
            f"{chars} characters, {world_keys} world elements, "
            f"{history_items} history items (~{self.token_estimate} tokens)"
        )

    def has_character(self, character_id: str) -> bool:
        """Check if character is included in context."""
        return character_id in self.characters

    def get_critical_elements(self) -> list[str]:
        """Get elements marked as critical priority."""
        return self.priority_elements.get(ContextPriority.CRITICAL, [])


@dataclass(frozen=True)
class ModelResponse:
    """
    Immutable representation of an AI model response.

    This value object encapsulates all metadata about a model's generation
    including performance metrics and technical details.
    """

    content: str
    model_name: str
    provider: str

    # Generation metadata
    timestamp: datetime
    tokens_used: int
    generation_time: float
    finish_reason: str = "completed"

    # Quality metrics
    confidence_score: float | None = None
    quality_metrics: dict[str, float] = field(default_factory=dict)

    # Technical details
    request_id: str | None = None
    model_version: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)

    def tokens_per_second(self) -> float:
        """Calculate generation speed in tokens per second."""
        if self.generation_time <= 0:
            return 0.0
        return self.tokens_used / self.generation_time

    def is_successful(self) -> bool:
        """Check if generation completed successfully."""
        return self.finish_reason == "completed" and bool(self.content.strip())

    def get_cost_estimate(self, input_tokens: int = 0) -> float | None:
        """Estimate generation cost if pricing info is available."""
        # This would integrate with pricing data in a real implementation
        return None

    def to_summary(self) -> dict[str, Any]:
        """Create a summary for logging/debugging."""
        return {
            "model": self.model_name,
            "provider": self.provider,
            "tokens": self.tokens_used,
            "time": self.generation_time,
            "speed": self.tokens_per_second(),
            "success": self.is_successful(),
            "length": len(self.content),
        }


@dataclass(frozen=True)
class SecurityValidation:
    """
    Immutable result of security validation.

    This value object represents the outcome of security checks on user input
    or system operations.
    """

    is_valid: bool
    threat_level: str

    # Validation details
    original_input: str
    sanitized_value: str | None = None
    error_message: str | None = None

    # Security metadata
    validation_timestamp: datetime = field(default_factory=datetime.now)
    validator_version: str = "1.0"
    checks_performed: list[str] = field(default_factory=list)

    def is_safe(self) -> bool:
        """Check if input is safe to process."""
        return self.is_valid and self.threat_level.lower() not in ("critical", "high")

    def get_safe_value(self) -> str:
        """Get safe value to use, preferring sanitized over original."""
        if not self.is_valid:
            return ""
        return self.sanitized_value or self.original_input


# Export all value objects
__all__ = [
    "ContextPriority",
    "MemoryState",
    "ModelResponse",
    "NarrativeContext",
    "SecurityValidation",
]
