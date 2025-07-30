# Rollback Engine Refactoring Recommendation

## Current Module Overview

**File**: `core/rollback_engine.py` (241 lines)  
**Purpose**: Manages story rollback functionality, allowing stories to be reverted to previous states.

**Key Components**:
1. **Rollback Point Management** - Functions to create, list, and manage rollback points
2. **Scene Management** - Functions to retrieve and backup scenes
3. **Rollback Execution** - Functions to perform rollbacks to specific scenes or timestamps
4. **Validation & Cleanup** - Functions to validate rollback integrity and clean up old data

**Current Responsibilities**:
- Creating and managing rollback points
- Identifying scenes to remove during rollback
- Backing up scenes that will be removed
- Executing rollbacks by reverting to previous scenes
- Restoring memory state during rollback
- Validating rollback data integrity
- Cleaning up old rollback data

## Issues Identified

1. **Module-Level Functions**: The module consists entirely of standalone functions without a class structure
2. **Direct Dependencies**: Direct coupling with scene_logger, memory_manager, and database modules
3. **Error Handling**: Limited error handling and recovery mechanisms
4. **Validation**: Validation logic intermixed with operational functions
5. **Configuration Management**: Lacks centralized configuration for settings like retention periods
6. **Testing Challenges**: Hard to test due to direct database dependencies
7. **Notification System**: No event notification for rollback operations

## Refactoring Recommendations

### 1. Convert to Package Structure

Transform the file into a structured package:

```
core/
  rollback/
    __init__.py              # Public API
    engine.py                # Main engine class
    models.py                # Data models
    point_manager.py         # Rollback point management
    backup_manager.py        # Backup management
    validation.py            # Validation utilities
    exceptions.py            # Custom exceptions
```

### 2. Implement Data Models

Create proper data models for rollback-related data:

```python
# models.py
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Any, Optional

@dataclass
class RollbackPoint:
    """Represents a rollback point in the story."""
    id: str
    scene_id: str
    timestamp: datetime
    description: str
    scene_data: Dict[str, Any]
    created_at: datetime
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RollbackPoint':
        """Create RollbackPoint from dictionary."""
        return cls(
            id=data["id"],
            scene_id=data["scene_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            description=data["description"],
            scene_data=data["scene_data"],
            created_at=datetime.fromisoformat(data["created_at"])
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "scene_id": self.scene_id,
            "timestamp": self.timestamp.isoformat(),
            "description": self.description,
            "scene_data": self.scene_data,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class SceneBackup:
    """Represents a backed-up scene."""
    backup_id: str
    scene_id: str
    scene_data: Dict[str, Any]
    reason: str
    created_at: datetime
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SceneBackup':
        """Create SceneBackup from dictionary."""
        return cls(
            backup_id=data["backup_id"],
            scene_id=data["scene_id"],
            scene_data=data["scene_data"],
            reason=data["reason"],
            created_at=datetime.fromisoformat(data["created_at"])
        )


@dataclass
class RollbackResult:
    """Represents the result of a rollback operation."""
    success: bool
    message: str
    scenes_removed: int
    target_scene: str
    memory_restored: bool
    memory_error: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RollbackResult':
        """Create RollbackResult from dictionary."""
        return cls(
            success=data["success"],
            message=data["message"],
            scenes_removed=data["scenes_removed"],
            target_scene=data["target_scene"],
            memory_restored=data["memory_restored"],
            memory_error=data.get("memory_error")
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "success": self.success,
            "message": self.message,
            "scenes_removed": self.scenes_removed,
            "target_scene": self.target_scene,
            "memory_restored": self.memory_restored
        }
        
        if self.memory_error:
            result["memory_error"] = self.memory_error
            
        return result


@dataclass
class RollbackCandidate:
    """Represents a scene that is a candidate for rollback."""
    scene_id: str
    timestamp: datetime
    input_preview: str
    has_flags: bool
    has_memory_snapshot: bool
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RollbackCandidate':
        """Create RollbackCandidate from dictionary."""
        return cls(
            scene_id=data["scene_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            input_preview=data["input_preview"],
            has_flags=data["has_flags"],
            has_memory_snapshot=data["has_memory_snapshot"]
        )
```

### 3. Create Rollback Point Manager

Extract rollback point management into a dedicated class:

```python
# point_manager.py
import json
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional
from .models import RollbackPoint
from ..database import get_connection, execute_query, execute_update


class RollbackPointManager:
    """Manages rollback points for stories."""
    
    def __init__(self, story_id: str):
        """Initialize with story ID."""
        self.story_id = story_id
    
    def create_point(self, scene_id: str, scene_data: Dict[str, Any], 
                    description: str = "Manual rollback point") -> RollbackPoint:
        """Create a rollback point at a specific scene."""
        rollback_id = f"rollback_{scene_id}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
        created_at = datetime.now(UTC)
        
        execute_update(self.story_id, '''
            INSERT OR REPLACE INTO rollback_points 
            (rollback_id, scene_id, timestamp, description, scene_data, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            rollback_id,
            scene_id,
            created_at.isoformat(),
            description,
            json.dumps(scene_data),
            created_at.isoformat()
        ))
        
        return RollbackPoint(
            id=rollback_id,
            scene_id=scene_id,
            timestamp=created_at,
            description=description,
            scene_data=scene_data,
            created_at=created_at
        )
    
    def list_points(self) -> List[RollbackPoint]:
        """List all available rollback points."""
        rows = execute_query(self.story_id, '''
            SELECT rollback_id, scene_id, timestamp, description, scene_data, created_at
            FROM rollback_points ORDER BY timestamp DESC
        ''')
        
        return [
            RollbackPoint(
                id=row["rollback_id"],
                scene_id=row["scene_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                description=row["description"],
                scene_data=json.loads(row["scene_data"]),
                created_at=datetime.fromisoformat(row.get("created_at") or row["timestamp"])
            )
            for row in rows
        ]
    
    def get_point(self, rollback_id: str) -> Optional[RollbackPoint]:
        """Get a specific rollback point."""
        rows = execute_query(self.story_id, '''
            SELECT rollback_id, scene_id, timestamp, description, scene_data, created_at
            FROM rollback_points WHERE rollback_id = ?
        ''', (rollback_id,))
        
        if not rows:
            return None
        
        row = rows[0]
        return RollbackPoint(
            id=row["rollback_id"],
            scene_id=row["scene_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            description=row["description"],
            scene_data=json.loads(row["scene_data"]),
            created_at=datetime.fromisoformat(row.get("created_at") or row["timestamp"])
        )
    
    def delete_point(self, rollback_id: str) -> bool:
        """Delete a rollback point."""
        rows_affected = execute_update(self.story_id, '''
            DELETE FROM rollback_points WHERE rollback_id = ?
        ''', (rollback_id,))
        
        return rows_affected > 0
    
    def clear_old_points(self, days_to_keep: int = 30) -> int:
        """Clear rollback points older than the specified number of days."""
        from datetime import timedelta
        
        cutoff_date = datetime.now(UTC) - timedelta(days=days_to_keep)
        cutoff_timestamp = cutoff_date.isoformat()
        
        rows_affected = execute_update(self.story_id, '''
            DELETE FROM rollback_points WHERE created_at < ?
        ''', (cutoff_timestamp,))
        
        return rows_affected
```

### 4. Create Backup Manager

Implement a dedicated backup manager:

```python
# backup_manager.py
import json
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional
from .models import SceneBackup
from ..database import execute_query, execute_update


class BackupManager:
    """Manages scene backups for rollback operations."""
    
    def __init__(self, story_id: str):
        """Initialize with story ID."""
        self.story_id = story_id
    
    def backup_scenes(self, scenes_data: Dict[str, Dict[str, Any]], 
                     reason: str = "rollback_preparation") -> str:
        """Backup multiple scenes."""
        if not scenes_data:
            return None
        
        backup_id = f"backup_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
        created_at = datetime.now(UTC)
        
        for scene_id, scene_data in scenes_data.items():
            execute_update(self.story_id, '''
                INSERT INTO rollback_backups 
                (backup_id, scene_id, scene_data, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                backup_id,
                scene_id,
                json.dumps(scene_data),
                reason,
                created_at.isoformat()
            ))
        
        return backup_id
    
    def get_backup(self, backup_id: str) -> Dict[str, SceneBackup]:
        """Get a specific backup."""
        rows = execute_query(self.story_id, '''
            SELECT backup_id, scene_id, scene_data, reason, created_at
            FROM rollback_backups WHERE backup_id = ?
        ''', (backup_id,))
        
        backups = {}
        for row in rows:
            backups[row["scene_id"]] = SceneBackup(
                backup_id=row["backup_id"],
                scene_id=row["scene_id"],
                scene_data=json.loads(row["scene_data"]),
                reason=row["reason"],
                created_at=datetime.fromisoformat(row.get("created_at") or datetime.now(UTC).isoformat())
            )
        
        return backups
    
    def list_backups(self) -> List[str]:
        """List all backup IDs."""
        rows = execute_query(self.story_id, '''
            SELECT DISTINCT backup_id FROM rollback_backups ORDER BY created_at DESC
        ''')
        
        return [row["backup_id"] for row in rows]
    
    def restore_backup(self, backup_id: str) -> Dict[str, Any]:
        """Restore scenes from a backup."""
        # Implementation depends on how scenes are stored
        pass
    
    def clear_old_backups(self, days_to_keep: int = 30) -> int:
        """Clear backups older than the specified number of days."""
        from datetime import timedelta
        
        cutoff_date = datetime.now(UTC) - timedelta(days=days_to_keep)
        cutoff_timestamp = cutoff_date.isoformat()
        
        rows_affected = execute_update(self.story_id, '''
            DELETE FROM rollback_backups WHERE created_at < ?
        ''', (cutoff_timestamp,))
        
        return rows_affected
```

### 5. Create Validation Utilities

Extract validation logic to a dedicated module:

```python
# validation.py
from datetime import datetime
from typing import List, Dict, Any
from ..database import execute_query


class RollbackValidator:
    """Validates rollback data integrity."""
    
    def __init__(self, story_id: str):
        """Initialize with story ID."""
        self.story_id = story_id
    
    def validate_integrity(self) -> List[str]:
        """Validate that rollback data is consistent."""
        issues = []
        
        # Check scene continuity
        rows = execute_query(self.story_id, '''
            SELECT scene_id, timestamp FROM scenes ORDER BY timestamp ASC
        ''')
        
        if not rows:
            issues.append("No scenes found")
            return issues
        
        # Check for timestamp sequence
        for i, row in enumerate(rows[:-1]):
            current_time = datetime.fromisoformat(row["timestamp"])
            next_time = datetime.fromisoformat(rows[i + 1]["timestamp"])
            
            # Handle timezone-aware/naive comparison
            if current_time.tzinfo is None and next_time.tzinfo is not None:
                current_time = current_time.replace(tzinfo=next_time.tzinfo)
            elif current_time.tzinfo is not None and next_time.tzinfo is None:
                next_time = next_time.replace(tzinfo=current_time.tzinfo)
            
            if current_time >= next_time:
                issues.append(f"Scene {row['scene_id']} timestamp is not before {rows[i + 1]['scene_id']}")
        
        # Check rollback points
        rollback_rows = execute_query(self.story_id, '''
            SELECT rollback_id, scene_id FROM rollback_points
        ''')
        
        scene_ids = [row["scene_id"] for row in rows]
        
        for rollback_row in rollback_rows:
            if rollback_row["scene_id"] not in scene_ids:
                issues.append(f"Rollback point {rollback_row['rollback_id']} references non-existent scene")
        
        return issues
    
    def validate_rollback_target(self, target_scene_id: str) -> Dict[str, Any]:
        """Validate that a rollback target is valid."""
        # Check scene exists
        scene_rows = execute_query(self.story_id, '''
            SELECT scene_id FROM scenes WHERE scene_id = ?
        ''', (target_scene_id,))
        
        if not scene_rows:
            return {
                "valid": False,
                "reason": f"Scene {target_scene_id} does not exist"
            }
        
        # Check memory snapshot exists
        memory_rows = execute_query(self.story_id, '''
            SELECT memory_snapshot FROM scenes WHERE scene_id = ?
        ''', (target_scene_id,))
        
        if not memory_rows or not memory_rows[0]["memory_snapshot"]:
            return {
                "valid": True,
                "warning": f"Scene {target_scene_id} does not have a memory snapshot"
            }
        
        return {
            "valid": True
        }
```

### 6. Create Main Engine Class

Implement a main engine class to coordinate between components:

```python
# engine.py
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Any, Optional

from .models import RollbackPoint, RollbackResult, RollbackCandidate
from .point_manager import RollbackPointManager
from .backup_manager import BackupManager
from .validation import RollbackValidator
from .exceptions import RollbackError

from ..scene_logger import load_scene, list_scenes
from ..memory_manager import restore_memory_from_snapshot
from ..database import init_database, execute_query, execute_update


class RollbackEngine:
    """Main engine for managing story rollbacks."""
    
    def __init__(self, story_id: str):
        """Initialize with story ID."""
        self.story_id = story_id
        init_database(story_id)
        
        # Initialize components
        self.point_manager = RollbackPointManager(story_id)
        self.backup_manager = BackupManager(story_id)
        self.validator = RollbackValidator(story_id)
    
    def create_rollback_point(self, scene_id: str, 
                            description: str = "Manual rollback point") -> RollbackPoint:
        """Create a rollback point at a specific scene."""
        # Verify scene exists
        scene_data = load_scene(self.story_id, scene_id)
        if not scene_data:
            raise RollbackError(f"Scene {scene_id} not found in story {self.story_id}")
        
        return self.point_manager.create_point(scene_id, scene_data, description)
    
    def list_rollback_points(self) -> List[RollbackPoint]:
        """List all available rollback points."""
        return self.point_manager.list_points()
    
    def get_scenes_after(self, target_scene_id: str) -> List[str]:
        """Get all scenes that come after a target scene."""
        all_scenes = list_scenes(self.story_id)
        
        try:
            target_index = all_scenes.index(target_scene_id)
            return all_scenes[target_index + 1:]
        except ValueError:
            raise RollbackError(f"Scene {target_scene_id} not found in story {self.story_id}")
    
    def backup_scenes_for_rollback(self, scenes_to_backup: List[str]) -> Optional[str]:
        """Backup scenes before rollback."""
        if not scenes_to_backup:
            return None
        
        # Load all scenes
        scenes_data = {}
        for scene_id in scenes_to_backup:
            scene_data = load_scene(self.story_id, scene_id)
            if scene_data:
                scenes_data[scene_id] = scene_data
        
        return self.backup_manager.backup_scenes(scenes_data)
    
    def rollback_to_scene(self, target_scene_id: str, 
                        create_backup: bool = True) -> RollbackResult:
        """Rollback story to a specific scene."""
        # Verify target scene exists
        target_scene = load_scene(self.story_id, target_scene_id)
        if not target_scene:
            raise RollbackError(f"Scene {target_scene_id} not found")
        
        # Get scenes that will be removed
        scenes_to_remove = self.get_scenes_after(target_scene_id)
        
        if not scenes_to_remove:
            return RollbackResult(
                success=True,
                message="Already at target scene",
                scenes_removed=0,
                target_scene=target_scene_id,
                memory_restored=True
            )
        
        # Create backup if requested
        if create_backup:
            self.backup_scenes_for_rollback(scenes_to_remove)
        
        # Remove scenes after target
        removed_count = 0
        for scene_id in scenes_to_remove:
            rows_affected = execute_update(self.story_id, '''
                DELETE FROM scenes WHERE scene_id = ?
            ''', (scene_id,))
            if rows_affected > 0:
                removed_count += 1
        
        # Restore memory state from target scene
        try:
            restore_memory_from_snapshot(self.story_id, target_scene_id)
            memory_restored = True
            memory_error = None
        except Exception as e:
            memory_restored = False
            memory_error = str(e)
        
        result = RollbackResult(
            success=True,
            message=f"Rolled back to scene {target_scene_id}",
            scenes_removed=removed_count,
            target_scene=target_scene_id,
            memory_restored=memory_restored,
            memory_error=memory_error
        )
        
        return result
    
    def rollback_to_timestamp(self, target_timestamp: str, 
                            create_backup: bool = True) -> RollbackResult:
        """Rollback to the scene closest to a specific timestamp."""
        rows = execute_query(self.story_id, '''
            SELECT scene_id, timestamp FROM scenes 
            WHERE timestamp <= ? 
            ORDER BY timestamp DESC 
            LIMIT 1
        ''', (target_timestamp,))
        
        if not rows:
            raise RollbackError(f"No scene found before timestamp {target_timestamp}")
        
        target_scene_id = rows[0]["scene_id"]
        return self.rollback_to_scene(target_scene_id, create_backup)
    
    def get_rollback_candidates(self, limit: int = 10) -> List[RollbackCandidate]:
        """Get recent scenes that are good rollback candidates."""
        rows = execute_query(self.story_id, '''
            SELECT scene_id, timestamp, input, flags, memory_snapshot
            FROM scenes ORDER BY timestamp DESC LIMIT ?
        ''', (limit,))
        
        candidates = []
        for row in rows:
            candidates.append(RollbackCandidate(
                scene_id=row["scene_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                input_preview=row["input"][:100] + "..." if len(row["input"]) > 100 else row["input"],
                has_flags=bool(row["flags"]),
                has_memory_snapshot=bool(row["memory_snapshot"])
            ))
        
        return candidates
    
    def validate_rollback_integrity(self) -> List[str]:
        """Validate that rollback data is consistent."""
        return self.validator.validate_integrity()
    
    def cleanup_old_rollback_data(self, days_to_keep: int = 30) -> Dict[str, Any]:
        """Clean up old rollback data and backups."""
        points_cleaned = self.point_manager.clear_old_points(days_to_keep)
        backups_cleaned = self.backup_manager.clear_old_backups(days_to_keep)
        
        total_cleaned = points_cleaned + backups_cleaned
        
        return {
            "cleaned": total_cleaned,
            "points_cleaned": points_cleaned,
            "backups_cleaned": backups_cleaned,
            "message": f"Cleaned {total_cleaned} old rollback items"
        }
```

### 7. Create Exceptions Module

Implement custom exceptions for rollback operations:

```python
# exceptions.py
class RollbackError(Exception):
    """Base exception for rollback errors."""
    pass


class RollbackTargetError(RollbackError):
    """Exception for invalid rollback targets."""
    pass


class RollbackMemoryError(RollbackError):
    """Exception for memory restoration errors."""
    pass


class RollbackBackupError(RollbackError):
    """Exception for backup errors."""
    pass
```

### 8. Create Public API

Provide a clean public API in the package `__init__.py`:

```python
# __init__.py
from .engine import RollbackEngine
from .models import RollbackPoint, RollbackResult, RollbackCandidate
from .exceptions import RollbackError, RollbackTargetError, RollbackMemoryError

# Factory function for main engine
def create_rollback_engine(story_id: str) -> RollbackEngine:
    """Create a rollback engine for a story."""
    return RollbackEngine(story_id)

# Expose key functions as module-level functions for backward compatibility
def create_rollback_point(story_id: str, scene_id: str, description: str = "Manual rollback point"):
    """Create a rollback point at a specific scene."""
    engine = create_rollback_engine(story_id)
    return engine.create_rollback_point(scene_id, description)

def list_rollback_points(story_id: str):
    """List all available rollback points."""
    engine = create_rollback_engine(story_id)
    return [point.to_dict() for point in engine.list_rollback_points()]

def rollback_to_scene(story_id: str, target_scene_id: str, create_backup: bool = True):
    """Rollback story to a specific scene."""
    engine = create_rollback_engine(story_id)
    result = engine.rollback_to_scene(target_scene_id, create_backup)
    return result.to_dict()

def rollback_to_timestamp(story_id: str, target_timestamp: str, create_backup: bool = True):
    """Rollback to the scene closest to a specific timestamp."""
    engine = create_rollback_engine(story_id)
    result = engine.rollback_to_timestamp(target_timestamp, create_backup)
    return result.to_dict()

def get_rollback_candidates(story_id: str, limit: int = 10):
    """Get recent scenes that are good rollback candidates."""
    engine = create_rollback_engine(story_id)
    candidates = engine.get_rollback_candidates(limit)
    return [
        {
            "scene_id": candidate.scene_id,
            "timestamp": candidate.timestamp.isoformat(),
            "input_preview": candidate.input_preview,
            "has_flags": candidate.has_flags,
            "has_memory_snapshot": candidate.has_memory_snapshot
        }
        for candidate in candidates
    ]

def validate_rollback_integrity(story_id: str):
    """Validate that rollback data is consistent."""
    engine = create_rollback_engine(story_id)
    return engine.validate_rollback_integrity()

def cleanup_old_rollback_data(story_id: str, days_to_keep: int = 30):
    """Clean up old rollback data and backups."""
    engine = create_rollback_engine(story_id)
    return engine.cleanup_old_rollback_data(days_to_keep)
```

## Implementation Strategy

1. **Create Package Structure**: Set up the directory and file structure
2. **Implement Data Models**: Create proper dataclasses for rollback data
3. **Implement Component Classes**: Create point manager, backup manager, and validator
4. **Create Main Engine**: Implement the main rollback engine class
5. **Implement Exceptions**: Create custom exceptions for rollback operations
6. **Create Public API**: Provide a clean public API with backward compatibility

## Benefits of Refactoring

1. **Improved Organization**: Smaller, focused components with clear responsibilities
2. **Enhanced Testability**: Components can be tested in isolation with proper mocking
3. **Better Error Handling**: Comprehensive error handling with custom exceptions
4. **Improved Validation**: Dedicated validation utilities
5. **Better API**: Well-defined interfaces for different operations
6. **Type Safety**: Comprehensive type annotations throughout the codebase
7. **Maintainability**: Clearer code organization and separation of concerns

## Migration Plan

1. **Incremental Refactoring**: Create the new package structure alongside the existing module
2. **Backward Compatibility**: Provide module-level functions that mirror the original API
3. **Unit Testing**: Develop comprehensive tests for the refactored components
4. **Gradual Adoption**: Update dependent code to use the new API incrementally
5. **Complete Migration**: Remove the original module once all dependencies are updated

By following this refactoring plan, the rollback_engine.py module will be transformed into a well-structured, maintainable package that adheres to modern Python best practices while preserving all existing functionality.
