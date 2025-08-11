"""
Context Building System

Context orchestrator for building contextual information for AI model generation
by coordinating memory, content analysis, and narrative systems.

Usage:
    from openchronicle.infrastructure.content.context import ContextOrchestrator

    orchestrator = ContextOrchestrator()
    context = await orchestrator.build_context(story_data, config)
"""

from .orchestrator import ContextOrchestrator


__all__ = ["ContextOrchestrator"]
