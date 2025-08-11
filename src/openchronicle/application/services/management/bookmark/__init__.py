"""
Bookmark Management System

Modular bookmark management for OpenChronicle Core.
Provides bookmark CRUD, search, and navigation capabilities.
"""

from .bookmark_data_manager import BookmarkDataManager
from .bookmark_data_manager import BookmarkValidator
from .bookmark_manager import BookmarkManager
from .navigation_manager import NavigationManager
from .search_engine import BookmarkSearchEngine


__all__ = [
    "BookmarkDataManager",
    "BookmarkManager",
    "BookmarkSearchEngine",
    "BookmarkValidator",
    "NavigationManager",
]
