# Refactoring Analysis for `search_engine.py`

## Executive Summary

The `search_engine.py` module is a well-structured and feature-rich component responsible for full-text search within an OpenChronicle story. It effectively uses SQLite's FTS5 extension and provides a comprehensive API for searching, filtering, and managing search history. However, the `SearchEngine` class has grown into a "God Object," handling too many distinct responsibilities, including query parsing, data access, caching, history management, and data exporting.

This refactoring plan aims to decompose the `SearchEngine` class into a more modular and maintainable architecture by applying the **Service Layer**, **Repository**, and **Strategy** design patterns. This will improve separation of concerns, enhance testability, and make the system more extensible.

## Architectural Issues

1.  **God Object Anti-Pattern**: The `SearchEngine` class violates the Single Responsibility Principle (SRP) by managing:
    *   **Query Parsing**: Complex logic for parsing search queries, including operators, filters, and wildcards.
    *   **Data Access**: Direct interaction with the database to execute FTS5 queries against scenes and memory.
    *   **Caching**: In-memory caching of search results.
    *   **History Management**: Tracking and managing search history.
    *   **Saved Searches**: CRUD operations for saved searches.
    *   **Data Exporting**: Converting search results into different formats (JSON, Markdown, CSV).
    *   **Health Checks**: Performing health checks on the search functionality.

2.  **Tight Coupling**: The business logic for searching is tightly coupled with the data access layer (SQLite FTS5). This makes it difficult to switch to a different search backend (e.g., Elasticsearch) in the future.

3.  **Limited Extensibility**: Adding new search backends or export formats requires modifying the `SearchEngine` class, which can become complex and error-prone.

## Proposed Refactoring

I propose refactoring the `search_engine.py` module into a layered architecture with distinct components for services, repositories, and data models.

### 1. New Directory Structure

Create a new directory `core/search` to house the refactored components:

```
core/
|-- search/
|   |-- __init__.py
|   |-- search_service.py       # High-level search operations
|   |-- search_repository.py    # Data access and FTS5 queries
|   |-- query_parser.py         # Query parsing and validation
|   |-- search_caching.py       # Caching logic for search results
|   |-- history_manager.py      # Manages search history
|   |-- saved_searches.py       # Manages saved searches
|   |-- exporters/
|   |   |-- __init__.py
|   |   |-- base_exporter.py
|   |   |-- json_exporter.py
|   |   |-- markdown_exporter.py
|   |   |-- csv_exporter.py
|   |-- models/
|   |   |-- __init__.py
|   |   |-- search_query.py
|   |   |-- search_result.py
|-- search_engine.py            # Facade for the search subsystem
```

### 2. Refactoring Steps

#### Step 1: Create Data Models

Create dedicated data models for `SearchQuery` and `SearchResult` in `core/search/models/`.

-   **`core/search/models/search_query.py`**:
    ```python
    from dataclasses import dataclass, field
    from typing import List, Dict

    @dataclass
    class SearchQuery:
        original: str
        sanitized: str
        terms: List[str]
        operators: List[str]
        quoted_phrases: List[str]
        filters: Dict[str, str]
        content_types: List[str]
        wildcards: List[str] = field(default_factory=list)
        proximity_searches: List[tuple[str, str, int]] = field(default_factory=list)
        sort_order: str = "relevance"
        limit: int = 50
    ```

-   **`core/search/models/search_result.py`**:
    ```python
    from dataclasses import dataclass, field
    from typing import Dict, Optional

    @dataclass
    class SearchResult:
        id: str
        content_type: str
        title: str
        content: str
        snippet: str
        score: float
        timestamp: Optional[str] = None
        scene_label: Optional[str] = None
        metadata: Dict = field(default_factory=dict)
    ```

#### Step 2: Implement the Query Parser

Create a `QueryParser` class in `core/search/query_parser.py` to handle all query parsing logic.

-   **`core/search/query_parser.py`**:
    ```python
    import re
    from .models.search_query import SearchQuery

    class QueryParser:
        def parse(self, query_string: str) -> SearchQuery:
            # All query parsing logic from the original SearchEngine class
            # ...
            pass
    ```

#### Step 3: Implement the Search Repository

Create a `SearchRepository` class in `core/search/search_repository.py` to handle all database interactions.

-   **`core/search/search_repository.py`**:
    ```python
    from .models.search_query import SearchQuery
    from .models.search_result import SearchResult
    from ..database import get_connection

    class SearchRepository:
        def __init__(self, story_id: str):
            self.story_id = story_id

        def search_scenes(self, query: SearchQuery, limit: int) -> List[SearchResult]:
            # Database logic for searching scenes
            pass

        def search_memory(self, query: SearchQuery, limit: int) -> List[SearchResult]:
            # Database logic for searching memory
            pass

        def check_fts_support(self) -> bool:
            # Logic to check for FTS5 support
            pass

        def optimize_indexes(self):
            # Logic to optimize FTS5 indexes
            pass
    ```

#### Step 4: Implement Caching and History Management

Create separate classes for caching and history management.

-   **`core/search/search_caching.py`**:
    ```python
    from typing import List, Optional
    from .models.search_result import SearchResult

    class SearchCache:
        def __init__(self, cache_size: int = 100):
            self.cache = {}
            self.cache_size = cache_size

        def get(self, key: str) -> Optional[List[SearchResult]]:
            # Caching logic
            pass

        def set(self, key: str, results: List[SearchResult]):
            # Caching logic
            pass
    ```

-   **`core/search/history_manager.py`**:
    ```python
    from datetime import datetime
    from typing import List
    from .models.search_query import SearchQuery

    class SearchHistory:
        # ... data model for history entries

    class HistoryManager:
        def __init__(self, history_limit: int = 10):
            self.history = []
            self.history_limit = history_limit

        def add_entry(self, query: SearchQuery, results_count: int, execution_time: float):
            # Logic to add a history entry
            pass

        def get_history(self, limit: int) -> List[SearchHistory]:
            # Logic to retrieve search history
            pass
    ```

#### Step 5: Implement the Exporter Strategy

Create an exporter system using the Strategy pattern.

-   **`core/search/exporters/base_exporter.py`**:
    ```python
    from abc import ABC, abstractmethod
    from typing import List
    from ..models.search_result import SearchResult

    class BaseExporter(ABC):
        @abstractmethod
        def export(self, results: List[SearchResult]) -> str:
            pass
    ```

-   **`core/search/exporters/json_exporter.py`**:
    ```python
    from .base_exporter import BaseExporter
    # ... implementation for JSON export
    ```

#### Step 6: Implement the Search Service

Create a `SearchService` class in `core/search/search_service.py` to orchestrate the different components.

-   **`core/search/search_service.py`**:
    ```python
    from .search_repository import SearchRepository
    from .query_parser import QueryParser
    from .search_caching import SearchCache
    from .history_manager import HistoryManager
    from .exporters.base_exporter import BaseExporter

    class SearchService:
        def __init__(self, story_id: str):
            self.repository = SearchRepository(story_id)
            self.parser = QueryParser()
            self.cache = SearchCache()
            self.history = HistoryManager()
            self.exporters = {
                'json': JSONExporter(),
                'markdown': MarkdownExporter(),
                'csv': CSVExporter(),
            }

        def search(self, query_string: str, limit: int = 50) -> List[SearchResult]:
            # Orchestration logic for searching
            pass

        def export_results(self, results: List[SearchResult], format: str) -> str:
            # Logic to export results using the appropriate exporter
            pass
    ```

#### Step 7: Refactor the `SearchEngine` Class as a Facade

Update the original `SearchEngine` class to act as a simple facade that delegates calls to the new services.

-   **`core/search_engine.py`**:
    ```python
    from .search.search_service import SearchService

    class SearchEngine:
        def __init__(self, story_id: str):
            self.service = SearchService(story_id)

        def search(self, query_string: str, limit: int = 50):
            return self.service.search(query_string, limit)

        def export_results(self, results, format: str):
            return self.service.export_results(results, format)
        
        # ... other methods delegating to the service
    ```

## Benefits of This Refactoring

-   **Improved Separation of Concerns**: Each class has a single, well-defined responsibility, making the system easier to understand and maintain.
-   **Enhanced Testability**: Each component can be tested independently, allowing for more focused and effective unit tests.
-   **Increased Flexibility**: The system is more flexible and extensible. For example, adding a new export format only requires creating a new exporter class, without modifying the `SearchService`.
-   **Better Scalability**: The modular design makes it easier to scale and optimize individual components as needed.

This refactoring will result in a more robust, maintainable, and scalable search engine for OpenChronicle.
