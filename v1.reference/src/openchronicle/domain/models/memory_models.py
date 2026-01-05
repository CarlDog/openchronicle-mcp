"""
Domain Memory Models

Simple domain models for memory validation that avoid infrastructure dependencies.
"""

from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Dict
from typing import List


@dataclass
class CharacterMemory:
    """Domain model for character memory used in validation."""

    name: str
    dialogue_history: List[Dict[str, Any]] = field(default_factory=list)
    background: str = ""
    traits: Dict[str, Any] = field(default_factory=dict)
    relationships: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure dialogue_history is initialized."""
        if self.dialogue_history is None:
            self.dialogue_history = []


@dataclass
class MemoryState:
    """Domain model for memory state used in validation."""

    characters: Dict[str, CharacterMemory] = field(default_factory=dict)
    story_metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure characters dict is initialized."""
        if self.characters is None:
            self.characters = {}
