"""TEMP re-export during migration to plugin-based architecture.

This module exposes narrative shared components from the storytelling plugin to
preserve import compatibility during Phase 1.
"""

from openchronicle.plugins.storytelling.domain.services.narrative.shared import *  # type: ignore # noqa: F401,F403
