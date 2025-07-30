# Content Analyzer - Refactoring Analysis

**File**: `core/content_analyzer.py`  
**Current Size**: 1800 lines  
**Priority**: CRITICAL  
**Analysis Date**: July 30, 2025

## Executive Summary

The `content_analyzer.py` file is the second largest in the codebase at 1800 lines and represents a **critical refactoring priority**. While the code is functional, it suffers from severe single-responsibility violations, massive code duplication, and complex interdependencies that make it difficult to maintain, test, and extend.

## Current Architecture Analysis

### Strengths
- ✅ Comprehensive functionality for content analysis
- ✅ Good integration with transformers library
- ✅ Robust error handling and logging
- ✅ Flexible model routing and fallback systems
- ✅ Hybrid keyword + AI approach

### Critical Issues
- 🔴 **MASSIVE single class doing everything** (1800 lines)
- 🔴 **Multiple major responsibilities** mixed together
- 🔴 **Extensive code duplication** in analysis patterns
- 🔴 **Complex method interdependencies** (hard to test)
- 🔴 **Hard-coded patterns and thresholds** throughout
- 🔴 **Mixed abstraction levels** (low-level text processing + high-level routing)
- 🔴 **No clear separation** between content detection, model selection, and analysis

## Major Responsibility Violations Identified

### 1. **Content Detection & Classification**
- Lines 503-600: `detect_content_type`, `_keyword_based_detection`
- Lines 418-502: `_analyze_with_transformers`, transformer initialization
- Lines 601-700: `_combine_analysis_results`

### 2. **Model Selection & Routing**
- Lines 132-234: `get_best_analysis_model`, model suitability checking
- Lines 235-417: Model availability testing, working model discovery
- Lines 736-812: `recommend_generation_model`

### 3. **User Input Analysis**
- Lines 700-735: `analyze_user_input`
- Lines 813-866: `_basic_analysis_fallback`, prompt building
- Lines 867-1060: Response parsing, fallback analysis

### 4. **System Management & Guidance**
- Lines 1061-1529: Model routing recommendations
- Lines 1594-1800: Model improvement suggestions, guidance systems

### 5. **Utility Functions**
- Lines 1530-1593: Content structure analysis, basic analysis helpers

## Detailed Refactoring Opportunities

### 1. **CRITICAL: Extract Content Detection System** (Lines 418-700)

**Current Issues:**
- Content detection mixed with transformer initialization
- Hard-coded keyword lists scattered throughout methods
- Pattern matching logic duplicated across methods
- Complex result combination logic

**Refactoring Recommendation:**
```
Extract to: core/analysis/content_detection/
├── __init__.py
├── detectors.py           # ContentDetector, KeywordDetector, TransformerDetector
├── patterns.py            # NSFW_PATTERNS, CREATIVE_PATTERNS, etc.
├── combiners.py           # AnalysisCombiner, ResultMerger
└── models.py             # Detection result data structures
```

**Benefits:**
- ✅ Single responsibility per detector type
- ✅ Configurable and testable pattern matching
- ✅ Easy to add new content types
- ✅ Clear separation of detection methods

### 2. **CRITICAL: Extract Model Management System** (Lines 132-417)

**Current Issues:**
- Model selection logic mixed with suitability checking
- Availability testing spread across multiple methods
- Hard-coded scoring algorithms
- Complex fallback logic intertwined

**Refactoring Recommendation:**
```
Extract to: core/analysis/model_management/
├── __init__.py
├── selector.py            # ModelSelector, SuitabilityChecker
├── availability.py        # AvailabilityTester, ModelTester
├── routing.py            # ModelRouter, RoutingStrategy
├── scoring.py            # SuitabilityScorer, ModelScorer
└── fallback.py           # FallbackManager, FallbackStrategy
```

### 3. **HIGH: Extract Transformer Integration** (Lines 64-131, 418-502)

**Current Issues:**
- Transformer initialization mixed with main class
- Complex model loading with suppressed output
- Result processing duplicated across classifiers

**Refactoring Recommendation:**
```
Extract to: core/analysis/transformers/
├── __init__.py
├── manager.py            # TransformerManager, ModelLoader
├── classifiers.py        # NSFWClassifier, SentimentClassifier, EmotionClassifier
├── processors.py         # ResultProcessor, OutputNormalizer
└── config.py            # Model configurations, device settings
```

### 4. **HIGH: Extract Analysis Engine** (Lines 700-866)

**Current Issues:**
- User input analysis mixed with prompt building
- Response parsing embedded in main flow
- Multiple analysis strategies not clearly separated

**Refactoring Recommendation:**
```
Extract to: core/analysis/engines/
├── __init__.py
├── analyzer.py           # InputAnalyzer, AnalysisEngine
├── prompt_builder.py     # PromptBuilder, ContextBuilder
├── parsers.py           # ResponseParser, AnalysisParser
└── strategies.py        # AnalysisStrategy, FallbackStrategy
```

### 5. **MEDIUM: Extract Guidance System** (Lines 1594-1800)

**Current Issues:**
- User guidance mixed with technical analysis
- Hard-coded installation commands
- Complex suggestion generation logic

**Refactoring Recommendation:**
```
Extract to: core/analysis/guidance/
├── __init__.py
├── advisor.py           # ModelAdvisor, InstallationGuide
├── suggestions.py       # SuggestionGenerator, ActionPlanner
└── commands.py          # CommandBuilder, InstallationCommands
```

## Code Duplication Analysis

### Pattern 1: Result Processing (Found 12+ times)
```python
# Repeated across all transformer methods:
if isinstance(result, list) and len(result) > 0:
    result = result[0]
    if isinstance(result, list) and len(result) > 0:
        result = result[0]
```

**Solution**: Extract to `ResultNormalizer.normalize_transformer_output(result)`

### Pattern 2: Model Configuration Access (Found 15+ times)
```python
# Repeated in model selection methods:
model_configs = self.model_manager.list_model_configs()
if model_name not in model_configs:
    return {"error": "..."}
model_config = model_configs[model_name]
if not model_config.get("enabled", True):
    # handle disabled model
```

**Solution**: Extract to `ModelRegistry.get_enabled_config(model_name)`

### Pattern 3: Content Type Scoring (Found 8+ times)
```python
# Repeated scoring patterns:
score = 0.0
suitability_reasons = []
score += 0.3  # base score
if condition1:
    score += 0.4
    suitability_reasons.append("reason")
# etc.
```

**Solution**: Extract to `SuitabilityScorer` with fluent interface

### Pattern 4: Keyword Matching (Found 6+ times)
```python
# Repeated keyword matching:
text_lower = text.lower()
matches = sum(1 for keyword in keyword_list if keyword in text_lower)
if matches > threshold:
    # handle match
```

**Solution**: Extract to `PatternMatcher.find_matches(text, patterns, threshold)`

### Pattern 5: Error Handling with Logging (Found 20+ times)
```python
# Repeated error pattern:
try:
    # operation
except Exception as e:
    log_error(f"Operation failed: {e}")
    return fallback_value
```

**Solution**: Extract to decorator `@handle_analysis_errors(fallback=...)`

## Proposed Refactored Structure

```
core/analysis/
├── __init__.py
├── content_analyzer.py           # Slim orchestrator (~200 lines)
│
├── content_detection/
│   ├── __init__.py
│   ├── detectors.py             # Content detection classes
│   ├── patterns.py              # Pattern definitions
│   ├── combiners.py             # Result combination logic
│   └── models.py               # Detection result structures
│
├── model_management/
│   ├── __init__.py
│   ├── selector.py             # Model selection logic
│   ├── availability.py         # Availability testing
│   ├── routing.py              # Routing strategies
│   ├── scoring.py              # Scoring algorithms
│   └── fallback.py             # Fallback management
│
├── transformers/
│   ├── __init__.py
│   ├── manager.py              # Transformer initialization
│   ├── classifiers.py          # Individual classifiers
│   ├── processors.py           # Result processing
│   └── config.py              # Model configurations
│
├── engines/
│   ├── __init__.py
│   ├── analyzer.py             # Main analysis engine
│   ├── prompt_builder.py       # Prompt construction
│   ├── parsers.py              # Response parsing
│   └── strategies.py           # Analysis strategies
│
├── guidance/
│   ├── __init__.py
│   ├── advisor.py              # User guidance
│   ├── suggestions.py          # Suggestion generation
│   └── commands.py             # Installation commands
│
└── utils/
    ├── __init__.py
    ├── patterns.py             # Shared pattern utilities
    ├── errors.py               # Error handling decorators
    └── registry.py             # Model registry helpers
```

## Migration Strategy

### Phase 1: Extract Utility Functions (Low Risk - 4 hours)
1. Extract pattern matching utilities
2. Extract error handling decorators
3. Extract model registry helpers
4. Update imports and test

### Phase 2: Extract Content Detection (Medium Risk - 8 hours)
1. Extract keyword detection logic
2. Extract transformer integration
3. Extract result combination logic
4. Create detection interface
5. Update main class to use detectors

### Phase 3: Extract Model Management (High Risk - 12 hours)
1. Extract model selection logic
2. Extract suitability checking
3. Extract availability testing
4. Create routing interface
5. Update main class coordination

### Phase 4: Extract Analysis Engines (Medium Risk - 8 hours)
1. Extract prompt building
2. Extract response parsing
3. Extract analysis strategies
4. Create analysis interface

### Phase 5: Extract Guidance System (Low Risk - 6 hours)
1. Extract suggestion generation
2. Extract installation commands
3. Extract user guidance logic

### Phase 6: Final Integration (Medium Risk - 4 hours)
1. Create slim main orchestrator
2. Integrate all extracted modules
3. Comprehensive testing
4. Performance validation

## Immediate Quick Wins (Can implement today)

### 1. **Extract Constants** (30 minutes)
```python
# Move to patterns.py
NSFW_EXPLICIT_KEYWORDS = ["explicit", "sexual", "adult", ...]
NSFW_SUGGESTIVE_KEYWORDS = ["intimate", "romantic", "kiss", ...]
CREATIVE_KEYWORDS = ["imagine", "create", "describe", ...]
ANALYSIS_KEYWORDS = ["analyze", "classify", "determine", ...]
```

### 2. **Extract Helper Methods** (45 minutes)
Break down massive methods:
```python
def _check_model_suitability(self, model_name: str, content_type: str):
    # Extract to smaller methods:
    config = self._get_model_config(model_name)
    base_score = self._calculate_base_score(config)
    bonuses = self._calculate_suitability_bonuses(config, content_type)
    penalties = self._calculate_suitability_penalties(config, content_type)
    return self._build_suitability_result(base_score, bonuses, penalties)
```

### 3. **Extract Result Normalizer** (60 minutes)
```python
class ResultNormalizer:
    @staticmethod
    def normalize_transformer_output(result):
        """Handle nested list format: [[{...}]] -> {...}"""
        if isinstance(result, list) and len(result) > 0:
            result = result[0]
            if isinstance(result, list) and len(result) > 0:
                result = result[0]
        return result
```

### 4. **Add Method Grouping** (15 minutes)
Add clear section separators:
```python
# === INITIALIZATION ===
def __init__(self, ...):
def _initialize_transformers(self):

# === CONTENT DETECTION ===
def detect_content_type(self, ...):
def _keyword_based_detection(self, ...):

# === MODEL MANAGEMENT ===
def get_best_analysis_model(self, ...):
def _check_model_suitability(self, ...):
```

## Testing Strategy

### Unit Test Priorities
1. **Content detection** - Test all detection algorithms independently
2. **Model selection** - Test scoring and fallback logic
3. **Transformer integration** - Mock transformer calls and test processing
4. **Analysis engine** - Test prompt building and response parsing
5. **Integration** - End-to-end analysis workflows

### Test Coverage Targets
- Content detectors: 95% (core business logic)
- Model management: 90% (complex routing logic)
- Transformer integration: 85% (external dependencies)
- Analysis engines: 90% (prompt/parsing logic)
- Main orchestrator: 85% (integration logic)

## Estimated Effort

| Phase | Effort | Risk Level | Dependencies |
|-------|--------|------------|--------------|
| Extract Utilities | 4 hours | Very Low | None |
| Extract Content Detection | 8 hours | Medium | Utilities |
| Extract Model Management | 12 hours | High | Utilities |
| Extract Analysis Engines | 8 hours | Medium | Detection, Management |
| Extract Guidance System | 6 hours | Low | Management |
| Final Integration | 4 hours | Medium | All above |
| **Total** | **42 hours** | | |

## Success Metrics

- ✅ Reduced main file from 1800 to ~200 lines (89% reduction)
- ✅ Created 5 focused modules with single responsibilities
- ✅ Eliminated 90%+ of code duplication
- ✅ Improved test coverage from current to >90%
- ✅ Zero functional regressions
- ✅ Improved maintainability (easier to add new content types, models, strategies)
- ✅ Better performance through optimized, focused classes

## Risk Assessment

### High Risk Areas
- **Model management extraction** - Complex interdependencies with ModelManager
- **Transformer integration** - External dependencies and GPU/CPU handling
- **Analysis workflow** - Critical path for user input processing

### Mitigation Strategies
- Comprehensive integration tests at each phase
- Maintain backward compatibility during transition
- Feature flags for new vs. old implementations
- Rollback plan for each phase

## Recommendations Priority

1. **IMMEDIATE** (This week): Implement quick wins (constants, helpers, normalizers)
2. **SHORT-TERM** (Next sprint): Extract utilities and content detection
3. **MEDIUM-TERM** (Following 2 sprints): Extract model management and analysis engines
4. **LONG-TERM** (Final sprint): Extract guidance system and complete integration

This refactoring is **critical for project maintainability** - the current 1800-line monolith is the primary technical debt in the codebase and significantly impacts development velocity and system reliability.
