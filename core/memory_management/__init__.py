"""
Memory Management System

This package provides a comprehensive modular memory management system for the
OpenChronicle narrative AI engine, replacing the monolithic memory_manager.py
with specialized components.

Components:
- Persistence Layer: Database operations, serialization, snapshots
- Character Management: Character-specific memory operations
- Context Management: Context generation and world state management
- Shared Models: Common data structures and utilities

Usage:
    from .memory_orchestrator import MemoryOrchestrator
    from .persistence import MemoryRepository, MemorySerializer, SnapshotManager
    from .character import CharacterManager, MoodTracker, VoiceManager
    from .context import ContextBuilder, WorldStateManager, SceneContextManager
    from .shared import MemorySnapshot, CharacterMemory, VoiceProfile
"""

# Persistence layer components
from .persistence import (
    MemoryRepository, 
    MemorySerializer, 
    SnapshotManager,
    DatabaseConnector
)

# Character management components
from .character import (
    CharacterManager,
    MoodTracker, 
    MoodAnalysis,
    MoodRecommendation,
    VoiceManager,
    VoiceAnalysis, 
    VoiceRecommendation
)

# Context management components
from .context import (
    ContextBuilder,
    ContextConfiguration,
    ContextMetrics,
    WorldStateManager,
    WorldStateAnalysis, 
    WorldStateUpdate,
    EventFilter,
    SceneContextManager,
    SceneContext,
    SceneTransition,
    ContextContinuity
)

# Shared models and utilities
from .shared import (
    MemorySnapshot,
    CharacterMemory, 
    VoiceProfile,
    DatabaseManager,
    MemoryUtilities
)

__all__ = [
    # Persistence layer
    'MemoryRepository',
    'MemorySerializer', 
    'SnapshotManager',
    'DatabaseConnector',
    
    # Character management
    'CharacterManager',
    'MoodTracker',
    'MoodAnalysis',
    'MoodRecommendation', 
    'VoiceManager',
    'VoiceAnalysis',
    'VoiceRecommendation',
    
    # Context management
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
    'ContextContinuity',
    
    # Shared components
    'MemorySnapshot',
    'CharacterMemory',
    'VoiceProfile',
    'DatabaseManager',
    'MemoryUtilities'
]
