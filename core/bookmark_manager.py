"""
Bookmark Management System for OpenChronicle.
Handles scene bookmarks and story navigation markers.
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from .database import execute_query, execute_insert, execute_update, init_database

class BookmarkManager:
    """Manages story bookmarks and navigation markers."""
    
    def __init__(self, story_id: str):
        self.story_id = story_id
        init_database(story_id)
    
    def create_bookmark(self, scene_id: str, label: str, description: Optional[str] = None, 
                       bookmark_type: str = "user", metadata: Optional[Dict[str, Any]] = None) -> int:
        """Create a new bookmark."""
        # Validate bookmark type
        valid_types = ["user", "auto", "chapter", "system"]
        if bookmark_type not in valid_types:
            raise ValueError(f"Invalid bookmark type: {bookmark_type}")
        
        # Check for duplicate bookmarks (same scene + label)
        existing = execute_query(self.story_id, '''
            SELECT id FROM bookmarks WHERE scene_id = ? AND label = ?
        ''', (scene_id, label))
        
        if existing:
            raise ValueError(f"Bookmark with label '{label}' already exists for scene {scene_id}")
        
        # Create the bookmark
        metadata_json = json.dumps(metadata or {})
        
        cursor = execute_insert(self.story_id, '''
            INSERT INTO bookmarks (story_id, scene_id, label, description, bookmark_type, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (self.story_id, scene_id, label, description, bookmark_type, metadata_json))
        
        if cursor is None:
            raise RuntimeError("Failed to create bookmark")
        
        return cursor
    
    def get_bookmark(self, bookmark_id: int) -> Optional[Dict[str, Any]]:
        """Get a bookmark by ID."""
        rows = execute_query(self.story_id, '''
            SELECT id, story_id, scene_id, label, description, bookmark_type, created_at, metadata
            FROM bookmarks WHERE id = ?
        ''', (bookmark_id,))
        
        if not rows:
            return None
        
        return self._format_bookmark(rows[0])
    
    def list_bookmarks(self, bookmark_type: Optional[str] = None, scene_id: Optional[str] = None, 
                      limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List bookmarks with optional filtering."""
        query = '''
            SELECT id, story_id, scene_id, label, description, bookmark_type, created_at, metadata
            FROM bookmarks WHERE story_id = ?
        '''
        params: List[Union[str, int]] = [self.story_id]
        
        if bookmark_type:
            query += ' AND bookmark_type = ?'
            params.append(bookmark_type)
        
        if scene_id:
            query += ' AND scene_id = ?'
            params.append(scene_id)
        
        query += ' ORDER BY created_at DESC'
        
        if limit:
            query += ' LIMIT ?'
            params.append(limit)
        
        rows = execute_query(self.story_id, query, params)
        return [self._format_bookmark(row) for row in rows]
    
    def update_bookmark(self, bookmark_id: int, label: Optional[str] = None, description: Optional[str] = None, 
                       bookmark_type: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Update an existing bookmark."""
        # Get current bookmark
        current = self.get_bookmark(bookmark_id)
        if not current:
            return False
        
        # Prepare update values
        updates = []
        params = []
        
        if label is not None:
            updates.append('label = ?')
            params.append(label)
        
        if description is not None:
            updates.append('description = ?')
            params.append(description)
        
        if bookmark_type is not None:
            valid_types = ["user", "auto", "chapter", "system"]
            if bookmark_type not in valid_types:
                raise ValueError(f"Invalid bookmark type: {bookmark_type}")
            updates.append('bookmark_type = ?')
            params.append(bookmark_type)
        
        if metadata is not None:
            updates.append('metadata = ?')
            params.append(json.dumps(metadata))
        
        if not updates:
            return False
        
        # Execute update
        params.append(bookmark_id)
        rowcount = execute_update(self.story_id, f'''
            UPDATE bookmarks SET {', '.join(updates)} WHERE id = ?
        ''', params)
        
        return rowcount > 0
    
    def delete_bookmark(self, bookmark_id: int) -> bool:
        """Delete a bookmark by ID."""
        rowcount = execute_update(self.story_id, '''
            DELETE FROM bookmarks WHERE id = ?
        ''', (bookmark_id,))
        
        return rowcount > 0
    
    def delete_bookmarks_for_scene(self, scene_id: str) -> int:
        """Delete all bookmarks for a specific scene."""
        rowcount = execute_update(self.story_id, '''
            DELETE FROM bookmarks WHERE scene_id = ?
        ''', (scene_id,))
        
        return rowcount
    
    def search_bookmarks(self, query: str, bookmark_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search bookmarks by label or description."""
        search_query = '''
            SELECT id, story_id, scene_id, label, description, bookmark_type, created_at, metadata
            FROM bookmarks WHERE story_id = ? AND (label LIKE ? OR description LIKE ?)
        '''
        params = [self.story_id, f'%{query}%', f'%{query}%']
        
        if bookmark_type:
            search_query += ' AND bookmark_type = ?'
            params.append(bookmark_type)
        
        search_query += ' ORDER BY created_at DESC'
        
        rows = execute_query(self.story_id, search_query, params)
        return [self._format_bookmark(row) for row in rows]
    
    def get_bookmarks_with_scenes(self, bookmark_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get bookmarks with their associated scene information."""
        query = '''
            SELECT b.id, b.story_id, b.scene_id, b.label, b.description, b.bookmark_type, 
                   b.created_at, b.metadata, s.timestamp, s.input, s.output
            FROM bookmarks b
            JOIN scenes s ON b.scene_id = s.scene_id
            WHERE b.story_id = ?
        '''
        params = [self.story_id]
        
        if bookmark_type:
            query += ' AND b.bookmark_type = ?'
            params.append(bookmark_type)
        
        query += ' ORDER BY b.created_at DESC'
        
        rows = execute_query(self.story_id, query, params)
        return [{
            'id': row['id'],
            'story_id': row['story_id'],
            'scene_id': row['scene_id'],
            'label': row['label'],
            'description': row['description'],
            'bookmark_type': row['bookmark_type'],
            'created_at': row['created_at'],
            'metadata': json.loads(row['metadata'] or '{}'),
            'scene_timestamp': row['timestamp'],
            'scene_input': row['input'],
            'scene_output': row['output']
        } for row in rows]
    
    def auto_create_chapter_bookmark(self, scene_id: str, chapter_title: str, 
                                   chapter_level: int = 1) -> int:
        """Automatically create a chapter bookmark."""
        metadata = {
            'chapter_level': chapter_level,
            'auto_generated': True,
            'created_by': 'chapter_tracker'
        }
        
        return self.create_bookmark(
            scene_id=scene_id,
            label=chapter_title,
            description=f"Auto-generated chapter bookmark: {chapter_title}",
            bookmark_type="chapter",
            metadata=metadata
        )
    
    def get_chapter_bookmarks(self) -> List[Dict[str, Any]]:
        """Get all chapter bookmarks in chronological order."""
        return self.list_bookmarks(bookmark_type="chapter")
    
    def get_timeline_bookmarks(self) -> List[Dict[str, Any]]:
        """Get all bookmarks with scene information for timeline building."""
        return self.get_bookmarks_with_scenes()
    
    def get_chapter_structure(self) -> Dict[int, List[Dict[str, Any]]]:
        """Get chapter structure from bookmarks organized by levels."""
        chapter_bookmarks = self.get_chapter_bookmarks()
        
        # Group chapters by level
        chapters_by_level = {}
        
        for bookmark in chapter_bookmarks:
            chapter_level = bookmark['metadata'].get('chapter_level', 1)
            if chapter_level not in chapters_by_level:
                chapters_by_level[chapter_level] = []
            chapters_by_level[chapter_level].append(bookmark)
        
        return chapters_by_level
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bookmark statistics."""
        # Total bookmarks
        total_rows = execute_query(self.story_id, '''
            SELECT COUNT(*) as count FROM bookmarks WHERE story_id = ?
        ''', (self.story_id,))
        total_bookmarks = total_rows[0]['count']
        
        # Bookmarks by type
        type_rows = execute_query(self.story_id, '''
            SELECT bookmark_type, COUNT(*) as count 
            FROM bookmarks WHERE story_id = ? 
            GROUP BY bookmark_type
        ''', (self.story_id,))
        
        by_type = {row['bookmark_type']: row['count'] for row in type_rows}
        
        # Recent bookmarks
        recent_rows = execute_query(self.story_id, '''
            SELECT id, label, bookmark_type, created_at
            FROM bookmarks WHERE story_id = ?
            ORDER BY created_at DESC LIMIT 5
        ''', (self.story_id,))
        
        recent_bookmarks = [{
            'id': row['id'],
            'label': row['label'],
            'bookmark_type': row['bookmark_type'],
            'created_at': row['created_at']
        } for row in recent_rows]
        
        return {
            'total_bookmarks': total_bookmarks,
            'by_type': by_type,
            'recent_bookmarks': recent_bookmarks
        }
    
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