# Context Builder Refactoring Recommendations

## Overview

The `context_builder.py` module (766 lines) is a central component of OpenChronicle that generates context for LLM prompts. It orchestrates various engines to build rich, detailed context that informs AI story generation, including character consistency, emotional stability, and narrative dynamics.

## Key Components

1. **Context Building Functions**:
   - `build_context`: Basic synchronous context builder
   - `build_context_with_analysis`: Async context builder with content analysis
   - `build_context_with_dynamic_models`: Advanced context builder with multiple engines

2. **Helper Functions**:
   - `load_canon_snippets`: Loads world lore and rules
   - `json_to_readable_text`: Converts JSON to human-readable format
   - `_build_system_context`, `_build_memory_context`, etc.: Section builders
   - `_assemble_context`: Combines sections in proper order

3. **Validation Functions**:
   - `validate_character_consistency`: Checks for character behavior violations
   - `validate_emotional_stability`: Detects emotional loops and stability issues

4. **Report Generation**:
   - `get_character_consistency_report`: Generates character consistency reports
   - `get_emotional_stability_report`: Generates emotional stability reports

## Key Observations

1. **Orchestration Hub**: This module acts as a central orchestration point, integrating multiple specialized engines.

2. **High Coupling**: The module directly imports and interacts with numerous other components:
   - `memory_manager`
   - `content_analyzer`
   - `character_style_manager`
   - `character_consistency_engine`
   - `emotional_stability_engine`
   - `character_interaction_engine`
   - `character_stat_engine`
   - `narrative_dice_engine`
   - `memory_consistency_engine`
   - `intelligent_response_engine`
   - `token_manager`

3. **Mixed Concerns**: The module handles several distinct responsibilities:
   - Loading and formatting canon/lore
   - Building context for different model capabilities
   - Validating generated output
   - Character and scene detection
   - Dice resolution and gameplay mechanics
   - Generating reports on character consistency/stability

4. **Inconsistent Function Styles**: The module mixes synchronous and asynchronous functions, sometimes with similar purposes.

5. **Component Initialization Repetition**: Components are re-initialized in multiple functions.

## Refactoring Recommendations

### 1. Split into Specialized Modules

Reorganize the file into a package structure with specialized modules:

```
context_builder/
  __init__.py
  core.py                # Core context building functions
  canon_manager.py       # Canon/lore management
  context_assembler.py   # Context assembly and formatting
  validation.py          # Output validation functions
  reporting.py           # Report generation functions
  dice_resolution.py     # Dice resolution and game mechanics
  detection.py           # Character and scene detection
```

### 2. Create a ContextBuilderFactory

Implement a factory pattern to centralize component initialization:

```python
# context_builder/factory.py
class ContextBuilderFactory:
    """Factory for creating context builder components."""
    
    @staticmethod
    def create_basic_builder():
        """Create a basic context builder."""
        return BasicContextBuilder()
    
    @staticmethod
    def create_advanced_builder(model_manager):
        """Create an advanced context builder with all engines."""
        return AdvancedContextBuilder(
            model_manager=model_manager,
            content_analyzer=ContentAnalyzer(model_manager),
            character_manager=CharacterStyleManager(model_manager),
            consistency_engine=CharacterConsistencyEngine(),
            emotional_engine=EmotionalStabilityEngine(),
            interaction_engine=CharacterInteractionEngine(),
            stat_engine=CharacterStatEngine(),
            dice_engine=NarrativeDiceEngine(),
            memory_engine=MemoryConsistencyEngine(),
            intelligent_response_engine=IntelligentResponseEngine(),
            token_manager=TokenManager(model_manager)
        )
    
    @staticmethod
    def create_validator():
        """Create a response validator."""
        return ResponseValidator(
            consistency_engine=CharacterConsistencyEngine(),
            emotional_engine=EmotionalStabilityEngine()
        )
```

### 3. Create Builder Classes with Clear Interfaces

Define clear class hierarchies for the context builders:

```python
# context_builder/core.py
from abc import ABC, abstractmethod

class ContextBuilder(ABC):
    """Base interface for context builders."""
    
    @abstractmethod
    async def build_context(self, user_input, story_data):
        """Build context for a user input and story data."""
        pass

class BasicContextBuilder(ContextBuilder):
    """Simple context builder without advanced analysis."""
    
    def __init__(self):
        pass
    
    async def build_context(self, user_input, story_data):
        """Build basic context without analysis."""
        # Implementation...

class AnalysisContextBuilder(ContextBuilder):
    """Context builder with content analysis."""
    
    def __init__(self, model_manager, content_analyzer):
        self.model_manager = model_manager
        self.content_analyzer = content_analyzer
    
    async def build_context(self, user_input, story_data):
        """Build context with content analysis."""
        # Implementation...

class AdvancedContextBuilder(ContextBuilder):
    """Full-featured context builder with all engines."""
    
    def __init__(self, model_manager, content_analyzer, character_manager, 
                consistency_engine, emotional_engine, interaction_engine,
                stat_engine, dice_engine, memory_engine, 
                intelligent_response_engine, token_manager):
        self.model_manager = model_manager
        self.content_analyzer = content_analyzer
        self.character_manager = character_manager
        self.consistency_engine = consistency_engine
        self.emotional_engine = emotional_engine
        self.interaction_engine = interaction_engine
        self.stat_engine = stat_engine
        self.dice_engine = dice_engine
        self.memory_engine = memory_engine
        self.intelligent_response_engine = intelligent_response_engine
        self.token_manager = token_manager
    
    async def build_context(self, user_input, story_data):
        """Build advanced context with all engines."""
        # Implementation...
```

### 4. Create a Dedicated CanonManager

Extract canon-related functionality to a dedicated component:

```python
# context_builder/canon_manager.py
import os
import json
import random
from typing import List, Dict, Any, Optional

class CanonManager:
    """Manager for canon/lore content."""
    
    @staticmethod
    def load_canon_snippets(storypack_path, refs=None, limit=5):
        """Load canon snippets from storypack."""
        # Implementation...
    
    @staticmethod
    def json_to_readable_text(data, indent=0):
        """Convert JSON data to readable text."""
        # Implementation...
    
    def optimize_canon_selection(self, analysis, story_data):
        """Select optimal canon based on content analysis."""
        # Implementation...
```

### 5. Create a ContextAssembler

Extract context assembly logic to a dedicated component:

```python
# context_builder/context_assembler.py
from typing import Dict, List, Any

class ContextAssembler:
    """Assembles context from various components."""
    
    def __init__(self, token_manager=None):
        self.token_manager = token_manager
    
    def build_system_context(self, story_data):
        """Build system context section."""
        # Implementation...
    
    def build_memory_context(self, memory):
        """Build memory context section."""
        # Implementation...
    
    def build_canon_context(self, canon_chunks):
        """Build canon context section."""
        # Implementation...
    
    def assemble_context(self, context_parts, section_order=None):
        """Assemble final context from parts."""
        # Implementation...
    
    def trim_context(self, context_parts, target_tokens, model_name):
        """Trim context to fit token limits."""
        # Implementation using token_manager if available
```

### 6. Create ResponseValidator

Extract validation logic to a dedicated component:

```python
# context_builder/validation.py
from typing import Dict, Any, Optional

class ResponseValidator:
    """Validates generated responses for consistency and stability."""
    
    def __init__(self, consistency_engine=None, emotional_engine=None):
        self.consistency_engine = consistency_engine
        self.emotional_engine = emotional_engine
    
    async def validate_character_consistency(self, generated_output, character_name, 
                                          scene_id, context=None):
        """Validate character consistency."""
        # Implementation...
    
    async def validate_emotional_stability(self, generated_output, character_name,
                                        scene_id, context=None):
        """Validate emotional stability."""
        # Implementation...
    
    def get_character_consistency_report(self, character_name=None):
        """Get character consistency report."""
        # Implementation...
    
    def get_emotional_stability_report(self, character_name=None):
        """Get emotional stability report."""
        # Implementation...
```

### 7. Create DiceResolutionHandler

Extract dice resolution logic to a dedicated component:

```python
# context_builder/dice_resolution.py
from typing import Dict, Any, Optional

class DiceResolutionHandler:
    """Handles dice resolution and game mechanics."""
    
    def __init__(self, dice_engine=None, stat_engine=None):
        self.dice_engine = dice_engine
        self.stat_engine = stat_engine
    
    def check_for_dice_resolution(self, user_input, character_id, character_stats):
        """Check if user input suggests an action that might need dice resolution."""
        # Implementation...
    
    def generate_resolution_prompt(self, character_id, resolution_type, difficulty):
        """Generate a prompt for a dice resolution."""
        # Implementation...
    
    def apply_resolution_outcome(self, character_id, resolution_type, outcome, narrative):
        """Apply the outcome of a dice resolution to the narrative."""
        # Implementation...
```

### 8. Create SceneDetector

Extract scene and character detection logic:

```python
# context_builder/detection.py
from typing import Dict, List, Any

class SceneDetector:
    """Detects scene elements from user input."""
    
    @staticmethod
    def detect_scene_characters(user_input, characters):
        """Detect which characters are in the current scene."""
        # Implementation...
    
    @staticmethod
    def detect_scene_location(user_input, locations):
        """Detect the current scene location."""
        # Implementation...
    
    @staticmethod
    def detect_active_character(user_input, characters):
        """Detect the currently active character."""
        # Implementation...
```

### 9. Update Public API in __init__.py

Provide a clean public API through the package's `__init__.py`:

```python
# context_builder/__init__.py
from .core import ContextBuilder, BasicContextBuilder, AnalysisContextBuilder, AdvancedContextBuilder
from .factory import ContextBuilderFactory
from .validation import ResponseValidator
from .reporting import ReportGenerator

# Legacy compatibility functions
async def build_context(user_input, story_data):
    """Legacy function for backward compatibility."""
    builder = ContextBuilderFactory.create_basic_builder()
    return await builder.build_context(user_input, story_data)

async def build_context_with_analysis(user_input, story_data):
    """Legacy function for backward compatibility."""
    from ..model_adapter import ModelManager
    model_manager = ModelManager()
    builder = ContextBuilderFactory.create_analysis_builder(model_manager)
    return await builder.build_context(user_input, story_data)

async def build_context_with_dynamic_models(user_input, story_data, model_manager):
    """Legacy function for backward compatibility."""
    builder = ContextBuilderFactory.create_advanced_builder(model_manager)
    return await builder.build_context(user_input, story_data)
```

## Implementation Strategy

### Phase 1: Package Structure and Interfaces
1. Create the package directory structure
2. Define base interfaces and abstract classes
3. Create factory for dependency management

### Phase 2: Core Component Implementation
1. Implement `CanonManager`
2. Implement `ContextAssembler`
3. Implement basic `ContextBuilder` classes

### Phase 3: Specialized Component Implementation
1. Implement `ResponseValidator`
2. Implement `DiceResolutionHandler`
3. Implement `SceneDetector`

### Phase 4: Legacy Support and Migration
1. Implement backward compatibility functions
2. Update imports in dependent modules
3. Add tests for new components

## Benefits of Refactoring

1. **Improved Separation of Concerns**: Each component has a clear, focused responsibility
2. **Better Dependency Management**: Components explicitly declare their dependencies
3. **Enhanced Testability**: Smaller, focused components are easier to test
4. **Reduced Coupling**: Components interact through well-defined interfaces
5. **Clearer API**: Consistent interfaces for context building functionality
6. **More Flexible Composition**: Mix and match components based on needs
7. **Centralized Component Creation**: Factory pattern simplifies object creation

## Minimal Compatibility Layer

To maintain backward compatibility, implement legacy functions that delegate to the new components:

```python
# Legacy compatibility functions

# Imported in main package __init__.py
async def build_context(user_input, story_data):
    builder = ContextBuilderFactory.create_basic_builder()
    return await builder.build_context(user_input, story_data)

async def build_context_with_analysis(user_input, story_data):
    from ..model_adapter import ModelManager
    model_manager = ModelManager()
    builder = ContextBuilderFactory.create_analysis_builder(model_manager)
    return await builder.build_context(user_input, story_data)

async def build_context_with_dynamic_models(user_input, story_data, model_manager):
    builder = ContextBuilderFactory.create_advanced_builder(model_manager)
    return await builder.build_context(user_input, story_data)

async def validate_character_consistency(generated_output, character_name, scene_id, consistency_engine, context=None):
    validator = ResponseValidator(consistency_engine=consistency_engine)
    return await validator.validate_character_consistency(generated_output, character_name, scene_id, context)

async def validate_emotional_stability(generated_output, character_name, scene_id, emotional_engine, context=None):
    validator = ResponseValidator(emotional_engine=emotional_engine)
    return await validator.validate_emotional_stability(generated_output, character_name, scene_id, context)
```

## Testing Considerations

1. Create unit tests for each component
2. Test components in isolation with mock dependencies
3. Create integration tests for combined functionality
4. Verify backward compatibility with existing code
5. Test edge cases in context assembly and token management

## Conclusion

The `context_builder.py` module would benefit from being restructured into a package with specialized components. By applying a more object-oriented design with clear interfaces and dependency injection, we can improve maintainability, testability, and flexibility.

The proposed modular structure aligns with the single responsibility principle and creates a more robust foundation for future enhancements to the context building system.

## Next Steps

1. Create the package structure and skeleton files
2. Begin implementing core interfaces and base classes
3. Move functionality to specialized components one by one
4. Implement factory for dependency management
5. Add comprehensive tests for all components

For project status tracking, see `.copilot/project_status.json`.
