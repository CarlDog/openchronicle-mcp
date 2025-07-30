# Refactoring & Deduplication Recommendations: database.py

## Overview
`database.py` provides SQLite database management for OpenChronicle, including schema initialization, query/update/insert helpers, migration from JSON, FTS5 indexing, and statistics.

## Key Observations
- **Procedural Structure**: All logic is implemented as standalone functions, which could be grouped for clarity and maintainability.
- **Repeated Patterns**: Database path resolution, connection management, and query execution are repeated across functions.
- **Schema Management**: Table/column creation and migration logic is embedded in `init_database`, making it complex and hard to test.
- **FTS5 Indexing**: FTS5 triggers and optimization logic are tightly coupled to schema management.
- **Migration & Cleanup**: Migration from JSON and cleanup logic are procedural and could be modularized.
- **Statistics & Optimization**: Stats, optimization, and rebuild logic are scattered and could be grouped.

## Refactoring Opportunities
1. **Extract Connection & Path Utilities**
   - Move database path resolution and connection management to a helper class/module.
   - Use a `DatabaseManager` class to encapsulate connection and schema logic.

2. **Modularize Schema Management**
   - Move table/column creation and migration logic to dedicated schema management modules.
   - Separate FTS5 indexing and trigger logic for clarity.

3. **Group Migration & Cleanup**
   - Extract migration and cleanup logic to a dedicated migration module/class.

4. **Centralize Statistics & Optimization**
   - Move stats, optimization, and rebuild logic to a database analytics/helper module.

5. **Improve Error Handling**
   - Use decorators or context managers for consistent error handling and logging.

## Example Extraction Plan
- `database.py` (core logic, entry points)
- `database_manager.py` (connection and schema management)
- `database_migration.py` (migration and cleanup)
- `database_fts.py` (FTS5 indexing and triggers)
- `database_analytics.py` (statistics and optimization)

## Next Steps
1. Identify repeated code and extract to utility modules.
2. Refactor schema, migration, and analytics logic for maintainability.
3. Move FTS5 and error handling to separate modules.
4. Document new module boundaries and update tests.

---
*For project status, see `.copilot/project_status.json`. Update this document as refactoring progresses.*
