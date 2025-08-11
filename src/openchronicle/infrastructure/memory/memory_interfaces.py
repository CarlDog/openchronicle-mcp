"""
Memory Management Interface Segregation

Following SOLID principles, this module splits the large MemoryOrchestrator
into focused, single-responsibility interfaces.

Phase 2 Week 11-12: Interface Segregation & Architecture Cleanup
"""

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


# === Core Data Structures ===


@dataclass
class MemorySnapshot:
    """Snapshot of memory state at a specific point in time."""

    story_id: str
    scene_id: str
    timestamp: datetime
    character_memories: dict[str, Any]
    world_state: dict[str, Any]
    active_flags: list[str]
    recent_events: list[dict[str, Any]]
    metadata: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemorySnapshot":
        """Create MemorySnapshot from dictionary data."""
        # Handle timestamp conversion if needed
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif isinstance(timestamp, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()

        return cls(
            story_id=data.get("story_id", ""),
            scene_id=data.get("scene_id", ""),
            timestamp=timestamp,
            character_memories=data.get("character_memories", {}),
            world_state=data.get("world_state", {}),
            active_flags=data.get("active_flags", []),
            recent_events=data.get("recent_events", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CharacterMemory:
    """Character-specific memory structure."""

    character_name: str
    personality: dict[str, Any]
    relationships: dict[str, Any]
    experiences: list[dict[str, Any]]
    current_mood: str
    voice_profile: dict[str, Any]
    last_updated: datetime
    metadata: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CharacterMemory":
        """Create CharacterMemory from dictionary data."""
        # Handle timestamp conversion if needed
        last_updated = data.get("last_updated")
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated)
        elif isinstance(last_updated, (int, float)):
            last_updated = datetime.fromtimestamp(last_updated)
        elif last_updated is None:
            last_updated = datetime.now()

        return cls(
            character_name=data.get("character_name", ""),
            personality=data.get("personality", {}),
            relationships=data.get("relationships", {}),
            experiences=data.get("experiences", []),
            current_mood=data.get("current_mood", "neutral"),
            voice_profile=data.get("voice_profile", {}),
            last_updated=last_updated,
            metadata=data.get("metadata", {}),
        )


@dataclass
class WorldState:
    """Global world state information."""

    locations: dict[str, Any]
    time_context: dict[str, Any]
    environmental_factors: dict[str, Any]
    active_plotlines: list[str]
    global_flags: list[str]
    last_updated: datetime


@dataclass
class MemoryContext:
    """Context information for memory operations."""

    story_id: str
    scene_id: str | None = None
    character_focus: str | None = None
    context_type: str = "general"
    include_world_state: bool = True
    include_recent_events: bool = True
    max_events: int = 10


# === Interface Segregation ===


class IMemoryPersistence(ABC):
    """
    Interface for memory data persistence operations.

    Single responsibility: Handle loading, saving, and archiving of memory data.
    """

    @abstractmethod
    async def load_current_memory(self, story_id: str) -> dict[str, Any]:
        """Load current memory state for story."""

    @abstractmethod
    async def save_current_memory(
        self, story_id: str, memory_data: dict[str, Any]
    ) -> bool:
        """Save current memory state for story."""

    @abstractmethod
    async def archive_memory_snapshot(
        self, story_id: str, scene_id: str, snapshot: MemorySnapshot
    ) -> bool:
        """Archive memory snapshot for specific scene."""

    @abstractmethod
    async def restore_memory_from_snapshot(
        self, story_id: str, scene_id: str
    ) -> dict[str, Any]:
        """Restore memory state from archived snapshot."""

    @abstractmethod
    async def get_memory_history(
        self, story_id: str, limit: int = 50
    ) -> list[MemorySnapshot]:
        """Get memory history for story."""

    @abstractmethod
    async def delete_memory_data(self, story_id: str) -> bool:
        """Delete all memory data for story."""

    @abstractmethod
    async def backup_memory_data(self, story_id: str, backup_path: str) -> bool:
        """Backup memory data to specified path."""

    @abstractmethod
    async def restore_memory_data(self, story_id: str, backup_path: str) -> bool:
        """Restore memory data from backup."""


class ICharacterMemoryManager(ABC):
    """
    Interface for character-specific memory management.

    Single responsibility: Manage individual character memories, moods, and relationships.
    """

    @abstractmethod
    async def get_character_memory(
        self, story_id: str, character_name: str
    ) -> CharacterMemory:
        """Get complete character memory."""

    @abstractmethod
    async def update_character_memory(
        self, story_id: str, character_name: str, updates: dict[str, Any]
    ) -> CharacterMemory:
        """Update character memory with new information."""

    @abstractmethod
    async def create_character_memory(
        self, story_id: str, character_name: str, initial_data: dict[str, Any]
    ) -> CharacterMemory:
        """Create new character memory."""

    @abstractmethod
    async def delete_character_memory(self, story_id: str, character_name: str) -> bool:
        """Delete character memory."""

    @abstractmethod
    async def update_character_mood(
        self, story_id: str, character_name: str, new_mood: str, reason: str
    ) -> bool:
        """Update character's current mood."""

    @abstractmethod
    async def update_character_relationship(
        self,
        story_id: str,
        character_name: str,
        other_character: str,
        relationship_data: dict[str, Any],
    ) -> bool:
        """Update relationship between characters."""

    @abstractmethod
    async def add_character_experience(
        self, story_id: str, character_name: str, experience: dict[str, Any]
    ) -> bool:
        """Add new experience to character memory."""

    @abstractmethod
    def get_character_voice_profile(
        self, story_id: str, character_name: str
    ) -> dict[str, Any]:
        """Get character's voice and speech patterns."""

    @abstractmethod
    def format_character_for_prompt(self, character_memory: CharacterMemory) -> str:
        """Format character memory for AI prompt inclusion."""


class IWorldStateManager(ABC):
    """
    Interface for world state management.

    Single responsibility: Manage global world state, locations, and environmental factors.
    """

    @abstractmethod
    async def get_world_state(self, story_id: str) -> WorldState:
        """Get current world state."""

    @abstractmethod
    async def update_world_state(
        self, story_id: str, updates: dict[str, Any]
    ) -> WorldState:
        """Update world state with new information."""

    @abstractmethod
    async def add_location(
        self, story_id: str, location_name: str, location_data: dict[str, Any]
    ) -> bool:
        """Add new location to world state."""

    @abstractmethod
    async def update_location(
        self, story_id: str, location_name: str, updates: dict[str, Any]
    ) -> bool:
        """Update existing location."""

    @abstractmethod
    async def get_location_info(
        self, story_id: str, location_name: str
    ) -> dict[str, Any]:
        """Get information about specific location."""

    @abstractmethod
    async def update_time_context(
        self, story_id: str, time_updates: dict[str, Any]
    ) -> bool:
        """Update time-related context (day/night, season, etc.)."""

    @abstractmethod
    async def add_global_flag(
        self, story_id: str, flag_name: str, description: str
    ) -> bool:
        """Add global story flag."""

    @abstractmethod
    async def remove_global_flag(self, story_id: str, flag_name: str) -> bool:
        """Remove global story flag."""

    @abstractmethod
    async def has_global_flag(self, story_id: str, flag_name: str) -> bool:
        """Check if global flag exists."""

    @abstractmethod
    def format_world_state_for_prompt(self, world_state: WorldState) -> str:
        """Format world state for AI prompt inclusion."""


class IMemoryContextBuilder(ABC):
    """
    Interface for building memory context for AI prompts.

    Single responsibility: Construct relevant memory context from various sources.
    """

    @abstractmethod
    async def build_scene_context(
        self, story_id: str, context_request: MemoryContext
    ) -> str:
        """Build memory context for scene generation."""

    @abstractmethod
    async def build_character_context(
        self, story_id: str, character_name: str, context_request: MemoryContext
    ) -> str:
        """Build memory context focused on specific character."""

    @abstractmethod
    async def build_world_context(
        self, story_id: str, context_request: MemoryContext
    ) -> str:
        """Build memory context focused on world state."""

    @abstractmethod
    async def build_full_context(
        self, story_id: str, context_request: MemoryContext
    ) -> str:
        """Build comprehensive memory context."""

    @abstractmethod
    async def get_recent_events(
        self, story_id: str, limit: int = 10, importance_threshold: float = 0.0
    ) -> list[dict[str, Any]]:
        """Get recent events filtered by importance."""

    @abstractmethod
    async def add_recent_event(
        self,
        story_id: str,
        event_description: str,
        importance: float = 1.0,
        event_type: str = "general",
    ) -> bool:
        """Add new event to recent events."""

    @abstractmethod
    def prioritize_context_elements(
        self, elements: list[dict[str, Any]], max_length: int
    ) -> list[dict[str, Any]]:
        """Prioritize context elements by importance and relevance."""


class IMemoryFlagManager(ABC):
    """
    Interface for memory flag management.

    Single responsibility: Manage story flags and memory markers.
    """

    @abstractmethod
    async def add_memory_flag(
        self,
        story_id: str,
        flag_name: str,
        description: str,
        flag_type: str = "general",
    ) -> bool:
        """Add memory flag."""

    @abstractmethod
    async def remove_memory_flag(self, story_id: str, flag_name: str) -> bool:
        """Remove memory flag."""

    @abstractmethod
    async def has_memory_flag(self, story_id: str, flag_name: str) -> bool:
        """Check if memory flag exists."""

    @abstractmethod
    async def get_active_flags(
        self, story_id: str, flag_type: str | None = None
    ) -> list[str]:
        """Get list of active flags, optionally filtered by type."""

    @abstractmethod
    async def update_flag_description(
        self, story_id: str, flag_name: str, new_description: str
    ) -> bool:
        """Update flag description."""

    @abstractmethod
    async def get_flag_info(self, story_id: str, flag_name: str) -> dict[str, Any]:
        """Get detailed information about specific flag."""

    @abstractmethod
    async def clear_flags_by_type(self, story_id: str, flag_type: str) -> int:
        """Clear all flags of specific type."""


# === Composite Interface (Facade Pattern) ===


class IMemoryOrchestrator(ABC):
    """
    Composite interface that provides access to all memory management capabilities.

    This serves as a facade for the segregated interfaces, maintaining
    backward compatibility while enabling focused interface usage.
    """

    @property
    @abstractmethod
    def persistence(self) -> IMemoryPersistence:
        """Access to memory persistence interface."""

    @property
    @abstractmethod
    def character_manager(self) -> ICharacterMemoryManager:
        """Access to character memory management interface."""

    @property
    @abstractmethod
    def world_manager(self) -> IWorldStateManager:
        """Access to world state management interface."""

    @property
    @abstractmethod
    def context_builder(self) -> IMemoryContextBuilder:
        """Access to memory context building interface."""

    @property
    @abstractmethod
    def flag_manager(self) -> IMemoryFlagManager:
        """Access to memory flag management interface."""

    # Convenience methods that delegate to appropriate interfaces
    @abstractmethod
    async def load_current_memory(self, story_id: str) -> dict[str, Any]:
        """Convenience method for loading memory."""

    @abstractmethod
    async def update_character_memory(
        self, story_id: str, character_name: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Convenience method for character memory updates."""

    @abstractmethod
    async def build_scene_context(self, story_id: str, scene_id: str) -> str:
        """Convenience method for building scene context."""

    @abstractmethod
    async def get_memory_summary(self, story_id: str) -> dict[str, Any]:
        """Get comprehensive memory summary for display."""


# === Service Discovery Interface ===


class IMemoryServiceDiscovery(ABC):
    """
    Interface for discovering and resolving memory management services.

    Enables dependency injection and service location patterns.
    """

    @abstractmethod
    def get_persistence_service(self) -> IMemoryPersistence:
        """Get memory persistence service."""

    @abstractmethod
    def get_character_manager_service(self) -> ICharacterMemoryManager:
        """Get character memory manager service."""

    @abstractmethod
    def get_world_manager_service(self) -> IWorldStateManager:
        """Get world state manager service."""

    @abstractmethod
    def get_context_builder_service(self) -> IMemoryContextBuilder:
        """Get memory context builder service."""

    @abstractmethod
    def get_flag_manager_service(self) -> IMemoryFlagManager:
        """Get memory flag manager service."""

    @abstractmethod
    def register_service(self, interface_type: type, implementation: Any) -> None:
        """Register service implementation for interface."""

    @abstractmethod
    def resolve_service(self, interface_type: type) -> Any:
        """Resolve service implementation for interface."""


# === Interface Factory ===


class MemoryInterfaceFactory:
    """
    Factory for creating segregated memory management interfaces.

    Provides centralized creation and configuration of interface implementations.
    """

    @staticmethod
    def create_persistence_manager(config: dict[str, Any]) -> IMemoryPersistence:
        """Create memory persistence implementation."""
        from .persistence import MemoryRepository

        return MemoryRepository(config)

    @staticmethod
    def create_character_manager(config: dict[str, Any]) -> ICharacterMemoryManager:
        """Create character memory manager implementation."""
        from .character import CharacterManager

        return CharacterManager(config)

    @staticmethod
    def create_world_manager(config: dict[str, Any]) -> IWorldStateManager:
        """Create world state manager implementation."""
        from .context import WorldStateManager

        return WorldStateManager(config)

    @staticmethod
    def create_context_builder(config: dict[str, Any]) -> IMemoryContextBuilder:
        """Create memory context builder implementation."""
        from .context import ContextBuilder

        return ContextBuilder(config)

    @staticmethod
    def create_flag_manager(config: dict[str, Any]) -> IMemoryFlagManager:
        """Create memory flag manager implementation."""
        from .flags import MemoryFlagManager

        return MemoryFlagManager(config)

    @staticmethod
    def create_orchestrator(config: dict[str, Any]) -> IMemoryOrchestrator:
        """Create complete orchestrator with all interfaces."""
        from .segregated_memory_orchestrator import SegregatedMemoryOrchestrator

        return SegregatedMemoryOrchestrator(config)
