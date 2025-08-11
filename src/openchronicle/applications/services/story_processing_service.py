"""Deprecated shim for backward compatibility.

Use openchronicle.application.services.story_processing_service instead.
This module will be removed in a future release.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "openchronicle.applications.services.story_processing_service is deprecated; use openchronicle.application.services.story_processing_service",
    DeprecationWarning,
    stacklevel=2,
)

from openchronicle.application.services.story_processing_service import *  # re-export
