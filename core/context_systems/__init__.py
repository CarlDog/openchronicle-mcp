"""
Context Systems - Unified Context Management

This module provides a unified interface for all context-related operations in OpenChronicle.
It coordinates between memory context, content analysis context, and narrative context systems.

Main Components:
- ContextOrchestrator: Main coordinator for all context operations
- Integration with memory_management/context/ for memory-based context
- Integration with content_analysis/context_orchestrator.py for content analysis
- Integration with narrative_systems/response/context_analyzer.py for narrative context

Usage:
    from core.context_systems import ContextOrchestrator
    
    orchestrator = ContextOrchestrator()
    context = await orchestrator.build_context_with_analysis(user_input, story_data)
"""

from .context_orchestrator import ContextOrchestrator, ContextConfiguration, ContextMetrics

__all__ = [
    'ContextOrchestrator',
    'ContextConfiguration', 
    'ContextMetrics'
]
