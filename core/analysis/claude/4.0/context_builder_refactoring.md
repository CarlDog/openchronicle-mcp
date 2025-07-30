# Context Builder - Refactoring Analysis

**File**: `core/context_builder.py`  
**Current Size**: 794 lines  
**Priority**: HIGH  
**Analysis Date**: July 30, 2025

## Executive Summary

The `context_builder.py` file serves as a central orchestration hub for assembling narrative context from multiple specialized engines. At 794 lines, it demonstrates the challenges of coordinating complex systems but suffers from significant responsibility violations, extensive engine coupling, and opportunities for better modularization.

## Current Architecture Analysis

### Strengths
- ✅ **Comprehensive context integration** from multiple engines
- ✅ **Multiple build strategies** (basic, analysis, dynamic)
- ✅ **Good error handling** and fallback mechanisms
- ✅ **Character-aware context building** with consistency tracking
- ✅ **Flexible canon and memory loading** system
- ✅ **Advanced validation** for consistency and emotional stability

### Critical Issues
- 🔴 **Massive engine coordination** - orchestrates 9+ different engines
- 🔴 **Mixed abstraction levels** - low-level JSON parsing + high-level orchestration
- 🔴 **Complex interdependencies** - engines tightly coupled in context building
- 🔴 **Multiple context build strategies** with significant code duplication
- 🔴 **Hard-coded prompt assembly** logic throughout methods
- 🔴 **Validation logic** mixed with context building
- 🔴 **Utility functions** mixed with orchestration logic

## Major Responsibility Violations Identified

### 1. **Data Loading & Transformation**
- Lines 24-61: `load_canon_snippets` - file system operations and format conversion
- Lines 62-84: `json_to_readable_text` - data transformation utilities
- Lines 689-717: `_detect_scene_characters` - character detection logic

### 2. **Context Assembly & Orchestration**
- Lines 85-141: `build_context` - basic context building
- Lines 142-239: `build_context_with_analysis` - analyzed context building  
- Lines 240-443: `build_context_with_dynamic_models` - advanced orchestration (~203 lines)

### 3. **Engine Coordination & Management**
- Lines 250-275: Engine initialization and configuration
- Lines 276-320: Analysis and model selection coordination
- Lines 321-410: Character engine coordination (style, consistency, emotional, stats, etc.)

### 4. **Validation & Post-Processing**
- Lines 500-563: `validate_character_consistency` 
- Lines 564-617: `validate_emotional_stability`
- Lines 618-646: `get_character_consistency_report`
- Lines 647-688: `get_emotional_stability_report`

### 5. **Prompt Engineering & Assembly**
- Lines 444-449: `_build_system_context`
- Lines 450-475: `_build_memory_context` 
- Lines 476-484: `_build_canon_context`
- Lines 485-499: `_assemble_context`

### 6. **Decision Logic & Intelligence**
- Lines 718-794: `_check_for_dice_resolution` - complex resolution detection (~76 lines)

## Detailed Refactoring Opportunities

### 1. **CRITICAL: Extract Data Loading System** (Lines 24-84, 689-717)

**Current Issues:**
- File system operations mixed with orchestration logic
- JSON transformation utilities embedded in main module
- Character detection logic scattered
- Hard-coded format conversion patterns

**Refactoring Recommendation:**
```
Extract to: core/context/data_loading/
├── __init__.py
├── canon_loader.py         # CanonLoader, file system operations
├── transformers.py         # JSONTransformer, format conversion
├── character_detector.py   # CharacterDetector, scene character identification
└── models.py              # Data loading configurations and models
```

**Benefits:**
- ✅ Testable data loading components
- ✅ Configurable format transformations
- ✅ Reusable character detection logic
- ✅ Clear separation from orchestration

### 2. **CRITICAL: Extract Context Assembly System** (Lines 444-499)

**Current Issues:**
- Prompt assembly logic scattered across multiple functions
- Hard-coded section formatting and ordering
- Context part management mixed with assembly
- Difficult to customize context structure

**Refactoring Recommendation:**
```
Extract to: core/context/assembly/
├── __init__.py
├── assembler.py           # ContextAssembler, main coordinator
├── builders.py            # SystemBuilder, MemoryBuilder, CanonBuilder
├── formatters.py          # ContextFormatter, section formatting
├── templates.py           # AssemblyTemplates, configurable structures
└── models.py             # Assembly configurations and data structures
```

### 3. **CRITICAL: Extract Engine Coordination** (Lines 250-443)

**Current Issues:**
- 9+ engines initialized and coordinated in single method
- Complex conditional logic for engine activation
- Engine interdependencies embedded in orchestration
- Difficult to test individual engine contributions

**Refactoring Recommendation:**
```
Extract to: core/context/coordination/
├── __init__.py
├── coordinator.py         # EngineCoordinator, main orchestration
├── managers.py           # EngineManager, initialization and lifecycle
├── strategies.py         # CoordinationStrategy, different orchestration approaches
├── dependencies.py       # DependencyResolver, engine interdependency management
└── models.py            # Coordination configurations and results
```

### 4. **HIGH: Extract Validation System** (Lines 500-688)

**Current Issues:**
- Validation logic mixed with context building
- Multiple validation types embedded in main module
- Report generation scattered across functions
- Validation results not standardized

**Refactoring Recommendation:**
```
Extract to: core/context/validation/
├── __init__.py
├── validator.py          # ContextValidator, validation coordinator
├── checkers.py          # ConsistencyChecker, EmotionalChecker
├── reporters.py         # ValidationReporter, report generation
└── models.py           # Validation results and configurations
```

### 5. **MEDIUM: Extract Context Build Strategies** (Lines 85-239)

**Current Issues:**
- Three different build strategies with significant duplication
- Strategy selection logic embedded in function names
- No clear strategy pattern implementation
- Difficult to add new build approaches

**Refactoring Recommendation:**
```
Extract to: core/context/strategies/
├── __init__.py
├── strategy.py          # ContextBuildStrategy (abstract base)
├── basic.py            # BasicContextStrategy
├── analysis.py         # AnalysisContextStrategy  
├── dynamic.py          # DynamicContextStrategy
└── factory.py          # StrategyFactory, strategy selection
```

### 6. **MEDIUM: Extract Decision Intelligence** (Lines 718-794)

**Current Issues:**
- Complex dice resolution detection embedded in main module
- Hard-coded resolution patterns and mappings
- Decision logic mixed with prompt generation
- Difficult to extend with new resolution types

**Refactoring Recommendation:**
```
Extract to: core/context/intelligence/
├── __init__.py
├── decision_detector.py  # DecisionDetector, resolution detection
├── patterns.py          # ResolutionPatterns, configurable detection patterns
├── intelligence.py      # ContextIntelligence, smart context enhancement
└── models.py           # Decision and intelligence data structures
```

## Code Duplication Analysis

### Pattern 1: Engine Initialization (Found 4+ times)
```python
# Repeated engine initialization pattern:
engine = SomeEngine()
engine.load_data(story_path)
if condition:
    result = engine.get_context(parameters)
    if result:
        context_parts["section"] = result
```

**Solution**: Extract to `EngineManager.initialize_and_execute(engine_type, story_path, operation)`

### Pattern 2: Context Part Assembly (Found 6+ times)
```python
# Repeated context assembly pattern:
context_parts = {}
context_parts["section"] = build_section(data)
if condition:
    context_parts["optional_section"] = build_optional(data)
final_context = assemble_context(context_parts)
```

**Solution**: Extract to `ContextAssembler` with fluent interface

### Pattern 3: Character Detection and Handling (Found 8+ times)
```python
# Repeated character handling:
if active_character:
    character_data = get_character_data(active_character)
    character_context = build_character_context(character_data)
    context_parts["character"] = character_context
```

**Solution**: Extract to `CharacterContextBuilder.build_for_character(character_name)`

### Pattern 4: Error Handling with Fallbacks (Found 10+ times)
```python
# Repeated error handling pattern:
try:
    result = operation()
    log_success("operation succeeded")
except Exception as e:
    log_error(f"operation failed: {e}")
    result = fallback_value
```

**Solution**: Extract to decorator `@with_fallback(fallback_value)`

### Pattern 5: Memory and Canon Loading (Found 3+ times)
```python
# Repeated loading pattern:
memory = load_current_memory(story_id)
canon_chunks = load_canon_snippets(story_path, refs)
optimized_data = optimize_data(analysis, data)
```

**Solution**: Extract to `DataLoader.load_story_data(story_id, story_path, analysis)`

### Pattern 6: Validation and Reporting (Found 4+ times)
```python
# Repeated validation pattern:
violations = engine.analyze_output(output, character, scene_id)
score = engine.get_score(character)
if violations:
    log_warnings(violations)
return {"violations": violations, "score": score}
```

**Solution**: Extract to `ValidationRunner.run_validation(engine, output, character, scene_id)`

## Proposed Refactored Structure

```
core/context/
├── __init__.py
├── context_builder.py              # Slim orchestrator (~150 lines)
│
├── data_loading/
│   ├── __init__.py
│   ├── canon_loader.py            # Canon file loading and caching
│   ├── transformers.py            # Data format transformations
│   ├── character_detector.py      # Scene character detection
│   └── models.py                 # Loading configurations
│
├── assembly/
│   ├── __init__.py
│   ├── assembler.py              # Context assembly coordinator
│   ├── builders.py               # Section builders (system, memory, canon)
│   ├── formatters.py             # Output formatting and templates
│   └── models.py                # Assembly data structures
│
├── coordination/
│   ├── __init__.py
│   ├── coordinator.py            # Engine coordination orchestrator
│   ├── managers.py               # Engine lifecycle management
│   ├── strategies.py             # Coordination strategies
│   └── dependencies.py           # Engine dependency resolution
│
├── strategies/
│   ├── __init__.py
│   ├── strategy.py               # Abstract strategy base
│   ├── basic.py                  # Basic context building
│   ├── analysis.py               # Analysis-driven building
│   ├── dynamic.py                # Dynamic model building
│   └── factory.py                # Strategy selection and factory
│
├── validation/
│   ├── __init__.py
│   ├── validator.py              # Validation coordinator
│   ├── checkers.py               # Individual validation checkers
│   ├── reporters.py              # Validation report generation
│   └── models.py                # Validation results and configs
│
├── intelligence/
│   ├── __init__.py
│   ├── decision_detector.py      # Decision and resolution detection
│   ├── patterns.py               # Detection patterns and rules
│   └── models.py                # Intelligence data structures
│
└── utils/
    ├── __init__.py
    ├── errors.py                 # Error handling decorators
    ├── logging.py                # Context-specific logging utilities
    └── helpers.py                # Shared helper functions
```

## Migration Strategy

### Phase 1: Extract Utility Functions (Low Risk - 4 hours)
1. Extract error handling decorators
2. Extract common helper functions
3. Extract logging utilities
4. Update all usage points

### Phase 2: Extract Data Loading (Medium Risk - 6 hours)
1. Extract canon loading and transformation
2. Extract character detection logic
3. Create data loading coordinator
4. Update context builders to use new loaders

### Phase 3: Extract Assembly System (Medium Risk - 6 hours)
1. Extract context section builders
2. Extract formatting and template logic
3. Create assembly coordinator
4. Update context building to use assemblers

### Phase 4: Extract Build Strategies (High Risk - 8 hours)
1. Create strategy base class and interface
2. Extract each build strategy to separate class
3. Create strategy factory
4. Update main orchestrator to use strategies

### Phase 5: Extract Coordination System (High Risk - 10 hours)
1. Extract engine management logic
2. Create coordination strategies
3. Extract dependency resolution
4. Update main context builder integration

### Phase 6: Extract Supporting Systems (Medium Risk - 6 hours)
1. Extract validation system
2. Extract intelligence and decision detection
3. Final integration testing

### Phase 7: Final Integration (Medium Risk - 4 hours)
1. Create slim main orchestrator
2. Comprehensive testing
3. Performance validation

## Immediate Quick Wins (Can implement today)

### 1. **Extract Constants** (20 minutes)
```python
# Move to constants.py
DEFAULT_CANON_LIMIT = 5
RESOLUTION_PATTERNS = {
    ResolutionType.PERSUASION: ["convince", "persuade", ...],
    # etc.
}
CHALLENGE_INDICATORS = ["try to", "attempt", "challenge", ...]
```

### 2. **Extract Utility Functions** (45 minutes)
```python
class ContextUtils:
    @staticmethod
    def detect_characters_in_text(text: str, characters: Dict) -> List[str]:
        # Extract character detection logic
    
    @staticmethod
    def format_context_section(title: str, content: List[str]) -> str:
        # Extract section formatting
```

### 3. **Extract Error Handling** (30 minutes)
```python
def with_engine_fallback(fallback_value=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_error(f"Engine operation failed: {e}")
                return fallback_value
        return wrapper
    return decorator
```

### 4. **Add Method Grouping** (15 minutes)
```python
# === DATA LOADING ===
def load_canon_snippets(...):
def json_to_readable_text(...):

# === CONTEXT BUILDING STRATEGIES ===
def build_context(...):
async def build_context_with_analysis(...):
async def build_context_with_dynamic_models(...):

# === VALIDATION ===
async def validate_character_consistency(...):
async def validate_emotional_stability(...):
```

## Testing Strategy

### Unit Test Priorities
1. **Data loading** - Test canon loading, transformation, character detection
2. **Assembly logic** - Test context section building and formatting
3. **Engine coordination** - Test engine initialization and orchestration
4. **Build strategies** - Test each strategy independently
5. **Validation** - Test consistency and emotional stability checking
6. **Integration** - End-to-end context building workflows

### Test Coverage Targets
- Data loaders: 95% (critical file operations)
- Assembly system: 90% (formatting and structure logic)
- Engine coordination: 85% (complex engine interactions)
- Build strategies: 90% (core business logic)
- Validation: 90% (quality assurance logic)
- Main orchestrator: 85% (integration logic)

## Estimated Effort

| Phase | Effort | Risk Level | Dependencies |
|-------|--------|------------|--------------|
| Extract Utilities | 4 hours | Very Low | None |
| Extract Data Loading | 6 hours | Medium | Utilities |
| Extract Assembly System | 6 hours | Medium | Data Loading |
| Extract Build Strategies | 8 hours | High | Assembly, Data Loading |
| Extract Coordination System | 10 hours | High | All above |
| Extract Supporting Systems | 6 hours | Medium | Coordination |
| Final Integration | 4 hours | Medium | All above |
| **Total** | **44 hours** | | |

## Success Metrics

- ✅ Reduced main file from 794 to ~150 lines (81% reduction)
- ✅ Created 6 focused modules with single responsibilities
- ✅ Eliminated 85%+ of code duplication in orchestration patterns
- ✅ Improved test coverage from current to >90%
- ✅ Zero functional regressions
- ✅ Maintainable strategy pattern for different context building approaches
- ✅ Testable engine coordination and validation systems

## Risk Assessment

### High Risk Areas
- **Engine coordination extraction** - Complex interdependencies between 9+ engines
- **Strategy extraction** - Different build approaches with shared dependencies
- **Integration testing** - Ensuring context quality and engine coordination is maintained

### Mitigation Strategies
- Preserve all existing engine interactions during extraction
- Comprehensive regression testing for context building quality
- Gradual migration with side-by-side comparison testing
- Feature flags for new vs. old coordination implementations

## Recommendations Priority

1. **IMMEDIATE** (This week): Extract utilities, constants, and error handling
2. **SHORT-TERM** (Next sprint): Extract data loading and assembly systems
3. **MEDIUM-TERM** (Following 2 sprints): Extract build strategies and coordination
4. **LONG-TERM** (Final sprint): Extract supporting systems and complete integration

This refactoring is **critical for system maintainability** - the current orchestration complexity makes it extremely difficult to test individual components and add new features. The context builder is a central coordination point that would benefit enormously from proper modularization.
