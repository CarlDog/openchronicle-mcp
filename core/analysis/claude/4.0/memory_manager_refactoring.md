# Memory Manager Refactoring Analysis

**File**: `core/memory_manager.py`  
**Size**: 582 lines  
**Complexity**: HIGH  
**Priority**: HIGH

## Executive Summary

The `memory_manager.py` module is a comprehensive memory persistence system that handles character memory, world state, event tracking, and memory context generation for narrative AI. While functionally complete, it suffers from significant architectural violations by mixing database operations, memory serialization, character state management, context formatting, rollback handling, and prompt generation in a single module with 18 separate functions. This analysis proposes a modular class-based architecture to improve maintainability and extensibility.

## Current Architecture Analysis

### Core Components
1. **18 Standalone Functions**: All memory operations implemented as module-level functions
2. **Mixed Responsibilities**: Database operations + serialization + formatting + context generation
3. **Complex Memory Structure**: Characters, world state, flags, recent events, metadata management
4. **Sophisticated Features**: Voice profiles, mood tracking, rollback support, prompt context generation

### Current Responsibilities
- **Memory Persistence**: Load/save memory state to database with JSON serialization
- **Character Management**: Character memory updates, voice profiles, mood tracking, history management
- **World State Management**: World state persistence and updates
- **Event Tracking**: Memory flags, recent events, and timeline management
- **Context Generation**: Formatted memory context for LLM prompts with character snapshots
- **Rollback Support**: Memory restoration from historical snapshots
- **Data Formatting**: Complex prompt formatting and character snapshot generation

## Major Refactoring Opportunities

### 1. Memory Persistence System (Critical Priority)

**Problem**: Database operations and serialization mixed with business logic
```python
def load_current_memory(story_id):
    # 40+ lines mixing database queries with memory structure building

def save_current_memory(story_id, memory_data):
    # Database updates mixed with metadata management
```

**Solution**: Extract to MemoryRepository and MemorySerializer
```python
class MemoryRepository:
    """Handles memory data persistence and retrieval."""
    
    def __init__(self, database_manager: DatabaseManager):
        self.db = database_manager
        self.serializer = MemorySerializer()
        self.snapshot_manager = MemorySnapshotManager(database_manager)
        
    def load_memory(self, story_id: str) -> MemoryState:
        """Load complete memory state for story."""
        
    def save_memory(self, story_id: str, memory: MemoryState) -> bool:
        """Save memory state with automatic timestamping."""
        
    def update_memory_section(self, story_id: str, section: str, data: Dict) -> bool:
        """Update specific memory section efficiently."""
        
    def get_memory_history(self, story_id: str, limit: int = 50) -> List[MemorySnapshot]:
        """Get memory history snapshots."""

class MemorySerializer:
    """Handles memory serialization and deserialization."""
    
    def __init__(self):
        self.validators = MemoryValidatorRegistry()
        
    def serialize_memory(self, memory: MemoryState) -> Dict[str, str]:
        """Serialize memory to database format."""
        
    def deserialize_memory(self, serialized_data: Dict[str, Any]) -> MemoryState:
        """Deserialize memory from database format."""
        
    def validate_memory_structure(self, memory: MemoryState) -> ValidationResult:
        """Validate memory structure integrity."""

class MemorySnapshotManager:
    """Manages memory snapshots and rollback functionality."""
    
    def __init__(self, database_manager: DatabaseManager):
        self.db = database_manager
        self.snapshot_retention = SnapshotRetentionPolicy()
        
    def create_snapshot(self, story_id: str, scene_id: str, memory: MemoryState) -> str:
        """Create memory snapshot linked to scene."""
        
    def restore_from_snapshot(self, story_id: str, scene_id: str) -> MemoryState:
        """Restore memory from specific snapshot."""
        
    def cleanup_old_snapshots(self, story_id: str) -> int:
        """Clean up old snapshots based on retention policy."""
        
    def get_snapshot_metadata(self, story_id: str) -> List[SnapshotMetadata]:
        """Get metadata for all snapshots."""

@dataclass
class MemoryState:
    """Complete memory state structure."""
    characters: Dict[str, CharacterMemory]
    world_state: Dict[str, Any]
    flags: List[MemoryFlag]
    recent_events: List[MemoryEvent]
    metadata: MemoryMetadata
    
    def get_character(self, name: str) -> Optional[CharacterMemory]:
        """Get character memory safely."""
        
    def add_character(self, name: str, character: CharacterMemory) -> None:
        """Add character with validation."""
        
    def update_metadata(self) -> None:
        """Update metadata timestamps."""

@dataclass
class CharacterMemory:
    """Character memory structure."""
    traits: Dict[str, Any]
    relationships: Dict[str, str]
    history: List[str]
    current_state: Dict[str, Any]
    voice_profile: VoiceProfile
    mood_state: MoodState
    
@dataclass
class VoiceProfile:
    """Character voice profile."""
    speaking_style: str = "default"
    tone: str = "neutral"
    vocabulary_level: str = "standard"
    emotional_state: str = "stable"
    
@dataclass
class MoodState:
    """Character mood state."""
    current_mood: str = "neutral"
    mood_history: List[MoodEntry] = field(default_factory=list)
    emotional_triggers: List[str] = field(default_factory=list)
    mood_stability: float = 1.0
```

### 2. Character Management System (Critical Priority)

**Problem**: Character updates, mood tracking, and voice management scattered across functions
```python
def update_character_memory(story_id, character_name, updates):
    # 50+ lines of complex character update logic

def update_character_mood(story_id: str, character_name: str, new_mood: str, ...):
    # Mood update logic mixed with memory operations
```

**Solution**: Extract to CharacterManager
```python
class CharacterManager:
    """Manages character memory, mood, and voice profiles."""
    
    def __init__(self, memory_repository: MemoryRepository):
        self.repository = memory_repository
        self.mood_tracker = MoodTracker()
        self.voice_manager = VoiceProfileManager()
        self.history_manager = CharacterHistoryManager()
        
    def update_character(self, story_id: str, character_name: str,
                        updates: CharacterUpdates) -> CharacterUpdateResult:
        """Update character with comprehensive validation."""
        
    def create_character(self, story_id: str, character_name: str,
                        initial_data: CharacterCreationData) -> CharacterMemory:
        """Create new character with default structure."""
        
    def get_character(self, story_id: str, character_name: str) -> Optional[CharacterMemory]:
        """Get character memory with error handling."""
        
    def update_character_mood(self, story_id: str, character_name: str,
                            mood_update: MoodUpdate) -> MoodUpdateResult:
        """Update character mood with tracking."""

class MoodTracker:
    """Tracks and manages character mood changes."""
    
    def __init__(self):
        self.mood_validator = MoodValidator()
        self.stability_calculator = MoodStabilityCalculator()
        
    def update_mood(self, character: CharacterMemory, new_mood: str,
                   context: str, triggers: List[str] = None) -> MoodUpdateResult:
        """Update mood with comprehensive tracking."""
        
    def calculate_mood_stability(self, mood_history: List[MoodEntry]) -> float:
        """Calculate mood stability score."""
        
    def analyze_mood_patterns(self, character: CharacterMemory) -> MoodPatternAnalysis:
        """Analyze mood change patterns."""
        
    def get_mood_recommendations(self, character: CharacterMemory) -> List[str]:
        """Get recommendations for mood consistency."""

class VoiceProfileManager:
    """Manages character voice profiles."""
    
    def __init__(self):
        self.voice_validator = VoiceValidator()
        self.style_analyzer = SpeechStyleAnalyzer()
        
    def update_voice_profile(self, character: CharacterMemory,
                           profile_updates: Dict[str, Any]) -> VoiceUpdateResult:
        """Update voice profile with validation."""
        
    def generate_voice_prompt(self, voice_profile: VoiceProfile) -> str:
        """Generate voice profile for LLM prompt."""
        
    def analyze_voice_consistency(self, character: CharacterMemory) -> VoiceConsistencyReport:
        """Analyze voice profile consistency."""

class CharacterHistoryManager:
    """Manages character history and progression."""
    
    def __init__(self):
        self.history_validator = HistoryValidator()
        self.progression_tracker = CharacterProgressionTracker()
        
    def add_history_entry(self, character: CharacterMemory, entry: str,
                         metadata: Dict = None) -> None:
        """Add history entry with validation."""
        
    def get_recent_history(self, character: CharacterMemory, limit: int = 5) -> List[str]:
        """Get recent history entries."""
        
    def analyze_character_progression(self, character: CharacterMemory) -> ProgressionAnalysis:
        """Analyze character development over time."""

@dataclass
class CharacterUpdates:
    """Character update request."""
    traits: Optional[Dict[str, Any]] = None
    relationships: Optional[Dict[str, str]] = None
    history: Optional[List[str]] = None
    current_state: Optional[Dict[str, Any]] = None
    voice_profile: Optional[Dict[str, Any]] = None
    mood_state: Optional[Dict[str, Any]] = None

@dataclass
class MoodUpdate:
    """Mood update request."""
    new_mood: str
    scene_context: str = ""
    emotional_triggers: List[str] = field(default_factory=list)
    stability_impact: Optional[float] = None

@dataclass
class MoodEntry:
    """Individual mood history entry."""
    mood: str
    timestamp: str
    scene_context: str
    triggers: List[str] = field(default_factory=list)
```

### 3. Context Generation System (High Priority)

**Problem**: Complex prompt formatting and context generation mixed with memory operations
```python
def get_memory_context_for_prompt(story_id: str, primary_characters: List[str] = None, ...):
    # 80+ lines of complex context formatting logic

def format_character_snapshot_for_prompt(snapshot: Dict[str, Any]) -> str:
    # Complex formatting logic for character snapshots
```

**Solution**: Extract to ContextGenerator
```python
class MemoryContextGenerator:
    """Generates formatted memory context for LLM prompts."""
    
    def __init__(self):
        self.character_formatter = CharacterSnapshotFormatter()
        self.world_formatter = WorldStateFormatter()
        self.event_formatter = EventFormatter()
        self.context_optimizer = ContextOptimizer()
        
    def generate_full_context(self, story_id: str, 
                            options: ContextGenerationOptions) -> FormattedContext:
        """Generate complete memory context."""
        
    def generate_character_focused_context(self, story_id: str,
                                         primary_characters: List[str]) -> FormattedContext:
        """Generate context focused on specific characters."""
        
    def generate_minimal_context(self, story_id: str) -> FormattedContext:
        """Generate minimal context for token efficiency."""
        
    def optimize_context_length(self, context: FormattedContext, 
                              max_tokens: int) -> FormattedContext:
        """Optimize context for token limits."""

class CharacterSnapshotFormatter:
    """Formats character snapshots for prompts."""
    
    def __init__(self):
        self.voice_formatter = VoiceProfileFormatter()
        self.mood_formatter = MoodStateFormatter()
        self.relationship_formatter = RelationshipFormatter()
        
    def format_character_snapshot(self, character: CharacterMemory,
                                character_name: str) -> CharacterSnapshot:
        """Create formatted character snapshot."""
        
    def format_multiple_characters(self, characters: Dict[str, CharacterMemory],
                                 priority_order: List[str] = None) -> List[CharacterSnapshot]:
        """Format multiple characters with priority ordering."""
        
    def create_character_summary(self, character: CharacterMemory,
                               character_name: str) -> str:
        """Create brief character summary."""

class WorldStateFormatter:
    """Formats world state for prompts."""
    
    def format_world_state(self, world_state: Dict[str, Any]) -> str:
        """Format world state for prompt inclusion."""
        
    def prioritize_world_elements(self, world_state: Dict[str, Any],
                                character_context: List[str]) -> Dict[str, Any]:
        """Prioritize world elements based on character relevance."""

class EventFormatter:
    """Formats events and flags for prompts."""
    
    def format_recent_events(self, events: List[MemoryEvent], limit: int = 5) -> str:
        """Format recent events for prompt."""
        
    def format_memory_flags(self, flags: List[MemoryFlag]) -> str:
        """Format active memory flags."""
        
    def summarize_timeline(self, events: List[MemoryEvent]) -> str:
        """Create timeline summary."""

@dataclass
class ContextGenerationOptions:
    """Options for context generation."""
    include_full_world_state: bool = True
    include_all_characters: bool = True
    include_events: bool = True
    include_flags: bool = True
    max_history_items: int = 5
    character_detail_level: str = "full"  # "full", "summary", "minimal"
    
@dataclass
class FormattedContext:
    """Formatted memory context."""
    full_context: str
    character_contexts: List[CharacterSnapshot]
    world_context: str
    event_context: str
    token_estimate: int
    sections: Dict[str, str]

@dataclass
class CharacterSnapshot:
    """Formatted character snapshot."""
    character_name: str
    formatted_text: str
    voice_prompt: str
    mood_summary: str
    key_relationships: List[str]
    recent_history: List[str]
```

### 4. World State and Event Management (Medium Priority)

**Problem**: World state, flags, and events management scattered across multiple functions
```python
def update_world_state(story_id, updates):
    # Simple world state update

def add_memory_flag(story_id, flag_name, flag_data=None):
    # Flag management logic

def add_recent_event(story_id, event_description, event_data=None):
    # Event management with trimming logic
```

**Solution**: Extract to WorldStateManager and EventManager
```python
class WorldStateManager:
    """Manages world state and environmental memory."""
    
    def __init__(self, memory_repository: MemoryRepository):
        self.repository = memory_repository
        self.state_validator = WorldStateValidator()
        self.state_tracker = StateChangeTracker()
        
    def update_world_state(self, story_id: str, updates: Dict[str, Any]) -> WorldStateUpdateResult:
        """Update world state with validation and tracking."""
        
    def get_world_state(self, story_id: str, filter_keys: List[str] = None) -> Dict[str, Any]:
        """Get world state with optional filtering."""
        
    def track_state_change(self, story_id: str, key: str, 
                          old_value: Any, new_value: Any) -> None:
        """Track significant world state changes."""
        
    def get_state_history(self, story_id: str, key: str = None) -> List[StateChangeEntry]:
        """Get history of world state changes."""

class EventManager:
    """Manages memory events and flags."""
    
    def __init__(self, memory_repository: MemoryRepository):
        self.repository = memory_repository
        self.flag_manager = FlagManager()
        self.event_tracker = EventTracker()
        
    def add_event(self, story_id: str, event: MemoryEvent) -> EventAddResult:
        """Add event with automatic management."""
        
    def get_recent_events(self, story_id: str, limit: int = 20,
                         filter_types: List[str] = None) -> List[MemoryEvent]:
        """Get recent events with filtering."""
        
    def manage_flag(self, story_id: str, operation: FlagOperation) -> FlagOperationResult:
        """Manage flags with comprehensive operations."""
        
    def analyze_event_patterns(self, story_id: str) -> EventPatternAnalysis:
        """Analyze patterns in story events."""

class FlagManager:
    """Manages memory flags and conditional states."""
    
    def add_flag(self, flags: List[MemoryFlag], flag: MemoryFlag) -> List[MemoryFlag]:
        """Add flag with validation."""
        
    def remove_flag(self, flags: List[MemoryFlag], flag_name: str) -> List[MemoryFlag]:
        """Remove flag by name."""
        
    def has_flag(self, flags: List[MemoryFlag], flag_name: str) -> bool:
        """Check flag existence."""
        
    def get_flag_data(self, flags: List[MemoryFlag], flag_name: str) -> Optional[Dict]:
        """Get flag data."""

@dataclass
class MemoryEvent:
    """Memory event structure."""
    description: str
    timestamp: str
    data: Dict[str, Any]
    event_type: str = "general"
    importance: int = 1  # 1-5 scale
    
@dataclass
class MemoryFlag:
    """Memory flag structure."""
    name: str
    timestamp: str
    data: Dict[str, Any]
    expires_at: Optional[str] = None
    flag_type: str = "general"
```

### 5. Rollback and Recovery System (Medium Priority)

**Problem**: Rollback functionality mixed with memory operations
```python
def refresh_memory_after_rollback(story_id: str, target_scene_id: str) -> Dict[str, Any]:
    # 40+ lines of complex rollback logic

def restore_memory_from_snapshot(story_id, scene_id):
    # Database restoration mixed with memory operations
```

**Solution**: Extract to RollbackManager
```python
class RollbackManager:
    """Manages memory rollback and recovery operations."""
    
    def __init__(self, memory_repository: MemoryRepository,
                 snapshot_manager: MemorySnapshotManager):
        self.repository = memory_repository
        self.snapshots = snapshot_manager
        self.recovery_analyzer = RecoveryAnalyzer()
        
    def perform_rollback(self, story_id: str, target_scene_id: str) -> RollbackResult:
        """Perform complete rollback operation."""
        
    def refresh_memory_after_rollback(self, story_id: str, 
                                    rollback_result: RollbackResult) -> MemoryState:
        """Refresh memory state after rollback."""
        
    def validate_rollback_target(self, story_id: str, scene_id: str) -> ValidationResult:
        """Validate that rollback target is valid."""
        
    def get_rollback_impact_analysis(self, story_id: str, 
                                   target_scene_id: str) -> ImpactAnalysis:
        """Analyze impact of potential rollback."""

@dataclass
class RollbackResult:
    """Result of rollback operation."""
    success: bool
    target_scene_id: str
    original_memory: MemoryState
    restored_memory: MemoryState
    affected_characters: List[str]
    rollback_timestamp: str
    warnings: List[str]
```

## Proposed Modular Architecture

```python
class MemoryManager:
    """Main orchestrator for memory management operations."""
    
    def __init__(self, database_manager: DatabaseManager, config: Dict[str, Any]):
        self.repository = MemoryRepository(database_manager)
        self.character_manager = CharacterManager(self.repository)
        self.world_state_manager = WorldStateManager(self.repository)
        self.event_manager = EventManager(self.repository)
        self.context_generator = MemoryContextGenerator()
        self.rollback_manager = RollbackManager(self.repository, self.repository.snapshot_manager)
        
    def get_memory_state(self, story_id: str) -> MemoryState:
        """Get complete memory state."""
        return self.repository.load_memory(story_id)
    
    def update_character(self, story_id: str, character_name: str,
                        updates: CharacterUpdates) -> CharacterUpdateResult:
        """Update character through character manager."""
        return self.character_manager.update_character(story_id, character_name, updates)
    
    def generate_prompt_context(self, story_id: str,
                              options: ContextGenerationOptions) -> FormattedContext:
        """Generate formatted context for prompts."""
        return self.context_generator.generate_full_context(story_id, options)
    
    def create_memory_snapshot(self, story_id: str, scene_id: str) -> str:
        """Create memory snapshot."""
        memory = self.repository.load_memory(story_id)
        return self.repository.snapshot_manager.create_snapshot(story_id, scene_id, memory)
    
    def perform_rollback(self, story_id: str, target_scene_id: str) -> RollbackResult:
        """Perform memory rollback."""
        return self.rollback_manager.perform_rollback(story_id, target_scene_id)
```

## Implementation Benefits

### Immediate Improvements
1. **Single Responsibility**: Each class handles one aspect of memory management
2. **Testability**: Components can be tested independently with mock data
3. **Maintainability**: Changes to context generation don't affect persistence
4. **Type Safety**: Proper dataclasses and type hints throughout

### Long-term Advantages
1. **Performance**: Specialized managers can optimize specific operations
2. **Scalability**: Repository pattern allows for different storage backends
3. **Extensibility**: New memory types or context formats can be added easily
4. **Integration**: Clean interfaces for other system components

## Migration Strategy

### Phase 1: Core Data Structures (Week 1)
1. Create all dataclasses and memory state structure
2. Implement MemoryRepository with basic CRUD operations
3. Create MemorySerializer for data handling

### Phase 2: Character Management (Week 2)
1. Extract CharacterManager with mood and voice tracking
2. Implement comprehensive character update system
3. Create character progression and history tracking

### Phase 3: Context Generation (Week 3)
1. Extract MemoryContextGenerator with formatting systems
2. Implement token-aware context optimization
3. Create flexible prompt formatting options

### Phase 4: World State and Events (Week 4)
1. Extract WorldStateManager and EventManager
2. Implement sophisticated event tracking and analysis
3. Create comprehensive flag management system

### Phase 5: Integration and Rollback (Week 5)
1. Extract RollbackManager with impact analysis
2. Integrate all managers through main MemoryManager
3. Performance optimization and comprehensive testing

## Risk Assessment

### Low Risk
- **Memory Repository**: Well-defined CRUD operations with clear interfaces
- **Data Structures**: Straightforward dataclass definitions

### Medium Risk
- **Context Generation**: Complex formatting logic with token considerations
- **Character Management**: Mood tracking and voice profile management

### High Risk
- **Migration**: Converting from functions to classes requires careful interface management
- **Rollback System**: Complex snapshot and recovery logic with data integrity concerns

## Conclusion

The `memory_manager.py` module represents a comprehensive memory management system that would significantly benefit from object-oriented refactoring. The proposed architecture separates persistence, character management, context generation, world state management, and rollback operations into focused components while maintaining all current functionality.

This refactoring would enable better testing, improved performance through specialized managers, and provide a solid foundation for advanced memory analytics and AI-driven memory optimization in future development.
