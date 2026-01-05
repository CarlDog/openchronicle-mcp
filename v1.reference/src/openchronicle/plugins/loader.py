"""
Plugin loader for OpenChronicle.

Provides plugin discovery functionality for the core CLI system.
"""

from typing import Any
from typing import List
from typing import Optional

from openchronicle.plugins import discover_plugins as _discover_plugins


def discover(mode: Optional[str] = None, project_root: Optional[str] = None) -> List[Any]:
    """
    Discover available plugins.

    Args:
        mode: If specified, load only that plugin. If None, discover all.
        project_root: Project root directory (currently unused, for future extensibility)

    Returns:
        List of plugin modules that have register and/or register_cli methods.
    """
    return _discover_plugins(mode)
