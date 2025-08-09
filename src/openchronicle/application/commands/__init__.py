"""
Application commands for OpenChronicle.

Commands represent write operations that change the system state.
They encapsulate the business use cases and coordinate between
domain services and infrastructure.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime
from abc import ABC, abstractmethod

from ...domain import Story, Character, Scene, StoryStatus, MemoryState


class Command(ABC):
    """Base class for all commands."""
    pass


class CommandResult:
    """Result of command execution."""
    
    def __init__(self, success: bool, message: str = "", data: Any = None, errors: List[str] = None):
        self.success = success
        self.message = message
        self.data = data
        self.errors = errors or []
        self.timestamp = datetime.now()
    
    @classmethod
    def success(cls, message: str = "Operation completed successfully", data: Any = None) -> "CommandResult":
        """Create a successful result."""
        return cls(True, message, data)
    
    @classmethod
    def failure(cls, message: str, errors: List[str] = None) -> "CommandResult":
        """Create a failed result."""
        return cls(False, message, errors=errors)


@dataclass
class CreateStoryCommand(Command):
    """Command to create a new story."""
    title: str
    description: str = ""
    initial_world_state: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.initial_world_state is None:
            self.initial_world_state = {}


@dataclass
class UpdateStoryCommand(Command):
    """Command to update an existing story."""
    story_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[StoryStatus] = None
    world_state_updates: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.world_state_updates is None:
            self.world_state_updates = {}


@dataclass
class CreateCharacterCommand(Command):
    """Command to create a new character."""
    story_id: str
    name: str
    description: str = ""
    personality_traits: Dict[str, Any] = None
    background: str = ""
    goals: List[str] = None
    
    def __post_init__(self):
        if self.personality_traits is None:
            self.personality_traits = {}
        if self.goals is None:
            self.goals = []


@dataclass 
class UpdateCharacterCommand(Command):
    """Command to update an existing character."""
    character_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    personality_updates: Dict[str, Any] = None
    emotional_updates: Dict[str, float] = None
    relationship_updates: Dict[str, Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.personality_updates is None:
            self.personality_updates = {}
        if self.emotional_updates is None:
            self.emotional_updates = {}
        if self.relationship_updates is None:
            self.relationship_updates = {}


@dataclass
class GenerateSceneCommand(Command):
    """Command to generate a new scene."""
    story_id: str
    user_input: str
    model_preference: Optional[str] = None
    scene_type: str = "narrative"
    participant_ids: List[str] = None
    location: str = ""
    context_override: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.participant_ids is None:
            self.participant_ids = []


@dataclass
class SaveSceneCommand(Command):
    """Command to save a generated scene."""
    story_id: str
    user_input: str
    ai_response: str
    model_used: str
    tokens_used: int = 0
    generation_time: float = 0.0
    scene_type: str = "narrative"
    participant_ids: List[str] = None
    location: str = ""
    memory_snapshot: Optional[MemoryState] = None
    character_updates: Dict[str, Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.participant_ids is None:
            self.participant_ids = []
        if self.character_updates is None:
            self.character_updates = {}


@dataclass
class UpdateMemoryCommand(Command):
    """Command to update story memory."""
    story_id: str
    character_updates: Dict[str, Dict[str, Any]] = None
    world_state_updates: Dict[str, Any] = None
    add_events: List[Dict[str, Any]] = None
    add_flags: Dict[str, Dict[str, Any]] = None
    remove_flags: List[str] = None
    
    def __post_init__(self):
        if self.character_updates is None:
            self.character_updates = {}
        if self.world_state_updates is None:
            self.world_state_updates = {}
        if self.add_events is None:
            self.add_events = []
        if self.add_flags is None:
            self.add_flags = {}
        if self.remove_flags is None:
            self.remove_flags = []


@dataclass
class RollbackStoryCommand(Command):
    """Command to rollback story to a previous state."""
    story_id: str
    target_scene_id: str
    preserve_characters: bool = True
    confirm_rollback: bool = False


@dataclass
class DeleteStoryCommand(Command):
    """Command to delete a story and all related data."""
    story_id: str
    confirm_deletion: bool = False
    backup_before_delete: bool = True


@dataclass
class DeleteCharacterCommand(Command):
    """Command to delete a character."""
    character_id: str
    story_id: str
    remove_from_scenes: bool = False
    confirm_deletion: bool = False


# Export all commands
__all__ = [
    "Command",
    "CommandResult", 
    "CreateStoryCommand",
    "UpdateStoryCommand",
    "CreateCharacterCommand",
    "UpdateCharacterCommand",
    "GenerateSceneCommand",
    "SaveSceneCommand",
    "UpdateMemoryCommand", 
    "RollbackStoryCommand",
    "DeleteStoryCommand",
    "DeleteCharacterCommand"
]
