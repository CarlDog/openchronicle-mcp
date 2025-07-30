# Character Consistency Engine Refactoring Recommendation

## Current Module Overview

**File**: `core/character_consistency_engine.py` (529 lines)  
**Purpose**: Maintains character consistency through motivation anchoring, trait locking, and behavioral auditing.

**Key Components**:
1. **ConsistencyViolationType Enum** - Types of consistency violations
2. **ConsistencyViolation Class** - Data model for violations
3. **MotivationAnchor Class** - Data model for character motivations
4. **CharacterConsistencyEngine Class** - Main engine implementing consistency features

**Core Functionality**:
- Loading character consistency data from files
- Generating motivation anchors from character profiles
- Analyzing scenes for consistency violations
- Tracking character consistency scores
- Reporting on consistency metrics

## Issues Identified

1. **Complex Logic Blocks**: Large methods with complex decision trees
2. **Mixed Responsibilities**: The main class handles loading, analysis, and reporting
3. **Limited Extensibility**: Adding new violation types requires modifying core logic
4. **Hard-coded Patterns**: Character trait patterns are hard-coded in methods
5. **Tight Coupling**: Direct dependencies on character data structure
6. **Error Handling**: Insufficient error handling in critical methods

## Refactoring Recommendations

### 1. Convert to Package Structure

Transform the file into a structured package:

```
core/
  character_consistency/
    __init__.py              # Public API
    engine.py                # Main engine (simplified)
    models.py                # Data models
    analyzers/               # Analysis components
      __init__.py
      motivation_analyzer.py
      trait_analyzer.py
      emotion_analyzer.py
    patterns/                # Pattern definitions
      __init__.py
      trait_patterns.py
      emotion_patterns.py
    loading.py               # Data loading utilities
    scoring.py               # Consistency scoring logic
    reporting.py             # Reporting utilities
```

### 2. Enhance Data Models

Improve the data models with proper typing and validation:

```python
# models.py
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional, Set, Tuple, Union

class ConsistencyViolationType(Enum):
    """Types of consistency violations that can be detected."""
    EMOTIONAL_CONTRADICTION = "emotional_contradiction"
    TRAIT_VIOLATION = "trait_violation"
    MOTIVATION_CONFLICT = "motivation_conflict"
    BEHAVIORAL_INCONSISTENCY = "behavioral_inconsistency"
    TONE_MISMATCH = "tone_mismatch"
    
    @classmethod
    def from_string(cls, value: str) -> 'ConsistencyViolationType':
        """Create enum from string value."""
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"Invalid violation type: {value}")

@dataclass
class ConsistencyViolation:
    """Represents a character consistency violation."""
    violation_type: ConsistencyViolationType
    character_name: str
    scene_id: str
    description: str
    severity: float  # 0.0-1.0, where 1.0 is most severe
    expected_behavior: str
    actual_behavior: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            'violation_type': self.violation_type.value,
            'character_name': self.character_name,
            'scene_id': self.scene_id,
            'description': self.description,
            'severity': self.severity,
            'expected_behavior': self.expected_behavior,
            'actual_behavior': self.actual_behavior,
            'timestamp': self.timestamp.timestamp()
        }
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConsistencyViolation':
        """Create instance from dictionary."""
        violation_type = ConsistencyViolationType.from_string(data['violation_type'])
        timestamp = datetime.fromtimestamp(data['timestamp'])
        
        return cls(
            violation_type=violation_type,
            character_name=data['character_name'],
            scene_id=data['scene_id'],
            description=data['description'],
            severity=data['severity'],
            expected_behavior=data['expected_behavior'],
            actual_behavior=data['actual_behavior'],
            timestamp=timestamp
        )

@dataclass
class MotivationAnchor:
    """Represents a locked character motivation that must persist."""
    trait_name: str
    value: Any
    description: str
    locked: bool = True
    priority: int = 1  # 1=highest, lower numbers = higher priority
    context_requirement: Optional[str] = None  # When this anchor should be emphasized
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'trait_name': self.trait_name,
            'value': self.value,
            'description': self.description,
            'locked': self.locked,
            'priority': self.priority,
            'context_requirement': self.context_requirement
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MotivationAnchor':
        """Create instance from dictionary."""
        return cls(**data)
```

### 3. Implement Pattern Registry

Extract pattern definitions to a dedicated module:

```python
# patterns/trait_patterns.py
from typing import Dict, List, Any

class TraitPatternRegistry:
    """Registry of patterns for detecting trait violations."""
    
    def __init__(self):
        self._patterns = self._default_patterns()
    
    def _default_patterns(self) -> Dict[str, List[str]]:
        """Create default trait violation patterns."""
        return {
            "pacifist": [
                "kill", "murder", "destroy", "attack", "fight", "violence",
                "blood", "weapon", "strike", "hurt"
            ],
            "honest": [
                "lie", "deceive", "trick", "manipulate", "false", "dishonest",
                "betray", "cheat"
            ],
            # Additional patterns...
        }
    
    def get_patterns(self, trait: str) -> List[str]:
        """Get patterns for a specific trait."""
        return self._patterns.get(trait, [])
    
    def add_pattern(self, trait: str, patterns: List[str]) -> None:
        """Add or update patterns for a trait."""
        if trait not in self._patterns:
            self._patterns[trait] = []
        self._patterns[trait].extend(patterns)
    
    def has_trait(self, trait: str) -> bool:
        """Check if patterns exist for a trait."""
        return trait in self._patterns

# patterns/emotion_patterns.py
from typing import Dict, List, Tuple

class EmotionPatternRegistry:
    """Registry of patterns for detecting emotional contradictions."""
    
    def __init__(self):
        self._patterns = self._default_patterns()
    
    def _default_patterns(self) -> List[Tuple[List[str], List[str]]]:
        """Create default emotional contradiction patterns."""
        return [
            (["happy", "joyful", "excited"], ["sad", "depressed", "miserable"]),
            (["angry", "furious", "rage"], ["calm", "peaceful", "serene"]),
            # Additional patterns...
        ]
    
    def get_patterns(self) -> List[Tuple[List[str], List[str]]]:
        """Get all emotional contradiction patterns."""
        return self._patterns
    
    def add_pattern(self, positive: List[str], negative: List[str]) -> None:
        """Add a new emotional contradiction pattern."""
        self._patterns.append((positive, negative))
```

### 4. Create Specialized Analyzers

Implement analyzer classes for different consistency checks:

```python
# analyzers/motivation_analyzer.py
from typing import List, Dict, Any, Optional
from ..models import MotivationAnchor, ConsistencyViolation, ConsistencyViolationType

class MotivationAnalyzer:
    """Analyzes motivation consistency."""
    
    def analyze(self, char_name: str, anchors: List[MotivationAnchor], 
                scene_output: str, scene_id: str, 
                context: Optional[Dict[str, Any]] = None) -> List[ConsistencyViolation]:
        """Analyze scene for motivation violations."""
        violations = []
        
        for anchor in anchors:
            violation = self._check_anchor_violation(
                char_name, anchor, scene_output, scene_id, context)
            if violation:
                violations.append(violation)
        
        return violations
    
    def _check_anchor_violation(self, char_name: str, anchor: MotivationAnchor, 
                              scene_output: str, scene_id: str, 
                              context: Optional[Dict[str, Any]]) -> Optional[ConsistencyViolation]:
        """Check for violations against a specific anchor."""
        # Implementation details...

# analyzers/trait_analyzer.py
from typing import List, Dict, Any, Optional, Set
from ..models import ConsistencyViolation, ConsistencyViolationType
from ..patterns.trait_patterns import TraitPatternRegistry

class TraitAnalyzer:
    """Analyzes trait consistency."""
    
    def __init__(self, pattern_registry: Optional[TraitPatternRegistry] = None):
        self.pattern_registry = pattern_registry or TraitPatternRegistry()
    
    def analyze(self, char_name: str, locked_traits: Set[str], 
                scene_output: str, scene_id: str, 
                context: Optional[Dict[str, Any]] = None) -> List[ConsistencyViolation]:
        """Analyze scene for trait violations."""
        # Implementation details...

# analyzers/emotion_analyzer.py
from typing import List, Dict, Any, Optional
from ..models import ConsistencyViolation, ConsistencyViolationType
from ..patterns.emotion_patterns import EmotionPatternRegistry

class EmotionAnalyzer:
    """Analyzes emotional consistency."""
    
    def __init__(self, pattern_registry: Optional[EmotionPatternRegistry] = None):
        self.pattern_registry = pattern_registry or EmotionPatternRegistry()
    
    def analyze(self, char_name: str, scene_output: str, scene_id: str, 
                context: Optional[Dict[str, Any]] = None) -> List[ConsistencyViolation]:
        """Analyze scene for emotional contradictions."""
        # Implementation details...
```

### 5. Refine Main Engine

Simplify the main engine to use specialized components:

```python
# engine.py
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
import os
import json

from .models import ConsistencyViolation, MotivationAnchor, ConsistencyViolationType
from .analyzers.motivation_analyzer import MotivationAnalyzer
from .analyzers.trait_analyzer import TraitAnalyzer
from .analyzers.emotion_analyzer import EmotionAnalyzer
from .patterns.trait_patterns import TraitPatternRegistry
from .patterns.emotion_patterns import EmotionPatternRegistry
from .loading import CharacterDataLoader
from .scoring import ConsistencyScorer

class CharacterConsistencyEngine:
    """Maintains character consistency through motivation anchoring, trait locking,
    and behavioral auditing across long narratives."""
    
    def __init__(self, character_style_manager=None):
        # Initialize dependencies
        self.character_style_manager = character_style_manager
        self.data_loader = CharacterDataLoader()
        self.trait_pattern_registry = TraitPatternRegistry()
        self.emotion_pattern_registry = EmotionPatternRegistry()
        
        # Initialize analyzers
        self.motivation_analyzer = MotivationAnalyzer()
        self.trait_analyzer = TraitAnalyzer(self.trait_pattern_registry)
        self.emotion_analyzer = EmotionAnalyzer(self.emotion_pattern_registry)
        self.consistency_scorer = ConsistencyScorer()
        
        # Initialize data structures
        self.motivation_anchors: Dict[str, List[MotivationAnchor]] = {}
        self.locked_traits: Dict[str, Set[str]] = {}
        self.violation_history: Dict[str, List[ConsistencyViolation]] = {}
        self.behavioral_patterns: Dict[str, List[Dict[str, Any]]] = {}
        self.emotional_states: Dict[str, Dict[str, Any]] = {}
        self.consistency_scores: Dict[str, float] = {}
    
    def load_character_consistency_data(self, story_path: str) -> None:
        """Load character consistency data from story characters."""
        character_data = self.data_loader.load_characters(story_path)
        
        for char_name, char_data in character_data.items():
            self._process_character_data(char_name, char_data)
    
    def analyze_behavioral_consistency(self, char_name: str, scene_output: str, 
                                     scene_id: str, context: Dict[str, Any] = None) -> List[ConsistencyViolation]:
        """Analyze scene output for behavioral consistency violations."""
        if char_name not in self.motivation_anchors:
            return []
        
        violations = []
        
        # Use specialized analyzers
        violations.extend(self.motivation_analyzer.analyze(
            char_name, self.motivation_anchors[char_name], scene_output, scene_id, context))
        
        violations.extend(self.trait_analyzer.analyze(
            char_name, self.locked_traits.get(char_name, set()), scene_output, scene_id, context))
        
        violations.extend(self.emotion_analyzer.analyze(
            char_name, scene_output, scene_id, context))
        
        # Store violations
        if violations:
            if char_name not in self.violation_history:
                self.violation_history[char_name] = []
            self.violation_history[char_name].extend(violations)
            
            # Update consistency score
            self.consistency_scores[char_name] = self.consistency_scorer.update_score(
                self.consistency_scores.get(char_name, 1.0), violations)
        
        return violations
    
    # Other methods simplified to use the new components...
```

### 6. Implement Configuration Service

Create a configuration service for pattern management:

```python
# config.py
from typing import Dict, List, Any, Optional
from .patterns.trait_patterns import TraitPatternRegistry
from .patterns.emotion_patterns import EmotionPatternRegistry

class ConsistencyConfig:
    """Configuration service for the consistency engine."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.trait_registry = TraitPatternRegistry()
        self.emotion_registry = EmotionPatternRegistry()
        
        if config_path:
            self.load_config(config_path)
    
    def load_config(self, config_path: str) -> None:
        """Load configuration from file."""
        # Load configuration data
        # Update registries
    
    def get_trait_patterns(self, trait: str) -> List[str]:
        """Get patterns for a specific trait."""
        return self.trait_registry.get_patterns(trait)
    
    def get_emotion_patterns(self) -> List[Any]:
        """Get emotional contradiction patterns."""
        return self.emotion_registry.get_patterns()
    
    def add_trait_patterns(self, trait: str, patterns: List[str]) -> None:
        """Add patterns for a specific trait."""
        self.trait_registry.add_pattern(trait, patterns)
    
    def add_emotion_pattern(self, positive: List[str], negative: List[str]) -> None:
        """Add an emotional contradiction pattern."""
        self.emotion_registry.add_pattern(positive, negative)
```

## Implementation Strategy

1. **Create Package Structure**: Set up the directory and file structure
2. **Enhance Data Models**: Improve the models with better typing and serialization
3. **Extract Pattern Logic**: Move pattern definitions to dedicated modules
4. **Implement Analyzers**: Create specialized analyzers for different consistency checks
5. **Refine Main Engine**: Update the main engine to use the new components
6. **Add Configuration**: Implement the configuration service
7. **Update Tests**: Create dedicated tests for each component

## Benefits of Refactoring

1. **Improved Maintainability**: Smaller, focused modules with clear responsibilities
2. **Enhanced Extensibility**: Easy to add new violation types and patterns
3. **Better Testability**: Components can be tested in isolation
4. **Reduced Complexity**: Simpler logic flow in each component
5. **Improved Error Handling**: More robust error handling in critical methods
6. **Configuration Management**: Centralized pattern management
7. **Type Safety**: Comprehensive type annotations throughout the codebase

## Migration Plan

1. **Incremental Refactoring**: Implement the new package structure alongside the existing module
2. **Backward Compatibility**: Provide legacy function wrappers for backward compatibility
3. **Dual Operation**: Allow both old and new implementations to run in parallel during transition
4. **Validation**: Compare results from old and new implementations to ensure consistency
5. **Gradual Adoption**: Update dependent code to use the new API incrementally
6. **Complete Migration**: Remove legacy implementation once all dependencies are updated

By following this refactoring plan, the character_consistency_engine will be transformed into a well-structured, maintainable package that adheres to modern Python best practices while preserving all existing functionality.
