# Search Engine Refactoring Recommendations

## Overview

The `search_engine.py` module (710 lines) provides advanced full-text search capabilities for OpenChronicle stories using SQLite's FTS5 virtual tables. The module is well-structured but could benefit from refactoring to improve maintainability, separation of concerns, and testability.

## Current Structure Analysis

The module currently handles several distinct responsibilities:
1. Query parsing and preparation
2. Search execution across different content types (scenes, memory)
3. Result processing and formatting
4. Search history and saved searches management
5. Performance tracking and caching
6. Export functionality in multiple formats

## Recommended Refactoring Approach

### 1. Module Splitting

Break the large file into several focused modules within a `search` package:

```powershell
# Recommended new structure
core/
  search/
    __init__.py                 # Package exports and main SearchEngine facade
    models.py                   # Data models (SearchResult, SearchQuery, etc.)
    parsers.py                  # Query parsing and FTS query building
    executors.py                # Search execution for different content types
    history.py                  # Search history and saved searches management
    exporters.py                # Result export functionality
    cache.py                    # Caching and performance tracking
```

### 2. Class Extraction

Extract key functionality into dedicated classes:

- `QueryParser`: Focused on query parsing and normalization
- `SearchExecutor`: Handles search execution against the database
- `SearchHistoryManager`: Manages search history and saved searches
- `ResultExporter`: Handles export in different formats
- `SearchCache`: Manages caching and performance tracking

### 3. Main Class Restructuring

Transform the `SearchEngine` into a facade that coordinates between specialized components:

```python
class SearchEngine:
    """Enhanced full-text search engine with FTS5 integration."""
    
    def __init__(self, story_id: str, cache_size: int = 100, history_limit: int = 10):
        """Initialize search engine for a specific story."""
        self.story_id = story_id
        self.fts_supported = check_fts_support()
        
        # Initialize specialized components
        self.parser = QueryParser()
        self.executor = SearchExecutor(story_id)
        self.history_manager = SearchHistoryManager(history_limit)
        self.exporter = ResultExporter()
        self.cache = SearchCache(cache_size)
        
        if not self.fts_supported:
            raise RuntimeError("FTS5 is not supported in this SQLite version")
    
    def search_all(self, query_string: str, limit: int = 50) -> List[SearchResult]:
        """Search across all content types with caching and performance tracking."""
        start_time = time.time()
        
        # Check cache
        cache_key = f"{query_string}::{limit}"
        cached_results = self.cache.get(cache_key)
        if cached_results:
            return cached_results
        
        # Parse query
        query = self.parser.parse_query(query_string)
        
        # Execute search
        scene_results = self.executor.search_scenes(query, limit)
        memory_results = self.executor.search_memory(query, limit)
        
        # Combine and sort results
        all_results = self._combine_and_sort_results(
            scene_results, memory_results, query.sort_order, query.limit
        )
        
        # Update cache and history
        self.cache.store(cache_key, all_results, execution_time=time.time() - start_time)
        self.history_manager.add_search(query_string, len(all_results), time.time() - start_time)
        
        return all_results
    
    # Other public methods delegate to specialized components...
```

### 4. Specific Improvements

#### Extract Query Parsing Logic

The query parsing logic is complex and should be extracted into its own class:

```python
class QueryParser:
    """Parses and normalizes search queries."""
    
    def parse_query(self, query: str) -> SearchQuery:
        """Parse and sanitize a search query with advanced features."""
        original = query.strip()
        
        # Extract quoted phrases
        quoted_phrases = self._extract_quoted_phrases(original)
        
        # Extract wildcards
        wildcards = self._extract_wildcards(original)
        
        # Extract proximity searches
        proximity_searches = self._extract_proximity_searches(original)
        
        # Extract filters
        filters = self._extract_filters(original)
        
        # Process remaining terms
        sanitized, terms, operators = self._process_terms_and_operators(
            original, quoted_phrases, wildcards, proximity_searches, filters
        )
        
        # Determine content types and other parameters
        content_types = self._determine_content_types(filters)
        sort_order = filters.pop('sort', 'relevance')
        limit = int(filters.pop('limit', '50'))
        
        return SearchQuery(
            original=original,
            sanitized=sanitized,
            terms=terms,
            operators=operators,
            quoted_phrases=quoted_phrases,
            filters=filters,
            content_types=content_types,
            wildcards=wildcards,
            proximity_searches=proximity_searches,
            sort_order=sort_order,
            limit=limit
        )
    
    def build_fts_query(self, query: SearchQuery) -> str:
        """Build FTS5 query from parsed query with advanced features."""
        # Implementation...
    
    # Helper methods for extraction...
```

#### Separate Search Execution Logic

Extract the search execution logic for different content types:

```python
class SearchExecutor:
    """Executes search queries against the database."""
    
    def __init__(self, story_id: str):
        self.story_id = story_id
    
    def search_scenes(self, query: SearchQuery, limit: int = 50) -> List[SearchResult]:
        """Search scenes using FTS5."""
        if 'scene' not in query.content_types:
            return []
        
        with get_connection(self.story_id) as conn:
            cursor = conn.cursor()
            
            # Build FTS5 query and execute search
            fts_query = self._build_fts_query(query)
            sql, params = self._build_scene_search_sql(query, fts_query, limit)
            cursor.execute(sql, params)
            
            # Process results
            return self._process_scene_results(cursor.fetchall())
    
    def search_memory(self, query: SearchQuery, limit: int = 50) -> List[SearchResult]:
        """Search memory using FTS5."""
        # Similar implementation...
    
    # Helper methods...
```

#### Create Dedicated History Manager

Extract search history and saved searches management:

```python
class SearchHistoryManager:
    """Manages search history and saved searches."""
    
    def __init__(self, history_limit: int = 10):
        self.history_limit = history_limit
        self.search_history: List[SearchHistory] = []
        self.saved_searches: Dict[str, SavedSearch] = {}
    
    def add_search(self, query: str, results_count: int, execution_time: float, 
                 filters: Dict[str, str] = None) -> None:
        """Add a search to history."""
        self.search_history.append(SearchHistory(
            query=query,
            timestamp=datetime.now(),
            results_count=results_count,
            execution_time=execution_time,
            filters=filters or {}
        ))
        
        # Limit history size
        if len(self.search_history) > self.history_limit:
            self.search_history = self.search_history[-self.history_limit:]
    
    def get_history(self, limit: int = 20) -> List[SearchHistory]:
        """Get recent search history."""
        return list(reversed(self.search_history[-limit:]))
    
    def clear_history(self) -> None:
        """Clear search history."""
        self.search_history.clear()
    
    # Saved searches methods...
```

#### Implement Result Exporters

Create dedicated exporters for different formats:

```python
class ResultExporter:
    """Exports search results in various formats."""
    
    def export(self, results: List[SearchResult], format: str = 'json') -> str:
        """Export search results in various formats."""
        if format == 'json':
            return self._export_json(results)
        elif format == 'markdown':
            return self._export_markdown(results)
        elif format == 'csv':
            return self._export_csv(results)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _export_json(self, results: List[SearchResult]) -> str:
        """Export results as JSON."""
        # Implementation...
    
    def _export_markdown(self, results: List[SearchResult]) -> str:
        """Export results as Markdown."""
        # Implementation...
    
    def _export_csv(self, results: List[SearchResult]) -> str:
        """Export results as CSV."""
        # Implementation...
```

## Implementation Plan

1. Create the new directory structure
2. Extract data models into `models.py`
3. Implement the `QueryParser` class
4. Extract search execution logic into `SearchExecutor`
5. Implement `SearchHistoryManager` and `ResultExporter`
6. Refactor the main `SearchEngine` class to use the new components
7. Update the convenience functions at the module level
8. Add comprehensive docstrings to all new files
9. Update imports and ensure backward compatibility
10. Run the full test suite to verify refactoring

## Backward Compatibility Notes

The refactoring should maintain the same public API. The main `SearchEngine` class should still be importable from `core.search_engine` with the same methods, and the convenience functions (`search_story`, `search_scenes_only`, `search_memory_only`) should continue to work as before.

## Benefits of Refactoring

- **Improved Maintainability**: Each component focuses on a specific responsibility
- **Enhanced Testability**: Isolated components can be tested independently
- **Better Code Organization**: Related functionality is grouped together
- **Reduced Complexity**: Each class is simpler and more focused
- **Easier Extensions**: New features can be added to specific components without modifying others

## Coding Instruction Compliance

This refactoring adheres to the provided coding instructions:
- Uses PowerShell-compatible path formats
- Maintains backward compatibility
- Follows clean development principles
- Preserves the existing functionality while improving organization
