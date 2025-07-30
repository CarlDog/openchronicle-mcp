# Search Engine Refactoring Analysis

**File**: `core/search_engine.py`  
**Size**: 710 lines  
**Complexity**: HIGH  
**Priority**: HIGH

## Executive Summary

The `SearchEngine` is a sophisticated full-text search system with FTS5 integration, providing comprehensive search capabilities across OpenChronicle stories. While functionally rich, it suffers from significant single-responsibility violations by combining query parsing, search execution, result formatting, caching, history management, and export functionality in a single class. This analysis proposes a modular architecture to improve maintainability and extensibility.

## Current Architecture Analysis

### Core Components
1. **4 Data Classes**: SearchResult, SearchQuery, SearchHistory, SavedSearch
2. **1 Main Engine Class**: SearchEngine with 20+ methods handling diverse responsibilities
3. **FTS5 Integration**: SQLite full-text search with advanced query capabilities
4. **Multi-format Export**: JSON, Markdown, and CSV export support

### Current Responsibilities
- **Query Parsing**: Complex query parsing with operators, filters, and advanced syntax
- **Search Execution**: FTS5 query execution across scenes and memory
- **Result Processing**: Result ranking, snippet generation, and highlighting
- **Cache Management**: Query result caching with performance optimization
- **History Tracking**: Search history management and analytics
- **Saved Searches**: Persistent search management with reuse capabilities
- **Export Functions**: Multi-format result export (JSON, Markdown, CSV)
- **Performance Monitoring**: Search statistics and health checking

## Major Refactoring Opportunities

### 1. Query Processing System (Critical Priority)

**Problem**: Complex query parsing and building embedded in main engine
```python
def parse_query(self, query: str) -> SearchQuery:
    # 80+ lines of complex query parsing logic
    
def _build_fts_query(self, query: SearchQuery) -> str:
    # Complex FTS5 query building with advanced features
```

**Solution**: Extract to QueryProcessor and QueryBuilder
```python
class QueryProcessor:
    """Processes and parses search queries into structured format."""
    
    def __init__(self):
        self.query_parser = QueryParser()
        self.query_validator = QueryValidator()
        self.syntax_analyzer = QuerySyntaxAnalyzer()
    
    def process_query(self, query_string: str) -> ProcessedQuery:
        """Process raw query string into structured query object."""
        
    def parse_advanced_syntax(self, query: str) -> AdvancedQuery:
        """Parse advanced query syntax (operators, filters, etc.)."""
        
    def validate_query(self, query: ProcessedQuery) -> ValidationResult:
        """Validate query structure and syntax."""
        
    def optimize_query(self, query: ProcessedQuery) -> OptimizedQuery:
        """Optimize query for better performance."""

class QueryParser:
    """Parses different query syntax elements."""
    
    def __init__(self):
        self.filter_parser = FilterParser()
        self.operator_parser = OperatorParser()
        self.phrase_parser = PhraseParser()
        self.wildcard_parser = WildcardParser()
        self.proximity_parser = ProximityParser()
    
    def parse_filters(self, query: str) -> Tuple[str, Dict[str, str]]:
        """Extract filters from query string."""
        
    def parse_quoted_phrases(self, query: str) -> Tuple[str, List[str]]:
        """Extract quoted phrases from query."""
        
    def parse_operators(self, query: str) -> Tuple[str, List[str]]:
        """Extract boolean operators from query."""
        
    def parse_wildcards(self, query: str) -> Tuple[str, List[str]]:
        """Extract wildcard patterns from query."""
        
    def parse_proximity_searches(self, query: str) -> Tuple[str, List[ProximitySearch]]:
        """Extract proximity search patterns."""

class QueryBuilder:
    """Builds FTS5 queries from parsed query objects."""
    
    def __init__(self):
        self.fts_translator = FTSTranslator()
        self.query_optimizer = QueryOptimizer()
    
    def build_fts_query(self, processed_query: ProcessedQuery) -> FTSQuery:
        """Build FTS5 query from processed query."""
        
    def build_scene_query(self, processed_query: ProcessedQuery) -> SceneQuery:
        """Build scene-specific query with filters."""
        
    def build_memory_query(self, processed_query: ProcessedQuery) -> MemoryQuery:
        """Build memory-specific query with filters."""
        
    def optimize_for_performance(self, query: FTSQuery) -> OptimizedFTSQuery:
        """Optimize FTS query for better performance."""

@dataclass
class ProcessedQuery:
    """Fully processed and structured query."""
    original: str
    sanitized: str
    terms: List[QueryTerm]
    operators: List[QueryOperator]
    phrases: List[QuotedPhrase]
    filters: Dict[str, FilterValue]
    content_types: List[str]
    wildcards: List[WildcardPattern]
    proximity_searches: List[ProximitySearch]
    sort_criteria: SortCriteria
    limit_config: LimitConfiguration

@dataclass
class QueryTerm:
    """Individual query term with metadata."""
    term: str
    weight: float
    boost: float
    required: bool
    excluded: bool

@dataclass
class ProximitySearch:
    """Proximity search configuration."""
    term1: str
    term2: str
    distance: int
    ordered: bool = False
```

### 2. Search Execution System (Critical Priority)

**Problem**: Search execution logic mixed with result processing
```python
def search_scenes(self, query: SearchQuery, limit: int = 50) -> List[SearchResult]:
    # 70+ lines of complex scene search with FTS5 integration
    
def search_memory(self, query: SearchQuery, limit: int = 50) -> List[SearchResult]:
    # Complex memory search logic
```

**Solution**: Extract to SearchExecutor and ResultProcessor
```python
class SearchExecutor:
    """Executes search queries against different content types."""
    
    def __init__(self, story_id: str):
        self.story_id = story_id
        self.scene_searcher = SceneSearcher(story_id)
        self.memory_searcher = MemorySearcher(story_id)
        self.database_connector = DatabaseConnector(story_id)
    
    def execute_search(self, processed_query: ProcessedQuery) -> SearchExecution:
        """Execute search across all specified content types."""
        
    def execute_scene_search(self, query: SceneQuery) -> SceneSearchResult:
        """Execute search specifically for scenes."""
        
    def execute_memory_search(self, query: MemoryQuery) -> MemorySearchResult:
        """Execute search specifically for memory."""
        
    def execute_combined_search(self, queries: List[ProcessedQuery]) -> CombinedSearchResult:
        """Execute multiple searches and combine results."""

class SceneSearcher:
    """Specialized scene search implementation."""
    
    def __init__(self, story_id: str):
        self.story_id = story_id
        self.fts_executor = FTSExecutor()
        self.filter_applier = SceneFilterApplier()
        self.ranking_calculator = SceneRankingCalculator()
    
    def search_scenes(self, query: SceneQuery) -> List[RawSceneResult]:
        """Search scenes using FTS5 with scene-specific optimizations."""
        
    def apply_scene_filters(self, results: List[RawSceneResult], 
                          filters: Dict[str, str]) -> List[FilteredSceneResult]:
        """Apply scene-specific filters to results."""
        
    def calculate_scene_relevance(self, result: RawSceneResult,
                                query: SceneQuery) -> float:
        """Calculate scene-specific relevance scoring."""

class MemorySearcher:
    """Specialized memory search implementation."""
    
    def __init__(self, story_id: str):
        self.story_id = story_id
        self.fts_executor = FTSExecutor()
        self.filter_applier = MemoryFilterApplier()
        self.ranking_calculator = MemoryRankingCalculator()
    
    def search_memory(self, query: MemoryQuery) -> List[RawMemoryResult]:
        """Search memory using FTS5 with memory-specific optimizations."""
        
    def apply_memory_filters(self, results: List[RawMemoryResult],
                           filters: Dict[str, str]) -> List[FilteredMemoryResult]:
        """Apply memory-specific filters to results."""
        
    def calculate_memory_relevance(self, result: RawMemoryResult,
                                 query: MemoryQuery) -> float:
        """Calculate memory-specific relevance scoring."""

class ResultProcessor:
    """Processes and enriches search results."""
    
    def __init__(self):
        self.snippet_generator = SnippetGenerator()
        self.result_ranker = ResultRanker()
        self.result_enricher = ResultEnricher()
    
    def process_results(self, raw_results: List[RawSearchResult],
                       query: ProcessedQuery) -> List[SearchResult]:
        """Process raw results into enriched search results."""
        
    def generate_snippets(self, results: List[RawSearchResult],
                         query: ProcessedQuery) -> List[SnippetResult]:
        """Generate highlighted snippets for results."""
        
    def rank_results(self, results: List[SearchResult],
                    ranking_criteria: RankingCriteria) -> List[RankedResult]:
        """Rank results based on relevance and other factors."""
        
    def enrich_metadata(self, results: List[SearchResult]) -> List[EnrichedResult]:
        """Enrich results with additional metadata."""

@dataclass
class SearchExecution:
    """Result of search execution."""
    query: ProcessedQuery
    results: List[SearchResult]
    execution_time: float
    total_matches: int
    applied_filters: List[str]
    performance_metrics: PerformanceMetrics
```

### 3. Caching and Performance System (High Priority)

**Problem**: Caching logic embedded in main search method
```python
def search_all(self, query_string: str, limit: int = 50) -> List[SearchResult]:
    # 50+ lines including caching, performance tracking, and result combination
```

**Solution**: Extract to CacheManager and PerformanceMonitor
```python
class CacheManager:
    """Manages search result caching and cache policies."""
    
    def __init__(self, config: CacheConfiguration):
        self.cache_storage = CacheStorage(config.storage_type)
        self.cache_policy = CachePolicy(config.policy_settings)
        self.cache_metrics = CacheMetrics()
    
    def get_cached_result(self, cache_key: str) -> Optional[CachedSearchResult]:
        """Retrieve cached search result if valid."""
        
    def cache_result(self, cache_key: str, result: SearchResult, 
                    metadata: CacheMetadata) -> bool:
        """Cache search result with metadata."""
        
    def invalidate_cache(self, pattern: str = None) -> int:
        """Invalidate cache entries matching pattern."""
        
    def get_cache_statistics(self) -> CacheStatistics:
        """Get comprehensive cache statistics."""

class PerformanceMonitor:
    """Monitors and tracks search engine performance."""
    
    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.performance_analyzer = PerformanceAnalyzer()
        self.alert_manager = AlertManager()
    
    def start_query_timing(self, query_id: str) -> QueryTimer:
        """Start timing a query execution."""
        
    def record_query_performance(self, timer: QueryTimer, 
                                result_count: int) -> PerformanceRecord:
        """Record query performance metrics."""
        
    def analyze_performance_trends(self, time_range: TimeRange) -> PerformanceTrends:
        """Analyze performance trends over time."""
        
    def detect_performance_issues(self) -> List[PerformanceIssue]:
        """Detect potential performance issues."""

class CacheStorage:
    """Handles cache storage operations."""
    
    def __init__(self, storage_type: str):
        self.storage_type = storage_type
        if storage_type == 'memory':
            self.store = MemoryCacheStore()
        elif storage_type == 'redis':
            self.store = RedisCacheStore()
        elif storage_type == 'file':
            self.store = FileCacheStore()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache storage."""
        
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache storage."""
        
    def delete(self, key: str) -> bool:
        """Delete value from cache storage."""

@dataclass
class CacheConfiguration:
    """Configuration for cache management."""
    storage_type: str = 'memory'
    max_size: int = 1000
    default_ttl: int = 300
    policy_settings: Dict[str, Any] = None

@dataclass
class PerformanceMetrics:
    """Performance metrics for search operations."""
    query_time: float
    result_count: int
    cache_hit: bool
    database_queries: int
    fts_queries: int
    memory_usage: float
```

### 4. Search History and Saved Searches (Medium Priority)

**Problem**: History management and saved searches mixed with main engine
```python
def save_search(self, name: str, query: str, description: str = "", filters: Dict[str, str] = None) -> SavedSearch:
def get_search_history(self, limit: int = 20) -> List[SearchHistory]:
def get_search_suggestions(self, partial_query: str, limit: int = 5) -> List[str]:
```

**Solution**: Extract to SearchHistoryManager and SavedSearchManager
```python
class SearchHistoryManager:
    """Manages search history and provides search suggestions."""
    
    def __init__(self, config: HistoryConfiguration):
        self.history_storage = HistoryStorage(config.storage_type)
        self.suggestion_engine = SuggestionEngine()
        self.analytics_tracker = HistoryAnalyticsTracker()
    
    def record_search(self, search_record: SearchRecord) -> bool:
        """Record a search in history."""
        
    def get_search_history(self, filters: HistoryFilters = None) -> List[SearchHistory]:
        """Get search history with optional filtering."""
        
    def generate_suggestions(self, partial_query: str, 
                           context: SuggestionContext) -> List[SearchSuggestion]:
        """Generate search suggestions based on history and patterns."""
        
    def analyze_search_patterns(self, time_range: TimeRange) -> SearchPatterns:
        """Analyze search patterns and trends."""

class SavedSearchManager:
    """Manages saved searches and search templates."""
    
    def __init__(self, storage: SavedSearchStorage):
        self.storage = storage
        self.template_engine = SearchTemplateEngine()
        self.validation_engine = SavedSearchValidator()
    
    def save_search(self, search_definition: SavedSearchDefinition) -> SavedSearch:
        """Save a search for future reuse."""
        
    def execute_saved_search(self, search_name: str, 
                           parameters: Dict[str, Any] = None) -> SearchResult:
        """Execute a saved search with optional parameters."""
        
    def create_search_template(self, template_definition: TemplateDefinition) -> SearchTemplate:
        """Create reusable search template."""
        
    def manage_search_collections(self, collection_name: str) -> SearchCollection:
        """Manage collections of related searches."""

class SuggestionEngine:
    """Generates intelligent search suggestions."""
    
    def __init__(self):
        self.pattern_analyzer = SearchPatternAnalyzer()
        self.content_analyzer = ContentBasedSuggestions()
        self.collaborative_filter = CollaborativeSuggestions()
    
    def generate_query_suggestions(self, partial: str, 
                                 context: SuggestionContext) -> List[QuerySuggestion]:
        """Generate query completion suggestions."""
        
    def generate_filter_suggestions(self, query: str) -> List[FilterSuggestion]:
        """Suggest relevant filters for query."""
        
    def generate_related_searches(self, current_query: str) -> List[RelatedSearch]:
        """Generate related search suggestions."""

@dataclass
class SearchRecord:
    """Record of a search execution."""
    query: str
    timestamp: datetime
    result_count: int
    execution_time: float
    user_interactions: List[UserInteraction]
    filters_applied: Dict[str, str]

@dataclass
class SavedSearchDefinition:
    """Definition for creating a saved search."""
    name: str
    query: str
    description: str
    filters: Dict[str, str]
    parameters: List[SearchParameter]
    tags: List[str]
    privacy_level: str
```

### 5. Export and Formatting System (Medium Priority)

**Problem**: Multiple export formats embedded in main engine
```python
def export_search_results(self, results: List[SearchResult], format: str = 'json') -> str:
def _export_json(self, results: List[SearchResult]) -> str:
def _export_markdown(self, results: List[SearchResult]) -> str:
def _export_csv(self, results: List[SearchResult]) -> str:
```

**Solution**: Extract to ResultExporter and FormatManager
```python
class ResultExporter:
    """Handles export of search results in various formats."""
    
    def __init__(self):
        self.format_registry = FormatRegistry()
        self.template_engine = ExportTemplateEngine()
        self.data_transformer = ExportDataTransformer()
    
    def export_results(self, results: List[SearchResult], 
                      export_config: ExportConfiguration) -> ExportResult:
        """Export search results in specified format."""
        
    def register_custom_format(self, format_name: str, 
                             formatter: ResultFormatter) -> bool:
        """Register custom export format."""
        
    def get_supported_formats(self) -> List[ExportFormat]:
        """Get list of supported export formats."""
        
    def create_export_template(self, template_definition: TemplateDefinition) -> ExportTemplate:
        """Create custom export template."""

class FormatRegistry:
    """Registry of available export formats."""
    
    def __init__(self):
        self.formatters = {
            'json': JSONFormatter(),
            'markdown': MarkdownFormatter(),
            'csv': CSVFormatter(),
            'html': HTMLFormatter(),
            'xml': XMLFormatter(),
            'yaml': YAMLFormatter()
        }
    
    def get_formatter(self, format_name: str) -> ResultFormatter:
        """Get formatter for specified format."""
        
    def register_formatter(self, format_name: str, 
                         formatter: ResultFormatter) -> bool:
        """Register new formatter."""

class JSONFormatter(ResultFormatter):
    """Formats search results as JSON."""
    
    def format_results(self, results: List[SearchResult], 
                      options: FormatOptions) -> str:
        """Format results as JSON with configurable options."""
        
    def format_single_result(self, result: SearchResult, 
                           options: FormatOptions) -> Dict[str, Any]:
        """Format single result as JSON object."""

class MarkdownFormatter(ResultFormatter):
    """Formats search results as Markdown."""
    
    def format_results(self, results: List[SearchResult], 
                      options: FormatOptions) -> str:
        """Format results as Markdown document."""
        
    def format_result_section(self, result: SearchResult, 
                            index: int, options: FormatOptions) -> str:
        """Format individual result as Markdown section."""

@dataclass
class ExportConfiguration:
    """Configuration for result export."""
    format: str
    include_metadata: bool = True
    include_snippets: bool = True
    template: Optional[str] = None
    custom_fields: List[str] = None
    sorting: Optional[str] = None
    limit: Optional[int] = None

@dataclass
class ExportResult:
    """Result of export operation."""
    content: str
    format: str
    size: int
    export_time: float
    metadata: Dict[str, Any]
```

## Proposed Modular Architecture

```python
class SearchEngine:
    """Main orchestrator for story search functionality."""
    
    def __init__(self, story_id: str, config: SearchConfiguration):
        self.story_id = story_id
        self.query_processor = QueryProcessor()
        self.search_executor = SearchExecutor(story_id)
        self.result_processor = ResultProcessor()
        self.cache_manager = CacheManager(config.cache_config)
        self.performance_monitor = PerformanceMonitor()
        self.history_manager = SearchHistoryManager(config.history_config)
        self.saved_search_manager = SavedSearchManager(config.saved_search_storage)
        self.result_exporter = ResultExporter()
    
    def search(self, query_string: str, options: SearchOptions = None) -> SearchResult:
        """Main search interface orchestrating all components."""
        # Start performance monitoring
        timer = self.performance_monitor.start_query_timing(query_string)
        
        # Check cache
        cache_key = self._generate_cache_key(query_string, options)
        cached_result = self.cache_manager.get_cached_result(cache_key)
        if cached_result and not cached_result.is_expired():
            return cached_result.result
        
        # Process query
        processed_query = self.query_processor.process_query(query_string)
        
        # Execute search
        execution_result = self.search_executor.execute_search(processed_query)
        
        # Process results
        final_results = self.result_processor.process_results(
            execution_result.raw_results, processed_query
        )
        
        # Cache results
        self.cache_manager.cache_result(cache_key, final_results)
        
        # Record in history
        self.history_manager.record_search(SearchRecord(
            query=query_string,
            timestamp=datetime.now(),
            result_count=len(final_results),
            execution_time=timer.elapsed()
        ))
        
        return final_results
    
    def export_results(self, results: List[SearchResult], 
                      export_config: ExportConfiguration) -> ExportResult:
        """Export results through result exporter."""
        return self.result_exporter.export_results(results, export_config)
    
    def get_search_suggestions(self, partial_query: str) -> List[SearchSuggestion]:
        """Get search suggestions through history manager."""
        return self.history_manager.generate_suggestions(partial_query)
```

## Implementation Benefits

### Immediate Improvements
1. **Single Responsibility**: Each class handles one aspect of search functionality
2. **Testability**: Components can be tested independently with mock data
3. **Maintainability**: Changes to export formats don't affect query processing
4. **Extensibility**: New search types or export formats can be added easily

### Long-term Advantages
1. **Performance**: Specialized caching and query optimization
2. **Scalability**: Components can be distributed or parallelized
3. **Flexibility**: Different search strategies can be plugged in
4. **Analytics**: Advanced search analytics and pattern recognition

## Migration Strategy

### Phase 1: Core Search Infrastructure (Week 1)
1. Extract `QueryProcessor` with comprehensive parsing capabilities
2. Extract `SearchExecutor` with FTS5 integration
3. Implement basic result processing pipeline

### Phase 2: Performance and Caching (Week 2)
1. Extract `CacheManager` with multiple storage backends
2. Extract `PerformanceMonitor` with comprehensive metrics
3. Implement query optimization strategies

### Phase 3: History and Suggestions (Week 3)
1. Extract `SearchHistoryManager` with analytics
2. Extract `SavedSearchManager` with templates
3. Implement intelligent suggestion engine

### Phase 4: Export and Formatting (Week 4)
1. Extract `ResultExporter` with pluggable formatters
2. Implement multiple export formats
3. Create template-based export system

### Phase 5: Integration and Enhancement (Week 5)
1. Refactor main engine to orchestrate components
2. Implement advanced search features
3. Comprehensive testing and performance optimization

## Risk Assessment

### Low Risk
- **Query Processing**: Well-defined parsing with clear input/output
- **Export System**: Clear format boundaries with standard outputs

### Medium Risk
- **Caching System**: Complex cache invalidation and performance tuning
- **History Management**: User data privacy and storage considerations

### High Risk
- **Search Execution**: Complex FTS5 integration with performance requirements
- **Result Processing**: Advanced ranking algorithms and snippet generation

## Conclusion

The `SearchEngine` represents a sophisticated search system that would greatly benefit from modular refactoring. The proposed architecture separates query processing, search execution, result processing, caching, history management, and export functionality into focused components while maintaining all current functionality.

This refactoring would enable more sophisticated search capabilities, better performance through specialized optimization, and provide a foundation for advanced AI-driven search features in future development.
