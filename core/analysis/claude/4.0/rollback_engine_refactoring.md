# Rollback Engine Refactoring Analysis

**File**: `core/rollback_engine.py`  
**Size**: 251 lines  
**Complexity**: LOW  
**Priority**: LOW

## Executive Summary

The `rollback_engine.py` module implements a story rollback and version control system that allows users to revert story state to previous scenes with backup mechanisms and integrity validation. While functionally complete with features like selective rollback, automatic backups, and data validation, it demonstrates minor architectural violations by combining rollback operations, backup management, validation logic, and cleanup operations in a single module with 9 standalone functions. This analysis proposes a lightweight class-based architecture to improve organization and maintainability.

## Current Architecture Analysis

### Core Components
1. **9 Standalone Functions**: All rollback operations implemented as module-level functions
2. **Simple Responsibilities**: Scene rollback, backup creation, validation, and cleanup
3. **Database Integration**: Direct database operations through imported modules
4. **Clean Functionality**: Well-defined rollback logic with error handling

### Current Responsibilities
- **Rollback Point Management**: Creating and listing rollback checkpoints
- **Scene Rollback Operations**: Rolling back to specific scenes or timestamps  
- **Backup Management**: Creating backups before destructive operations
- **Data Validation**: Checking rollback data integrity and consistency
- **Cleanup Operations**: Removing old rollback data and backups

## Major Refactoring Opportunities

### 1. Rollback Operations System (Medium Priority)

**Problem**: Rollback operations scattered across multiple functions
```python
def create_rollback_point(story_id, scene_id, description="Manual rollback point"):
    # Rollback point creation logic

def rollback_to_scene(story_id, target_scene_id, create_backup=True):
    # Scene rollback logic

def rollback_to_timestamp(story_id, target_timestamp, create_backup=True):
    # Timestamp-based rollback logic
```

**Solution**: Extract to RollbackOperationsManager
```python
class RollbackOperationsManager:
    """Manages rollback operations and checkpoints."""
    
    def __init__(self, story_id: str):
        self.story_id = story_id
        self.database_manager = DatabaseManager(story_id)
        self.rollback_validator = RollbackValidator()
        self.scene_manager = SceneManager(story_id)
        
    def create_rollback_point(self, scene_id: str, description: str = "Manual rollback point") -> RollbackPoint:
        """Create a rollback checkpoint at specific scene."""
        
    def list_rollback_points(self) -> List[RollbackPoint]:
        """List all available rollback points."""
        
    def rollback_to_scene(self, target_scene_id: str, create_backup: bool = True) -> RollbackResult:
        """Rollback story to specific scene."""
        
    def rollback_to_timestamp(self, target_timestamp: str, create_backup: bool = True) -> RollbackResult:
        """Rollback to scene closest to timestamp."""
        
    def get_rollback_candidates(self, limit: int = 10) -> List[RollbackCandidate]:
        """Get recent scenes suitable for rollback."""

class RollbackValidator:
    """Validates rollback operations and data integrity."""
    
    def __init__(self):
        self.integrity_checker = DataIntegrityChecker()
        self.sequence_validator = SceneSequenceValidator()
        
    def validate_rollback_target(self, story_id: str, target_scene_id: str) -> ValidationResult:
        """Validate rollback target scene exists and is valid."""
        
    def validate_rollback_integrity(self, story_id: str) -> List[str]:
        """Validate that rollback data is consistent."""
        
    def check_rollback_impact(self, story_id: str, target_scene_id: str) -> ImpactAssessment:
        """Assess impact of rolling back to target scene."""

@dataclass
class RollbackPoint:
    """Rollback checkpoint data."""
    rollback_id: str
    scene_id: str
    timestamp: str
    description: str
    scene_data: Dict[str, Any]
    created_at: str
    
@dataclass
class RollbackResult:
    """Result of rollback operation."""
    success: bool
    message: str
    scenes_removed: int
    target_scene: str
    memory_restored: bool
    memory_error: Optional[str] = None
    
@dataclass
class RollbackCandidate:
    """Scene candidate for rollback."""
    scene_id: str
    timestamp: str
    input_preview: str
    has_flags: bool
    memory_snapshot: bool
```

### 2. Backup Management System (Medium Priority)

**Problem**: Backup operations mixed with rollback logic
```python
def backup_scenes_for_rollback(story_id, scenes_to_backup):
    # Backup creation logic

def get_scenes_after(story_id, target_scene_id):
    # Scene identification logic
```

**Solution**: Extract to BackupManager
```python
class BackupManager:
    """Manages rollback backups and data preservation."""
    
    def __init__(self, story_id: str):
        self.story_id = story_id
        self.backup_storage = BackupStorage(story_id)
        self.scene_analyzer = SceneAnalyzer()
        
    def create_rollback_backup(self, scenes_to_backup: List[str], reason: str = "rollback_preparation") -> BackupResult:
        """Create backup of scenes before rollback."""
        
    def get_scenes_after_target(self, target_scene_id: str) -> List[str]:
        """Get all scenes that come after target scene."""
        
    def restore_from_backup(self, backup_id: str) -> RestoreResult:
        """Restore scenes from backup."""
        
    def list_backups(self, limit: int = 10) -> List[BackupInfo]:
        """List available backups."""
        
    def cleanup_old_backups(self, days_to_keep: int = 30) -> CleanupResult:
        """Clean up old backup data."""

class BackupStorage:
    """Handles backup data storage and retrieval."""
    
    def __init__(self, story_id: str):
        self.story_id = story_id
        self.storage_manager = DatabaseManager(story_id)
        
    def store_scene_backup(self, backup_id: str, scene_id: str, 
                         scene_data: Dict[str, Any], reason: str) -> bool:
        """Store individual scene backup."""
        
    def retrieve_scene_backup(self, backup_id: str, scene_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve scene data from backup."""
        
    def list_backup_contents(self, backup_id: str) -> List[str]:
        """List scenes included in backup."""
        
    def delete_backup(self, backup_id: str) -> bool:
        """Delete backup and all associated data."""

@dataclass
class BackupResult:
    """Result of backup operation."""
    success: bool
    backup_id: str
    scenes_backed_up: int
    backup_size_bytes: int
    error_message: Optional[str] = None
    
@dataclass
class BackupInfo:
    """Information about a backup."""
    backup_id: str
    created_at: str
    scene_count: int
    reason: str
    total_size_bytes: int
```

### 3. Cleanup and Maintenance System (Low Priority)

**Problem**: Cleanup operations as standalone function
```python
def cleanup_old_rollback_data(story_id, days_to_keep=30):
    # Cleanup logic for rollback data and backups
```

**Solution**: Extract to MaintenanceManager
```python
class RollbackMaintenanceManager:
    """Manages rollback system maintenance and cleanup."""
    
    def __init__(self, story_id: str):
        self.story_id = story_id
        self.cleanup_scheduler = CleanupScheduler()
        self.maintenance_logger = MaintenanceLogger()
        
    def cleanup_old_data(self, days_to_keep: int = 30) -> CleanupResult:
        """Clean up old rollback points and backups."""
        
    def optimize_rollback_storage(self) -> OptimizationResult:
        """Optimize rollback data storage."""
        
    def generate_maintenance_report(self) -> MaintenanceReport:
        """Generate rollback system maintenance report."""
        
    def schedule_automatic_cleanup(self, schedule: CleanupSchedule) -> None:
        """Schedule automatic cleanup operations."""

class CleanupScheduler:
    """Schedules and manages cleanup operations."""
    
    def calculate_cleanup_targets(self, story_id: str, retention_days: int) -> CleanupTargets:
        """Calculate what data should be cleaned up."""
        
    def execute_cleanup_plan(self, cleanup_targets: CleanupTargets) -> CleanupExecution:
        """Execute calculated cleanup plan."""
        
    def validate_cleanup_safety(self, cleanup_targets: CleanupTargets) -> ValidationResult:
        """Validate cleanup is safe to execute."""

@dataclass
class CleanupResult:
    """Result of cleanup operation."""
    success: bool
    items_cleaned: int
    space_freed_bytes: int
    errors: List[str]
    warnings: List[str]
    
@dataclass
class MaintenanceReport:
    """Rollback system maintenance report."""
    story_id: str
    total_rollback_points: int
    total_backups: int
    storage_used_bytes: int
    oldest_data_age_days: int
    cleanup_recommendations: List[str]
```

## Proposed Modular Architecture

```python
class RollbackEngine:
    """Main orchestrator for rollback operations."""
    
    def __init__(self, story_id: str):
        self.story_id = story_id
        
        # Core components
        self.operations_manager = RollbackOperationsManager(story_id)
        self.backup_manager = BackupManager(story_id)
        self.maintenance_manager = RollbackMaintenanceManager(story_id)
        
        # Initialize database
        init_database(story_id)
        
    def create_rollback_point(self, scene_id: str, description: str = "Manual rollback point") -> RollbackPoint:
        """Create rollback checkpoint."""
        return self.operations_manager.create_rollback_point(scene_id, description)
    
    def list_rollback_points(self) -> List[RollbackPoint]:
        """List available rollback points."""
        return self.operations_manager.list_rollback_points()
    
    def rollback_to_scene(self, target_scene_id: str, create_backup: bool = True) -> RollbackResult:
        """Rollback story to specific scene."""
        return self.operations_manager.rollback_to_scene(target_scene_id, create_backup)
    
    def rollback_to_timestamp(self, target_timestamp: str, create_backup: bool = True) -> RollbackResult:
        """Rollback to scene closest to timestamp."""
        return self.operations_manager.rollback_to_timestamp(target_timestamp, create_backup)
    
    def get_rollback_candidates(self, limit: int = 10) -> List[RollbackCandidate]:
        """Get scenes suitable for rollback."""
        return self.operations_manager.get_rollback_candidates(limit)
    
    def validate_integrity(self) -> List[str]:
        """Validate rollback system integrity."""
        return self.operations_manager.rollback_validator.validate_rollback_integrity(self.story_id)
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> CleanupResult:
        """Clean up old rollback data."""
        return self.maintenance_manager.cleanup_old_data(days_to_keep)
    
    def get_maintenance_report(self) -> MaintenanceReport:
        """Get rollback system status report."""
        return self.maintenance_manager.generate_maintenance_report()

# Maintain backward compatibility with existing function-based API
def create_rollback_point(story_id: str, scene_id: str, description: str = "Manual rollback point") -> Dict[str, Any]:
    """Legacy function wrapper for rollback point creation."""
    engine = RollbackEngine(story_id)
    result = engine.create_rollback_point(scene_id, description)
    return {
        "id": result.rollback_id,
        "scene_id": result.scene_id,
        "timestamp": result.timestamp,
        "description": result.description,
        "scene_data": result.scene_data,
        "created_at": result.created_at
    }

def rollback_to_scene(story_id: str, target_scene_id: str, create_backup: bool = True) -> Dict[str, Any]:
    """Legacy function wrapper for scene rollback."""
    engine = RollbackEngine(story_id)
    result = engine.rollback_to_scene(target_scene_id, create_backup)
    return {
        "success": result.success,
        "message": result.message,
        "scenes_removed": result.scenes_removed,
        "target_scene": result.target_scene,
        "memory_restored": result.memory_restored,
        "memory_error": result.memory_error
    }

# Additional legacy wrappers for remaining functions...
```

## Implementation Benefits

### Immediate Improvements
1. **Organization**: Clear separation of rollback, backup, and maintenance concerns
2. **Maintainability**: Easier to modify specific rollback functionality
3. **Testability**: Components can be tested independently
4. **Error Handling**: Centralized error management and validation

### Long-term Advantages
1. **Extensibility**: Easy addition of new rollback features
2. **Monitoring**: Better tracking of rollback operations and performance
3. **Reliability**: Improved validation and integrity checking
4. **Automation**: Support for scheduled maintenance and cleanup

## Migration Strategy

### Phase 1: Core Infrastructure (Week 1)
1. Create RollbackEngine main class and basic structure
2. Extract RollbackOperationsManager with point creation and rollback
3. Maintain backward compatibility with function wrappers

### Phase 2: Backup System (Week 2)
1. Extract BackupManager with storage and retrieval
2. Implement comprehensive backup validation
3. Add backup restoration capabilities

### Phase 3: Maintenance and Cleanup (Week 3)
1. Extract RollbackMaintenanceManager with cleanup operations
2. Implement optimization and reporting features
3. Add scheduled maintenance capabilities

## Risk Assessment

### Low Risk
- **Function Compatibility**: Existing API can be maintained through wrappers
- **Database Operations**: Well-defined database interactions

### Medium Risk
- **Memory Integration**: Tight coupling with memory_manager module
- **Scene Dependencies**: Dependencies on scene_logger functionality

### High Risk
- **Data Migration**: Ensuring rollback data integrity during refactoring
- **Backward Compatibility**: Maintaining exact function behavior for existing users

## Conclusion

The `rollback_engine.py` module represents a clean, focused system that would benefit from lightweight class-based organization. The proposed architecture separates rollback operations, backup management, and maintenance concerns into focused components while maintaining all current functionality through backward-compatible wrappers.

This refactoring would enable better organization through clear component separation, improved maintainability through focused responsibilities, and provide a foundation for enhanced rollback features and automation in future development.
