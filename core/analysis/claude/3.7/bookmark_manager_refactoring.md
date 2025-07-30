# Bookmark Manager Refactoring Recommendation

## Current Module Overview

**File**: `core/bookmark_manager.py` (276 lines)  
**Purpose**: Manages story bookmarks and navigation markers for scene organization and retrieval.

**Key Components**:
1. **BookmarkManager Class** - Main class handling bookmark operations
2. **Bookmark CRUD Operations** - Methods to create, read, update, and delete bookmarks
3. **Search & Filtering** - Methods to search and filter bookmarks
4. **Chapter Management** - Functions for handling chapter-specific bookmarks
5. **Statistics & Reporting** - Functions to generate bookmark statistics

**Current Responsibilities**:
- Creating and managing bookmarks for scenes
- Validating bookmark types and preventing duplicates
- Searching and filtering bookmarks
- Retrieving bookmarks with associated scene information
- Automatically generating chapter bookmarks
- Providing chapter structure and organization
- Tracking bookmark statistics

## Issues Identified

1. **Database Coupling**: Direct coupling with database module for all operations
2. **Limited Error Handling**: Basic error handling with minimal recovery mechanisms
3. **Lack of Data Models**: No clear data models for bookmarks
4. **Limited Validation**: Basic validation without comprehensive rules
5. **Missing Events/Signals**: No event notification for bookmark changes
6. **Basic Querying**: Simple querying without advanced options like pagination or sorting
7. **Lack of Caching**: No caching mechanism for frequently accessed bookmarks

## Refactoring Recommendations

### 1. Convert to Package Structure

Transform the file into a structured package:

```
core/
  bookmarks/
    __init__.py              # Public API
    manager.py               # Main manager class
    models.py                # Data models
    repository.py            # Data access layer
    validators.py            # Validation utilities
    events.py                # Event system
    chapters.py              # Chapter-specific functionality
    stats.py                 # Statistics utilities
    exceptions.py            # Custom exceptions
```

### 2. Implement Data Models

Create proper data models for bookmarks:

```python
# models.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional

@dataclass
class Bookmark:
    """Represents a story bookmark."""
    scene_id: str
    label: str
    bookmark_type: str
    story_id: str
    description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Bookmark':
        """Create a bookmark from a dictionary."""
        bookmark = cls(
            id=data.get('id'),
            story_id=data['story_id'],
            scene_id=data['scene_id'],
            label=data['label'],
            description=data.get('description'),
            bookmark_type=data['bookmark_type'],
            metadata=data.get('metadata', {})
        )
        
        if 'created_at' in data and data['created_at']:
            bookmark.created_at = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
        
        return bookmark
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert bookmark to a dictionary."""
        result = {
            'scene_id': self.scene_id,
            'label': self.label,
            'bookmark_type': self.bookmark_type,
            'story_id': self.story_id
        }
        
        if self.id is not None:
            result['id'] = self.id
        
        if self.description:
            result['description'] = self.description
            
        if self.metadata:
            result['metadata'] = self.metadata
            
        if self.created_at:
            result['created_at'] = self.created_at.isoformat()
            
        return result


@dataclass
class BookmarkWithScene(Bookmark):
    """Bookmark with associated scene information."""
    scene_timestamp: Optional[str] = None
    scene_input: Optional[str] = None
    scene_output: Optional[str] = None
    
    @classmethod
    def from_bookmark(cls, bookmark: Bookmark, scene_data: Dict[str, Any]) -> 'BookmarkWithScene':
        """Create a BookmarkWithScene from a Bookmark and scene data."""
        return cls(
            id=bookmark.id,
            story_id=bookmark.story_id,
            scene_id=bookmark.scene_id,
            label=bookmark.label,
            description=bookmark.description,
            bookmark_type=bookmark.bookmark_type,
            metadata=bookmark.metadata,
            created_at=bookmark.created_at,
            scene_timestamp=scene_data.get('timestamp'),
            scene_input=scene_data.get('input'),
            scene_output=scene_data.get('output')
        )


@dataclass
class ChapterBookmark(Bookmark):
    """Specialized bookmark for chapters."""
    chapter_level: int = 1
    auto_generated: bool = False
    
    @classmethod
    def from_bookmark(cls, bookmark: Bookmark) -> 'ChapterBookmark':
        """Create a ChapterBookmark from a Bookmark."""
        metadata = bookmark.metadata or {}
        return cls(
            id=bookmark.id,
            story_id=bookmark.story_id,
            scene_id=bookmark.scene_id,
            label=bookmark.label,
            description=bookmark.description,
            bookmark_type="chapter",
            metadata=metadata,
            created_at=bookmark.created_at,
            chapter_level=metadata.get('chapter_level', 1),
            auto_generated=metadata.get('auto_generated', False)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert chapter bookmark to a dictionary."""
        result = super().to_dict()
        result['chapter_level'] = self.chapter_level
        result['auto_generated'] = self.auto_generated
        return result
```

### 3. Create Repository Layer

Implement a dedicated repository for data access:

```python
# repository.py
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple

from .models import Bookmark, BookmarkWithScene, ChapterBookmark
from .exceptions import BookmarkError
from ..database import execute_query, execute_insert, execute_update, init_database

class BookmarkRepository:
    """Data access layer for bookmarks."""
    
    def __init__(self, story_id: str):
        """Initialize with story ID."""
        self.story_id = story_id
        init_database(story_id)
    
    def create(self, bookmark: Bookmark) -> int:
        """Create a new bookmark."""
        metadata_json = json.dumps(bookmark.metadata or {})
        
        cursor = execute_insert(self.story_id, '''
            INSERT INTO bookmarks (story_id, scene_id, label, description, bookmark_type, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            self.story_id,
            bookmark.scene_id,
            bookmark.label,
            bookmark.description,
            bookmark.bookmark_type,
            metadata_json
        ))
        
        return cursor
    
    def get_by_id(self, bookmark_id: int) -> Optional[Bookmark]:
        """Get a bookmark by ID."""
        rows = execute_query(self.story_id, '''
            SELECT id, story_id, scene_id, label, description, bookmark_type, created_at, metadata
            FROM bookmarks WHERE id = ?
        ''', (bookmark_id,))
        
        if not rows:
            return None
        
        return self._row_to_bookmark(rows[0])
    
    def get_by_scene_and_label(self, scene_id: str, label: str) -> Optional[Bookmark]:
        """Get a bookmark by scene ID and label."""
        rows = execute_query(self.story_id, '''
            SELECT id, story_id, scene_id, label, description, bookmark_type, created_at, metadata
            FROM bookmarks WHERE scene_id = ? AND label = ?
        ''', (scene_id, label))
        
        if not rows:
            return None
        
        return self._row_to_bookmark(rows[0])
    
    def list(self, bookmark_type: Optional[str] = None, scene_id: Optional[str] = None, 
           limit: Optional[int] = None) -> List[Bookmark]:
        """List bookmarks with optional filtering."""
        query = '''
            SELECT id, story_id, scene_id, label, description, bookmark_type, created_at, metadata
            FROM bookmarks WHERE story_id = ?
        '''
        params = [self.story_id]
        
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
        return [self._row_to_bookmark(row) for row in rows]
    
    def update(self, bookmark: Bookmark) -> bool:
        """Update an existing bookmark."""
        if bookmark.id is None:
            raise BookmarkError("Cannot update bookmark without ID")
        
        metadata_json = json.dumps(bookmark.metadata or {})
        
        rowcount = execute_update(self.story_id, '''
            UPDATE bookmarks 
            SET label = ?, description = ?, bookmark_type = ?, metadata = ?
            WHERE id = ?
        ''', (
            bookmark.label,
            bookmark.description,
            bookmark.bookmark_type,
            metadata_json,
            bookmark.id
        ))
        
        return rowcount > 0
    
    def delete(self, bookmark_id: int) -> bool:
        """Delete a bookmark by ID."""
        rowcount = execute_update(self.story_id, '''
            DELETE FROM bookmarks WHERE id = ?
        ''', (bookmark_id,))
        
        return rowcount > 0
    
    def delete_by_scene(self, scene_id: str) -> int:
        """Delete all bookmarks for a specific scene."""
        rowcount = execute_update(self.story_id, '''
            DELETE FROM bookmarks WHERE scene_id = ?
        ''', (scene_id,))
        
        return rowcount
    
    def search(self, query: str, bookmark_type: Optional[str] = None) -> List[Bookmark]:
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
        return [self._row_to_bookmark(row) for row in rows]
    
    def get_with_scenes(self, bookmark_type: Optional[str] = None) -> List[BookmarkWithScene]:
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
        return [self._row_to_bookmark_with_scene(row) for row in rows]
    
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
    
    def _row_to_bookmark(self, row) -> Bookmark:
        """Convert a database row to a Bookmark object."""
        bookmark_type = row['bookmark_type']
        
        # Create basic bookmark
        bookmark = Bookmark(
            id=row['id'],
            story_id=row['story_id'],
            scene_id=row['scene_id'],
            label=row['label'],
            description=row['description'],
            bookmark_type=bookmark_type,
            metadata=json.loads(row['metadata'] or '{}')
        )
        
        if 'created_at' in row and row['created_at']:
            bookmark.created_at = datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
        
        # Convert to specialized bookmark type if needed
        if bookmark_type == 'chapter':
            return ChapterBookmark.from_bookmark(bookmark)
        
        return bookmark
    
    def _row_to_bookmark_with_scene(self, row) -> BookmarkWithScene:
        """Convert a database row to a BookmarkWithScene object."""
        bookmark = self._row_to_bookmark(row)
        
        scene_data = {
            'timestamp': row.get('timestamp'),
            'input': row.get('input'),
            'output': row.get('output')
        }
        
        return BookmarkWithScene.from_bookmark(bookmark, scene_data)
```

### 4. Create Validator Component

Implement a dedicated validator for bookmarks:

```python
# validators.py
from typing import Dict, Any, List, Optional
from .models import Bookmark
from .exceptions import BookmarkValidationError

class BookmarkValidator:
    """Validates bookmark data."""
    
    VALID_TYPES = ["user", "auto", "chapter", "system"]
    
    @classmethod
    def validate_bookmark(cls, bookmark: Bookmark) -> List[str]:
        """Validate a bookmark, returning a list of validation errors."""
        errors = []
        
        # Check required fields
        if not bookmark.scene_id:
            errors.append("Scene ID is required")
        
        if not bookmark.label:
            errors.append("Label is required")
        
        # Check bookmark type
        if bookmark.bookmark_type not in cls.VALID_TYPES:
            errors.append(f"Invalid bookmark type: {bookmark.bookmark_type}")
        
        # Check special rules for chapter bookmarks
        if bookmark.bookmark_type == "chapter":
            if not bookmark.metadata.get("chapter_level"):
                errors.append("Chapter level is required for chapter bookmarks")
        
        return errors
    
    @classmethod
    def validate_or_raise(cls, bookmark: Bookmark) -> None:
        """Validate a bookmark, raising an exception if invalid."""
        errors = cls.validate_bookmark(bookmark)
        
        if errors:
            raise BookmarkValidationError(errors)
```

### 5. Create Events System

Implement an event system for bookmark changes:

```python
# events.py
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
from .models import Bookmark

@dataclass
class BookmarkEvent:
    """Base class for bookmark events."""
    bookmark: Bookmark
    timestamp: datetime = datetime.now()


@dataclass
class BookmarkCreatedEvent(BookmarkEvent):
    """Event raised when a bookmark is created."""
    pass


@dataclass
class BookmarkUpdatedEvent(BookmarkEvent):
    """Event raised when a bookmark is updated."""
    previous_state: Dict[str, Any]


@dataclass
class BookmarkDeletedEvent(BookmarkEvent):
    """Event raised when a bookmark is deleted."""
    pass


class EventEmitter:
    """Simple event emitter for bookmark events."""
    
    def __init__(self):
        """Initialize event emitter."""
        self._handlers = {
            'created': [],
            'updated': [],
            'deleted': []
        }
    
    def on(self, event_type: str, handler: Callable) -> None:
        """Register an event handler."""
        if event_type in self._handlers:
            self._handlers[event_type].append(handler)
    
    def emit(self, event_type: str, event: BookmarkEvent) -> None:
        """Emit an event."""
        if event_type in self._handlers:
            for handler in self._handlers[event_type]:
                try:
                    handler(event)
                except Exception as e:
                    # Log error but don't crash
                    print(f"Error in event handler: {e}")
```

### 6. Create Chapters Module

Implement dedicated functionality for chapter bookmarks:

```python
# chapters.py
from typing import Dict, List, Any, Optional
from datetime import datetime
from .models import Bookmark, ChapterBookmark
from .repository import BookmarkRepository
from .validators import BookmarkValidator
from .exceptions import BookmarkError

class ChapterManager:
    """Manages chapter bookmarks."""
    
    def __init__(self, repository: BookmarkRepository):
        """Initialize with repository."""
        self.repository = repository
    
    def create_chapter(self, scene_id: str, title: str, 
                     level: int = 1, auto_generated: bool = False) -> int:
        """Create a chapter bookmark."""
        metadata = {
            'chapter_level': level,
            'auto_generated': auto_generated,
            'created_by': 'chapter_manager'
        }
        
        chapter = ChapterBookmark(
            scene_id=scene_id,
            label=title,
            description=f"Chapter: {title}",
            bookmark_type="chapter",
            story_id=self.repository.story_id,
            metadata=metadata,
            chapter_level=level,
            auto_generated=auto_generated
        )
        
        BookmarkValidator.validate_or_raise(chapter)
        
        return self.repository.create(chapter)
    
    def get_chapters(self) -> List[ChapterBookmark]:
        """Get all chapter bookmarks."""
        bookmarks = self.repository.list(bookmark_type="chapter")
        return [ChapterBookmark.from_bookmark(b) for b in bookmarks]
    
    def get_chapter_structure(self) -> Dict[int, List[ChapterBookmark]]:
        """Get chapter structure organized by levels."""
        chapters = self.get_chapters()
        
        # Group chapters by level
        chapters_by_level = {}
        
        for chapter in chapters:
            level = chapter.chapter_level
            if level not in chapters_by_level:
                chapters_by_level[level] = []
            chapters_by_level[level].append(chapter)
        
        return chapters_by_level
    
    def update_chapter(self, chapter_id: int, title: Optional[str] = None,
                     level: Optional[int] = None) -> bool:
        """Update a chapter bookmark."""
        chapter = self.repository.get_by_id(chapter_id)
        
        if not chapter or chapter.bookmark_type != "chapter":
            raise BookmarkError(f"No chapter found with ID {chapter_id}")
        
        chapter_bookmark = ChapterBookmark.from_bookmark(chapter)
        
        if title:
            chapter_bookmark.label = title
            
        if level is not None:
            chapter_bookmark.chapter_level = level
            chapter_bookmark.metadata['chapter_level'] = level
        
        BookmarkValidator.validate_or_raise(chapter_bookmark)
        
        return self.repository.update(chapter_bookmark)
```

### 7. Create Stats Module

Implement dedicated functionality for bookmark statistics:

```python
# stats.py
from typing import Dict, List, Any
from datetime import datetime, timedelta
from .repository import BookmarkRepository

class BookmarkStats:
    """Provides bookmark statistics and reporting."""
    
    def __init__(self, repository: BookmarkRepository):
        """Initialize with repository."""
        self.repository = repository
    
    def get_basic_stats(self) -> Dict[str, Any]:
        """Get basic bookmark statistics."""
        return self.repository.get_stats()
    
    def get_detailed_stats(self) -> Dict[str, Any]:
        """Get detailed bookmark statistics."""
        basic_stats = self.repository.get_stats()
        
        # Get all bookmarks for more detailed analysis
        all_bookmarks = self.repository.list()
        
        # Add timestamps for time-based analysis
        timestamps = []
        for bookmark in all_bookmarks:
            if bookmark.created_at:
                timestamps.append(bookmark.created_at)
        
        # Calculate time-based metrics
        time_stats = {}
        if timestamps:
            timestamps.sort()
            time_stats = {
                'first_bookmark': timestamps[0].isoformat(),
                'last_bookmark': timestamps[-1].isoformat(),
                'total_days': (timestamps[-1] - timestamps[0]).days or 1
            }
            
            # Calculate bookmarks per day
            time_stats['bookmarks_per_day'] = len(timestamps) / time_stats['total_days']
        
        # Combine stats
        detailed_stats = {**basic_stats, 'time_stats': time_stats}
        
        return detailed_stats
    
    def get_usage_patterns(self) -> Dict[str, Any]:
        """Analyze bookmark usage patterns."""
        all_bookmarks = self.repository.list()
        
        # Group by day
        bookmarks_by_day = {}
        for bookmark in all_bookmarks:
            if bookmark.created_at:
                day = bookmark.created_at.date().isoformat()
                if day not in bookmarks_by_day:
                    bookmarks_by_day[day] = []
                bookmarks_by_day[day].append(bookmark)
        
        # Calculate patterns
        patterns = {
            'days_with_bookmarks': len(bookmarks_by_day),
            'max_bookmarks_in_day': max(len(day_bookmarks) for day_bookmarks in bookmarks_by_day.values()) if bookmarks_by_day else 0,
            'bookmark_type_distribution': {}
        }
        
        # Calculate type distribution
        type_counts = {}
        for bookmark in all_bookmarks:
            if bookmark.bookmark_type not in type_counts:
                type_counts[bookmark.bookmark_type] = 0
            type_counts[bookmark.bookmark_type] += 1
        
        patterns['bookmark_type_distribution'] = type_counts
        
        return patterns
```

### 8. Create Exceptions Module

Implement custom exceptions for bookmark operations:

```python
# exceptions.py
from typing import List

class BookmarkError(Exception):
    """Base exception for bookmark errors."""
    pass


class BookmarkNotFoundError(BookmarkError):
    """Exception raised when a bookmark is not found."""
    
    def __init__(self, bookmark_id: int):
        """Initialize with bookmark ID."""
        self.bookmark_id = bookmark_id
        super().__init__(f"Bookmark with ID {bookmark_id} not found")


class BookmarkValidationError(BookmarkError):
    """Exception raised when a bookmark fails validation."""
    
    def __init__(self, errors: List[str]):
        """Initialize with validation errors."""
        self.errors = errors
        error_message = "; ".join(errors)
        super().__init__(f"Bookmark validation failed: {error_message}")


class DuplicateBookmarkError(BookmarkError):
    """Exception raised when attempting to create a duplicate bookmark."""
    
    def __init__(self, scene_id: str, label: str):
        """Initialize with scene ID and label."""
        self.scene_id = scene_id
        self.label = label
        super().__init__(f"Bookmark with label '{label}' already exists for scene {scene_id}")
```

### 9. Refine Main Manager Class

Implement a main manager class to coordinate between components:

```python
# manager.py
from typing import Dict, List, Any, Optional
from datetime import datetime

from .models import Bookmark, BookmarkWithScene, ChapterBookmark
from .repository import BookmarkRepository
from .validators import BookmarkValidator
from .events import EventEmitter, BookmarkCreatedEvent, BookmarkUpdatedEvent, BookmarkDeletedEvent
from .chapters import ChapterManager
from .stats import BookmarkStats
from .exceptions import BookmarkError, BookmarkNotFoundError, BookmarkValidationError, DuplicateBookmarkError

class BookmarkManager:
    """Manages story bookmarks and navigation markers."""
    
    def __init__(self, story_id: str):
        """Initialize bookmark manager."""
        self.story_id = story_id
        
        # Initialize components
        self.repository = BookmarkRepository(story_id)
        self.validator = BookmarkValidator()
        self.events = EventEmitter()
        self.chapter_manager = ChapterManager(self.repository)
        self.stats = BookmarkStats(self.repository)
    
    def create_bookmark(self, scene_id: str, label: str, description: Optional[str] = None, 
                      bookmark_type: str = "user", metadata: Optional[Dict[str, Any]] = None) -> int:
        """Create a new bookmark."""
        # Check for duplicate bookmarks
        existing = self.repository.get_by_scene_and_label(scene_id, label)
        if existing:
            raise DuplicateBookmarkError(scene_id, label)
        
        # Create bookmark object
        bookmark = Bookmark(
            story_id=self.story_id,
            scene_id=scene_id,
            label=label,
            description=description,
            bookmark_type=bookmark_type,
            metadata=metadata or {}
        )
        
        # Validate bookmark
        self.validator.validate_or_raise(bookmark)
        
        # Create in repository
        bookmark_id = self.repository.create(bookmark)
        bookmark.id = bookmark_id
        
        # Emit event
        self.events.emit('created', BookmarkCreatedEvent(bookmark=bookmark))
        
        return bookmark_id
    
    def get_bookmark(self, bookmark_id: int) -> Bookmark:
        """Get a bookmark by ID."""
        bookmark = self.repository.get_by_id(bookmark_id)
        
        if not bookmark:
            raise BookmarkNotFoundError(bookmark_id)
        
        return bookmark
    
    def list_bookmarks(self, bookmark_type: Optional[str] = None, scene_id: Optional[str] = None, 
                     limit: Optional[int] = None) -> List[Bookmark]:
        """List bookmarks with optional filtering."""
        return self.repository.list(bookmark_type, scene_id, limit)
    
    def update_bookmark(self, bookmark_id: int, label: Optional[str] = None, 
                      description: Optional[str] = None, bookmark_type: Optional[str] = None, 
                      metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Update an existing bookmark."""
        # Get current bookmark
        bookmark = self.get_bookmark(bookmark_id)
        previous_state = bookmark.to_dict()
        
        # Update fields
        if label is not None:
            bookmark.label = label
        
        if description is not None:
            bookmark.description = description
        
        if bookmark_type is not None:
            bookmark.bookmark_type = bookmark_type
        
        if metadata is not None:
            bookmark.metadata = metadata
        
        # Validate updated bookmark
        self.validator.validate_or_raise(bookmark)
        
        # Update in repository
        success = self.repository.update(bookmark)
        
        if success:
            # Emit event
            self.events.emit('updated', BookmarkUpdatedEvent(
                bookmark=bookmark,
                previous_state=previous_state
            ))
        
        return success
    
    def delete_bookmark(self, bookmark_id: int) -> bool:
        """Delete a bookmark by ID."""
        # Get bookmark before deleting
        bookmark = self.get_bookmark(bookmark_id)
        
        # Delete from repository
        success = self.repository.delete(bookmark_id)
        
        if success:
            # Emit event
            self.events.emit('deleted', BookmarkDeletedEvent(bookmark=bookmark))
        
        return success
    
    def delete_bookmarks_for_scene(self, scene_id: str) -> int:
        """Delete all bookmarks for a specific scene."""
        # Get bookmarks before deleting
        bookmarks = self.repository.list(scene_id=scene_id)
        
        # Delete from repository
        count = self.repository.delete_by_scene(scene_id)
        
        # Emit events
        for bookmark in bookmarks:
            self.events.emit('deleted', BookmarkDeletedEvent(bookmark=bookmark))
        
        return count
    
    def search_bookmarks(self, query: str, bookmark_type: Optional[str] = None) -> List[Bookmark]:
        """Search bookmarks by label or description."""
        return self.repository.search(query, bookmark_type)
    
    def get_bookmarks_with_scenes(self, bookmark_type: Optional[str] = None) -> List[BookmarkWithScene]:
        """Get bookmarks with their associated scene information."""
        return self.repository.get_with_scenes(bookmark_type)
    
    def create_chapter_bookmark(self, scene_id: str, chapter_title: str, 
                             chapter_level: int = 1, auto_generated: bool = False) -> int:
        """Create a chapter bookmark."""
        return self.chapter_manager.create_chapter(
            scene_id, chapter_title, chapter_level, auto_generated)
    
    def get_chapter_bookmarks(self) -> List[ChapterBookmark]:
        """Get all chapter bookmarks."""
        return self.chapter_manager.get_chapters()
    
    def get_chapter_structure(self) -> Dict[int, List[ChapterBookmark]]:
        """Get chapter structure organized by levels."""
        return self.chapter_manager.get_chapter_structure()
    
    def get_bookmark_stats(self) -> Dict[str, Any]:
        """Get bookmark statistics."""
        return self.stats.get_basic_stats()
    
    def get_detailed_stats(self) -> Dict[str, Any]:
        """Get detailed bookmark statistics."""
        return self.stats.get_detailed_stats()
    
    def on_bookmark_event(self, event_type: str, handler) -> None:
        """Register an event handler."""
        self.events.on(event_type, handler)
```

### 10. Create Public API

Provide a clean public API:

```python
# __init__.py
from .manager import BookmarkManager
from .models import Bookmark, BookmarkWithScene, ChapterBookmark
from .exceptions import BookmarkError, BookmarkNotFoundError, BookmarkValidationError, DuplicateBookmarkError

# Factory function
def create_bookmark_manager(story_id: str) -> BookmarkManager:
    """Create a bookmark manager for a story."""
    return BookmarkManager(story_id)

# Backward compatibility
def create_bookmark(story_id: str, scene_id: str, label: str, **kwargs):
    """Create a bookmark (backward compatibility)."""
    manager = create_bookmark_manager(story_id)
    return manager.create_bookmark(scene_id, label, **kwargs)

def get_bookmark(story_id: str, bookmark_id: int):
    """Get a bookmark (backward compatibility)."""
    manager = create_bookmark_manager(story_id)
    bookmark = manager.get_bookmark(bookmark_id)
    return bookmark.to_dict()

def list_bookmarks(story_id: str, **kwargs):
    """List bookmarks (backward compatibility)."""
    manager = create_bookmark_manager(story_id)
    bookmarks = manager.list_bookmarks(**kwargs)
    return [b.to_dict() for b in bookmarks]

def update_bookmark(story_id: str, bookmark_id: int, **kwargs):
    """Update a bookmark (backward compatibility)."""
    manager = create_bookmark_manager(story_id)
    return manager.update_bookmark(bookmark_id, **kwargs)

def delete_bookmark(story_id: str, bookmark_id: int):
    """Delete a bookmark (backward compatibility)."""
    manager = create_bookmark_manager(story_id)
    return manager.delete_bookmark(bookmark_id)
```

## Implementation Strategy

1. **Create Package Structure**: Set up the directory and file structure
2. **Implement Data Models**: Create proper dataclasses for bookmarks
3. **Implement Repository**: Create the repository layer for data access
4. **Implement Validator**: Create the validator for bookmark validation
5. **Implement Events**: Create the event system for bookmark changes
6. **Implement Chapters**: Create the chapter management functionality
7. **Implement Stats**: Create the statistics functionality
8. **Implement Exceptions**: Create custom exceptions
9. **Implement Main Manager**: Create the main bookmark manager class
10. **Implement Public API**: Provide a clean public API with backward compatibility

## Benefits of Refactoring

1. **Improved Organization**: Clear separation of concerns with specialized components
2. **Enhanced Testability**: Components can be tested in isolation
3. **Better Error Handling**: Comprehensive error handling with custom exceptions
4. **Improved Validation**: Dedicated validation system
5. **Event Notifications**: Event system for bookmark changes
6. **Better API**: Well-defined interfaces for bookmark operations
7. **Type Safety**: Comprehensive type annotations throughout the codebase
8. **Maintainability**: Clearer code organization and separation of concerns

## Migration Plan

1. **Incremental Refactoring**: Create the new package structure alongside the existing file
2. **Backward Compatibility**: Provide module-level functions that mirror the original API
3. **Unit Testing**: Develop comprehensive tests for the refactored components
4. **Gradual Adoption**: Update dependent code to use the new API incrementally
5. **Complete Migration**: Remove the original file once all dependencies are updated

By following this refactoring plan, the bookmark_manager.py module will be transformed into a well-structured, maintainable package that adheres to modern Python best practices while preserving all existing functionality.
