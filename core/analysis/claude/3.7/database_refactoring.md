# Database Module Refactoring Recommendation

## Current Module Overview

**File**: `core/database.py` (479 lines)  
**Purpose**: Provides SQLite database functionality for storing and retrieving story data, with advanced features like FTS5 full-text search support.

**Key Components**:
1. **Database Initialization** - Functions to set up database tables and indexes
2. **Connection Management** - Functions to establish and use database connections
3. **Query Execution** - Functions to execute various types of SQL operations
4. **Data Migration** - Functions to migrate from JSON files to SQLite
5. **FTS5 Support** - Functions to manage full-text search capabilities
6. **Statistics** - Functions to gather database statistics

**Current Structure**:
- Collection of module-level functions
- Direct SQLite operations with no abstraction layer
- Global connection management
- Mixed responsibilities (initialization, querying, migration, optimization)

## Issues Identified

1. **Procedural Design**: The module consists entirely of standalone functions without object organization
2. **Global State**: Connections are created and managed globally without proper encapsulation
3. **Mixed Responsibilities**: Initialization, querying, migration, and optimization are all in the same module
4. **Error Handling**: Inconsistent error handling across different functions
5. **Connection Management**: Database connections are created frequently rather than being pooled or reused
6. **Code Duplication**: Similar SQL operations are repeated across functions
7. **Configuration Hardcoding**: Database paths and settings are partially hardcoded

## Refactoring Recommendations

### 1. Convert to Package Structure

Convert the file into a package with dedicated modules:

```
core/
  database/
    __init__.py              # Public API exports
    connection.py            # Connection management
    schema.py                # Database schema and initialization
    query.py                 # Query execution utilities
    migration.py             # Data migration utilities
    fts.py                   # Full-text search functionality
    stats.py                 # Database statistics functions
    config.py                # Database configuration
```

### 2. Implement Class-Based Connection Management

Create a proper connection manager class:

```python
# connection.py
import sqlite3
from typing import Dict, Optional, Any
from pathlib import Path
import threading
from .config import DatabaseConfig

class ConnectionManager:
    """Manages SQLite connections for different stories."""
    
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls) -> 'ConnectionManager':
        """Get singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance
    
    def __init__(self):
        """Initialize connection manager."""
        self.connections: Dict[str, sqlite3.Connection] = {}
        self.config = DatabaseConfig()
    
    def get_connection(self, story_id: str, is_test: bool = False) -> sqlite3.Connection:
        """Get a database connection for a story."""
        connection_key = f"{story_id}_{is_test}"
        
        # Return existing connection if available
        if connection_key in self.connections:
            return self.connections[connection_key]
        
        # Create new connection
        db_path = self.config.get_db_path(story_id, is_test)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        
        # Store connection
        self.connections[connection_key] = conn
        return conn
    
    def close_connection(self, story_id: str, is_test: bool = False) -> None:
        """Close a specific database connection."""
        connection_key = f"{story_id}_{is_test}"
        if connection_key in self.connections:
            self.connections[connection_key].close()
            del self.connections[connection_key]
    
    def close_all_connections(self) -> None:
        """Close all database connections."""
        for conn in self.connections.values():
            conn.close()
        self.connections.clear()
```

### 3. Create Configuration Class

Extract configuration into a dedicated class:

```python
# config.py
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

class DatabaseConfig:
    """Database configuration settings."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize database configuration."""
        self.config: Dict[str, Any] = {}
        
        # Default settings
        self.config['storage_dir'] = "storage"
        self.config['test_data_dir'] = os.path.join("storage", "temp", "test_data")
        self.config['production_data_dir'] = os.path.join("storage", "storypacks")
        self.config['db_filename'] = "openchronicle.db"
        
        # Load custom settings if provided
        if config_path and os.path.exists(config_path):
            self._load_config(config_path)
    
    def _load_config(self, config_path: str) -> None:
        """Load configuration from file."""
        import json
        with open(config_path, 'r', encoding='utf-8') as f:
            custom_config = json.load(f)
            self.config.update(custom_config)
    
    def get_db_path(self, story_id: str, is_test: bool = False) -> str:
        """Get the path to the SQLite database for a story."""
        if is_test is None:
            is_test = self._is_test_context()
        
        if is_test:
            # Test data goes in temp folder
            return os.path.join(
                self.config['test_data_dir'], 
                story_id, 
                self.config['db_filename']
            )
        else:
            # Production data goes in storypacks
            return os.path.join(
                self.config['production_data_dir'], 
                story_id, 
                self.config['db_filename']
            )
    
    def _is_test_context(self) -> bool:
        """Detect if we're running in a test context."""
        return 'pytest' in sys.modules or 'unittest' in sys.modules
```

### 4. Create Schema Manager

Extract schema management into a dedicated class:

```python
# schema.py
import sqlite3
from typing import List, Dict, Any, Optional
from .connection import ConnectionManager

class SchemaManager:
    """Manages database schema creation and updates."""
    
    def __init__(self, connection_manager: Optional[ConnectionManager] = None):
        """Initialize schema manager."""
        self.connection_manager = connection_manager or ConnectionManager.get_instance()
    
    def init_database(self, story_id: str, is_test: bool = False) -> None:
        """Initialize the database with required tables."""
        conn = self.connection_manager.get_connection(story_id, is_test)
        cursor = conn.cursor()
        
        # Create tables
        self._create_scenes_table(cursor)
        self._create_memory_table(cursor)
        self._create_memory_history_table(cursor)
        self._create_rollback_tables(cursor)
        self._create_bookmarks_table(cursor)
        
        # Create indexes
        self._create_indexes(cursor)
        
        # Create FTS tables if supported
        if self._has_fts5_support():
            self._create_fts_tables(cursor)
            self._create_fts_triggers(cursor)
            self._populate_fts_tables(cursor)
        
        conn.commit()
    
    def _create_scenes_table(self, cursor: sqlite3.Cursor) -> None:
        """Create scenes table."""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scenes (
                scene_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                input TEXT NOT NULL,
                output TEXT NOT NULL,
                memory_snapshot TEXT,
                flags TEXT,
                canon_refs TEXT,
                analysis TEXT,
                scene_label TEXT,
                structured_tags TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    
    def _create_memory_table(self, cursor: sqlite3.Cursor) -> None:
        """Create memory table."""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                story_id TEXT NOT NULL,
                type TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(story_id, type, key)
            )
        ''')
    
    # Additional methods for creating other tables, indexes, and FTS components...
    
    def check_and_update_schema(self, story_id: str, is_test: bool = False) -> List[str]:
        """Check if schema needs updates and apply them."""
        conn = self.connection_manager.get_connection(story_id, is_test)
        cursor = conn.cursor()
        
        updates_applied = []
        
        # Check for missing columns in scenes table
        cursor.execute("PRAGMA table_info(scenes)")
        columns = {column[1] for column in cursor.fetchall()}
        
        if 'analysis' not in columns:
            cursor.execute('ALTER TABLE scenes ADD COLUMN analysis TEXT')
            updates_applied.append("Added analysis column to scenes table")
        
        if 'scene_label' not in columns:
            cursor.execute('ALTER TABLE scenes ADD COLUMN scene_label TEXT')
            updates_applied.append("Added scene_label column to scenes table")
        
        if 'structured_tags' not in columns:
            cursor.execute('ALTER TABLE scenes ADD COLUMN structured_tags TEXT')
            updates_applied.append("Added structured_tags column to scenes table")
        
        conn.commit()
        return updates_applied
    
    def _has_fts5_support(self) -> bool:
        """Check if SQLite supports FTS5."""
        try:
            with sqlite3.connect(':memory:') as conn:
                cursor = conn.cursor()
                cursor.execute("CREATE VIRTUAL TABLE test_fts USING fts5(content)")
                cursor.execute("DROP TABLE test_fts")
                return True
        except sqlite3.OperationalError:
            return False
```

### 5. Create Query Manager

Extract query execution into a dedicated class:

```python
# query.py
import sqlite3
from typing import List, Dict, Any, Optional, Tuple, Union
from .connection import ConnectionManager

class QueryManager:
    """Manages database queries and transactions."""
    
    def __init__(self, connection_manager: Optional[ConnectionManager] = None):
        """Initialize query manager."""
        self.connection_manager = connection_manager or ConnectionManager.get_instance()
    
    def execute_query(self, story_id: str, query: str, 
                     params: Optional[Union[Tuple, Dict]] = None, 
                     is_test: bool = False) -> List[sqlite3.Row]:
        """Execute a query and return results."""
        conn = self.connection_manager.get_connection(story_id, is_test)
        cursor = conn.cursor()
        
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchall()
        except sqlite3.Error as e:
            # Log error
            raise DatabaseError(f"Query execution failed: {e}") from e
    
    def execute_update(self, story_id: str, query: str, 
                      params: Optional[Union[Tuple, Dict]] = None, 
                      is_test: bool = False) -> int:
        """Execute an update/insert query and return affected rows."""
        conn = self.connection_manager.get_connection(story_id, is_test)
        cursor = conn.cursor()
        
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            return cursor.rowcount
        except sqlite3.Error as e:
            conn.rollback()
            # Log error
            raise DatabaseError(f"Update execution failed: {e}") from e
    
    def execute_insert(self, story_id: str, query: str, 
                      params: Optional[Union[Tuple, Dict]] = None, 
                      is_test: bool = False) -> int:
        """Execute an insert query and return the last row ID."""
        conn = self.connection_manager.get_connection(story_id, is_test)
        cursor = conn.cursor()
        
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            conn.rollback()
            # Log error
            raise DatabaseError(f"Insert execution failed: {e}") from e
    
    def execute_transaction(self, story_id: str, queries: List[Dict[str, Any]], 
                           is_test: bool = False) -> bool:
        """Execute multiple queries in a single transaction."""
        conn = self.connection_manager.get_connection(story_id, is_test)
        cursor = conn.cursor()
        
        try:
            for query_data in queries:
                query = query_data["query"]
                params = query_data.get("params")
                
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            conn.rollback()
            # Log error
            raise DatabaseError(f"Transaction execution failed: {e}") from e

class DatabaseError(Exception):
    """Custom exception for database errors."""
    pass
```

### 6. Create Full-Text Search Manager

Extract FTS functionality into a dedicated class:

```python
# fts.py
from typing import Dict, Any, Optional, List
from .connection import ConnectionManager

class FullTextSearchManager:
    """Manages full-text search functionality."""
    
    def __init__(self, connection_manager: Optional[ConnectionManager] = None):
        """Initialize FTS manager."""
        self.connection_manager = connection_manager or ConnectionManager.get_instance()
    
    def optimize_fts_index(self, story_id: str, is_test: bool = False) -> None:
        """Optimize FTS5 indexes for better performance."""
        conn = self.connection_manager.get_connection(story_id, is_test)
        cursor = conn.cursor()
        
        # Optimize scenes FTS5 index
        cursor.execute("INSERT INTO scenes_fts(scenes_fts) VALUES('optimize')")
        
        # Optimize memory FTS5 index
        cursor.execute("INSERT INTO memory_fts(memory_fts) VALUES('optimize')")
        
        conn.commit()
    
    def rebuild_fts_index(self, story_id: str, is_test: bool = False) -> None:
        """Rebuild FTS5 indexes from scratch."""
        conn = self.connection_manager.get_connection(story_id, is_test)
        cursor = conn.cursor()
        
        # Rebuild scenes FTS5 index
        cursor.execute("INSERT INTO scenes_fts(scenes_fts) VALUES('rebuild')")
        
        # Rebuild memory FTS5 index
        cursor.execute("INSERT INTO memory_fts(memory_fts) VALUES('rebuild')")
        
        conn.commit()
    
    def get_fts_stats(self, story_id: str, is_test: bool = False) -> Dict[str, Any]:
        """Get FTS5 index statistics."""
        conn = self.connection_manager.get_connection(story_id, is_test)
        cursor = conn.cursor()
        
        stats = {}
        
        # Check if FTS5 tables exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name LIKE '%_fts'
        """)
        fts_tables = [row[0] for row in cursor.fetchall()]
        stats['fts_tables'] = fts_tables
        
        # Get FTS5 table sizes
        for table in fts_tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[f'{table}_entries'] = cursor.fetchone()[0]
        
        return stats
    
    def search_scenes(self, story_id: str, query: str, limit: int = 20, 
                     is_test: bool = False) -> List[Dict[str, Any]]:
        """Search scenes using FTS5."""
        conn = self.connection_manager.get_connection(story_id, is_test)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT s.scene_id, s.timestamp, s.input, s.output, s.scene_label,
                   highlight(scenes_fts, 0, '<mark>', '</mark>') as input_highlight,
                   highlight(scenes_fts, 1, '<mark>', '</mark>') as output_highlight,
                   rank
            FROM scenes_fts 
            JOIN scenes s ON scenes_fts.rowid = s.rowid
            WHERE scenes_fts MATCH ? 
            ORDER BY rank
            LIMIT ?
        ''', (query, limit))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'scene_id': row['scene_id'],
                'timestamp': row['timestamp'],
                'input': row['input'],
                'output': row['output'],
                'scene_label': row['scene_label'],
                'input_highlight': row['input_highlight'],
                'output_highlight': row['output_highlight'],
                'rank': row['rank']
            })
        
        return results
```

### 7. Simplify the Public API

Create a clean, streamlined API in the __init__.py:

```python
# __init__.py
from .connection import ConnectionManager
from .schema import SchemaManager
from .query import QueryManager, DatabaseError
from .fts import FullTextSearchManager
from .migration import MigrationManager
from .stats import StatsManager
from .config import DatabaseConfig

# Create default instances
connection_manager = ConnectionManager.get_instance()
schema_manager = SchemaManager(connection_manager)
query_manager = QueryManager(connection_manager)
fts_manager = FullTextSearchManager(connection_manager)
migration_manager = MigrationManager(connection_manager, query_manager)
stats_manager = StatsManager(connection_manager)

# Legacy function wrappers for backward compatibility
def init_database(story_id, is_test=None):
    """Initialize the database with required tables."""
    schema_manager.init_database(story_id, is_test)

def get_connection(story_id, is_test=None):
    """Get a database connection for a story."""
    return connection_manager.get_connection(story_id, is_test)

def execute_query(story_id, query, params=None, is_test=None):
    """Execute a query and return results."""
    return query_manager.execute_query(story_id, query, params, is_test)

def execute_update(story_id, query, params=None, is_test=None):
    """Execute an update/insert query."""
    return query_manager.execute_update(story_id, query, params, is_test)

def execute_insert(story_id, query, params=None, is_test=None):
    """Execute an insert query and return the last row ID."""
    return query_manager.execute_insert(story_id, query, params, is_test)

# Export public API
__all__ = [
    'ConnectionManager', 'SchemaManager', 'QueryManager', 'DatabaseError',
    'FullTextSearchManager', 'MigrationManager', 'StatsManager', 'DatabaseConfig',
    'connection_manager', 'schema_manager', 'query_manager', 'fts_manager',
    'migration_manager', 'stats_manager',
    # Legacy functions
    'init_database', 'get_connection', 'execute_query', 'execute_update', 'execute_insert'
]
```

## Implementation Strategy

1. **Create Package Structure**: Set up the directory and file structure
2. **Implement Connection Manager**: Create the connection management class
3. **Implement Config Class**: Extract configuration settings
4. **Implement Schema Manager**: Create the schema management class
5. **Implement Query Manager**: Create the query execution class
6. **Implement FTS Manager**: Create the full-text search class
7. **Create Migration & Stats Classes**: Extract remaining functionality
8. **Add Backward Compatibility**: Create wrappers for existing functions

## Benefits of Refactoring

1. **Improved Organization**: Clear separation of concerns with dedicated classes
2. **Better Connection Management**: Proper connection pooling and lifecycle management
3. **Enhanced Error Handling**: Consistent error handling with custom exceptions
4. **Cleaner API**: Well-defined interfaces for different database operations
5. **Improved Testability**: Components can be tested in isolation with mock dependencies
6. **Configuration Flexibility**: Centralized configuration with customization options
7. **Performance Improvements**: Better connection reuse and management

## Migration Approach

1. **Staged Implementation**: Implement the new package while keeping the old module
2. **Compatibility Layer**: Provide wrappers for existing functions
3. **Gradual Adoption**: Update dependencies to use the new API incrementally
4. **Parallel Operation**: Run old and new implementations side by side during transition
5. **Testing**: Comprehensive testing to ensure identical behavior
6. **Final Switchover**: Remove legacy implementation once all dependencies are updated

By following this refactoring plan, the database module will be transformed into a well-structured, maintainable package that adheres to modern Python best practices while preserving all existing functionality.
