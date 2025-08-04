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

from .context_builder import ContextBuilder, ContextConfiguration, ContextMetrics
from .world_state_manager import (
    WorldStateManager, 
    WorldStateAnalysis, 
    WorldStateUpdate,
    EventFilter
)
from .scene_context_manager import (
    SceneContextManager, 
    SceneContext, 
    SceneTransition,
    ContextContinuity
)

__all__ = [
    'ContextBuilder',
    'ContextConfiguration',
    'ContextMetrics',
    'WorldStateManager',
    'WorldStateAnalysis', 
    'WorldStateUpdate',
    'EventFilter',
    'SceneContextManager',
    'SceneContext',
    'SceneTransition',
    'ContextContinuity'
]
