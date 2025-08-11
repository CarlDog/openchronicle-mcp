"""
OpenChronicle Core - Narrative Systems Shared Components

Common utilities, base classes, and shared functionality for all narrative components.
"""

from .narrative_base import (
    NarrativeComponent,
    NarrativeEvent,
    ValidationResult,
    StateManager,
    EventProcessor,
    ValidationBase,
)
from .narrative_state import NarrativeStateManager, NarrativeState

__all__ = [
    "NarrativeComponent",
    "NarrativeEvent",
    "ValidationResult",
    "StateManager",
    "EventProcessor",
    "ValidationBase",
    "NarrativeStateManager",
    "NarrativeState",
]
