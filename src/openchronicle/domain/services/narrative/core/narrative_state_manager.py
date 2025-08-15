"""TEMP re-export during migration to plugin-based architecture.

This module exposes narrative state manager from the storytelling plugin to
preserve import compatibility during Phase 1.
"""

from openchronicle.plugins.storytelling.domain.services.narrative.core.narrative_state_manager import *  # type: ignore # noqa: F401,F403
