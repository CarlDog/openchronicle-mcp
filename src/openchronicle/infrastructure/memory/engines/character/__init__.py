"""
Character Management Components

This package provides specialized components for character-related memory operations
in the OpenChronicle narrative AI engine.

Components:
- CharacterManager: Core character memory operations and updates
- MoodTracker: Advanced mood analysis and emotional state tracking
- VoiceManager: Voice profile management and consistency analysis

Usage:
    from .character_manager import CharacterManager
    from .mood_tracker import MoodTracker, MoodAnalysis
    from .voice_manager import VoiceManager, VoiceAnalysis
"""

from .character_manager import CharacterManager
from .mood_tracker import MoodAnalysis
from .mood_tracker import MoodPattern
from .mood_tracker import MoodTracker
from .voice_manager import VoiceAnalysis
from .voice_manager import VoiceManager
from .voice_manager import VoiceRecommendation


__all__ = [
    "CharacterManager",
    "MoodAnalysis",
    "MoodPattern",
    "MoodTracker",
    "VoiceAnalysis",
    "VoiceManager",
    "VoiceRecommendation",
]
