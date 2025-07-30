# Narrative Dice Engine Refactoring Recommendations

## Overview

The Narrative Dice Engine module (`narrative_dice_engine.py`) implements an RPG-style dice rolling system for determining success/failure of character actions in OpenChronicle. The module is well-structured but has grown to over 800 lines, making it a candidate for refactoring to improve maintainability.

## Recommended Refactoring Approach

### 1. Module Splitting

Break the large module into several smaller, focused modules:

```powershell
# Recommended new structure
core/
  dice_engine/
    __init__.py                 # Package exports
    resolution_models.py        # Data classes (ResolutionResult, Config, etc.)
    core_engine.py              # Core dice rolling mechanics
    narrative_generation.py     # Narrative text generation
    character_tracking.py       # Character performance tracking
    persistence.py              # Import/export functionality
```

### 2. Class Extraction

Extract key functionality into dedicated classes:

- `DiceRoller`: Encapsulate dice rolling functionality
- `NarrativeGenerator`: Handle all narrative text generation
- `CharacterPerformanceTracker`: Track character performance stats
- `ResolutionHistoryManager`: Manage resolution history

### 3. Code Organization 

Group related methods together and extract large methods into smaller, focused functions:

```python
# Before
def _update_character_performance(self, result: ResolutionResult) -> None:
    # 50+ lines of character performance tracking

# After
def _update_character_performance(self, result: ResolutionResult) -> None:
    """Update character performance tracking."""
    char_id = result.character_id
    self._ensure_character_record_exists(char_id)
    self._update_character_totals(char_id, result)
    self._update_character_type_performance(char_id, result)
    self._update_recent_results(char_id, result)
```

### 4. Specific Improvements

#### Reduce Duplication in Dice Rolling Functions

```python
# Before (multiple similar methods)
def _roll_d6(self) -> List[int]:
    return [random.randint(1, 6)]

def _roll_d10(self) -> List[int]:
    return [random.randint(1, 10)]

# After (unified method)
def _roll_dice_of_type(self, sides: int, count: int = 1, drop_lowest: bool = False) -> List[int]:
    """Roll dice with specified number of sides."""
    rolls = [random.randint(1, sides) for _ in range(count)]
    if drop_lowest and len(rolls) > 1:
        rolls.remove(min(rolls))
    return rolls
```

#### Improve Configuration Management

Use dataclass features more effectively:

```python
@dataclass
class ResolutionConfig:
    enabled: bool = True
    dice_type: DiceType = DiceType.D20
    modifier_tolerance: int = 3
    skill_dependency: bool = True
    failure_narrative_required: bool = True
    critical_range: int = 1
    advantage_enabled: bool = True
    disadvantage_enabled: bool = True
    
    # Use post_init to validate configuration
    def __post_init__(self):
        """Validate configuration settings."""
        if self.critical_range < 1:
            logger.warning("Critical range below 1 is invalid, setting to 1")
            self.critical_range = 1
        
        if self.modifier_tolerance < 0:
            logger.warning("Negative modifier tolerance is invalid, setting to 0")
            self.modifier_tolerance = 0
```

#### Streamline Narrative Branch Management

Add methods for finding and filtering narrative branches:

```python
def get_branches_for_scene(self, scene_id: str) -> List[NarrativeBranch]:
    """Get all narrative branches for a scene."""
    return self.narrative_branches.get(scene_id, [])
    
def get_branches_by_outcome(self, scene_id: str, outcome: OutcomeType) -> List[NarrativeBranch]:
    """Get narrative branches for a scene filtered by outcome type."""
    branches = self.get_branches_for_scene(scene_id)
    return [b for b in branches if b.outcome_type == outcome]
```

## Implementation Plan

1. Create the new directory structure
2. Extract models into `resolution_models.py`
3. Move core dice rolling to `core_engine.py`
4. Extract narrative generation to `narrative_generation.py`
5. Move character tracking to `character_tracking.py`
6. Add comprehensive docstrings to all new files
7. Update imports and ensure backward compatibility
8. Run the full test suite to verify refactoring

## Backward Compatibility Notes

The refactoring should maintain full backward compatibility. The main `NarrativeDiceEngine` class should still be importable from `core.narrative_dice_engine` with the same API.

## Coding Instruction Compliance

This refactoring adheres to the provided coding instructions:
- Maintains PowerShell-compatible syntax and path formats
- Preserves the core architecture and maintains backward compatibility
- Follows the clean development guidelines
- Respects the project's async patterns (though this module is synchronous)
- Improves code organization without compromising functionality

## Benefits of Refactoring

- **Improved Maintainability**: Smaller, focused modules are easier to understand and modify
- **Enhanced Testability**: Isolated components can be tested independently
- **Better Code Organization**: Related functionality is grouped together
- **Reduced Cognitive Load**: Developers can focus on one aspect at a time
- **Easier Future Development**: New features can be added to specific modules without impacting others
