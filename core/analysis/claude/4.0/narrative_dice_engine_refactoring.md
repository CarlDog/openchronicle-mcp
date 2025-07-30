# Narrative Dice Engine Refactoring Analysis

**File**: `core/narrative_dice_engine.py`  
**Size**: 809 lines  
**Complexity**: HIGH  
**Priority**: HIGH

## Executive Summary

The `NarrativeDiceEngine` is a comprehensive RPG-style dice resolution system that manages character statistics, dice mechanics, outcome determination, and narrative impact generation. While functionally complete, it suffers from significant single-responsibility violations and could benefit from modular architecture to improve maintainability and testability.

## Current Architecture Analysis

### Core Components
1. **8 Data Classes/Enums**: DiceType, ResolutionType, DifficultyLevel, OutcomeType, ResolutionResult, ResolutionConfig, NarrativeBranch, NarrativeDiceEngine
2. **5 Primary Responsibilities**: Dice rolling, stat calculations, outcome determination, narrative generation, performance tracking
3. **20+ Methods**: Mix of public APIs and private helpers handling diverse functionality
4. **Statistical Analysis**: Advanced simulation and performance tracking capabilities

### Current Responsibilities
- **Dice Mechanics**: Multiple dice types (d6, d10, d12, d20, d100, 2d10, 3d6, 4d6-drop-lowest)
- **Resolution System**: Success/failure determination with critical outcomes
- **Modifier Calculation**: Character stat integration with resolution types
- **Narrative Impact**: Template-based story consequence generation
- **Performance Tracking**: Character-specific success rate analytics
- **Branch Generation**: Multiple outcome path creation for story branching
- **Data Persistence**: Export/import engine state
- **Statistical Simulation**: Probability analysis for game balance

## Major Refactoring Opportunities

### 1. Dice System Extraction (Critical Priority)

**Problem**: 8 different dice rolling methods embedded in main class
```python
def _roll_d6(self) -> List[int]:
def _roll_d10(self) -> List[int]:
def _roll_d20(self) -> List[int]:
# ... 5 more similar methods
```

**Solution**: Extract to dedicated DiceSystem
```python
class DiceSystem:
    """Handles all dice rolling mechanics and configurations."""
    
    def __init__(self, dice_type: DiceType, advantage_enabled: bool = True):
        self.dice_type = dice_type
        self.advantage_enabled = advantage_enabled
        self.roll_functions = self._initialize_roll_functions()
    
    def roll(self, advantage: bool = False, disadvantage: bool = False) -> List[int]:
        """Main rolling interface with advantage/disadvantage."""
        
    def roll_with_modifier(self, base_modifier: int = 0) -> int:
        """Roll with automatic modifier application."""
        
    def simulate_rolls(self, iterations: int = 1000) -> Dict[str, float]:
        """Statistical analysis of dice probabilities."""

class D20System(DiceSystem):
    """Specialized D20 system with critical ranges."""
    
class D6System(DiceSystem):
    """Specialized D6 system for narrative games."""
```

**Benefits**:
- Isolated dice logic for easier testing
- Pluggable dice systems for different game types
- Cleaner separation of mechanics from narrative logic

### 2. Outcome Determination Engine (High Priority)

**Problem**: Complex outcome logic mixed with dice rolling
```python
def _determine_outcome(self, dice_rolled: List[int], final_result: int, difficulty: int) -> OutcomeType:
    # 20+ lines of critical/success/failure logic
    if self.config.dice_type == DiceType.D20 and len(dice_rolled) == 1:
        natural_roll = dice_rolled[0]
        if natural_roll <= self.config.critical_range:
            return OutcomeType.CRITICAL_FAILURE
        # ... more complex logic
```

**Solution**: Extract to OutcomeResolver
```python
class OutcomeResolver:
    """Determines resolution outcomes based on dice results and difficulty."""
    
    def __init__(self, dice_type: DiceType, critical_range: int):
        self.dice_type = dice_type
        self.critical_range = critical_range
    
    def resolve_outcome(self, dice_result: DiceResult, difficulty: int) -> ResolutionOutcome:
        """Main outcome resolution with all edge cases."""
        
    def check_critical_results(self, dice_rolled: List[int]) -> Optional[OutcomeType]:
        """Handle critical success/failure detection."""
        
    def calculate_margin_outcome(self, margin: int) -> OutcomeType:
        """Determine outcome based on success margin."""

@dataclass
class DiceResult:
    """Encapsulates dice rolling results."""
    dice_rolled: List[int]
    total_roll: int
    modifiers: Dict[str, int]
    final_result: int

@dataclass
class ResolutionOutcome:
    """Complete resolution outcome data."""
    outcome_type: OutcomeType
    success: bool
    margin: int
    critical: bool
```

### 3. Narrative Impact Generator (High Priority)

**Problem**: Template-based narrative generation embedded in main class
```python
def _generate_narrative_impact(self, character_id: str, resolution_type: ResolutionType,
                             outcome: OutcomeType, margin: int, scene_context: str) -> str:
    impact_templates = {
        OutcomeType.CRITICAL_SUCCESS: [
            f"{character_id} exceeds all expectations in {resolution_type.value}",
            # ... more hardcoded templates
```

**Solution**: Extract to NarrativeImpactGenerator
```python
class NarrativeImpactGenerator:
    """Generates narrative consequences and story impacts from resolutions."""
    
    def __init__(self, template_registry: NarrativeTemplateRegistry):
        self.templates = template_registry
    
    def generate_impact_description(self, resolution: ResolutionResult) -> str:
        """Generate narrative impact text."""
        
    def create_story_branches(self, resolution_type: ResolutionType, 
                            context: str) -> Dict[OutcomeType, NarrativeBranch]:
        """Create branching story paths."""
        
    def get_emotional_consequences(self, outcome: OutcomeType, 
                                 character_context: str) -> EmotionalImpact:
        """Generate emotional state changes."""

class NarrativeTemplateRegistry:
    """Manages narrative templates and generation rules."""
    
    def __init__(self):
        self.impact_templates = self._load_impact_templates()
        self.branch_templates = self._load_branch_templates()
    
    def get_impact_template(self, outcome: OutcomeType, 
                          resolution_type: ResolutionType) -> str:
        """Get appropriate narrative template."""
        
    def register_custom_template(self, key: str, template: str):
        """Allow runtime template registration."""

@dataclass
class EmotionalImpact:
    """Character emotional state changes."""
    primary_emotion: str
    intensity: int
    stat_modifications: Dict[str, int]
    duration: int
```

### 4. Character Performance Analytics (Medium Priority)

**Problem**: Performance tracking mixed with core resolution logic
```python
def _update_character_performance(self, result: ResolutionResult) -> None:
    # 30+ lines of performance tracking logic
    
def get_character_performance_summary(self, character_id: str) -> Dict[str, Any]:
    # 25+ lines of analytics calculation
```

**Solution**: Extract to PerformanceAnalytics
```python
class CharacterPerformanceAnalytics:
    """Tracks and analyzes character resolution performance."""
    
    def __init__(self):
        self.performance_data: Dict[str, CharacterPerformance] = {}
    
    def record_resolution(self, result: ResolutionResult):
        """Record a resolution result for analytics."""
        
    def get_performance_summary(self, character_id: str) -> PerformanceSummary:
        """Get comprehensive performance analysis."""
        
    def calculate_success_trends(self, character_id: str) -> TrendAnalysis:
        """Analyze success rate trends over time."""
        
    def get_comparative_analysis(self, character_ids: List[str]) -> ComparisonReport:
        """Compare performance across multiple characters."""

@dataclass
class CharacterPerformance:
    """Character-specific performance data."""
    character_id: str
    total_resolutions: int
    success_history: List[ResolutionRecord]
    type_performance: Dict[str, TypePerformance]
    
@dataclass
class PerformanceSummary:
    """Complete performance analysis."""
    overall_stats: OverallStats
    type_breakdown: Dict[str, TypeStats]
    recent_trends: TrendData
    strengths_weaknesses: StrengthAnalysis
```

### 5. Configuration Management (Medium Priority)

**Problem**: Configuration handling embedded in main class
```python
class ResolutionConfig:
    # Configuration embedded in engine
    
def export_engine_data(self) -> Dict[str, Any]:
def import_engine_data(self, data: Dict[str, Any]) -> None:
```

**Solution**: Extract to ConfigurationManager
```python
class NarrativeDiceConfiguration:
    """Manages dice engine configuration and persistence."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.current_config = self._load_default_config()
    
    def load_configuration(self, config_data: Dict[str, Any]) -> ResolutionConfig:
        """Load configuration from external source."""
        
    def save_configuration(self, config: ResolutionConfig):
        """Persist configuration to storage."""
        
    def validate_configuration(self, config: ResolutionConfig) -> ValidationResult:
        """Ensure configuration is valid and consistent."""
        
    def get_configuration_schema(self) -> Dict[str, Any]:
        """Get JSON schema for configuration validation."""
```

## Proposed Modular Architecture

```python
class NarrativeDiceEngine:
    """Main orchestrator for dice-based narrative resolutions."""
    
    def __init__(self, config: ResolutionConfig):
        self.dice_system = DiceSystemFactory.create(config.dice_type)
        self.outcome_resolver = OutcomeResolver(config.dice_type, config.critical_range)
        self.modifier_calculator = ModifierCalculator(config.skill_dependency)
        self.narrative_generator = NarrativeImpactGenerator()
        self.performance_analytics = CharacterPerformanceAnalytics()
        self.config_manager = NarrativeDiceConfiguration()
    
    def resolve_action(self, character_id: str, resolution_type: ResolutionType,
                      difficulty: DifficultyLevel, **kwargs) -> ResolutionResult:
        """Main resolution interface - orchestrates all components."""
        
    def create_narrative_branches(self, resolution_type: ResolutionType,
                                scene_context: str) -> Dict[OutcomeType, NarrativeBranch]:
        """Create story branches through narrative generator."""
        
    def get_performance_analysis(self, character_id: str) -> PerformanceSummary:
        """Get performance data through analytics component."""

class ModifierCalculator:
    """Calculates stat-based modifiers for resolutions."""
    
    def __init__(self, skill_dependency: bool, stat_mappings: Dict[ResolutionType, str]):
        self.skill_dependency = skill_dependency
        self.stat_mappings = stat_mappings
    
    def calculate_modifiers(self, character_stats: Dict[str, int],
                          resolution_type: ResolutionType) -> Dict[str, int]:
        """Calculate all applicable modifiers."""

class DiceSystemFactory:
    """Factory for creating appropriate dice systems."""
    
    @staticmethod
    def create(dice_type: DiceType, **config) -> DiceSystem:
        """Create appropriate dice system implementation."""
```

## Implementation Benefits

### Immediate Improvements
1. **Single Responsibility**: Each class handles one aspect of dice resolution
2. **Testability**: Isolated components can be unit tested independently
3. **Maintainability**: Changes to dice mechanics don't affect narrative generation
4. **Extensibility**: New dice systems or narrative generators can be plugged in

### Long-term Advantages
1. **Performance**: Specialized classes can be optimized for their specific tasks
2. **Reusability**: Components can be reused in other narrative engines
3. **Configuration**: Different game types can use different component combinations
4. **Analytics**: Performance tracking becomes more sophisticated and queryable

## Migration Strategy

### Phase 1: Extract Core Systems (Week 1-2)
1. Create `DiceSystem` hierarchy with all rolling logic
2. Extract `OutcomeResolver` for result determination
3. Implement basic factory pattern for dice system creation

### Phase 2: Narrative Components (Week 3)
1. Extract `NarrativeImpactGenerator` with template system
2. Create `NarrativeTemplateRegistry` for flexible template management
3. Implement emotional impact and consequence generation

### Phase 3: Analytics and Configuration (Week 4)
1. Extract `CharacterPerformanceAnalytics` with comprehensive tracking
2. Create `NarrativeDiceConfiguration` for config management
3. Implement data export/import through configuration manager

### Phase 4: Integration and Testing (Week 5)
1. Refactor main `NarrativeDiceEngine` to orchestrate components
2. Comprehensive integration testing of all components
3. Performance testing and optimization

## Risk Assessment

### Low Risk
- **Dice System Extraction**: Self-contained logic with clear interfaces
- **Configuration Management**: Already well-defined data structures

### Medium Risk
- **Outcome Resolution**: Complex logic with many edge cases
- **Narrative Generation**: Template system needs careful design

### High Risk
- **Performance Analytics**: Complex data relationships and calculations
- **Component Integration**: Ensuring all components work together seamlessly

## Conclusion

The `NarrativeDiceEngine` represents a sophisticated dice resolution system that would greatly benefit from modular refactoring. The proposed architecture separates concerns while maintaining the engine's comprehensive functionality. This refactoring would make the system more maintainable, testable, and extensible while preserving all current capabilities.

The migration can be done incrementally with minimal risk to existing functionality, and the resulting architecture would serve as a foundation for more advanced narrative mechanics in future development.
