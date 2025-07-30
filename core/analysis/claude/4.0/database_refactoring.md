# Database Module Refactoring Analysis

**File**: `core/database.py`  
**Size**: 479 lines  
**Complexity**: MEDIUM  
**Priority**: MEDIUM

## Executive Summary

The `database.py` module is a comprehensive SQLite database management system that handles database initialization, FTS5 full-text search setup, migration from JSON, and various database operations. While functionally complete with sophisticated features like FTS5 indexing and automatic triggers, it suffers from architectural violations by mixing database schema management, connection handling, query execution, migration logic, and FTS5 management in a single module with 16 separate functions. This analysis proposes a modular class-based architecture to improve maintainability and extensibility.

## Current Architecture Analysis

### Core Components
1. **16 Standalone Functions**: All database operations implemented as module-level functions
2. **Mixed Responsibilities**: Schema management + connection handling + query execution + migration + FTS5 operations
3. **Complex Schema**: 6 tables with sophisticated FTS5 indexing, triggers, and performance optimizations
4. **Advanced Features**: Test context detection, JSON migration, FTS5 optimization, statistical reporting

### Current Responsibilities
- **Schema Management**: Database initialization, table creation, index management, trigger setup
- **Connection Management**: Database connection handling with test context detection
- **Query Execution**: SQL execution wrappers for queries, updates, and inserts
- **Migration System**: JSON to SQLite migration with cleanup functionality
- **FTS5 Management**: Full-text search setup, optimization, rebuilding, and statistics
- **Database Operations**: Path management, directory creation, statistics generation
- **Test Support**: Test context detection and separate test database handling

## Major Refactoring Opportunities

### 1. Database Schema Management (Critical Priority)

**Problem**: Schema initialization, table creation, and index management mixed in single function
```python
def init_database(story_id, is_test=None):
    # 200+ lines mixing table creation, trigger setup, index creation, and FTS5 configuration
```

**Solution**: Extract to SchemaManager
```python
class SchemaManager:
    """Manages database schema creation and evolution."""
    
    def __init__(self):
        self.table_definitions = TableDefinitionRegistry()
        self.index_manager = IndexManager()
        self.trigger_manager = TriggerManager()
        self.migration_manager = SchemaMigrationManager()
        
    def initialize_schema(self, connection: sqlite3.Connection) -> SchemaInitResult:
        """Initialize complete database schema."""
        
    def create_tables(self, connection: sqlite3.Connection) -> None:
        """Create all required tables."""
        
    def create_indexes(self, connection: sqlite3.Connection) -> None:
        """Create all performance indexes."""
        
    def setup_triggers(self, connection: sqlite3.Connection) -> None:
        """Setup automatic FTS5 synchronization triggers."""
        
    def migrate_schema(self, connection: sqlite3.Connection, 
                      from_version: int, to_version: int) -> MigrationResult:
        """Migrate schema between versions."""

class TableDefinitionRegistry:
    """Registry of table definitions."""
    
    def __init__(self):
        self.tables = {
            'scenes': ScenesTableDefinition(),
            'memory': MemoryTableDefinition(),
            'memory_history': MemoryHistoryTableDefinition(),
            'rollback_points': RollbackPointsTableDefinition(),
            'rollback_backups': RollbackBackupsTableDefinition(),
            'bookmarks': BookmarksTableDefinition()
        }
        
    def get_table_definition(self, table_name: str) -> TableDefinition:
        """Get table definition by name."""
        
    def get_all_definitions(self) -> Dict[str, TableDefinition]:
        """Get all table definitions."""
        
    def validate_schema_compatibility(self, existing_schema: Dict) -> ValidationResult:
        """Validate existing schema compatibility."""

class IndexManager:
    """Manages database indexes."""
    
    def __init__(self):
        self.index_definitions = self._load_index_definitions()
        
    def create_all_indexes(self, connection: sqlite3.Connection) -> List[IndexCreationResult]:
        """Create all performance indexes."""
        
    def create_index(self, connection: sqlite3.Connection, 
                    index_definition: IndexDefinition) -> IndexCreationResult:
        """Create specific index."""
        
    def analyze_index_usage(self, connection: sqlite3.Connection) -> IndexUsageReport:
        """Analyze index usage and performance."""
        
    def suggest_new_indexes(self, query_patterns: List[str]) -> List[IndexSuggestion]:
        """Suggest new indexes based on query patterns."""

class TriggerManager:
    """Manages database triggers."""
    
    def __init__(self):
        self.trigger_registry = TriggerRegistry()
        
    def setup_fts_triggers(self, connection: sqlite3.Connection) -> List[TriggerSetupResult]:
        """Setup FTS5 synchronization triggers."""
        
    def create_trigger(self, connection: sqlite3.Connection, 
                      trigger_def: TriggerDefinition) -> TriggerCreationResult:
        """Create specific trigger."""
        
    def validate_triggers(self, connection: sqlite3.Connection) -> TriggerValidationReport:
        """Validate all triggers are working correctly."""

@dataclass
class TableDefinition:
    """Database table definition."""
    name: str
    columns: List[ColumnDefinition]
    constraints: List[str]
    version: int = 1
    
@dataclass
class ColumnDefinition:
    """Database column definition."""
    name: str
    type: str
    nullable: bool = True
    default: Optional[str] = None
    primary_key: bool = False
    unique: bool = False

@dataclass
class IndexDefinition:
    """Database index definition."""
    name: str
    table: str
    columns: List[str]
    unique: bool = False
    partial_condition: Optional[str] = None

@dataclass
class SchemaInitResult:
    """Result of schema initialization."""
    success: bool
    tables_created: List[str]
    indexes_created: List[str]
    triggers_created: List[str]
    errors: List[str]
    warnings: List[str]
```

### 2. Connection Management System (Critical Priority)

**Problem**: Connection handling, path management, and test detection scattered across functions
```python
def get_connection(story_id, is_test=None):
    # Connection creation mixed with initialization logic

def get_db_path(story_id, is_test=None):
    # Path resolution with test context detection

def _is_test_context():
    # Test detection logic
```

**Solution**: Extract to ConnectionManager
```python
class ConnectionManager:
    """Manages database connections and paths."""
    
    def __init__(self, config: DatabaseConfig = None):
        self.config = config or DatabaseConfig()
        self.path_resolver = DatabasePathResolver(self.config)
        self.test_detector = TestContextDetector()
        self.connection_pool = ConnectionPool(self.config)
        
    def get_connection(self, story_id: str, 
                      is_test: Optional[bool] = None) -> DatabaseConnection:
        """Get database connection with automatic initialization."""
        
    def create_connection(self, story_id: str, 
                         is_test: Optional[bool] = None) -> sqlite3.Connection:
        """Create new database connection."""
        
    def ensure_database_exists(self, story_id: str, 
                              is_test: Optional[bool] = None) -> bool:
        """Ensure database exists and is initialized."""
        
    def close_all_connections(self) -> None:
        """Close all open connections."""

class DatabasePathResolver:
    """Resolves database file paths."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        
    def get_database_path(self, story_id: str, is_test: bool = False) -> Path:
        """Get database file path for story."""
        
    def ensure_directory_exists(self, db_path: Path) -> None:
        """Ensure database directory exists."""
        
    def get_backup_path(self, story_id: str, backup_id: str) -> Path:
        """Get backup file path."""
        
    def validate_path_permissions(self, db_path: Path) -> ValidationResult:
        """Validate database path permissions."""

class TestContextDetector:
    """Detects test execution context."""
    
    def is_test_context(self) -> bool:
        """Detect if running in test environment."""
        
    def get_test_indicators(self) -> List[str]:
        """Get indicators that suggest test context."""
        
    def override_test_detection(self, is_test: bool) -> None:
        """Override test detection for specific scenarios."""

class ConnectionPool:
    """Manages connection pooling and lifecycle."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.active_connections: Dict[str, sqlite3.Connection] = {}
        self.connection_stats = ConnectionStatistics()
        
    def get_pooled_connection(self, story_id: str, 
                             is_test: bool = False) -> sqlite3.Connection:
        """Get connection from pool or create new one."""
        
    def return_connection(self, story_id: str, 
                         connection: sqlite3.Connection) -> None:
        """Return connection to pool."""
        
    def cleanup_idle_connections(self) -> int:
        """Clean up idle connections."""

@dataclass
class DatabaseConfig:
    """Database configuration."""
    production_base_path: str = "storage/storypacks"
    test_base_path: str = "storage/temp/test_data"
    connection_timeout: int = 30
    enable_connection_pooling: bool = True
    max_pool_size: int = 10
    enable_wal_mode: bool = True
    enable_foreign_keys: bool = True

@dataclass
class DatabaseConnection:
    """Enhanced database connection wrapper."""
    connection: sqlite3.Connection
    story_id: str
    is_test: bool
    created_at: datetime
    
    def execute_query(self, query: str, params: Optional[Tuple] = None) -> List[sqlite3.Row]:
        """Execute query with error handling."""
        
    def execute_update(self, query: str, params: Optional[Tuple] = None) -> int:
        """Execute update with transaction management."""
        
    def begin_transaction(self) -> None:
        """Begin transaction."""
        
    def commit_transaction(self) -> None:
        """Commit transaction."""
        
    def rollback_transaction(self) -> None:
        """Rollback transaction."""
```

### 3. FTS5 Management System (High Priority)

**Problem**: FTS5 setup, optimization, and management scattered across multiple functions
```python
def optimize_fts_index(story_id, is_test=None):
    # FTS5 optimization logic

def rebuild_fts_index(story_id, is_test=None):
    # FTS5 rebuild logic

def get_fts_stats(story_id, is_test=None):
    # FTS5 statistics collection
```

**Solution**: Extract to FTSManager
```python
class FTSManager:
    """Manages FTS5 full-text search functionality."""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.fts_schema_manager = FTSSchemaManager()
        self.fts_optimizer = FTSOptimizer()
        self.fts_analyzer = FTSAnalyzer()
        
    def setup_fts_tables(self, connection: sqlite3.Connection) -> FTSSetupResult:
        """Setup all FTS5 virtual tables."""
        
    def optimize_fts_indexes(self, story_id: str, 
                           is_test: bool = False) -> FTSOptimizationResult:
        """Optimize FTS5 indexes for better performance."""
        
    def rebuild_fts_indexes(self, story_id: str, 
                          is_test: bool = False) -> FTSRebuildResult:
        """Rebuild FTS5 indexes from scratch."""
        
    def analyze_fts_performance(self, story_id: str, 
                              is_test: bool = False) -> FTSPerformanceReport:
        """Analyze FTS5 performance and usage."""
        
    def validate_fts_integrity(self, story_id: str, 
                             is_test: bool = False) -> FTSIntegrityReport:
        """Validate FTS5 data integrity."""

class FTSSchemaManager:
    """Manages FTS5 schema and virtual tables."""
    
    def __init__(self):
        self.fts_tables = {
            'scenes_fts': ScenesF̈TSDefinition(),
            'memory_fts': MemoryFTSDefinition()
        }
        
    def create_fts_table(self, connection: sqlite3.Connection,
                        fts_definition: FTSTableDefinition) -> FTSCreationResult:
        """Create FTS5 virtual table."""
        
    def populate_fts_table(self, connection: sqlite3.Connection,
                          table_name: str) -> FTSPopulationResult:
        """Populate FTS5 table with existing data."""
        
    def check_fts_support(self, connection: sqlite3.Connection) -> bool:
        """Check if FTS5 is supported."""

class FTSOptimizer:
    """Optimizes FTS5 performance."""
    
    def optimize_table(self, connection: sqlite3.Connection, 
                      table_name: str) -> OptimizationResult:
        """Optimize specific FTS5 table."""
        
    def analyze_search_patterns(self, query_log: List[str]) -> SearchPatternAnalysis:
        """Analyze search patterns for optimization opportunities."""
        
    def suggest_fts_improvements(self, performance_data: FTSPerformanceData) -> List[Improvement]:
        """Suggest FTS5 performance improvements."""

class FTSAnalyzer:
    """Analyzes FTS5 usage and performance."""
    
    def get_fts_statistics(self, connection: sqlite3.Connection) -> FTSStatistics:
        """Get comprehensive FTS5 statistics."""
        
    def measure_search_performance(self, connection: sqlite3.Connection,
                                 test_queries: List[str]) -> PerformanceMetrics:
        """Measure FTS5 search performance."""
        
    def analyze_index_fragmentation(self, connection: sqlite3.Connection) -> FragmentationReport:
        """Analyze FTS5 index fragmentation."""

@dataclass
class FTSTableDefinition:
    """FTS5 table definition."""
    name: str
    content_table: str
    indexed_columns: List[str]
    unindexed_columns: List[str]
    tokenizer: str = "unicode61"
    
@dataclass
class FTSSetupResult:
    """Result of FTS5 setup."""
    success: bool
    tables_created: List[str]
    triggers_created: List[str]
    population_results: Dict[str, FTSPopulationResult]
    errors: List[str]

@dataclass
class FTSStatistics:
    """FTS5 statistics."""
    table_counts: Dict[str, int]
    index_sizes: Dict[str, int]
    fragmentation_levels: Dict[str, float]
    last_optimization: Optional[datetime]
    performance_metrics: PerformanceMetrics
```

### 4. Migration and Cleanup System (Medium Priority)

**Problem**: JSON migration and cleanup logic embedded in single functions
```python
def migrate_from_json(story_id):
    # 80+ lines of complex migration logic

def cleanup_json_files(story_id):
    # File cleanup after migration
```

**Solution**: Extract to MigrationManager
```python
class MigrationManager:
    """Manages data migration and cleanup operations."""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.json_migrator = JSONMigrator()
        self.file_cleaner = MigrationFileCleaner()
        self.migration_validator = MigrationValidator()
        
    def migrate_from_json(self, story_id: str) -> MigrationResult:
        """Migrate JSON data to SQLite database."""
        
    def validate_migration(self, story_id: str, 
                          migration_result: MigrationResult) -> ValidationResult:
        """Validate migration completeness and integrity."""
        
    def rollback_migration(self, story_id: str, 
                          migration_id: str) -> RollbackResult:
        """Rollback failed migration."""
        
    def cleanup_after_migration(self, story_id: str, 
                              confirmed: bool = False) -> CleanupResult:
        """Clean up source files after successful migration."""

class JSONMigrator:
    """Migrates JSON data to SQLite."""
    
    def __init__(self):
        self.scene_migrator = SceneDataMigrator()
        self.memory_migrator = MemoryDataMigrator()
        self.rollback_migrator = RollbackDataMigrator()
        
    def migrate_scenes(self, story_id: str, 
                      connection: sqlite3.Connection) -> SceneMigrationResult:
        """Migrate scene data from JSON files."""
        
    def migrate_memory(self, story_id: str, 
                      connection: sqlite3.Connection) -> MemoryMigrationResult:
        """Migrate memory data from JSON files."""
        
    def migrate_rollback_data(self, story_id: str, 
                            connection: sqlite3.Connection) -> RollbackMigrationResult:
        """Migrate rollback data from JSON files."""

class MigrationFileCleaner:
    """Cleans up files after migration."""
    
    def find_migration_files(self, story_id: str) -> List[Path]:
        """Find all files eligible for cleanup."""
        
    def create_backup_before_cleanup(self, files: List[Path]) -> BackupResult:
        """Create backup before deleting files."""
        
    def cleanup_files(self, files: List[Path], 
                     create_backup: bool = True) -> CleanupResult:
        """Clean up migration files."""

@dataclass
class MigrationResult:
    """Result of data migration."""
    migration_id: str
    story_id: str
    success: bool
    migrated_counts: Dict[str, int]
    total_migrated: int
    errors: List[str]
    warnings: List[str]
    duration_seconds: float
    
@dataclass
class ValidationResult:
    """Result of migration validation."""
    is_valid: bool
    data_integrity_checks: Dict[str, bool]
    missing_data: List[str]
    corrupted_data: List[str]
    recommendations: List[str]
```

### 5. Database Operations and Statistics (Medium Priority)

**Problem**: Database operations, statistics, and utility functions scattered across module
```python
def execute_query(story_id, query, params=None, is_test=None):
    # Basic query execution

def get_database_stats(story_id, is_test=None):
    # Database statistics collection
```

**Solution**: Extract to DatabaseOperations
```python
class DatabaseOperations:
    """Handles database operations and utilities."""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.query_executor = QueryExecutor()
        self.statistics_collector = DatabaseStatisticsCollector()
        self.performance_monitor = DatabasePerformanceMonitor()
        
    def execute_query(self, story_id: str, query: str, 
                     params: Optional[Tuple] = None,
                     is_test: bool = False) -> QueryResult:
        """Execute query with comprehensive error handling."""
        
    def execute_batch_queries(self, story_id: str, 
                            queries: List[QueryDefinition],
                            is_test: bool = False) -> BatchQueryResult:
        """Execute multiple queries in transaction."""
        
    def get_database_statistics(self, story_id: str, 
                              is_test: bool = False) -> DatabaseStatistics:
        """Get comprehensive database statistics."""
        
    def analyze_database_performance(self, story_id: str, 
                                   is_test: bool = False) -> PerformanceAnalysis:
        """Analyze database performance metrics."""

class QueryExecutor:
    """Executes database queries with monitoring."""
    
    def __init__(self):
        self.query_monitor = QueryPerformanceMonitor()
        self.error_handler = QueryErrorHandler()
        
    def execute_with_monitoring(self, connection: sqlite3.Connection,
                              query: str, params: Optional[Tuple] = None) -> QueryResult:
        """Execute query with performance monitoring."""
        
    def execute_transaction(self, connection: sqlite3.Connection,
                          queries: List[QueryDefinition]) -> TransactionResult:
        """Execute multiple queries in transaction."""
        
    def validate_query_safety(self, query: str) -> QueryValidation:
        """Validate query for safety and performance."""

class DatabaseStatisticsCollector:
    """Collects comprehensive database statistics."""
    
    def collect_table_statistics(self, connection: sqlite3.Connection) -> TableStatistics:
        """Collect statistics for all tables."""
        
    def collect_index_statistics(self, connection: sqlite3.Connection) -> IndexStatistics:
        """Collect index usage and performance statistics."""
        
    def collect_storage_statistics(self, db_path: Path) -> StorageStatistics:
        """Collect storage and file system statistics."""

@dataclass
class QueryResult:
    """Result of query execution."""
    success: bool
    rows: List[sqlite3.Row]
    execution_time_ms: float
    rows_affected: int
    errors: List[str]
    
@dataclass
class DatabaseStatistics:
    """Comprehensive database statistics."""
    story_id: str
    table_counts: Dict[str, int]
    database_size_mb: float
    index_usage: Dict[str, IndexUsageStats]
    fts_statistics: FTSStatistics
    performance_metrics: PerformanceMetrics
    last_updated: datetime
```

## Proposed Modular Architecture

```python
class DatabaseManager:
    """Main orchestrator for database operations."""
    
    def __init__(self, config: DatabaseConfig = None):
        self.config = config or DatabaseConfig()
        self.connection_manager = ConnectionManager(self.config)
        self.schema_manager = SchemaManager()
        self.fts_manager = FTSManager(self.connection_manager)
        self.migration_manager = MigrationManager(self.connection_manager)
        self.operations = DatabaseOperations(self.connection_manager)
        
    def initialize_database(self, story_id: str, 
                          is_test: bool = False) -> InitializationResult:
        """Initialize database with complete setup."""
        
        connection = self.connection_manager.create_connection(story_id, is_test)
        
        # Initialize schema
        schema_result = self.schema_manager.initialize_schema(connection)
        
        # Setup FTS5
        fts_result = self.fts_manager.setup_fts_tables(connection)
        
        return InitializationResult(
            schema_result=schema_result,
            fts_result=fts_result,
            success=schema_result.success and fts_result.success
        )
    
    def get_connection(self, story_id: str, 
                      is_test: bool = False) -> DatabaseConnection:
        """Get database connection."""
        return self.connection_manager.get_connection(story_id, is_test)
    
    def execute_query(self, story_id: str, query: str, 
                     params: Optional[Tuple] = None,
                     is_test: bool = False) -> QueryResult:
        """Execute database query."""
        return self.operations.execute_query(story_id, query, params, is_test)
    
    def migrate_from_json(self, story_id: str) -> MigrationResult:
        """Migrate JSON data to database."""
        return self.migration_manager.migrate_from_json(story_id)
    
    def get_statistics(self, story_id: str, 
                      is_test: bool = False) -> DatabaseStatistics:
        """Get comprehensive database statistics."""
        return self.operations.get_database_statistics(story_id, is_test)

@dataclass
class InitializationResult:
    """Result of database initialization."""
    success: bool
    schema_result: SchemaInitResult
    fts_result: FTSSetupResult
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
```

## Implementation Benefits

### Immediate Improvements
1. **Single Responsibility**: Each class handles one aspect of database management
2. **Testability**: Components can be tested independently with mock connections
3. **Maintainability**: Changes to FTS5 management don't affect schema operations
4. **Error Handling**: Comprehensive error handling and validation throughout

### Long-term Advantages
1. **Performance**: Specialized managers can optimize specific operations
2. **Scalability**: Connection pooling and performance monitoring
3. **Extensibility**: New database features or migration types can be added easily
4. **Monitoring**: Comprehensive database performance and usage analytics

## Migration Strategy

### Phase 1: Core Infrastructure (Week 1)
1. Create DatabaseConfig and connection management system
2. Implement ConnectionManager with pooling and test detection
3. Create basic DatabaseConnection wrapper with transaction support

### Phase 2: Schema Management (Week 2)
1. Extract SchemaManager with table definitions and migration support
2. Implement IndexManager and TriggerManager
3. Create comprehensive schema validation and versioning

### Phase 3: FTS5 Management (Week 3)
1. Extract FTSManager with optimization and analysis capabilities
2. Implement FTS5 performance monitoring and tuning
3. Create FTS5 integrity validation and reporting

### Phase 4: Migration and Operations (Week 4)
1. Extract MigrationManager with JSON migration and cleanup
2. Implement DatabaseOperations with comprehensive query execution
3. Create statistics collection and performance analysis

### Phase 5: Integration and Optimization (Week 5)
1. Integrate all managers through main DatabaseManager
2. Implement comprehensive error handling and logging
3. Performance optimization and integration testing

## Risk Assessment

### Low Risk
- **Connection Management**: Well-defined connection patterns with clear interfaces
- **Query Execution**: Straightforward SQL execution wrappers

### Medium Risk
- **Schema Migration**: Complex schema evolution and backwards compatibility
- **FTS5 Management**: FTS5-specific functionality with SQLite version dependencies

### High Risk
- **Migration**: Data integrity during JSON to SQLite migration
- **Performance**: Connection pooling and transaction management complexity

## Conclusion

The `database.py` module represents a comprehensive database management system that would significantly benefit from object-oriented refactoring. The proposed architecture separates connection management, schema operations, FTS5 functionality, migration logic, and database operations into focused components while maintaining all current functionality.

This refactoring would enable better performance through connection pooling and monitoring, improved maintainability through clear separation of concerns, and provide a foundation for advanced database analytics and optimization in future development.
