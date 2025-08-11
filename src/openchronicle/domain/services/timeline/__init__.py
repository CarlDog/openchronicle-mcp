"""
Timeline Systems - Unified Timeline Management and State Orchestration

This module provides unified timeline management, navigation, and rollback capabilities
for OpenChronicle narrative management. Consolidates timeline building and state rollback
functionality under a single orchestrator pattern.

Key Components:
- TimelineOrchestrator: Main coordinator for all timeline operations
- Timeline Management: Story timeline building, navigation, auto-summaries
- State Management: Rollback points, versioning, state snapshots
- Shared Utilities: Common temporal state patterns and validation

Replaces legacy timeline_builder.py and rollback_engine.py with modular architecture.
"""

from .timeline_orchestrator import TimelineOrchestrator

__all__ = ["TimelineOrchestrator"]
