"""TEMP re-export during migration to plugin-based architecture.

All character services have been relocated to the storytelling plugin. This
module re-exports from the plugin to preserve import compatibility.
"""

from openchronicle.plugins.storytelling.domain.services.characters import *  # noqa: F401,F403
