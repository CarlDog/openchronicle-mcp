# Refactoring & Deduplication Recommendations: scene_logger.py

## Overview
`scene_logger.py` is a large module (521 lines) responsible for saving, loading, querying, and managing scenes in the OpenChronicle database. It handles structured tagging, token usage, mood tracking, and provides various query utilities.

## Key Observations
- **Monolithic Structure**: All scene-related logic is in a single file, mixing database operations, token management, structured tagging, and analytics.
- **Repeated Patterns**: Many functions repeat similar patterns for database initialization, query execution, and JSON parsing.
- **Structured Tags Handling**: Building and parsing `structured_tags` is duplicated across multiple functions.
- **Query Utilities**: Functions for filtering by mood, type, label, etc., share similar logic and could be generalized.
- **Error Handling**: JSON decode errors and database exceptions are handled in many places, often with similar code.
- **Logging**: Logging is scattered and could be centralized for consistency.

## Refactoring Opportunities
1. **Extract Database Utilities**
   - Move repeated database initialization and query logic to a helper module/class.
   - Use a `SceneRepository` class to encapsulate all DB operations.

2. **Centralize Structured Tag Handling**
   - Create utility functions/classes for building, updating, and parsing `structured_tags`.
   - Reduce duplication in extracting mood, type, token usage, etc.

3. **Generalize Query Functions**
   - Merge similar query functions (by mood, type, label) into a single, parameterized function.
   - Use filter objects or keyword arguments for flexible querying.

4. **Modularize Analytics**
   - Move analytics/statistics functions (token usage, summary stats) to a dedicated analytics module.

5. **Improve Error Handling**
   - Use decorators or context managers for consistent error handling and logging.

6. **Logging Consistency**
   - Centralize logging calls and ensure all major actions/events are logged in a uniform way.

## Example Extraction Plan
- `scene_logger.py` (core logic, entry points)
- `scene_repository.py` (database operations)
- `scene_tags.py` (structured tag utilities)
- `scene_analytics.py` (statistics and reporting)
- `scene_filters.py` (query/filter logic)

## Next Steps
1. Identify and extract repeated code into utility modules.
2. Refactor query functions to use generalized filtering.
3. Move analytics/statistics to a separate module.
4. Document new module boundaries and update tests.

---
*For project status, see `.copilot/project_status.json`. Update this document as refactoring progresses.*
