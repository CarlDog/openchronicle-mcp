"""
OpenChronicle package initializer.

Provides a version accessor and marks the top-level package for absolute imports.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version


try:
    __version__ = version("openchronicle")
except PackageNotFoundError:  # pragma: no cover - during editable/dev installs
    __version__ = "0.0.0+dev"

__all__ = ["__version__"]
