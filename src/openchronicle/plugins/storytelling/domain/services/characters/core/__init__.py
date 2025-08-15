"""
Character Core Infrastructure

Core infrastructure components that provide the foundation for all character management.
These components are used throughout the character system.

Components:
- character_base.py - Base classes and interfaces
- character_data.py - Data structures and enums
- character_storage.py - Data persistence
"""

from .character_base import CharacterBehaviorProvider
from .character_base import CharacterEngineBase
from .character_base import CharacterEventHandler
from .character_base import CharacterStateProvider
from .character_base import CharacterValidationProvider
from .character_data import CharacterBehaviorType
from .character_data import CharacterData
from .character_data import CharacterInteractionType
from .character_data import CharacterRelationType
from .character_data import CharacterStats
from .character_data import CharacterStatType
from .character_storage import CharacterStorage


__all__ = [
    "CharacterBehaviorProvider",
    "CharacterBehaviorType",
    "CharacterData",
    "CharacterEngineBase",
    "CharacterEventHandler",
    "CharacterInteractionType",
    "CharacterRelationType",
    "CharacterStatType",
    "CharacterStats",
    "CharacterStateProvider",
    "CharacterStorage",
    "CharacterValidationProvider",
]
