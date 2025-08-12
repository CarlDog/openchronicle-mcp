"""
Context Management Components

This package provides specialized components for context generation and world state
management in the OpenChronicle narrative AI engine.

Components:
- ContextBuilder: Advanced context generation for narrative AI prompts
- WorldStateManager: World state, events, and flags management
- SceneContextManager: Scene-specific context and narrative continuity

Usage:
    from .context_builder import ContextBuilder, ContextConfiguration, ContextMetrics
    from .world_state_manager import WorldStateManager, WorldStateAnalysis, EventFilter
    from .scene_context_manager import SceneContextManager, SceneContext, ContextContinuity
"""

from .context_builder import ContextBuilder
from .context_builder import ContextConfiguration
from .context_builder import ContextMetrics
from .scene_context_manager import ContextContinuity
from .scene_context_manager import SceneContext
from .scene_context_manager import SceneContextManager
from .scene_context_manager import SceneTransition
from .world_state_manager import EventFilter
from .world_state_manager import WorldStateAnalysis
from .world_state_manager import WorldStateManager
from .world_state_manager import WorldStateUpdate


__all__ = [
    "ContextBuilder",
    "ContextConfiguration",
    "ContextContinuity",
    "ContextMetrics",
    "EventFilter",
    "SceneContext",
    "SceneContextManager",
    "SceneTransition",
    "WorldStateAnalysis",
    "WorldStateManager",
    "WorldStateUpdate",
]
