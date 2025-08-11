"""
Bookmark Management System

Modular bookmark management for OpenChronicle Core.
Provides bookmark CRUD, search, and navigation capabilities.
"""

from .bookmark_manager import BookmarkManager
from .bookmark_data_manager import BookmarkDataManager, BookmarkValidator
from .search_engine import BookmarkSearchEngine
from .navigation_manager import NavigationManager

__all__ = [
    "BookmarkManager",
    "BookmarkDataManager",
    "BookmarkValidator",
    "BookmarkSearchEngine",
    "NavigationManager",
]
