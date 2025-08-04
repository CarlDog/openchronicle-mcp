"""
Modular Content Analysis System

A comprehensive content analysis system that replaces the monolithic content_analyzer.py
with a modular, maintainable architecture.

Date: August 4, 2025
Purpose: Phase 5A - Content Analysis Enhancement
Architecture: Modular system with detection, extraction, and routing components

Components:
- Detection: Content classification and type detection
- Extraction: Structured data extraction from content
- Routing: Model selection and routing recommendations
- Orchestrator: Main coordination and backward compatibility

Usage:
    from core.content_analysis import ContentAnalysisOrchestrator
    
    analyzer = ContentAnalysisOrchestrator(model_manager)
    result = await analyzer.process(content, context)
"""

from .context_orchestrator import ContentAnalysisOrchestrator

# Component modules
from . import detection
from . import extraction
from . import routing
from . import shared

# Main components for direct access
from .detection import ContentClassifier, KeywordDetector, TransformerAnalyzer
from .extraction import CharacterExtractor, LocationExtractor, LoreExtractor
from .routing import ModelSelector, ContentRouter, RecommendationEngine

__version__ = "5.0.0"
__all__ = [
    # Main orchestrator
    'ContentAnalysisOrchestrator',
    
    # Component modules
    'detection',
    'extraction', 
    'routing',
    'shared',
    
    # Individual components
    'ContentClassifier',
    'KeywordDetector',
    'TransformerAnalyzer',
    'CharacterExtractor',
    'LocationExtractor',
    'LoreExtractor',
    'ModelSelector',
    'ContentRouter',
    'RecommendationEngine'
]

# Backward compatibility alias
ContentAnalyzer = ContentAnalysisOrchestrator
