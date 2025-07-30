# Timeline Builder Refactoring Recommendations

## Overview

The `timeline_builder.py` module (707 lines) provides timeline generation, navigation utilities, and analytical functions for OpenChronicle stories. The module is functionally complete but could benefit from refactoring to improve maintainability and separation of concerns.

## Current Structure Analysis

The module currently handles several distinct responsibilities:
1. Timeline data retrieval and formatting (full timeline, chapter view, labeled scenes)
2. Navigation aids (menu generation, scene context)
3. Analytical functions (tone consistency auditing, statistics)
4. Summarization capabilities (narrative, character, and event summaries)
5. Export functionality (JSON, Markdown)

## Recommended Refactoring Approach

### 1. Module Splitting

Break the large file into several focused modules within a `timeline` package:

```powershell
# Recommended new structure
core/
  timeline/
    __init__.py                # Package exports and TimelineBuilder facade
    retrieval.py               # Timeline data retrieval functions
    navigation.py              # Navigation and context functions
    analytics.py               # Statistical and analytical functions
    summarization.py           # Auto-summary generation
    exporters.py               # Export functionality (JSON, Markdown)
```

### 2. Class Extraction

Extract key functionality into dedicated classes:

- `TimelineRetriever`: Core timeline data retrieval functions
- `TimelineNavigator`: Navigation and context functions
- `TimelineAnalyzer`: Statistical and analytical functions
- `SummaryGenerator`: Auto-summary generation
- `TimelineExporter`: Export functionality

### 3. Main Class Restructuring

Transform the `TimelineBuilder` into a facade that coordinates between specialized classes:

```python
class TimelineBuilder:
    """Coordinates timeline operations."""
    
    def __init__(self, story_id: str):
        self.story_id = story_id
        self.bookmark_manager = BookmarkManager(story_id)
        init_database(story_id)
        
        # Initialize specialized components
        self.retriever = TimelineRetriever(story_id, self.bookmark_manager)
        self.navigator = TimelineNavigator(story_id)
        self.analyzer = TimelineAnalyzer(story_id)
        self.summarizer = SummaryGenerator(story_id)
        self.exporter = TimelineExporter(story_id)
    
    def get_full_timeline(self) -> Dict[str, Any]:
        """Get complete story timeline with scenes and bookmarks."""
        return self.retriever.get_full_timeline()
    
    # Other methods delegate to specialized components
```

### 4. Specific Improvements

#### Separate Tone Consistency Logic

The tone consistency audit is complex and should be extracted into its own class:

```python
class ToneConsistencyAnalyzer:
    """Analyzes tone consistency across story scenes."""
    
    def __init__(self, story_id: str):
        self.story_id = story_id
    
    def analyze_tone_consistency(self) -> Dict[str, Any]:
        """Analyze tone consistency across story scenes."""
        try:
            log_info(f"Starting tone consistency audit for story: {self.story_id}")
            
            # Get scenes with structured tags
            scenes = self._get_tagged_scenes()
            
            # Process scenes
            tone_timeline = self._build_tone_timeline(scenes)
            tone_inconsistencies = self._detect_inconsistencies(tone_timeline)
            tone_transitions = self._analyze_transitions(tone_timeline)
            character_profiles = self._build_character_profiles(scenes)
            
            # Generate results
            return self._compile_results(
                tone_timeline, 
                tone_inconsistencies, 
                tone_transitions, 
                character_profiles
            )
            
        except Exception as e:
            log_error(f"Error during tone consistency audit: {e}")
            return {
                'story_id': self.story_id,
                'error': str(e),
                'audit_timestamp': datetime.now(UTC).isoformat()
            }
    
    # Helper methods...
```

#### Modularize Summarization Logic

The summarization functions should be split into separate strategy classes:

```python
class SummaryStrategy(ABC):
    """Abstract base class for summary generation strategies."""
    
    @abstractmethod
    def generate_summary(self, scenes: List, important_scenes: List, 
                        mood_progression: List, character_developments: Dict) -> str:
        """Generate summary based on scene data."""
        pass

class NarrativeSummaryStrategy(SummaryStrategy):
    """Generates narrative-focused summaries."""
    
    def generate_summary(self, scenes: List, important_scenes: List, 
                        mood_progression: List, character_developments: Dict) -> str:
        """Generate a narrative-style summary."""
        # Implementation...

# Then in SummaryGenerator:
def generate_summary(self, scene_range: Tuple[int, int] = None, 
                   summary_type: str = "narrative") -> Dict[str, Any]:
    # Get data...
    
    # Select strategy based on type
    if summary_type == "narrative":
        strategy = NarrativeSummaryStrategy()
    elif summary_type == "character_focused":
        strategy = CharacterSummaryStrategy()
    elif summary_type == "event_focused":
        strategy = EventSummaryStrategy()
    else:
        strategy = NarrativeSummaryStrategy()
    
    # Generate summary using strategy
    summary_text = strategy.generate_summary(
        scenes, important_scenes, mood_progression, character_developments
    )
    
    # Return results...
```

#### Simplify Export Functions

Create a dedicated exporter with format-specific methods:

```python
class TimelineExporter:
    """Exports timeline in various formats."""
    
    def __init__(self, story_id: str, retriever: TimelineRetriever):
        self.story_id = story_id
        self.retriever = retriever
    
    def to_json(self, include_content: bool = True) -> str:
        """Export timeline as JSON string."""
        if include_content:
            timeline = self.retriever.get_full_timeline()
        else:
            timeline = self.retriever.get_chapter_timeline()
        
        return json.dumps(timeline, indent=2, ensure_ascii=False)
    
    def to_markdown(self) -> str:
        """Export timeline as Markdown."""
        # Implementation...
    
    def to_html(self) -> str:
        """Export timeline as HTML."""
        # Implementation...
```

## Implementation Plan

1. Create the new directory structure
2. Extract the base interfaces/abstract classes
3. Implement the specialized components one by one:
   - Start with `TimelineRetriever` as it's the foundation
   - Implement `TimelineNavigator` next
   - Then add `TimelineAnalyzer`, `SummaryGenerator`, and `TimelineExporter`
4. Refactor the main `TimelineBuilder` class to delegate to components
5. Add comprehensive docstrings to all new files
6. Update imports and ensure backward compatibility
7. Run the full test suite to verify refactoring

## Backward Compatibility Notes

The refactoring should maintain the same public API. The main `TimelineBuilder` class should still be importable from `core.timeline_builder` with the same methods, even though internally it delegates to specialized components.

## Benefits of Refactoring

- **Improved Maintainability**: Each component focuses on a specific responsibility
- **Enhanced Testability**: Isolated components can be tested independently
- **Better Code Organization**: Related functionality is grouped together
- **Reduced Complexity**: Each class is simpler and more focused
- **Easier Extensions**: New features can be added to specific components without modifying others

## Coding Instruction Compliance

This refactoring adheres to the provided coding instructions:
- Uses PowerShell-compatible path formats
- Maintains backward compatibility
- Follows clean development principles
- Preserves the existing functionality while improving organization
