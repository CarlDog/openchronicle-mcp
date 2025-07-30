# Scene Logger Refactoring Recommendation

## Current Module Overview

**File**: `core/scene_logger.py` (536 lines)  
**Purpose**: Manages the storage, retrieval, and analysis of story scenes and their associated metadata.

**Current Structure**:
- Collection of module-level functions for scene management
- No classes, but a procedural design with shared database access
- Heavy reliance on structured_tags for storing metadata
- Multiple query functions for different types of scene analysis

**Key Functionality**:
- Scene creation and storage
- Scene retrieval with various filters
- Token usage tracking and statistics
- Character mood timeline tracking
- Scene labeling and organization

## Issues Identified

1. **Procedural Design**: The module consists of standalone functions without object organization
2. **Database Coupling**: Functions directly invoke database operations with repeated init_database calls
3. **Code Duplication**: Similar SQL queries and JSON parsing patterns repeated across functions
4. **Error Handling**: Inconsistent error handling across functions
5. **Mixed Responsibilities**: Handles both storage logic and analysis in the same module
6. **Primitive Function Parameters**: Many functions have long parameter lists rather than structured objects

## Refactoring Recommendations

### 1. Convert to Package Structure

Convert the file into a package with dedicated modules:

```
core/
  scene_logger/
    __init__.py           # Public API exports
    storage.py            # Scene storage operations
    retrieval.py          # Scene retrieval operations
    analysis.py           # Scene analysis and statistics
    models.py             # Data models for scenes and tags
    utils.py              # Utility functions
```

### 2. Implement Class-Based Architecture

Create a proper class hierarchy for better organization:

```python
# models.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional

@dataclass
class SceneMetadata:
    """Model for scene metadata and structured tags."""
    scene_id: str
    timestamp: datetime
    scene_label: Optional[str] = None
    mood: str = "neutral"
    scene_type: str = "dialogue"
    content_type: str = "general"
    token_usage: Dict[str, Any] = field(default_factory=dict)
    character_moods: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    @classmethod
    def from_structured_tags(cls, scene_id: str, timestamp: str, 
                             structured_tags: Dict[str, Any], scene_label: Optional[str] = None):
        # Implementation...
    
    def to_structured_tags(self) -> Dict[str, Any]:
        # Implementation...

@dataclass
class Scene:
    """Model for a complete scene."""
    scene_id: str
    timestamp: datetime
    input: str
    output: str
    metadata: SceneMetadata
    memory_snapshot: Dict[str, Any] = field(default_factory=dict)
    flags: List[str] = field(default_factory=list)
    canon_refs: List[str] = field(default_factory=list)
    analysis_data: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]):
        # Implementation...
    
    def to_db_values(self) -> tuple:
        # Implementation...
```

### 3. Create a Proper SceneLogger Class

Implement a main class for scene management:

```python
# storage.py
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from .models import Scene, SceneMetadata

class SceneLogger:
    """Manages scene storage and retrieval."""
    
    def __init__(self, story_id: str, token_manager=None):
        self.story_id = story_id
        self.token_manager = token_manager
        self._init_database()
    
    def _init_database(self):
        from ..database import init_database
        init_database(self.story_id)
    
    def save_scene(self, user_input: str, model_output: str, 
                   memory_snapshot: Optional[Dict] = None, 
                   flags: Optional[List] = None,
                   context_refs: Optional[List] = None, 
                   analysis_data: Optional[Dict] = None,
                   scene_label: Optional[str] = None,
                   model_name: Optional[str] = None,
                   structured_tags: Optional[Dict] = None) -> str:
        """Save a scene to the database."""
        # Implementation that creates and saves a Scene object
    
    def load_scene(self, scene_id: str) -> Scene:
        """Load a scene from the database."""
        # Implementation...
    
    def update_scene_label(self, scene_id: str, scene_label: str) -> bool:
        """Update the label for a specific scene."""
        # Implementation...
    
    def list_scenes(self) -> List[SceneMetadata]:
        """List all scene metadata for the story."""
        # Implementation...
```

### 4. Create Dedicated Query Service

Create a separate service for complex scene queries:

```python
# retrieval.py
from typing import Dict, List, Any, Optional
from .models import Scene, SceneMetadata

class SceneQueryService:
    """Handles complex scene queries and filtering."""
    
    def __init__(self, story_id: str):
        self.story_id = story_id
        self._init_database()
    
    def _init_database(self):
        from ..database import init_database
        init_database(self.story_id)
    
    def get_scenes_by_mood(self, mood: str) -> List[Scene]:
        """Get scenes filtered by mood."""
        # Implementation...
    
    def get_scenes_by_type(self, scene_type: str) -> List[Scene]:
        """Get scenes filtered by scene type."""
        # Implementation...
    
    def get_scenes_by_label(self, scene_label: str) -> List[Scene]:
        """Get all scenes with a specific label."""
        # Implementation...
    
    def get_scenes_with_long_turns(self) -> List[Scene]:
        """Get all scenes that were flagged as long turns."""
        # Implementation...
    
    def get_character_mood_timeline(self, character_name: str) -> List[Dict[str, Any]]:
        """Get character mood changes over time."""
        # Implementation...
```

### 5. Create Analysis Service

Separate analysis functions into their own service:

```python
# analysis.py
from typing import Dict, List, Any, Optional

class SceneAnalysisService:
    """Provides analysis and statistics for scenes."""
    
    def __init__(self, story_id: str):
        self.story_id = story_id
        self._init_database()
    
    def _init_database(self):
        from ..database import init_database
        init_database(self.story_id)
    
    def get_token_usage_stats(self) -> Dict[str, Any]:
        """Get token usage statistics for a story."""
        # Implementation...
    
    def get_scene_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics about scenes with structured tags."""
        # Implementation...
    
    def analyze_scene_trends(self) -> Dict[str, Any]:
        """Analyze trends across scenes in the story."""
        # Implementation...
```

### 6. Implement Proper Database Interaction

Create a dedicated repository pattern for database operations:

```python
# utils.py
from typing import Dict, List, Any, Optional, Tuple
from ..database import execute_query, execute_update

class SceneRepository:
    """Handles database operations for scenes."""
    
    def __init__(self, story_id: str):
        self.story_id = story_id
        self._init_database()
    
    def _init_database(self):
        from ..database import init_database
        init_database(self.story_id)
    
    def insert_scene(self, scene_values: Tuple) -> None:
        """Insert a scene into the database."""
        # Implementation...
    
    def update_scene(self, scene_id: str, field: str, value: Any) -> bool:
        """Update a specific field in a scene."""
        # Implementation...
    
    def get_scene(self, scene_id: str) -> Dict[str, Any]:
        """Get a scene by ID."""
        # Implementation...
    
    def query_scenes(self, query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """Execute a custom query for scenes."""
        # Implementation...
```

### 7. Simplify the Public API

Create a clean, streamlined API in the __init__.py:

```python
# __init__.py
from .storage import SceneLogger
from .retrieval import SceneQueryService
from .analysis import SceneAnalysisService
from .models import Scene, SceneMetadata

# Legacy function wrappers for backward compatibility
def save_scene(story_id, user_input, model_output, **kwargs):
    logger = SceneLogger(story_id)
    return logger.save_scene(user_input, model_output, **kwargs)

def load_scene(story_id, scene_id):
    logger = SceneLogger(story_id)
    return logger.load_scene(scene_id)

# Export main classes
__all__ = [
    'SceneLogger', 'SceneQueryService', 'SceneAnalysisService',
    'Scene', 'SceneMetadata', 
    # Legacy functions
    'save_scene', 'load_scene'
]
```

## Implementation Steps

1. **Create Package Structure**: Set up the directory and file structure
2. **Implement Data Models**: Create Scene and SceneMetadata classes
3. **Implement SceneLogger**: Create the primary class for scene management
4. **Implement Query Service**: Create the service for complex queries
5. **Implement Analysis Service**: Create the service for scene analysis
6. **Add Compatibility Layer**: Create wrappers for backward compatibility
7. **Update Dependencies**: Update code that depends on scene_logger

## Benefits of Refactoring

1. **Improved Organization**: Clear separation of concerns with dedicated classes
2. **Better Maintainability**: Smaller, focused modules with specific responsibilities
3. **Reduced Duplication**: Centralized database operations and error handling
4. **Enhanced Testability**: Classes can be tested in isolation with mock dependencies
5. **Improved API**: Cleaner interface with proper object models
6. **Better Type Safety**: Comprehensive type hints throughout the codebase
7. **Simplified Error Handling**: Consistent approach to error management

## Additional Recommendations

1. **Error Strategy**: Implement consistent error handling using custom exceptions
2. **Database Abstraction**: Consider further abstracting database operations
3. **Caching**: Add caching for frequently accessed scenes or statistics
4. **Pagination**: Implement pagination for queries that could return many scenes
5. **Bulk Operations**: Add support for bulk scene operations
6. **Documentation**: Add comprehensive docstrings for all classes and methods
7. **Testing**: Create dedicated test files for each component

By implementing these refactoring suggestions, the scene_logger module will be transformed into a well-organized, maintainable package that adheres to modern Python best practices while preserving all existing functionality.
