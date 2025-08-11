"""
Character Management Module

This module provides the consolidated character management system for OpenChronicle,
replacing the previous separate character engines with a unified, modular architecture.

Components:
- character_base.py - Base classes and interfaces
- character_data.py - Unified dataclasses and enums
- character_storage.py - Character data persistence
- character_orchestrator.py - Main coordinator
- stats/ - Character statistics and behavior
- interactions/ - Relationships and scene management
- consistency/ - Character trait consistency
- presentation/ - Style and model selection
"""

__version__ = "1.0.0"
__all__ = [
    "CharacterOrchestrator",
    "CharacterEngineBase",
    "CharacterData",
    "CharacterStorage",
    "CharacterStatType",
    "CharacterBehaviorType",
    "CharacterRelationType",
    "CharacterInteractionType",
    "StatsBehaviorEngine",
    "InteractionDynamicsEngine",
    "ConsistencyValidationEngine",
    "PresentationStyleEngine",
]

# Core infrastructure imports
from .character_orchestrator import CharacterOrchestrator
from .character_base import CharacterEngineBase
from .character_data import (
    CharacterData,
    CharacterStatType,
    CharacterBehaviorType,
    CharacterRelationType,
    CharacterInteractionType,
)
from .character_storage import CharacterStorage

# Component imports
from .stats import StatsBehaviorEngine
from .interactions import InteractionDynamicsEngine
from .consistency import ConsistencyValidationEngine
from .presentation import PresentationStyleEngine
