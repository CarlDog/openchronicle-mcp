"""
Unified Content Management System

A comprehensive system combining content analysis and context building.

Components:
- Analysis: Content classification, extraction, and routing (ContentAnalysisOrchestrator)
- Context: Context building for AI generation (ContextOrchestrator)

Usage:
    # Content Analysis
    from src.openchronicle.infrastructure.content.analysis import ContentAnalysisOrchestrator
    analyzer = ContentAnalysisOrchestrator(model_manager)

    # Context Building
    from src.openchronicle.infrastructure.content.context import ContextOrchestrator
    context_builder = ContextOrchestrator()
"""

# Import both orchestrators for unified access
from .analysis import ContentAnalysisOrchestrator
from .context import ContextOrchestrator

# Export submodules
from . import analysis
from . import context

__version__ = "5.0.0"
__all__ = [
    # Main orchestrators
    "ContentAnalysisOrchestrator",
    "ContextOrchestrator",
    # Submodules
    "analysis",
    "context",
]

# Backward compatibility aliases
ContentAnalyzer = ContentAnalysisOrchestrator
