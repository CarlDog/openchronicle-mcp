"""Deprecated shim for backward compatibility.

Use openchronicle.application.cli_app instead.
This module will be removed in a future release.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "openchronicle.applications.cli_app is deprecated; use openchronicle.application.cli_app",
    DeprecationWarning,
    stacklevel=2,
)

from openchronicle.application.cli_app import *  # re-export
