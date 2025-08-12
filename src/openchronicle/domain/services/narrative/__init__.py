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

from .narrative_orchestrator import NarrativeOrchestrator
from .core.narrative_operation_router import NarrativeOperation
from .core.narrative_state_manager import NarrativeState
from .shared.narrative_base import EventProcessor
from .shared.narrative_base import NarrativeComponent
from .shared.narrative_base import NarrativeEvent
from .shared.narrative_base import StateManager
from .shared.narrative_base import ValidationBase
from .shared.narrative_base import ValidationResult


# Version info
__version__ = "1.0.0"
__status__ = "Phase 6 Development"

# Main orchestrator class for external use
__all__ = [
    "EventProcessor",
    "NarrativeComponent",
    "NarrativeEvent",
    "NarrativeOperation",
    "NarrativeOrchestrator",
    "NarrativeState",
    "StateManager",
    "ValidationBase",
    "ValidationResult",
]
