"""
OpenChronicle Core - Management Systems

Modular management systems for token and bookmark management.
Provides unified orchestration with backward compatibility.

Usage:
    from openchronicle.application.services.management import ManagementOrchestrator

    # Unified management
    orchestrator = ManagementOrchestrator(config)

    # Token operations
    token_count = orchestrator.count_tokens(text, model)

    # Bookmark operations
    bookmark_id = orchestrator.create_bookmark(story_id, scene_id, label)

    # Individual systems
    from openchronicle.application.services.management.token import TokenManager
    from openchronicle.application.services.management.bookmark import BookmarkManager
"""

from .bookmark import BookmarkManager
from .management_orchestrator import ManagementOrchestrator
from .shared import BookmarkManagerConfig
from .shared import BookmarkManagerException
from .shared import BookmarkRecord
from .shared import BookmarkType
from .shared import CacheManager
from .shared import ConfigValidator
from .shared import ManagementConfig
from .shared import StatisticsCalculator
from .shared import TokenManagerConfig
from .shared import TokenManagerException
from .shared import TokenUsageRecord
from .shared import TokenUsageType
from .token import TokenManager


__all__ = [
    # Main orchestrator
    "ManagementOrchestrator",
    # Individual managers
    "TokenManager",
    "BookmarkManager",
    # Configuration classes
    "ManagementConfig",
    "TokenManagerConfig",
    "BookmarkManagerConfig",
    # Data models
    "TokenUsageRecord",
    "BookmarkRecord",
    "TokenUsageType",
    "BookmarkType",
    # Exceptions
    "TokenManagerException",
    "BookmarkManagerException",
    # Utilities
    "ConfigValidator",
    "StatisticsCalculator",
    "CacheManager",
]

# Version info
__version__ = "1.0.0"
__author__ = "OpenChronicle Core Team"
