# Refactoring & Deduplication Recommendations: bookmark_manager.py

## Overview
`bookmark_manager.py` implements a `BookmarkManager` class for managing scene bookmarks and navigation markers. It provides CRUD operations, filtering, searching, and statistics for bookmarks.

## Key Observations
- **Single Class Structure**: All logic is contained in one class, which is good for encapsulation but can be split for clarity and testability.
- **Repeated Query Patterns**: SQL query construction and execution are repeated across methods, especially for filtering and searching.
- **Metadata Handling**: JSON encoding/decoding of metadata is performed in multiple places.
- **Type Validation**: Bookmark type validation logic is duplicated in several methods.
- **Formatting**: The `_format_bookmark` method is used repeatedly; could be a static utility or moved to a helper module.
- **Statistics & Analytics**: Methods for stats and chapter structure could be extracted to a separate analytics/helper class.

## Refactoring Opportunities
1. **Extract Query Utilities**
   - Move SQL query construction and execution to a helper or repository class.
   - Use parameterized methods for filtering/searching to reduce duplication.

2. **Centralize Metadata Handling**
   - Create utility functions for encoding/decoding metadata.
   - Reduce repeated `json.loads`/`json.dumps` calls.

3. **Type Validation Utility**
   - Move bookmark type validation to a static method or external utility.

4. **Split Analytics/Stats**
   - Extract statistics and chapter structure logic to a dedicated analytics/helper module.

5. **Improve Formatting**
   - Make `_format_bookmark` a static method or move to a utility module for reuse.

## Example Extraction Plan
- `bookmark_manager.py` (core class, entry points)
- `bookmark_repository.py` (database/query operations)
- `bookmark_utils.py` (metadata and type validation)
- `bookmark_analytics.py` (statistics and chapter structure)

## Next Steps
1. Identify repeated code and extract to utility modules.
2. Refactor query and filtering logic for maintainability.
3. Move analytics/statistics to a separate module.
4. Document new module boundaries and update tests.

---
*For project status, see `.copilot/project_status.json`. Update this document as refactoring progresses.*
