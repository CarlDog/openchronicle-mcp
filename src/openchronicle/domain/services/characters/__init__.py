"""
Character Management Module

This module provides the consolidated character management system for OpenChronicle,
replacing the previous separate character engines with a unified, modular architecture.

Components:
- character_base.py - Base classes and interfaces
- character_data.py - Unified dataclasses and enums  
- character_storage.py - Character data persistence
- character_orchestrator.py - Main coordinator
- character_management_engine.py - Character lifecycle operations
- character_behavior_engine.py - Behavior and response generation
- character_stats_engine.py - Statistics and calculations
- character_validation_engine.py - Validation and consistency
- stats_behavior_engine.py - Statistics-based behavior analysis
- interaction_dynamics_engine.py - Relationships and interactions
- consistency_validation_engine.py - Character trait consistency
- presentation_style_engine.py - Style and presentation management
"""

__version__ = "1.0.0"
__all__ = [
    "CharacterBehaviorType",
    "CharacterData",
    "CharacterEngineBase",
    "CharacterInteractionType",
    "CharacterOrchestrator",
    "CharacterRelationType",
    "CharacterStatType",
    "CharacterStorage",
    "ConsistencyValidationEngine",
    "InteractionDynamicsEngine",
    "PresentationStyleEngine",
    "StatsBehaviorEngine",
]

# Core infrastructure imports
from .core.character_base import CharacterEngineBase
from .core.character_data import CharacterBehaviorType
from .core.character_data import CharacterData
from .core.character_data import CharacterInteractionType
from .core.character_data import CharacterRelationType
from .core.character_data import CharacterStatType
from .character_orchestrator import CharacterOrchestrator
from .core.character_storage import CharacterStorage
from .specialized.consistency_validation_engine import ConsistencyValidationEngine
from .specialized.interaction_dynamics_engine import InteractionDynamicsEngine
from .specialized.presentation_style_engine import PresentationStyleEngine

# Component imports
from .specialized.stats_behavior_engine import StatsBehaviorEngine
