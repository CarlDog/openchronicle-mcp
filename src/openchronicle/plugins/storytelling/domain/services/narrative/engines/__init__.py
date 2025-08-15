"""
Narrative Engine Components

Specialized engine components that provide specific narrative functionality.
These engines handle distinct aspects of narrative generation and validation.

Engine Categories:
- consistency/ - Memory validation and consistency checking
- emotional/ - Emotional stability and mood tracking
- mechanics/ - Dice mechanics, branching, and resolution
- response/ - Intelligent response generation and quality
"""

# Import orchestrators from each engine category
from .consistency.consistency_orchestrator import ConsistencyOrchestrator
from .emotional.emotional_orchestrator import EmotionalOrchestrator
from .mechanics.mechanics_orchestrator import MechanicsOrchestrator
from .response.response_orchestrator import ResponseOrchestrator


__all__ = [
    "ConsistencyOrchestrator",
    "EmotionalOrchestrator", 
    "MechanicsOrchestrator",
    "ResponseOrchestrator",
]
