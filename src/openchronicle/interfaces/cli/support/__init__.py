"""
OpenChronicle CLI Core Module.

Provides shared infrastructure for all CLI commands including:
- Output management and formatting
- Configuration handling
- Base command classes
- Common utilities
"""

from .base_command import ModelCommand
from .base_command import OpenChronicleCommand
from .base_command import StoryCommand
from .base_command import SystemCommand
from .config_manager import ConfigManager
from .output_manager import OutputManager


__all__ = [
    "ConfigManager",
    "ModelCommand",
    "OpenChronicleCommand",
    "OutputManager",
    "StoryCommand",
    "SystemCommand"
]

__version__ = "1.0.0"
