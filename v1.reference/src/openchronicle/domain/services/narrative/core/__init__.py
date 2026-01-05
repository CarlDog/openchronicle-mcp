"""TEMP re-export during migration to plugin-based architecture.

This module exposes narrative core components from the storytelling plugin to
preserve import compatibility during Phase 1.
"""

from openchronicle.domain.services.narrative.core.narrative_character_integration import NarrativeCharacterIntegration
from openchronicle.domain.services.narrative.core.narrative_mechanics_handler import NarrativeMechanicsHandler
from openchronicle.domain.services.narrative.core.narrative_operation_router import NarrativeOperation
from openchronicle.domain.services.narrative.core.narrative_operation_router import NarrativeOperationRouter
from openchronicle.domain.services.narrative.core.narrative_state_manager import NarrativeStateManager


__all__ = [
    "NarrativeCharacterIntegration",
    "NarrativeMechanicsHandler",
    "NarrativeOperation",
    "NarrativeOperationRouter",
    "NarrativeStateManager",
]
