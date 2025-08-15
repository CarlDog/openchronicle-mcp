"""TEMP re-export during migration to plugin-based architecture.

This module exposes NarrativeOrchestrator from the storytelling plugin to
preserve import compatibility during Phase 1.
"""

from openchronicle.plugins.storytelling.domain.services.narrative.narrative_orchestrator import *  # type: ignore # noqa: F401,F403
