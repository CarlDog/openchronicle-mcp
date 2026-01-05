"""
CLI interfaces for OpenChronicle.

This module provides command-line interfaces for interactive storytelling
and story management. It serves as the CLI interface layer in the hexagonal architecture.
"""

from openchronicle.infrastructure.bootstrap import build_facade
from openchronicle.infrastructure.bootstrap import get_facade


def _facade(name="story"):
    """
    Get a facade by name with fallback to building a new one.

    Args:
        name: The facade name to retrieve ("story", "core", etc.)

    Returns:
        The requested facade or a newly built facade as fallback
    """
    try:
        facade = get_facade(name)
        return facade or build_facade()
    except Exception:
        return build_facade()
