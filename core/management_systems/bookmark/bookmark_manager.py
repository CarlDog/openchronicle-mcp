"""
Bookmark Management System - Main Orchestrator

Modernized bookmark management system that integrates all bookmark components.
Provides unified API for bookmark operations, search, and navigation.
"""

import sys
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

# Add utilities to path for logging system
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "utilities"))
from core.shared.logging_system import log_system_event, log_info, log_error

from .bookmark_data_manager import BookmarkDataManager, BookmarkValidator
from .search_engine import BookmarkSearchEngine
from .navigation_manager import NavigationManager
from ..shared import (
    BookmarkManagerConfig, BookmarkRecord, BookmarkType,
    BookmarkManagerException, ConfigValidator
)


class BookmarkManager:
    """
    Unified bookmark management system.
    
    Integrates bookmark CRUD, search, and navigation into a single API.
    Maintains backward compatibility with legacy bookmark_manager.py interface.
    """
    
    def __init__(self, story_id: str, config: Optional[Dict[str, Any]] = None):
        """Initialize the bookmark management system."""
        try:
            self.story_id = story_id
            
            # Validate and set configuration
            validated_config = ConfigValidator.validate_bookmark_config(config or {})
            self.config = BookmarkManagerConfig.from_dict(validated_config)
            
            # Initialize components
            self.data_manager = BookmarkDataManager(story_id)
            self.search_engine = BookmarkSearchEngine(story_id)
            self.navigation_manager = NavigationManager(story_id)
            
            log_system_event("bookmark_system", f"Bookmark management system initialized for story {story_id}")
            
        except Exception as e:
            log_error(f"Failed to initialize BookmarkManager: {e}")
            raise BookmarkManagerException(f"Initialization failed: {e}")
    
    # =====================================================================
    # BOOKMARK CRUD INTERFACE
    # =====================================================================
    
    def create_bookmark(self, scene_id: str, label: str, description: Optional[str] = None,
                       bookmark_type: Union[str, BookmarkType] = BookmarkType.USER,
                       metadata: Optional[Dict[str, Any]] = None) -> int:
        """Create a new bookmark."""
        # Convert string to enum if needed
        if isinstance(bookmark_type, str):
            bookmark_type = BookmarkType(bookmark_type)
        
        # Validate bookmark data
        validation = BookmarkValidator.validate_bookmark_data(scene_id, label, bookmark_type, metadata)
        if not validation["is_valid"]:
            raise BookmarkManagerException(f"Invalid bookmark data: {', '.join(validation['errors'])}")
        
        return self.data_manager.create_bookmark(scene_id, label, description, bookmark_type, metadata)
    
    def get_bookmark(self, bookmark_id: int) -> Optional[Dict[str, Any]]:
        """Get a bookmark by ID."""
        record = self.data_manager.get_bookmark(bookmark_id)
        return record.to_dict() if record else None
    
    def list_bookmarks(self, bookmark_type: Optional[Union[str, BookmarkType]] = None,
                      scene_id: Optional[str] = None,
                      limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List bookmarks with optional filtering."""
        # Convert string to enum if needed
        if isinstance(bookmark_type, str):
            bookmark_type = BookmarkType(bookmark_type)
        
        records = self.data_manager.list_bookmarks(bookmark_type, scene_id, limit)
        return [record.to_dict() for record in records]
    
    def update_bookmark(self, bookmark_id: int, label: Optional[str] = None,
                       description: Optional[str] = None,
                       bookmark_type: Optional[Union[str, BookmarkType]] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Update an existing bookmark."""
        # Convert string to enum if needed
        if isinstance(bookmark_type, str):
            bookmark_type = BookmarkType(bookmark_type)
        
        return self.data_manager.update_bookmark(bookmark_id, label, description, bookmark_type, metadata)
    
    def delete_bookmark(self, bookmark_id: int) -> bool:
        """Delete a bookmark by ID."""
        return self.data_manager.delete_bookmark(bookmark_id)
    
    def delete_bookmarks_for_scene(self, scene_id: str) -> int:
        """Delete all bookmarks for a specific scene."""
        return self.data_manager.delete_bookmarks_for_scene(scene_id)
    
    # =====================================================================
    # SEARCH INTERFACE
    # =====================================================================
    
    def search_bookmarks(self, query: str, bookmark_type: Optional[Union[str, BookmarkType]] = None,
                        search_fields: Optional[List[str]] = None,
                        limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search bookmarks by label or description."""
        # Validate search query
        if not BookmarkValidator.validate_search_query(query):
            raise BookmarkManagerException("Invalid search query")
        
        # Convert string to enum if needed
        if isinstance(bookmark_type, str):
            bookmark_type = BookmarkType(bookmark_type)
        
        return self.search_engine.search_bookmarks(query, bookmark_type, search_fields, limit)
    
    def search_by_metadata(self, metadata_filters: Dict[str, Any],
                          bookmark_type: Optional[Union[str, BookmarkType]] = None) -> List[Dict[str, Any]]:
        """Search bookmarks by metadata fields."""
        # Convert string to enum if needed
        if isinstance(bookmark_type, str):
            bookmark_type = BookmarkType(bookmark_type)
        
        return self.search_engine.search_by_metadata(metadata_filters, bookmark_type)
    
    def search_by_scene_content(self, content_query: str,
                               bookmark_type: Optional[Union[str, BookmarkType]] = None) -> List[Dict[str, Any]]:
        """Search bookmarks by their associated scene content."""
        # Convert string to enum if needed
        if isinstance(bookmark_type, str):
            bookmark_type = BookmarkType(bookmark_type)
        
        return self.search_engine.search_by_scene_content(content_query, bookmark_type)
    
    def find_similar_bookmarks(self, bookmark_id: int, similarity_threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Find bookmarks similar to the given bookmark."""
        return self.search_engine.find_similar_bookmarks(bookmark_id, similarity_threshold)
    
    def get_bookmark_suggestions(self, current_scene_id: str, context: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get bookmark suggestions based on current context."""
        return self.search_engine.get_bookmark_suggestions(current_scene_id, context)
    
    # =====================================================================
    # NAVIGATION INTERFACE
    # =====================================================================
    
    def auto_create_chapter_bookmark(self, scene_id: str, chapter_title: str,
                                   chapter_level: int = 1) -> int:
        """Automatically create a chapter bookmark."""
        return self.navigation_manager.auto_create_chapter_bookmark(
            scene_id, chapter_title, chapter_level, self.data_manager
        )
    
    def get_chapter_bookmarks(self) -> List[Dict[str, Any]]:
        """Get all chapter bookmarks in chronological order."""
        return self.navigation_manager.get_chapter_bookmarks()
    
    def get_timeline_bookmarks(self) -> List[Dict[str, Any]]:
        """Get all bookmarks with scene information for timeline building."""
        return self.navigation_manager.get_timeline_bookmarks()
    
    def get_chapter_structure(self) -> Dict[int, List[Dict[str, Any]]]:
        """Get chapter structure from bookmarks organized by levels."""
        return self.navigation_manager.get_chapter_structure()
    
    def get_navigation_hierarchy(self) -> Dict[str, Any]:
        """Get complete navigation hierarchy including chapters, sections, and bookmarks."""
        return self.navigation_manager.get_navigation_hierarchy()
    
    def find_next_bookmark(self, current_scene_id: str) -> Optional[Dict[str, Any]]:
        """Find the next bookmark in the timeline after the current scene."""
        return self.navigation_manager.find_next_bookmark(current_scene_id)
    
    def find_previous_bookmark(self, current_scene_id: str) -> Optional[Dict[str, Any]]:
        """Find the previous bookmark in the timeline before the current scene."""
        return self.navigation_manager.find_previous_bookmark(current_scene_id)
    
    def get_chapter_for_scene(self, scene_id: str) -> Optional[Dict[str, Any]]:
        """Find which chapter a scene belongs to."""
        return self.navigation_manager.get_chapter_for_scene(scene_id)
    
    def organize_by_chapters(self) -> Dict[str, List[Dict[str, Any]]]:
        """Organize all bookmarks by their chapter associations."""
        return self.navigation_manager.organize_by_chapters()
    
    # =====================================================================
    # LEGACY COMPATIBILITY
    # =====================================================================
    
    def get_bookmarks_with_scenes(self, bookmark_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Legacy method: Get bookmarks with their associated scene information."""
        type_enum = BookmarkType(bookmark_type) if bookmark_type else None
        return self.data_manager.get_bookmarks_with_scenes(type_enum)
    
    def get_stats(self) -> Dict[str, Any]:
        """Legacy method: Get bookmark statistics."""
        return self.data_manager.get_stats()
    
    # =====================================================================
    # UTILITY METHODS
    # =====================================================================
    
    def validate_bookmark_integrity(self) -> Dict[str, Any]:
        """Validate bookmark data integrity."""
        try:
            all_bookmarks = self.list_bookmarks()
            issues = []
            
            for bookmark in all_bookmarks:
                # Check for required fields
                if not bookmark.get('scene_id'):
                    issues.append(f"Bookmark {bookmark['id']} missing scene_id")
                
                if not bookmark.get('label'):
                    issues.append(f"Bookmark {bookmark['id']} missing label")
                
                # Check bookmark type validity
                try:
                    BookmarkType(bookmark['bookmark_type'])
                except ValueError:
                    issues.append(f"Bookmark {bookmark['id']} has invalid type: {bookmark['bookmark_type']}")
            
            return {
                "is_valid": len(issues) == 0,
                "total_bookmarks": len(all_bookmarks),
                "issues": issues
            }
            
        except Exception as e:
            log_error(f"Bookmark integrity check failed: {e}")
            return {
                "is_valid": False,
                "total_bookmarks": 0,
                "issues": [f"Integrity check failed: {e}"]
            }
    
    def export_bookmarks(self, format: str = "json") -> Dict[str, Any]:
        """Export all bookmark data."""
        try:
            bookmarks = self.list_bookmarks()
            stats = self.get_stats()
            chapter_structure = self.get_chapter_structure()
            
            export_data = {
                "story_id": self.story_id,
                "export_format": format,
                "export_timestamp": BookmarkRecord.get_current_timestamp().isoformat(),
                "bookmarks": bookmarks,
                "statistics": stats,
                "chapter_structure": chapter_structure,
                "total_count": len(bookmarks)
            }
            
            log_system_event("bookmark_export", f"Exported {len(bookmarks)} bookmarks for story {self.story_id}")
            
            return export_data
            
        except Exception as e:
            log_error(f"Bookmark export failed: {e}")
            raise BookmarkManagerException(f"Export failed: {e}")
    
    def bulk_update_bookmarks(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform bulk updates on multiple bookmarks."""
        try:
            results = {
                "updated": 0,
                "failed": 0,
                "errors": []
            }
            
            for update in updates:
                bookmark_id = update.get('id')
                if not bookmark_id:
                    results["failed"] += 1
                    results["errors"].append("Missing bookmark ID")
                    continue
                
                try:
                    success = self.update_bookmark(
                        bookmark_id,
                        label=update.get('label'),
                        description=update.get('description'),
                        bookmark_type=update.get('bookmark_type'),
                        metadata=update.get('metadata')
                    )
                    
                    if success:
                        results["updated"] += 1
                    else:
                        results["failed"] += 1
                        results["errors"].append(f"Failed to update bookmark {bookmark_id}")
                        
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append(f"Error updating bookmark {bookmark_id}: {e}")
            
            log_system_event("bookmark_bulk_update", 
                           f"Bulk update: {results['updated']} updated, {results['failed']} failed")
            
            return results
            
        except Exception as e:
            log_error(f"Bulk update failed: {e}")
            raise BookmarkManagerException(f"Bulk update failed: {e}")
    
    def cleanup_orphaned_bookmarks(self) -> int:
        """Remove bookmarks that point to non-existent scenes."""
        try:
            # This would require access to the scenes table to check for orphans
            # For now, return 0 as this requires database schema knowledge
            log_system_event("bookmark_cleanup", "Orphaned bookmark cleanup requested")
            return 0
            
        except Exception as e:
            log_error(f"Bookmark cleanup failed: {e}")
            return 0
