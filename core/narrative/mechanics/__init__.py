"""
OpenChronicle Core - Narrative Mechanics Subsystem

Modular mechanics system for narrative dice rolling, branching, and resolution.
Extracted from NarrativeDiceEngine for improved maintainability.

Author: OpenChronicle Development Team
"""

from .mechanics_models import (
    DiceType, ResolutionType, DifficultyLevel, OutcomeType,
    DiceRoll, ResolutionResult, ResolutionConfig, NarrativeBranch,
    MechanicsRequest, MechanicsResult, CharacterPerformance
)
from .dice_engine import DiceEngine
from .narrative_branching import NarrativeBranchingEngine
from .mechanics_orchestrator import MechanicsOrchestrator

__all__ = [
    # Data models
    "DiceType",
    "ResolutionType", 
    "DifficultyLevel",
    "OutcomeType",
    "DiceRoll",
    "ResolutionResult",
    "ResolutionConfig",
    "NarrativeBranch",
    "MechanicsRequest",
    "MechanicsResult",
    "CharacterPerformance",
    
    # Components
    "DiceEngine",
    "NarrativeBranchingEngine",
    "MechanicsOrchestrator"
]

# Version info
__version__ = "1.0.0"
__author__ = "OpenChronicle Development Team"
