"""
OpenChronicle CLI Core Module.

Provides shared infrastructure for all CLI commands including:
- Output management and formatting
- Configuration handling
- Base command classes
- Common utilities
"""

from .output_manager import OutputManager
from .config_manager import ConfigManager  
from .base_command import OpenChronicleCommand, ModelCommand, StoryCommand, SystemCommand

__all__ = [
    "OutputManager",
    "ConfigManager", 
    "OpenChronicleCommand",
    "ModelCommand",
    "StoryCommand", 
    "SystemCommand"
]

__version__ = "1.0.0"
