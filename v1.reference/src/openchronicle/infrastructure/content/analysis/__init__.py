"""
Content Analysis System

A comprehensive content analysis system for extracting and analyzing story content.

Components:
- Detection: Content classification and type detection
- Extraction: Structured data extraction from content
- Routing: Model selection and routing recommendations
- Orchestrator: Main coordination interface

Usage:
    The orchestrator is now provided by plugins through domain ports; use ports.
"""

# Component modules
from . import detection
from . import extraction
from . import routing
from . import shared

# Main components for direct access
from .detection import ContentClassifier
from .detection import KeywordDetector
from .detection import TransformerAnalyzer
from .extraction import CharacterExtractor
from .extraction import LocationExtractor
from .extraction import LoreExtractor
from .routing import ContentRouter
from .routing import ModelSelector
from .routing import RecommendationEngine


__version__ = "5.0.0"
__all__ = [
    # Component modules
    "detection",
    "extraction",
    "routing",
    "shared",
    # Individual components
    "ContentClassifier",
    "KeywordDetector",
    "TransformerAnalyzer",
    "CharacterExtractor",
    "LocationExtractor",
    "LoreExtractor",
    "ModelSelector",
    "ContentRouter",
    "RecommendationEngine",
]
