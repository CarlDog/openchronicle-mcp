"""
Bookmark Management - Navigation Manager

Extracted from bookmark_manager.py
Handles chapter structure, timeline navigation, and story organization.
"""

import json
import sys
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

# Add utilities to path for logging system
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "utilities"))
from logging_system import log_system_event, log_info, log_warning

from ..shared import BookmarkRecord, BookmarkType, BookmarkManagerException


class NavigationManager:
    """Manages story navigation, chapters, and timeline structure."""
    
    def __init__(self, story_id: str):
        self.story_id = story_id
        # Import database utilities with fallback
        try:
            from core.database import execute_query
            self.execute_query = execute_query
        except ImportError:
            # Fallback for testing
            self.execute_query = self._mock_execute_query
    
    def _mock_execute_query(self, *args, **kwargs):
        """Mock query function for testing."""
        return []
    
    def auto_create_chapter_bookmark(self, scene_id: str, chapter_title: str,
                                   chapter_level: int = 1, data_manager=None) -> int:
        """Automatically create a chapter bookmark."""
        if not data_manager:
            raise BookmarkManagerException("BookmarkDataManager required for chapter creation")
        
        try:
            metadata = {
                'chapter_level': chapter_level,
                'auto_generated': True,
                'created_by': 'chapter_tracker',
                'navigation_type': 'chapter'
            }
            
            bookmark_id = data_manager.create_bookmark(
                scene_id=scene_id,
                label=chapter_title,
                description=f"Auto-generated chapter bookmark: {chapter_title}",
                bookmark_type=BookmarkType.CHAPTER,
                metadata=metadata
            )
            
            log_system_event("auto_chapter_created", 
                           f"Created chapter bookmark '{chapter_title}' at level {chapter_level}")
            
            return bookmark_id
            
        except Exception as e:
            log_warning(f"Failed to create auto chapter bookmark: {e}")
            raise BookmarkManagerException(f"Auto chapter creation failed: {e}")
    
    def get_chapter_bookmarks(self) -> List[Dict[str, Any]]:
        """Get all chapter bookmarks in chronological order."""
        try:
            rows = self.execute_query(self.story_id, '''
                SELECT id, story_id, scene_id, label, description, bookmark_type, created_at, metadata
                FROM bookmarks WHERE story_id = ? AND bookmark_type = ?
                ORDER BY created_at ASC
            ''', (self.story_id, BookmarkType.CHAPTER.value))
            
            return [self._format_bookmark(row) for row in rows]
            
        except Exception as e:
            log_warning(f"Failed to get chapter bookmarks: {e}")
            return []
    
    def get_timeline_bookmarks(self) -> List[Dict[str, Any]]:
        """Get all bookmarks with scene information for timeline building."""
        try:
            query = '''
                SELECT b.id, b.story_id, b.scene_id, b.label, b.description, b.bookmark_type, 
                       b.created_at, b.metadata, s.timestamp, s.input, s.output
                FROM bookmarks b
                JOIN scenes s ON b.scene_id = s.scene_id
                WHERE b.story_id = ?
                ORDER BY s.timestamp ASC
            '''
            
            rows = self.execute_query(self.story_id, query, (self.story_id,))
            
            timeline = []
            for row in rows:
                timeline.append({
                    'id': row['id'],
                    'story_id': row['story_id'],
                    'scene_id': row['scene_id'],
                    'label': row['label'],
                    'description': row['description'],
                    'bookmark_type': row['bookmark_type'],
                    'bookmark_created_at': row['created_at'],
                    'metadata': json.loads(row['metadata'] or '{}'),
                    'scene_timestamp': row['timestamp'],
                    'scene_input': row['input'],
                    'scene_output': row['output'],
                    'timeline_position': len(timeline) + 1
                })
            
            log_system_event("timeline_generated", f"Generated timeline with {len(timeline)} bookmarks")
            
            return timeline
            
        except Exception as e:
            log_warning(f"Failed to get timeline bookmarks: {e}")
            return []
    
    def get_chapter_structure(self) -> Dict[int, List[Dict[str, Any]]]:
        """Get chapter structure from bookmarks organized by levels."""
        try:
            chapter_bookmarks = self.get_chapter_bookmarks()
            
            # Group chapters by level
            chapters_by_level = {}
            
            for bookmark in chapter_bookmarks:
                chapter_level = bookmark['metadata'].get('chapter_level', 1)
                if chapter_level not in chapters_by_level:
                    chapters_by_level[chapter_level] = []
                chapters_by_level[chapter_level].append(bookmark)
            
            # Sort each level by creation time
            for level in chapters_by_level:
                chapters_by_level[level].sort(key=lambda x: x['created_at'])
            
            log_system_event("chapter_structure_built", 
                           f"Built structure with {len(chapters_by_level)} levels")
            
            return chapters_by_level
            
        except Exception as e:
            log_warning(f"Failed to get chapter structure: {e}")
            return {}
    
    def get_navigation_hierarchy(self) -> Dict[str, Any]:
        """Get complete navigation hierarchy including chapters, sections, and bookmarks."""
        try:
            structure = self.get_chapter_structure()
            timeline = self.get_timeline_bookmarks()
            
            hierarchy = {
                'chapters': structure,
                'timeline': timeline,
                'navigation_stats': self._calculate_navigation_stats(structure, timeline),
                'quick_links': self._generate_quick_links(timeline)
            }
            
            return hierarchy
            
        except Exception as e:
            log_warning(f"Failed to build navigation hierarchy: {e}")
            return {'chapters': {}, 'timeline': [], 'navigation_stats': {}, 'quick_links': []}
    
    def find_next_bookmark(self, current_scene_id: str) -> Optional[Dict[str, Any]]:
        """Find the next bookmark in the timeline after the current scene."""
        try:
            timeline = self.get_timeline_bookmarks()
            
            # Find current position
            current_index = None
            for i, bookmark in enumerate(timeline):
                if bookmark['scene_id'] == current_scene_id:
                    current_index = i
                    break
            
            # Return next bookmark if found
            if current_index is not None and current_index + 1 < len(timeline):
                return timeline[current_index + 1]
            
            return None
            
        except Exception as e:
            log_warning(f"Failed to find next bookmark: {e}")
            return None
    
    def find_previous_bookmark(self, current_scene_id: str) -> Optional[Dict[str, Any]]:
        """Find the previous bookmark in the timeline before the current scene."""
        try:
            timeline = self.get_timeline_bookmarks()
            
            # Find current position
            current_index = None
            for i, bookmark in enumerate(timeline):
                if bookmark['scene_id'] == current_scene_id:
                    current_index = i
                    break
            
            # Return previous bookmark if found
            if current_index is not None and current_index > 0:
                return timeline[current_index - 1]
            
            return None
            
        except Exception as e:
            log_warning(f"Failed to find previous bookmark: {e}")
            return None
    
    def get_chapter_for_scene(self, scene_id: str) -> Optional[Dict[str, Any]]:
        """Find which chapter a scene belongs to."""
        try:
            timeline = self.get_timeline_bookmarks()
            
            # Find the scene and work backwards to find the most recent chapter bookmark
            scene_position = None
            for i, bookmark in enumerate(timeline):
                if bookmark['scene_id'] == scene_id:
                    scene_position = i
                    break
            
            if scene_position is None:
                return None
            
            # Work backwards to find the most recent chapter bookmark
            for i in range(scene_position, -1, -1):
                bookmark = timeline[i]
                if bookmark['bookmark_type'] == BookmarkType.CHAPTER.value:
                    return bookmark
            
            return None
            
        except Exception as e:
            log_warning(f"Failed to find chapter for scene: {e}")
            return None
    
    def organize_by_chapters(self) -> Dict[str, List[Dict[str, Any]]]:
        """Organize all bookmarks by their chapter associations."""
        try:
            timeline = self.get_timeline_bookmarks()
            organized = {}
            current_chapter = "Uncategorized"
            
            for bookmark in timeline:
                # If this is a chapter bookmark, update current chapter
                if bookmark['bookmark_type'] == BookmarkType.CHAPTER.value:
                    current_chapter = bookmark['label']
                    if current_chapter not in organized:
                        organized[current_chapter] = []
                    organized[current_chapter].append(bookmark)
                else:
                    # Add to current chapter
                    if current_chapter not in organized:
                        organized[current_chapter] = []
                    organized[current_chapter].append(bookmark)
            
            return organized
            
        except Exception as e:
            log_warning(f"Failed to organize by chapters: {e}")
            return {}
    
    def _calculate_navigation_stats(self, chapters: Dict[int, List[Dict[str, Any]]],
                                  timeline: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate navigation statistics."""
        total_chapters = sum(len(level_chapters) for level_chapters in chapters.values())
        total_bookmarks = len(timeline)
        
        # Count bookmark types in timeline
        type_counts = {}
        for bookmark in timeline:
            bookmark_type = bookmark['bookmark_type']
            type_counts[bookmark_type] = type_counts.get(bookmark_type, 0) + 1
        
        return {
            'total_chapters': total_chapters,
            'total_bookmarks': total_bookmarks,
            'chapter_levels': len(chapters),
            'bookmark_types': type_counts,
            'average_bookmarks_per_chapter': total_bookmarks / max(total_chapters, 1)
        }
    
    def _generate_quick_links(self, timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate quick navigation links."""
        quick_links = []
        
        # Add first bookmark
        if timeline:
            quick_links.append({
                'type': 'first',
                'label': 'Beginning',
                'bookmark': timeline[0]
            })
        
        # Add chapter bookmarks as quick links
        chapter_bookmarks = [b for b in timeline if b['bookmark_type'] == BookmarkType.CHAPTER.value]
        for chapter in chapter_bookmarks[-5:]:  # Last 5 chapters
            quick_links.append({
                'type': 'chapter',
                'label': chapter['label'],
                'bookmark': chapter
            })
        
        # Add last bookmark
        if timeline and len(timeline) > 1:
            quick_links.append({
                'type': 'last',
                'label': 'Latest',
                'bookmark': timeline[-1]
            })
        
        return quick_links
    
    def _format_bookmark(self, row) -> Dict[str, Any]:
        """Format a bookmark row into a dictionary."""
        return {
            'id': row['id'],
            'story_id': row['story_id'],
            'scene_id': row['scene_id'],
            'label': row['label'],
            'description': row['description'],
            'bookmark_type': row['bookmark_type'],
            'created_at': row['created_at'],
            'metadata': json.loads(row['metadata'] or '{}')
        }
