"""
Scene Systems - Modular Scene Management for OpenChronicle

Provides unified scene operations through orchestrated components:
- Scene persistence and data management
- Scene analysis and statistics
- Scene labeling and organization
- Rollback and state management

Replaces the legacy monolithic scene_logger.py with clean modular architecture.
"""

from .scene_orchestrator import SceneOrchestrator


# Main interface for backward compatibility
def get_scene_orchestrator(story_id: str) -> SceneOrchestrator:
    """Get a scene orchestrator instance for the given story."""
    return SceneOrchestrator(story_id)


# Export main components
__all__ = ["SceneOrchestrator", "get_scene_orchestrator"]
