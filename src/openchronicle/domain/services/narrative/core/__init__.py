"""
Narrative Core Components

Core coordination and integration components that handle the main narrative operations.
These components orchestrate between different narrative engines and manage state.

Components:
- narrative_character_integration.py - Character-specific narrative operations
- narrative_mechanics_handler.py - Mechanics handling and coordination
- narrative_operation_router.py - Operation routing and dispatching
- narrative_state_manager.py - State management and persistence
"""

from .narrative_character_integration import NarrativeCharacterIntegration
from .narrative_mechanics_handler import NarrativeMechanicsHandler
from .narrative_operation_router import NarrativeOperation
from .narrative_operation_router import NarrativeOperationRouter
from .narrative_state_manager import NarrativeStateManager

__all__ = [
    "NarrativeCharacterIntegration",
    "NarrativeMechanicsHandler",
    "NarrativeOperation",
    "NarrativeOperationRouter",
    "NarrativeStateManager",
]
