# Character Consistency Engine - Refactoring Analysis

**File**: `core/character_consistency_engine.py`  
**Current Size**: 529 lines  
**Priority**: HIGH  
**Analysis Date**: July 30, 2025

## Executive Summary

The `character_consistency_engine.py` file is well-structured but has clear opportunities for modularization and code deduplication. While the current implementation is functional, breaking it into focused modules would improve maintainability, testability, and align with single-responsibility principles.

## Current Architecture Analysis

### Strengths
- ✅ Clear class and method organization
- ✅ Comprehensive type hints and dataclasses
- ✅ Good use of enums for violation types
- ✅ Consistent error handling and logging
- ✅ Well-documented methods and purposes

### Areas for Improvement
- 🔴 Single large class handling multiple responsibilities
- 🔴 Repetitive pattern matching code
- 🔴 Hard-coded violation detection logic
- 🔴 Mixed data processing and business logic
- 🔴 Large methods that could be decomposed

## Identified Refactoring Opportunities

### 1. **CRITICAL: Extract Violation Detection Logic** (Lines 235-420)

**Current Issues:**
- Methods `_check_motivation_violations`, `_check_trait_violations`, and `_check_emotional_contradictions` contain repetitive pattern matching
- Hard-coded dictionaries and lists scattered throughout methods
- Similar text analysis patterns repeated across different violation types

**Refactoring Recommendation:**
```
Extract to: core/consistency/violation_detectors.py
Classes:
- AbstractViolationDetector (base class)
- MotivationViolationDetector
- TraitViolationDetector  
- EmotionalContradictionDetector
- PatternBasedDetector (shared functionality)
```

**Benefits:**
- ✅ Single responsibility per detector
- ✅ Easy to add new violation types
- ✅ Testable in isolation
- ✅ Reusable pattern matching logic

### 2. **HIGH: Extract Anchor Management** (Lines 92-177)

**Current Issues:**
- Anchor creation logic mixed with data processing
- Complex conditional logic for different anchor types
- Repeated patterns for emotional vs. stat anchors

**Refactoring Recommendation:**
```
Extract to: core/consistency/anchor_factory.py
Classes:
- AnchorFactory (main factory)
- EmotionalAnchorBuilder
- StatAnchorBuilder
- AnchorValidator
```

**Benefits:**
- ✅ Clear separation of anchor creation logic
- ✅ Easy to extend with new anchor types
- ✅ Centralized anchor validation

### 3. **HIGH: Extract Data Structures** (Lines 17-50)

**Current Issues:**
- Dataclasses and enums mixed with main engine logic
- Could be reused by other consistency-related modules

**Refactoring Recommendation:**
```
Extract to: core/consistency/models.py
Contains:
- ConsistencyViolationType (enum)
- ConsistencyViolation (dataclass)
- MotivationAnchor (dataclass)
- Additional consistency-related data structures
```

### 4. **MEDIUM: Extract Pattern Definitions** (Lines 346-376)

**Current Issues:**
- Hard-coded dictionaries and lists for violation patterns
- Not easily configurable or extensible
- Mixed with detection logic

**Refactoring Recommendation:**
```
Extract to: core/consistency/patterns.py or patterns.json
Structure:
- TRAIT_VIOLATION_PATTERNS (dict)
- EMOTIONAL_CONTRADICTION_PATTERNS (list)
- MOTIVATION_PATTERNS (dict)
- Configuration loader for external pattern files
```

### 5. **MEDIUM: Extract Scoring Logic** (Lines 426-440)

**Current Issues:**
- Scoring algorithm embedded in main class
- Could benefit from different scoring strategies

**Refactoring Recommendation:**
```
Extract to: core/consistency/scoring.py
Classes:
- ConsistencyScorer (abstract base)
- ViolationBasedScorer (current implementation)
- WeightedScorer (future enhancement)
```

## Detailed Code Duplication Analysis

### Pattern 1: Text Analysis (Found 8 times)
```python
# Repeated pattern in multiple methods:
output_lower = scene_output.lower()
for pattern in patterns:
    if pattern in output_lower:
        # create violation
```

**Solution**: Extract to `TextAnalyzer` utility class with methods like:
- `find_patterns(text, patterns) -> List[Match]`
- `check_contradictions(text, pattern_groups) -> List[Contradiction]`

### Pattern 2: Violation Creation (Found 6 times)
```python
# Repeated violation creation pattern:
return ConsistencyViolation(
    violation_type=ConsistencyViolationType.SOME_TYPE,
    character_name=char_name,
    scene_id=scene_id,
    description=f"Some description",
    severity=0.X,
    expected_behavior="...",
    actual_behavior="...",
    timestamp=time.time()
)
```

**Solution**: Extract to `ViolationBuilder` with fluent interface:
```python
ViolationBuilder.for_character(char_name, scene_id)\
    .trait_violation("description")\
    .severity(0.8)\
    .expected("behavior")\
    .actual("behavior")\
    .build()
```

### Pattern 3: Character Data Initialization (Found 4 times)
```python
# Repeated in _process_character_data:
self.motivation_anchors[char_name] = []
self.locked_traits[char_name] = set()
self.violation_history[char_name] = []
# etc.
```

**Solution**: Extract to `CharacterRegistry.initialize_character(char_name)`

## Proposed Refactored Structure

```
core/consistency/
├── __init__.py
├── models.py                    # Data structures and enums
├── engine.py                    # Main CharacterConsistencyEngine (slimmed down)
├── anchor_factory.py            # Anchor creation logic
├── violation_detectors.py       # Violation detection classes
├── patterns.py                  # Pattern definitions and loaders
├── scoring.py                   # Scoring algorithms
├── text_analyzer.py             # Text analysis utilities
└── character_registry.py        # Character data management
```

## Migration Strategy

### Phase 1: Extract Data Structures (Low Risk)
1. Move dataclasses and enums to `models.py`
2. Update imports in main file
3. Run tests to ensure no regressions

### Phase 2: Extract Pattern Definitions (Low Risk)  
1. Move hard-coded patterns to `patterns.py`
2. Create pattern loader utilities
3. Update detection methods to use new patterns

### Phase 3: Extract Violation Detectors (Medium Risk)
1. Create abstract base detector
2. Extract each detector type incrementally
3. Replace method calls with detector instances
4. Comprehensive testing at each step

### Phase 4: Extract Anchor Factory (Medium Risk)
1. Create factory and builder classes
2. Replace anchor creation logic
3. Update tests for new interface

### Phase 5: Extract Supporting Classes (Low Risk)
1. Move scoring, text analysis, and registry logic
2. Slim down main engine class
3. Final integration testing

## Immediate Quick Wins

### 1. **Extract Constants** (15 minutes)
Move hard-coded strings and magic numbers to module-level constants:
```python
# At module top
EMOTIONAL_INDICATORS = ["screaming", "sobbing", "hysterical", ...]
APPROVAL_SEEKING_PHRASES = ["do you like me", "am i good enough", ...]
HIGH_STAT_THRESHOLD = 8
LOW_STAT_THRESHOLD = 3
MAX_PENALTY_PER_VIOLATION = 0.1
```

### 2. **Extract Helper Methods** (30 minutes)
Break down large methods like `_check_anchor_violation` into smaller, focused methods:
```python
def _check_anchor_violation(self, char_name, anchor, scene_output, scene_id, context):
    if anchor.trait_name == "emotional_control":
        return self._check_emotional_control_violation(char_name, anchor, scene_output, scene_id)
    elif anchor.trait_name == "independence":
        return self._check_independence_violation(char_name, anchor, scene_output, scene_id)
    # etc.
```

### 3. **Improve Method Organization** (20 minutes)
Group related methods and add clear section comments:
```python
# === ANCHOR MANAGEMENT ===
def load_character_consistency_data(self, story_path: str) -> None:
def _process_character_data(self, char_name: str, char_data: Dict[str, Any]) -> None:
# etc.

# === VIOLATION DETECTION ===  
def analyze_behavioral_consistency(self, char_name: str, scene_output: str, ...) -> List[ConsistencyViolation]:
# etc.

# === SCORING AND REPORTING ===
def get_consistency_score(self, char_name: str) -> float:
# etc.
```

## Testing Strategy for Refactoring

### Unit Tests Priority
1. **Test data structure extraction first** - Ensure dataclasses work identically
2. **Test pattern matching logic** - Verify detection still works with extracted patterns  
3. **Test anchor creation** - Ensure factory produces identical anchors
4. **Test main engine integration** - End-to-end functionality preserved

### Test Coverage Targets
- `models.py`: 100% (simple data structures)
- `patterns.py`: 95% (pattern loading and validation)
- `violation_detectors.py`: 90% (core business logic)
- `anchor_factory.py`: 85% (factory patterns)
- Main engine: 85% (integration and coordination)

## Estimated Effort

| Phase | Effort | Risk Level | Dependencies |
|-------|--------|------------|--------------|
| Extract Constants & Quick Wins | 2 hours | Very Low | None |
| Extract Data Structures | 4 hours | Low | None |
| Extract Patterns | 6 hours | Low | Data Structures |
| Extract Violation Detectors | 12 hours | Medium | Patterns, Data Structures |
| Extract Anchor Factory | 8 hours | Medium | Data Structures |
| Extract Supporting Classes | 10 hours | Medium | All above |
| **Total** | **42 hours** | | |

## Success Metrics

- ✅ Reduced main file size from 529 to ~200 lines
- ✅ Increased test coverage from current to >85%
- ✅ Improved maintainability score (easier to add new violation types)
- ✅ Zero functional regressions
- ✅ Improved performance through focused, optimized classes

## Recommendations Priority

1. **IMMEDIATE** (This week): Extract constants and implement quick wins
2. **SHORT-TERM** (Next sprint): Extract data structures and patterns  
3. **MEDIUM-TERM** (Following sprint): Extract violation detectors
4. **LONG-TERM** (Future sprint): Complete remaining extractions

This refactoring will significantly improve the maintainability and extensibility of the character consistency system while preserving all existing functionality.
