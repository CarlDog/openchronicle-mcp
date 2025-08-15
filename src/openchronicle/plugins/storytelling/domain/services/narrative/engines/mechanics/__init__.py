"""
OpenChronicle Core - Narrative Mechanics Subsystem

Modular mechanics system for narrative dice rolling, branching, and resolution.
Extracted from NarrativeDiceEngine for improved maintainability.

Author: OpenChronicle Development Team
"""

from .dice_engine import DiceEngine
from .mechanics_models import CharacterPerformance
from .mechanics_models import DiceRoll
from .mechanics_models import DiceType
from .mechanics_models import DifficultyLevel
from .mechanics_models import MechanicsRequest
from .mechanics_models import MechanicsResult
from .mechanics_models import NarrativeBranch
from .mechanics_models import OutcomeType
from .mechanics_models import ResolutionConfig
from .mechanics_models import ResolutionResult
from .mechanics_models import ResolutionType
from .mechanics_orchestrator import MechanicsOrchestrator
from .narrative_branching import NarrativeBranchingEngine


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
    "MechanicsOrchestrator",
]

# Version info
__version__ = "1.0.0"
__author__ = "OpenChronicle Development Team"
