"""
Core domain entities for OpenChronicle.

These are the fundamental business objects that represent the core concepts
of the narrative engine. They contain business logic but no external dependencies.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class StoryStatus(Enum):
    """Story lifecycle status."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


@dataclass
class Story:
    """
    Core story entity representing a narrative session.
    
    A story is the top-level container for all narrative elements including
    characters, scenes, timeline, and world state.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    status: StoryStatus = StoryStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Core narrative elements
    world_state: Dict[str, Any] = field(default_factory=dict)
    active_flags: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_world_state(self, key: str, value: Any) -> None:
        """Update world state and refresh timestamp."""
        self.world_state[key] = value
        self.updated_at = datetime.now()
    
    def add_flag(self, flag_name: str, description: str, flag_type: str = "general") -> None:
        """Add a story flag for tracking narrative elements."""
        self.active_flags[flag_name] = {
            "description": description,
            "type": flag_type,
            "created_at": datetime.now()
        }
        self.updated_at = datetime.now()
    
    def remove_flag(self, flag_name: str) -> bool:
        """Remove a story flag. Returns True if flag existed."""
        if flag_name in self.active_flags:
            del self.active_flags[flag_name]
            self.updated_at = datetime.now()
            return True
        return False
    
    def is_active(self) -> bool:
        """Check if story is in an active state."""
        return self.status in (StoryStatus.ACTIVE, StoryStatus.DRAFT)


@dataclass
class Character:
    """
    Character entity representing a story participant.
    
    Characters maintain their own state, relationships, and development arcs
    throughout the narrative.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    story_id: str = ""
    
    # Character attributes
    description: str = ""
    personality_traits: Dict[str, Any] = field(default_factory=dict)
    background: str = ""
    goals: List[str] = field(default_factory=list)
    
    # Dynamic state
    current_mood: str = "neutral"
    emotional_state: Dict[str, float] = field(default_factory=dict)
    relationships: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    memory_profile: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    
    # Development tracking
    character_arc: List[Dict[str, Any]] = field(default_factory=list)
    consistency_score: float = 1.0
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def update_emotional_state(self, emotion: str, intensity: float) -> None:
        """Update character's emotional state."""
        self.emotional_state[emotion] = max(0.0, min(1.0, intensity))
        self.updated_at = datetime.now()
    
    def add_relationship(self, other_character_id: str, relationship_type: str, 
                        strength: float = 0.5) -> None:
        """Add or update a relationship with another character."""
        self.relationships[other_character_id] = {
            "type": relationship_type,
            "strength": max(0.0, min(1.0, strength)),
            "established_at": datetime.now()
        }
        self.updated_at = datetime.now()
    
    def add_development_event(self, event_description: str, impact_level: float = 0.5) -> None:
        """Record a character development event."""
        self.character_arc.append({
            "description": event_description,
            "impact_level": impact_level,
            "timestamp": datetime.now()
        })
        self.updated_at = datetime.now()


@dataclass 
class Scene:
    """
    Scene entity representing a narrative interaction.
    
    Scenes are the atomic units of story progression, containing user input,
    AI responses, and the resulting state changes.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    story_id: str = ""
    sequence_number: int = 0
    
    # Scene content
    user_input: str = ""
    ai_response: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Scene metadata
    scene_type: str = "narrative"  # narrative, dialogue, action, description
    participants: List[str] = field(default_factory=list)  # character IDs
    location: str = ""
    
    # Technical metadata
    model_used: str = ""
    tokens_used: int = 0
    generation_time: float = 0.0
    
    # State changes
    memory_snapshot: Optional[Dict[str, Any]] = None
    world_state_changes: Dict[str, Any] = field(default_factory=dict)
    character_updates: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def add_participant(self, character_id: str) -> None:
        """Add a character as a participant in this scene."""
        if character_id not in self.participants:
            self.participants.append(character_id)
    
    def update_character_state(self, character_id: str, updates: Dict[str, Any]) -> None:
        """Record character state changes from this scene."""
        if character_id not in self.character_updates:
            self.character_updates[character_id] = {}
        self.character_updates[character_id].update(updates)
    
    def get_word_count(self) -> int:
        """Get total word count for this scene."""
        return len(self.user_input.split()) + len(self.ai_response.split())


# Export all entities
__all__ = [
    "Story",
    "Character", 
    "Scene",
    "StoryStatus"
]
