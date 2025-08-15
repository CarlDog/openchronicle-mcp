"""
OpenChronicle Core - Narrative Systems Shared Components

Common utilities, base classes, and shared functionality for all narrative components.
"""

from .narrative_base import EventProcessor
from .narrative_base import NarrativeComponent
from .narrative_base import NarrativeEvent
from .narrative_base import StateManager
from .narrative_base import ValidationBase
from .narrative_base import ValidationResult
from .narrative_state import NarrativeState
from .narrative_state import NarrativeStateManager


__all__ = [
    "EventProcessor",
    "NarrativeComponent",
    "NarrativeEvent",
    "NarrativeState",
    "NarrativeStateManager",
    "StateManager",
    "ValidationBase",
    "ValidationResult",
]
