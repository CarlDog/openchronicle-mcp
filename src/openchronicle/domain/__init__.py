"""
OpenChronicle Domain Layer

This package contains the core business logic and domain model for OpenChronicle.
The domain layer is independent of external frameworks and focuses on the
essential business concepts and rules.

Architecture:
- entities/: Core business objects with identity (Story, Character, Scene)
- value_objects/: Immutable objects representing complex values (MemoryState, Context)
- services/: Business logic that doesn't belong to entities (StoryGenerator, CharacterAnalyzer)

Key Principles:
- No external dependencies (pure business logic)
- Rich domain model with behavior
- Immutable value objects
- Domain services for complex business operations
"""

# Import all domain components for easy access
from .entities import Character
from .entities import Scene
from .entities import Story
from .entities import StoryStatus
from .services import CharacterAnalyzer
from .services import StoryGenerator
from .value_objects import ContextPriority
from .value_objects import MemoryState
from .value_objects import ModelResponse
from .value_objects import NarrativeContext
from .value_objects import SecurityValidation


# Domain layer version
__version__ = "1.0.0"

# Export all domain components
__all__ = [
    # Entities
    "Story",
    "Character",
    "Scene",
    "StoryStatus",
    # Value Objects
    "MemoryState",
    "NarrativeContext",
    "ModelResponse",
    "SecurityValidation",
    "ContextPriority",
    # Services
    "StoryGenerator",
    "CharacterAnalyzer",
]
