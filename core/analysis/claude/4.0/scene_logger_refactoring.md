# Scene Logger Refactoring Analysis

**File**: `core/scene_logger.py`  
**Size**: 536 lines  
**Complexity**: HIGH  
**Priority**: HIGH

## Executive Summary

The `scene_logger.py` module is a comprehensive scene management system that handles scene persistence, structured tagging, token tracking, mood analysis, and statistical reporting. While functionally sophisticated with advanced features like token usage tracking and character mood timelines, it suffers from significant architectural violations by mixing database operations, scene serialization, statistical analysis, filtering operations, and metadata management in a single module with 14 separate functions. This analysis proposes a modular class-based architecture to improve maintainability and extensibility.

## Current Architecture Analysis

### Core Components
1. **14 Standalone Functions**: All scene operations implemented as module-level functions
2. **Mixed Responsibilities**: Database operations + serialization + analysis + statistics + filtering
3. **Complex Scene Structure**: User input, model output, memory snapshots, flags, context refs, structured tags
4. **Sophisticated Features**: Token tracking, mood timelines, scene categorization, long turn detection

### Current Responsibilities
- **Scene Persistence**: Save/load scenes to database with JSON serialization
- **Structured Tagging**: Complex metadata tagging system with mood, scene type, token usage
- **Token Management**: Token usage tracking, long turn detection, model usage statistics
- **Scene Analysis**: Mood analysis, scene type classification, character mood tracking
- **Filtering and Querying**: Scene filtering by mood, type, labels, character involvement
- **Statistical Reporting**: Token usage stats, mood timelines, summary statistics
- **Scene Management**: Scene labeling, rollback support, scene listing

## Major Refactoring Opportunities

### 1. Scene Persistence System (Critical Priority)

**Problem**: Database operations and serialization mixed with business logic and metadata generation
```python
def save_scene(story_id, user_input, model_output, memory_snapshot=None, flags=None, ...):
    # 100+ lines mixing token calculation, metadata building, and database operations

def load_scene(story_id, scene_id):
    # Database query mixed with JSON deserialization
```

**Solution**: Extract to SceneRepository and SceneSerializer
```python
class SceneRepository:
    """Handles scene data persistence and retrieval."""
    
    def __init__(self, database_manager: DatabaseManager):
        self.db = database_manager
        self.serializer = SceneSerializer()
        self.id_generator = SceneIdGenerator()
        
    def save_scene(self, story_id: str, scene: Scene) -> str:
        """Save scene with automatic ID generation."""
        
    def load_scene(self, story_id: str, scene_id: str) -> Scene:
        """Load scene with deserialization."""
        
    def update_scene(self, story_id: str, scene_id: str, updates: SceneUpdates) -> bool:
        """Update specific scene fields."""
        
    def delete_scene(self, story_id: str, scene_id: str) -> bool:
        """Delete scene from storage."""
        
    def get_scenes_batch(self, story_id: str, scene_ids: List[str]) -> List[Scene]:
        """Get multiple scenes efficiently."""

class SceneSerializer:
    """Handles scene serialization and deserialization."""
    
    def __init__(self):
        self.validators = SceneValidatorRegistry()
        
    def serialize_scene(self, scene: Scene) -> Dict[str, str]:
        """Serialize scene to database format."""
        
    def deserialize_scene(self, serialized_data: Dict[str, Any]) -> Scene:
        """Deserialize scene from database format."""
        
    def validate_scene_structure(self, scene: Scene) -> ValidationResult:
        """Validate scene structure integrity."""
        
    def migrate_scene_format(self, old_scene: Dict) -> Scene:
        """Migrate old scene format to new structure."""

class SceneIdGenerator:
    """Generates unique scene identifiers."""
    
    def generate_id(self) -> str:
        """Generate unique scene ID."""
        
    def generate_batch_ids(self, count: int) -> List[str]:
        """Generate multiple unique IDs."""
        
    def validate_id_format(self, scene_id: str) -> bool:
        """Validate scene ID format."""

@dataclass
class Scene:
    """Complete scene data structure."""
    scene_id: str
    timestamp: str
    user_input: str
    model_output: str
    memory_snapshot: Dict[str, Any]
    flags: List[str]
    context_refs: List[str]
    analysis_data: Optional[Dict[str, Any]]
    scene_label: Optional[str]
    structured_tags: Dict[str, Any]
    
    def get_tag(self, key: str, default: Any = None) -> Any:
        """Get structured tag safely."""
        
    def set_tag(self, key: str, value: Any) -> None:
        """Set structured tag with validation."""
        
    def calculate_length_metrics(self) -> LengthMetrics:
        """Calculate input/output length metrics."""

@dataclass
class LengthMetrics:
    """Scene length metrics."""
    input_length: int
    output_length: int
    total_length: int
    input_word_count: int
    output_word_count: int
    total_word_count: int

@dataclass
class SceneUpdates:
    """Scene update request."""
    scene_label: Optional[str] = None
    structured_tags: Optional[Dict[str, Any]] = None
    analysis_data: Optional[Dict[str, Any]] = None
    flags: Optional[List[str]] = None
```

### 2. Structured Tagging System (Critical Priority)

**Problem**: Complex metadata generation and tag management embedded in save function
```python
def save_scene(...):
    # Complex structured tags building with token calculation, mood extraction, metadata
    structured_tags.update({
        "token_usage": {...},
        "mood": mood,
        "scene_type": scene_type,
        "character_moods": character_moods
    })
```

**Solution**: Extract to TaggingEngine
```python
class TaggingEngine:
    """Manages structured scene tagging and metadata generation."""
    
    def __init__(self, token_manager: Optional[Any] = None):
        self.token_calculator = TokenCalculator(token_manager)
        self.mood_extractor = MoodExtractor()
        self.scene_classifier = SceneClassifier()
        self.metadata_generator = MetadataGenerator()
        
    def generate_structured_tags(self, scene: Scene, 
                                analysis_data: Optional[Dict] = None,
                                model_name: Optional[str] = None) -> Dict[str, Any]:
        """Generate complete structured tags for scene."""
        
    def update_tags(self, existing_tags: Dict[str, Any], 
                   updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing tags with new data."""
        
    def extract_analysis_tags(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract tags from analysis data."""
        
    def extract_memory_tags(self, memory_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Extract tags from memory snapshot."""

class TokenCalculator:
    """Calculates token usage and metrics."""
    
    def __init__(self, token_manager: Optional[Any] = None):
        self.token_manager = token_manager
        self.long_turn_threshold = 4000  # Configurable threshold
        
    def calculate_token_usage(self, scene: Scene, model_name: str) -> TokenUsageMetrics:
        """Calculate comprehensive token usage metrics."""
        
    def is_long_turn(self, total_tokens: int) -> bool:
        """Determine if scene represents a long turn."""
        
    def estimate_tokens_without_manager(self, text: str) -> int:
        """Fallback token estimation when manager unavailable."""

class MoodExtractor:
    """Extracts mood information from scenes and memory."""
    
    def extract_scene_mood(self, analysis_data: Dict[str, Any]) -> str:
        """Extract primary scene mood from analysis."""
        
    def extract_character_moods(self, memory_snapshot: Dict[str, Any]) -> Dict[str, CharacterMoodInfo]:
        """Extract character mood information."""
        
    def validate_mood(self, mood: str) -> bool:
        """Validate mood value."""

class SceneClassifier:
    """Classifies scenes by type and content."""
    
    def classify_scene_type(self, analysis_data: Dict[str, Any]) -> str:
        """Classify scene type (dialogue, action, description, etc.)."""
        
    def classify_content_type(self, analysis_data: Dict[str, Any]) -> str:
        """Classify content type (general, romantic, dramatic, etc.)."""
        
    def determine_significance(self, scene: Scene) -> str:
        """Determine scene significance level."""

class MetadataGenerator:
    """Generates scene metadata."""
    
    def generate_basic_metadata(self, scene: Scene) -> Dict[str, Any]:
        """Generate basic scene metadata."""
        
    def generate_timestamp_metadata(self) -> Dict[str, str]:
        """Generate timestamp-related metadata."""
        
    def generate_statistical_metadata(self, scene: Scene) -> Dict[str, int]:
        """Generate statistical metadata (lengths, counts)."""

@dataclass
class TokenUsageMetrics:
    """Token usage metrics."""
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model_used: str
    is_long_turn: bool
    timestamp: str
    efficiency_score: float = 0.0

@dataclass
class CharacterMoodInfo:
    """Character mood information."""
    character_name: str
    mood: str
    stability: float
    triggers: List[str] = field(default_factory=list)
```

### 3. Scene Query and Filtering System (High Priority)

**Problem**: Multiple filtering functions with similar database query patterns
```python
def get_scenes_by_mood(story_id: str, mood: str) -> List[Dict[str, Any]]:
    # Database query with JSON parsing for mood filtering

def get_scenes_by_type(story_id: str, scene_type: str) -> List[Dict[str, Any]]:
    # Similar pattern for scene type filtering

def get_scenes_with_long_turns(story_id: str) -> List[Dict[str, Any]]:
    # Long turn detection filtering
```

**Solution**: Extract to SceneQueryEngine
```python
class SceneQueryEngine:
    """Handles scene querying and filtering operations."""
    
    def __init__(self, repository: SceneRepository):
        self.repository = repository
        self.filter_builder = SceneFilterBuilder()
        self.query_optimizer = QueryOptimizer()
        
    def query_scenes(self, story_id: str, query: SceneQuery) -> List[Scene]:
        """Execute scene query with filters."""
        
    def get_scenes_by_mood(self, story_id: str, mood: str) -> List[Scene]:
        """Get scenes filtered by mood."""
        
    def get_scenes_by_type(self, story_id: str, scene_type: str) -> List[Scene]:
        """Get scenes filtered by scene type."""
        
    def get_scenes_with_long_turns(self, story_id: str) -> List[Scene]:
        """Get scenes flagged as long turns."""
        
    def get_scenes_by_character(self, story_id: str, character_name: str) -> List[Scene]:
        """Get scenes involving specific character."""
        
    def get_scenes_by_date_range(self, story_id: str, 
                                start_date: str, end_date: str) -> List[Scene]:
        """Get scenes within date range."""

class SceneFilterBuilder:
    """Builds scene filters and queries."""
    
    def __init__(self):
        self.supported_filters = SceneFilterRegistry()
        
    def build_mood_filter(self, mood: str) -> SceneFilter:
        """Build mood-based filter."""
        
    def build_type_filter(self, scene_type: str) -> SceneFilter:
        """Build type-based filter."""
        
    def build_character_filter(self, character_name: str) -> SceneFilter:
        """Build character involvement filter."""
        
    def build_token_filter(self, min_tokens: int = None, 
                          max_tokens: int = None) -> SceneFilter:
        """Build token usage filter."""
        
    def combine_filters(self, filters: List[SceneFilter]) -> CombinedFilter:
        """Combine multiple filters."""

class QueryOptimizer:
    """Optimizes scene queries for performance."""
    
    def optimize_query(self, query: SceneQuery) -> OptimizedQuery:
        """Optimize query for database execution."""
        
    def suggest_indices(self, query: SceneQuery) -> List[str]:
        """Suggest database indices for query optimization."""
        
    def estimate_query_cost(self, query: SceneQuery) -> QueryCostEstimate:
        """Estimate query execution cost."""

@dataclass
class SceneQuery:
    """Scene query specification."""
    filters: List[SceneFilter] = field(default_factory=list)
    sort_by: str = "timestamp"
    sort_order: str = "ASC"
    limit: Optional[int] = None
    offset: Optional[int] = None
    include_tags: bool = True
    include_analysis: bool = False

@dataclass 
class SceneFilter:
    """Individual scene filter."""
    field: str
    operator: str
    value: Any
    filter_type: str = "tag"  # "tag", "field", "json_field"

@dataclass
class OptimizedQuery:
    """Optimized scene query."""
    sql_query: str
    parameters: List[Any]
    estimated_rows: int
    use_index: Optional[str] = None
```

### 4. Statistical Analysis System (High Priority)

**Problem**: Statistical calculations scattered across multiple functions
```python
def get_token_usage_stats(story_id: str) -> Dict[str, Any]:
    # 50+ lines of complex token statistics calculation

def get_character_mood_timeline(story_id: str, character_name: str) -> List[Dict[str, Any]]:
    # Character mood analysis over time

def get_scene_summary_stats(story_id: str) -> Dict[str, Any]:
    # Scene summary statistics with tag analysis
```

**Solution**: Extract to StatisticsEngine
```python
class StatisticsEngine:
    """Generates comprehensive scene statistics and analytics."""
    
    def __init__(self, query_engine: SceneQueryEngine):
        self.query_engine = query_engine
        self.token_analyzer = TokenUsageAnalyzer()
        self.mood_analyzer = MoodAnalyzer()
        self.pattern_analyzer = ScenePatternAnalyzer()
        
    def generate_comprehensive_stats(self, story_id: str) -> ComprehensiveStats:
        """Generate complete statistical report."""
        
    def get_token_usage_stats(self, story_id: str) -> TokenStatistics:
        """Get detailed token usage statistics."""
        
    def get_mood_statistics(self, story_id: str) -> MoodStatistics:
        """Get mood distribution and trends."""
        
    def get_character_analytics(self, story_id: str, 
                              character_name: str) -> CharacterAnalytics:
        """Get comprehensive character analytics."""
        
    def get_scene_type_distribution(self, story_id: str) -> SceneTypeDistribution:
        """Get scene type distribution analysis."""

class TokenUsageAnalyzer:
    """Analyzes token usage patterns and trends."""
    
    def analyze_token_usage(self, scenes: List[Scene]) -> TokenAnalysisResult:
        """Analyze token usage across scenes."""
        
    def detect_token_trends(self, scenes: List[Scene]) -> TokenTrendAnalysis:
        """Detect trends in token usage over time."""
        
    def analyze_model_efficiency(self, scenes: List[Scene]) -> ModelEfficiencyReport:
        """Analyze efficiency of different models."""
        
    def identify_high_token_scenes(self, scenes: List[Scene], 
                                 threshold_percentile: float = 95) -> List[Scene]:
        """Identify scenes with unusually high token usage."""

class MoodAnalyzer:
    """Analyzes mood patterns and character emotional arcs."""
    
    def analyze_mood_distribution(self, scenes: List[Scene]) -> MoodDistribution:
        """Analyze mood distribution across scenes."""
        
    def track_character_mood_timeline(self, scenes: List[Scene], 
                                    character_name: str) -> MoodTimeline:
        """Track character mood changes over time."""
        
    def detect_mood_patterns(self, scenes: List[Scene]) -> List[MoodPattern]:
        """Detect recurring mood patterns."""
        
    def analyze_mood_stability(self, character_timelines: Dict[str, MoodTimeline]) -> StabilityAnalysis:
        """Analyze emotional stability across characters."""

class ScenePatternAnalyzer:
    """Analyzes patterns in scene structure and content."""
    
    def analyze_scene_length_patterns(self, scenes: List[Scene]) -> LengthPatternAnalysis:
        """Analyze patterns in scene lengths."""
        
    def detect_repetitive_patterns(self, scenes: List[Scene]) -> RepetitionAnalysis:
        """Detect repetitive elements across scenes."""
        
    def analyze_pacing_patterns(self, scenes: List[Scene]) -> PacingAnalysis:
        """Analyze story pacing patterns."""

@dataclass
class ComprehensiveStats:
    """Comprehensive scene statistics."""
    total_scenes: int
    token_statistics: TokenStatistics
    mood_statistics: MoodStatistics
    scene_type_distribution: SceneTypeDistribution
    character_analytics: Dict[str, CharacterAnalytics]
    temporal_patterns: TemporalPatterns
    quality_metrics: QualityMetrics

@dataclass
class TokenStatistics:
    """Token usage statistics."""
    total_tokens: int
    average_tokens_per_scene: float
    token_distribution: Dict[str, int]
    long_turn_percentage: float
    model_usage_breakdown: Dict[str, ModelUsageStats]
    efficiency_trends: List[EfficiencyDataPoint]

@dataclass
class MoodStatistics:
    """Mood-related statistics."""
    mood_distribution: Dict[str, int]
    mood_transitions: Dict[str, Dict[str, int]]
    character_mood_stability: Dict[str, float]
    dominant_moods: List[str]
    mood_diversity_score: float

@dataclass
class CharacterAnalytics:
    """Character-specific analytics."""
    character_name: str
    scene_appearances: int
    mood_timeline: MoodTimeline
    dialogue_patterns: DialoguePatterns
    relationship_interactions: RelationshipAnalytics
    character_development_arc: DevelopmentArc
```

### 5. Scene Management System (Medium Priority)

**Problem**: Scene management operations scattered across functions
```python
def update_scene_label(story_id, scene_id, scene_label):
    # Simple scene label update

def rollback_to_scene(story_id, scene_id):
    # Rollback functionality mixed with data loading

def list_scenes(story_id):
    # Scene listing with metadata extraction
```

**Solution**: Extract to SceneManager
```python
class SceneManager:
    """Manages scene operations and lifecycle."""
    
    def __init__(self, repository: SceneRepository, 
                 tagging_engine: TaggingEngine,
                 query_engine: SceneQueryEngine):
        self.repository = repository
        self.tagging_engine = tagging_engine
        self.query_engine = query_engine
        self.rollback_handler = SceneRollbackHandler(repository)
        self.labeling_system = SceneLabelingSystem()
        
    def create_scene(self, story_id: str, scene_data: SceneCreationData) -> Scene:
        """Create new scene with full processing."""
        
    def update_scene(self, story_id: str, scene_id: str, 
                    updates: SceneUpdates) -> Scene:
        """Update existing scene."""
        
    def label_scene(self, story_id: str, scene_id: str, label: str) -> bool:
        """Add or update scene label."""
        
    def get_scene_details(self, story_id: str, scene_id: str) -> SceneDetails:
        """Get comprehensive scene details."""
        
    def list_scenes(self, story_id: str, options: SceneListOptions = None) -> List[SceneSummary]:
        """List scenes with optional filtering and sorting."""

class SceneRollbackHandler:
    """Handles scene rollback operations."""
    
    def __init__(self, repository: SceneRepository):
        self.repository = repository
        
    def prepare_rollback(self, story_id: str, scene_id: str) -> RollbackData:
        """Prepare rollback data for scene."""
        
    def validate_rollback_target(self, story_id: str, scene_id: str) -> ValidationResult:
        """Validate rollback target scene."""
        
    def execute_rollback(self, story_id: str, rollback_data: RollbackData) -> RollbackResult:
        """Execute scene rollback operation."""

class SceneLabelingSystem:
    """Manages scene labeling and categorization."""
    
    def suggest_labels(self, scene: Scene) -> List[str]:
        """Suggest appropriate labels for scene."""
        
    def validate_label(self, label: str) -> ValidationResult:
        """Validate scene label format and content."""
        
    def get_label_statistics(self, story_id: str) -> LabelStatistics:
        """Get statistics about label usage."""

@dataclass
class SceneCreationData:
    """Data for creating new scene."""
    user_input: str
    model_output: str
    memory_snapshot: Dict[str, Any]
    flags: List[str] = field(default_factory=list)
    context_refs: List[str] = field(default_factory=list)
    analysis_data: Optional[Dict[str, Any]] = None
    scene_label: Optional[str] = None
    model_name: Optional[str] = None

@dataclass
class SceneDetails:
    """Comprehensive scene details."""
    scene: Scene
    computed_metrics: SceneMetrics
    related_scenes: List[str]
    character_involvement: List[str]
    quality_score: float

@dataclass
class SceneSummary:
    """Scene summary for listing."""
    scene_id: str
    timestamp: str
    scene_label: Optional[str]
    mood: str
    scene_type: str
    token_count: int
    is_long_turn: bool
    character_count: int
```

## Proposed Modular Architecture

```python
class SceneLogger:
    """Main orchestrator for scene logging and management."""
    
    def __init__(self, database_manager: DatabaseManager, 
                 token_manager: Optional[Any] = None,
                 config: Dict[str, Any] = None):
        
        self.repository = SceneRepository(database_manager)
        self.tagging_engine = TaggingEngine(token_manager)
        self.query_engine = SceneQueryEngine(self.repository)
        self.statistics_engine = StatisticsEngine(self.query_engine)
        self.scene_manager = SceneManager(
            self.repository, self.tagging_engine, self.query_engine
        )
        
    def log_scene(self, story_id: str, scene_data: SceneCreationData) -> str:
        """Log new scene with complete processing."""
        
        # Create and tag scene
        scene = Scene(
            scene_id=self.repository.id_generator.generate_id(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_input=scene_data.user_input,
            model_output=scene_data.model_output,
            memory_snapshot=scene_data.memory_snapshot,
            flags=scene_data.flags,
            context_refs=scene_data.context_refs,
            analysis_data=scene_data.analysis_data,
            scene_label=scene_data.scene_label,
            structured_tags={}
        )
        
        # Generate structured tags
        scene.structured_tags = self.tagging_engine.generate_structured_tags(
            scene, scene_data.analysis_data, scene_data.model_name
        )
        
        # Save scene
        return self.repository.save_scene(story_id, scene)
    
    def get_scene(self, story_id: str, scene_id: str) -> Scene:
        """Get scene by ID."""
        return self.repository.load_scene(story_id, scene_id)
    
    def query_scenes(self, story_id: str, query: SceneQuery) -> List[Scene]:
        """Query scenes with filters."""
        return self.query_engine.query_scenes(story_id, query)
    
    def get_statistics(self, story_id: str) -> ComprehensiveStats:
        """Get comprehensive scene statistics."""
        return self.statistics_engine.generate_comprehensive_stats(story_id)
    
    def rollback_to_scene(self, story_id: str, scene_id: str) -> RollbackData:
        """Prepare rollback to specific scene."""
        return self.scene_manager.rollback_handler.prepare_rollback(story_id, scene_id)
```

## Implementation Benefits

### Immediate Improvements
1. **Single Responsibility**: Each class handles one aspect of scene management
2. **Testability**: Components can be tested independently with mock data
3. **Maintainability**: Changes to statistics don't affect scene persistence
4. **Type Safety**: Proper dataclasses and type hints throughout

### Long-term Advantages
1. **Performance**: Specialized engines can optimize specific operations
2. **Scalability**: Repository pattern allows for different storage backends
3. **Extensibility**: New analysis types or filtering options can be added easily
4. **Analytics**: Sophisticated scene analytics and pattern detection

## Migration Strategy

### Phase 1: Core Infrastructure (Week 1)
1. Create all dataclasses and scene structure
2. Implement SceneRepository with basic CRUD operations
3. Create SceneSerializer and ID generation system

### Phase 2: Tagging and Metadata (Week 2)
1. Extract TaggingEngine with token calculation and mood extraction
2. Implement sophisticated metadata generation
3. Create structured tag validation and management

### Phase 3: Querying and Filtering (Week 3)
1. Extract SceneQueryEngine with flexible filtering
2. Implement query optimization and builder patterns
3. Create comprehensive scene search capabilities

### Phase 4: Statistics and Analytics (Week 4)
1. Extract StatisticsEngine with pattern analysis
2. Implement character analytics and mood tracking
3. Create comprehensive reporting and trend analysis

### Phase 5: Integration and Management (Week 5)
1. Extract SceneManager with rollback and labeling
2. Integrate all components through main SceneLogger
3. Performance optimization and comprehensive testing

## Risk Assessment

### Low Risk
- **Scene Repository**: Well-defined CRUD operations with clear interfaces
- **Data Structures**: Straightforward dataclass definitions

### Medium Risk
- **Tagging System**: Complex metadata generation with multiple data sources
- **Query Engine**: SQL optimization and performance considerations

### High Risk
- **Migration**: Converting from functions to classes requires careful interface management
- **Statistics**: Complex analytical calculations with performance implications

## Conclusion

The `scene_logger.py` module represents a sophisticated scene management system that would significantly benefit from object-oriented refactoring. The proposed architecture separates persistence, tagging, querying, statistics, and management into focused components while maintaining all current functionality.

This refactoring would enable better performance through specialized engines, improved maintainability through clear separation of concerns, and provide a foundation for advanced scene analytics and AI-driven narrative analysis in future development.
