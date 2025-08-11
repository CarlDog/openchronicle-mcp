"""
OpenChronicle Core - Narrative Systems

Unified narrative system for OpenChronicle providing intelligent response coordination,
narrative mechanics, consistency validation, and emotional stability management.

This modular system replaces and consolidates:
- IntelligentResponseEngine (995 lines)
- NarrativeDiceEngine (796 lines)
- MemoryConsistencyEngine (698 lines)
- EmotionalStabilityEngine (570 lines)

Main Components:
- NarrativeOrchestrator: Central coordination and state management
- ResponseOrchestrator: Intelligent response quality and recommendations
- MechanicsOrchestrator: Dice mechanics, branching, and resolution
- ConsistencyOrchestrator: Memory validation and conflict detection
- EmotionalOrchestrator: Character emotional stability tracking

Author: OpenChronicle Development Team
"""

from .narrative_orchestrator import (
    NarrativeOrchestrator,
    NarrativeState,
    NarrativeOperation,
)
from .shared.narrative_base import (
    NarrativeComponent,
    NarrativeEvent,
    ValidationResult,
    StateManager,
    EventProcessor,
    ValidationBase,
)

# Version info
__version__ = "1.0.0"
__status__ = "Phase 6 Development"

# Main orchestrator class for external use
__all__ = [
    "NarrativeOrchestrator",
    "NarrativeState",
    "NarrativeOperation",
    "NarrativeComponent",
    "NarrativeEvent",
    "ValidationResult",
    "StateManager",
    "EventProcessor",
    "ValidationBase",
]
