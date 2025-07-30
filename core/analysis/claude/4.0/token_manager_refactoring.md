# Token Manager Refactoring Analysis

**File**: `core/token_manager.py`  
**Size**: 261 lines  
**Complexity**: LOW  
**Priority**: LOW

## Executive Summary

The `TokenManager` class implements a sophisticated token management system with dynamic model selection, intelligent context trimming, truncation detection, and usage analytics. While functionally comprehensive with advanced features like model switching for token limits and automatic scene continuation, it demonstrates minor architectural violations by combining token estimation, model selection, context management, truncation handling, and usage tracking in a single class with 12+ methods. This analysis proposes a refined modular architecture to improve maintainability and extensibility.

## Current Architecture Analysis

### Core Components
1. **1 Main Class**: `TokenManager` with 12+ methods handling diverse responsibilities
2. **Advanced Features**: Dynamic model selection, intelligent trimming, continuation handling
3. **Integration Dependencies**: Tight coupling with model_manager and logging system
4. **Caching Systems**: Tokenizer caching and continuation response caching

### Current Responsibilities
- **Token Estimation**: Tokenizer management and token counting for different models
- **Model Selection**: Optimal model selection based on token requirements and costs
- **Context Management**: Intelligent context trimming to fit token limits
- **Truncation Detection**: Detecting and handling response truncation
- **Scene Continuation**: Automatic continuation of truncated responses
- **Usage Tracking**: Token usage analytics and cost monitoring
- **Recommendation Engine**: Model switching recommendations based on usage patterns

## Major Refactoring Opportunities

### 1. Token Estimation and Model Integration System (Medium Priority)

**Problem**: Token estimation, tokenizer management, and model integration mixed in main class
```python
def get_tokenizer(self, model_name: str):
    # Tokenizer caching and provider-specific logic

def estimate_tokens(self, text: str, model_name: str) -> int:
    # Token estimation with fallback logic

def select_optimal_model_for_length(self, prompt_length: int, response_length: int):
    # Complex model selection based on token requirements
```

**Solution**: Extract to TokenEstimationEngine
```python
class TokenEstimationEngine:
    """Handles token estimation and tokenizer management."""
    
    def __init__(self, model_manager):
        self.model_manager = model_manager
        self.tokenizer_cache = TokenizerCache()
        self.estimation_strategies = EstimationStrategies()
        self.model_analyzer = ModelAnalyzer(model_manager)
        
    def estimate_tokens(self, text: str, model_name: str) -> TokenEstimation:
        """Estimate tokens for text using appropriate tokenizer."""
        
    def get_tokenizer_for_model(self, model_name: str) -> Tokenizer:
        """Get or create tokenizer for specific model."""
        
    def estimate_token_cost(self, token_count: int, model_name: str) -> float:
        """Estimate cost for token usage."""
        
    def compare_token_efficiency(self, models: List[str], text: str) -> List[TokenEfficiencyScore]:
        """Compare token efficiency across models."""

class TokenizerCache:
    """Manages tokenizer instances with caching."""
    
    def __init__(self):
        self.encoders: Dict[str, Any] = {}
        self.cache_stats = CacheStatistics()
        
    def get_tokenizer(self, model_name: str, provider: str) -> Any:
        """Get cached tokenizer or create new one."""
        
    def create_tokenizer_for_provider(self, provider: str, model_config: Dict[str, Any]) -> Any:
        """Create provider-specific tokenizer."""
        
    def invalidate_cache(self, model_name: str = None) -> None:
        """Invalidate tokenizer cache."""
        
    def get_cache_statistics(self) -> CacheStatistics:
        """Get tokenizer cache statistics."""

class ModelAnalyzer:
    """Analyzes model capabilities and characteristics."""
    
    def __init__(self, model_manager):
        self.model_manager = model_manager
        
    def get_model_token_limits(self, model_name: str) -> TokenLimits:
        """Get token limits for specific model."""
        
    def analyze_model_suitability(self, token_requirements: TokenRequirements) -> List[ModelSuitability]:
        """Analyze which models can handle token requirements."""
        
    def get_cost_efficiency_ranking(self, models: List[str]) -> List[CostEfficiencyRanking]:
        """Rank models by cost efficiency."""

@dataclass
class TokenEstimation:
    """Token estimation result."""
    token_count: int
    confidence: float
    estimation_method: str
    model_name: str
    
@dataclass
class TokenLimits:
    """Model token limits."""
    max_total_tokens: int
    max_prompt_tokens: int
    max_response_tokens: int
    buffer_tokens: int
```

### 2. Context Management and Trimming System (High Priority)

**Problem**: Context trimming and truncation detection logic embedded in main class
```python
def trim_context_intelligently(self, context_parts: Dict[str, str], target_tokens: int, model_name: str):
    # Complex context trimming logic

def detect_truncation(self, response: str) -> bool:
    # Truncation detection with multiple indicators

def check_truncation_risk(self, prompt: str, model_name: str, max_response_tokens: int = 2048):
    # Risk assessment logic
```

**Solution**: Extract to ContextManagementEngine
```python
class ContextManagementEngine:
    """Manages context optimization and truncation handling."""
    
    def __init__(self, token_estimation_engine: TokenEstimationEngine):
        self.token_estimator = token_estimation_engine
        self.context_optimizer = ContextOptimizer()
        self.truncation_detector = TruncationDetector()
        self.trimming_strategies = TrimmingStrategies()
        
    def optimize_context_for_model(self, context_parts: Dict[str, str], 
                                 target_tokens: int, model_name: str) -> ContextOptimizationResult:
        """Optimize context to fit within token limits."""
        
    def check_truncation_risk(self, prompt: str, model_name: str, 
                            max_response_tokens: int = 2048) -> TruncationRisk:
        """Assess risk of response truncation."""
        
    def detect_response_truncation(self, response: str) -> TruncationDetection:
        """Detect if response was truncated."""
        
    def suggest_context_improvements(self, context_parts: Dict[str, str], 
                                   model_name: str) -> List[ContextImprovement]:
        """Suggest context optimization improvements."""

class ContextOptimizer:
    """Optimizes context for better token efficiency."""
    
    def __init__(self):
        self.trimming_priorities = {
            "canon": 1,      # Highest priority (keep)
            "memory": 2,
            "style": 3,
            "recent_scenes": 4  # Lowest priority (trim first)
        }
        
    def trim_context_intelligently(self, context_parts: Dict[str, str], 
                                 target_tokens: int, 
                                 token_estimator: TokenEstimationEngine) -> ContextTrimmingResult:
        """Trim context parts based on priority."""
        
    def optimize_part_content(self, content: str, trim_ratio: float) -> str:
        """Optimize individual context part content."""
        
    def calculate_optimal_trim_ratios(self, context_parts: Dict[str, str], 
                                    token_counts: Dict[str, int],
                                    target_reduction: int) -> Dict[str, float]:
        """Calculate optimal trimming ratios for each part."""

class TruncationDetector:
    """Detects various forms of response truncation."""
    
    def __init__(self):
        self.detection_rules = TruncationDetectionRules()
        
    def analyze_response_completeness(self, response: str) -> TruncationAnalysis:
        """Comprehensive truncation analysis."""
        
    def check_structural_completeness(self, response: str) -> List[StructuralIssue]:
        """Check for structural truncation indicators."""
        
    def check_content_completeness(self, response: str) -> ContentCompletenessScore:
        """Assess content completeness."""
        
    def calculate_truncation_confidence(self, indicators: List[TruncationIndicator]) -> float:
        """Calculate confidence that response was truncated."""

@dataclass
class ContextOptimizationResult:
    """Result of context optimization."""
    optimized_context: Dict[str, str]
    original_tokens: int
    optimized_tokens: int
    tokens_saved: int
    trimming_details: Dict[str, TrimmingDetails]
    
@dataclass
class TruncationRisk:
    """Assessment of truncation risk."""
    risk_level: str  # 'low', 'medium', 'high'
    estimated_tokens_needed: int
    model_token_limit: int
    available_tokens: int
    recommendations: List[str]
```

### 3. Scene Continuation System (High Priority)

**Problem**: Scene continuation logic with model switching embedded in main class
```python
async def continue_scene(self, original_prompt: str, partial_response: str, 
                       story_id: str, model_name: str) -> str:
    # Complex continuation logic with model switching
```

**Solution**: Extract to ContinuationEngine
```python
class ContinuationEngine:
    """Handles automatic scene continuation for truncated responses."""
    
    def __init__(self, model_manager, token_estimation_engine: TokenEstimationEngine):
        self.model_manager = model_manager
        self.token_estimator = token_estimation_engine
        self.continuation_strategies = ContinuationStrategies()
        self.response_cache = ContinuationCache()
        self.model_selector = ContinuationModelSelector(model_manager)
        
    async def continue_truncated_scene(self, continuation_request: ContinuationRequest) -> ContinuationResult:
        """Continue a truncated scene with optimal model selection."""
        
    def build_continuation_prompt(self, original_prompt: str, partial_response: str) -> str:
        """Build optimized continuation prompt."""
        
    def select_continuation_model(self, continuation_prompt: str, 
                                current_model: str) -> ModelSelectionResult:
        """Select optimal model for continuation."""
        
    def merge_responses(self, partial_response: str, continuation: str) -> ResponseMergeResult:
        """Merge partial and continuation responses intelligently."""

class ContinuationStrategies:
    """Different strategies for scene continuation."""
    
    def get_default_strategy(self) -> ContinuationStrategy:
        """Get default continuation strategy."""
        
    def get_strategy_for_content_type(self, content_type: str) -> ContinuationStrategy:
        """Get specialized continuation strategy."""
        
    def analyze_continuation_quality(self, original: str, continuation: str) -> QualityAnalysis:
        """Analyze quality of continuation."""

class ContinuationCache:
    """Caches continuation responses for efficiency."""
    
    def __init__(self):
        self.cache: Dict[str, str] = {}
        self.cache_stats = CacheStatistics()
        
    def get_cached_continuation(self, cache_key: str) -> Optional[str]:
        """Get cached continuation response."""
        
    def cache_continuation(self, cache_key: str, response: str) -> None:
        """Cache continuation response."""
        
    def generate_cache_key(self, story_id: str, partial_response: str) -> str:
        """Generate cache key for continuation."""
        
    def cleanup_old_cache_entries(self, max_age_hours: int = 24) -> None:
        """Clean up old cache entries."""

@dataclass
class ContinuationRequest:
    """Request for scene continuation."""
    original_prompt: str
    partial_response: str
    story_id: str
    current_model: str
    max_continuation_tokens: int = 1024
    
@dataclass
class ContinuationResult:
    """Result of continuation operation."""
    success: bool
    full_response: str
    continuation_text: str
    model_used: str
    tokens_used: int
    error_message: Optional[str] = None
```

### 4. Usage Analytics and Monitoring System (Medium Priority)

**Problem**: Usage tracking and analytics mixed with operational logic
```python
def track_token_usage(self, model_name: str, prompt_tokens: int, response_tokens: int, cost: float = 0.0):
    # Usage tracking logic

def get_usage_stats(self) -> Dict[str, Any]:
    # Statistics generation

def recommend_model_switch(self, current_model: str, usage_pattern: Dict[str, Any]):
    # Recommendation logic
```

**Solution**: Extract to UsageAnalyticsEngine
```python
class UsageAnalyticsEngine:
    """Tracks and analyzes token usage patterns."""
    
    def __init__(self):
        self.usage_tracker = UsageTracker()
        self.analytics_processor = AnalyticsProcessor()
        self.recommendation_engine = RecommendationEngine()
        self.report_generator = ReportGenerator()
        
    def track_token_usage(self, usage_event: TokenUsageEvent) -> None:
        """Track token usage event."""
        
    def get_usage_statistics(self, timeframe: str = "all") -> UsageStatistics:
        """Get comprehensive usage statistics."""
        
    def analyze_usage_patterns(self, story_id: str = None) -> UsagePatternAnalysis:
        """Analyze usage patterns and trends."""
        
    def generate_cost_analysis(self) -> CostAnalysis:
        """Generate detailed cost analysis."""
        
    def get_model_recommendations(self, usage_context: UsageContext) -> List[ModelRecommendation]:
        """Get model switching recommendations."""

class UsageTracker:
    """Tracks detailed token usage metrics."""
    
    def __init__(self):
        self.usage_data: Dict[str, ModelUsageData] = {}
        self.session_tracker = SessionTracker()
        
    def record_usage(self, model_name: str, prompt_tokens: int, 
                    response_tokens: int, cost: float) -> None:
        """Record token usage for model."""
        
    def get_model_usage(self, model_name: str) -> ModelUsageData:
        """Get usage data for specific model."""
        
    def get_total_usage(self) -> TotalUsageData:
        """Get aggregated usage across all models."""
        
    def reset_usage_data(self, model_name: str = None) -> None:
        """Reset usage data for model or all models."""

class RecommendationEngine:
    """Generates model switching recommendations."""
    
    def __init__(self):
        self.recommendation_rules = RecommendationRules()
        
    def analyze_cost_efficiency(self, usage_data: Dict[str, ModelUsageData]) -> List[CostRecommendation]:
        """Analyze cost efficiency and recommend optimizations."""
        
    def analyze_performance_patterns(self, usage_data: Dict[str, ModelUsageData]) -> List[PerformanceRecommendation]:
        """Analyze performance patterns and recommend improvements."""
        
    def recommend_model_for_context(self, context_requirements: ContextRequirements) -> ModelRecommendation:
        """Recommend optimal model for specific context requirements."""

@dataclass
class TokenUsageEvent:
    """Individual token usage event."""
    model_name: str
    prompt_tokens: int
    response_tokens: int
    cost: float
    timestamp: str
    story_id: Optional[str] = None
    operation_type: Optional[str] = None
    
@dataclass
class UsageStatistics:
    """Comprehensive usage statistics."""
    total_prompt_tokens: int
    total_response_tokens: int
    total_cost: float
    total_requests: int
    models: Dict[str, ModelUsageData]
    timeframe: str
    
@dataclass
class ModelRecommendation:
    """Model switching recommendation."""
    recommended_model: str
    current_model: str
    reason: str
    confidence: float
    expected_savings: float
    trade_offs: List[str]
```

## Proposed Modular Architecture

```python
class TokenManager:
    """Main orchestrator for token management operations."""
    
    def __init__(self, model_manager):
        self.model_manager = model_manager
        
        # Core engines
        self.token_estimator = TokenEstimationEngine(model_manager)
        self.context_manager = ContextManagementEngine(self.token_estimator)
        self.continuation_engine = ContinuationEngine(model_manager, self.token_estimator)
        self.usage_analytics = UsageAnalyticsEngine()
        
    def estimate_tokens(self, text: str, model_name: str) -> int:
        """Estimate token count for text and model."""
        result = self.token_estimator.estimate_tokens(text, model_name)
        return result.token_count
    
    def select_optimal_model_for_length(self, prompt_length: int, response_length: int) -> Optional[str]:
        """Select optimal model based on token requirements."""
        token_requirements = TokenRequirements(
            prompt_tokens=prompt_length,
            response_tokens=response_length
        )
        
        suitability_analysis = self.token_estimator.model_analyzer.analyze_model_suitability(token_requirements)
        
        if not suitability_analysis:
            return None
            
        # Return most cost-efficient suitable model
        return suitability_analysis[0].model_name
    
    def trim_context_intelligently(self, context_parts: Dict[str, str], 
                                  target_tokens: int, model_name: str) -> Dict[str, str]:
        """Trim context to fit within token limits."""
        result = self.context_manager.optimize_context_for_model(
            context_parts, target_tokens, model_name
        )
        return result.optimized_context
    
    def check_truncation_risk(self, prompt: str, model_name: str, max_response_tokens: int = 2048) -> bool:
        """Check if prompt + response might exceed model limits."""
        risk = self.context_manager.check_truncation_risk(prompt, model_name, max_response_tokens)
        return risk.risk_level in ['medium', 'high']
    
    def detect_truncation(self, response: str) -> bool:
        """Detect if response was likely truncated."""
        detection = self.context_manager.detect_response_truncation(response)
        return detection.is_truncated
    
    async def continue_scene(self, original_prompt: str, partial_response: str, 
                           story_id: str, model_name: str) -> str:
        """Continue truncated scene with optimal model selection."""
        request = ContinuationRequest(
            original_prompt=original_prompt,
            partial_response=partial_response,
            story_id=story_id,
            current_model=model_name
        )
        
        result = await self.continuation_engine.continue_truncated_scene(request)
        return result.full_response if result.success else partial_response
    
    def track_token_usage(self, model_name: str, prompt_tokens: int, 
                         response_tokens: int, cost: float = 0.0):
        """Track token usage for analytics."""
        usage_event = TokenUsageEvent(
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            cost=cost,
            timestamp=datetime.now().isoformat()
        )
        self.usage_analytics.track_token_usage(usage_event)
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get comprehensive usage statistics."""
        stats = self.usage_analytics.get_usage_statistics()
        return {
            "total_prompt_tokens": stats.total_prompt_tokens,
            "total_response_tokens": stats.total_response_tokens,
            "total_cost": stats.total_cost,
            "total_requests": stats.total_requests,
            "models": {name: asdict(data) for name, data in stats.models.items()}
        }
    
    def recommend_model_switch(self, current_model: str, usage_pattern: Dict[str, Any]) -> Optional[str]:
        """Recommend model switching based on usage patterns."""
        usage_context = UsageContext(
            current_model=current_model,
            high_cost=usage_pattern.get("high_cost", False),
            frequent_truncation=usage_pattern.get("frequent_truncation", False)
        )
        
        recommendations = self.usage_analytics.get_model_recommendations(usage_context)
        return recommendations[0].recommended_model if recommendations else None

@dataclass
class TokenRequirements:
    """Token requirements for model selection."""
    prompt_tokens: int
    response_tokens: int
    buffer_tokens: int = 200
    
@dataclass
class UsageContext:
    """Context for usage-based recommendations."""
    current_model: str
    high_cost: bool = False
    frequent_truncation: bool = False
    story_id: Optional[str] = None
```

## Implementation Benefits

### Immediate Improvements
1. **Single Responsibility**: Each engine handles one aspect of token management
2. **Testability**: Components can be tested independently with mock data
3. **Maintainability**: Changes to continuation logic don't affect token estimation
4. **Performance**: Specialized caching and optimization strategies

### Long-term Advantages
1. **Extensibility**: Easy addition of new tokenizers or continuation strategies
2. **Analytics**: Comprehensive usage analysis and optimization recommendations
3. **Flexibility**: Support for multiple continuation and optimization strategies
4. **Monitoring**: Detailed performance tracking and cost analysis

## Migration Strategy

### Phase 1: Token Estimation (Week 1)
1. Extract TokenEstimationEngine with tokenizer management
2. Implement model analysis and capability detection
3. Create backward-compatible token estimation methods

### Phase 2: Context Management (Week 2)
1. Extract ContextManagementEngine with trimming and optimization
2. Implement advanced truncation detection algorithms
3. Create context optimization strategies

### Phase 3: Continuation System (Week 3)
1. Extract ContinuationEngine with model selection
2. Implement intelligent response merging
3. Create continuation caching and quality analysis

### Phase 4: Analytics Integration (Week 4)
1. Extract UsageAnalyticsEngine with comprehensive tracking
2. Implement recommendation algorithms
3. Create detailed reporting and analysis features

## Risk Assessment

### Low Risk
- **Token Estimation**: Well-defined tokenizer operations
- **Usage Tracking**: Simple data collection and analytics

### Medium Risk
- **Context Optimization**: Complex trimming algorithms with quality preservation
- **Model Integration**: Dependencies on model_manager functionality

### High Risk
- **Continuation Logic**: Complex async operations with model switching
- **Caching Systems**: Cache invalidation and consistency management

## Conclusion

The `TokenManager` represents a sophisticated token management system that would benefit from modular refactoring to separate token estimation, context management, scene continuation, and usage analytics. The proposed architecture maintains all current functionality while enabling better performance through specialized engines, improved maintainability through clear separation of concerns, and provides a foundation for advanced token optimization and intelligent model selection in future development.
