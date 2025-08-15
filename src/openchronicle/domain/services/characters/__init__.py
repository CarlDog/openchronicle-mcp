"""TEMP re-export during migration to plugin-based architecture.

This module exposes characters services from the storytelling plugin to
preserve import compatibility during Phase 1.
"""

from openchronicle.plugins.storytelling.domain.services.characters import *  # type: ignore # noqa: F401,F403
