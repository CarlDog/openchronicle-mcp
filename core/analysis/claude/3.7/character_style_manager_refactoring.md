# Character Style Manager Refactoring Recommendation

## Current Module Overview

**File**: `core/character_style_manager.py` (465 lines)  
**Purpose**: Manages character style consistency across different LLM models with tone auditing and model selection.

**Key Components**:
1. **CharacterStyleManager Class** - Main class handling all character style functionality
2. **Model Format Adapters** - Methods to format style prompts for different LLM providers
3. **Tone Analysis** - Functions to analyze and track character tone consistency
4. **Model Selection** - Logic to select appropriate models for characters
5. **Scene Anchoring** - System to maintain consistency across scenes

**Current Responsibilities**:
- Loading character style data from files
- Formatting style prompts for different model providers
- Analyzing character tone consistency
- Selecting optimal models for characters
- Managing consistency scores
- Creating scene anchors for model transitions
- Providing character statistics

## Issues Identified

1. **Mixed Responsibilities**: The main class handles file I/O, formatting, analysis, and model selection
2. **Direct Dependencies**: Direct coupling with model_manager without abstraction
3. **Async/Sync Mix**: Mix of async and sync methods without clear separation
4. **Error Handling**: Limited error handling and recovery mechanisms
5. **Configuration Management**: Configuration scattered throughout the class
6. **State Management**: Multiple state collections managed directly in the class
7. **Format Adaptation Duplication**: Similar formatting logic duplicated across methods

## Refactoring Recommendations

### 1. Convert to Package Structure

Transform the file into a structured package:

```
core/
  character_style/
    __init__.py              # Public API
    manager.py               # Main manager (simplified)
    formatters/              # Style formatting
      __init__.py
      base.py
      openai.py
      anthropic.py
      ollama.py
    analyzers/               # Tone analysis
      __init__.py
      tone_analyzer.py
      consistency_tracker.py
    selection/               # Model selection
      __init__.py
      model_selector.py
      model_matcher.py
    anchoring/               # Scene anchoring
      __init__.py
      scene_anchor.py
      stitching.py
    loaders/                 # Data loading
      __init__.py
      style_loader.py
```

### 2. Implement Style Formatter Strategy Pattern

Create a formatting strategy pattern:

```python
# formatters/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class StyleFormatter(ABC):
    """Base class for style formatters."""
    
    @abstractmethod
    def format_style(self, style: Dict[str, Any]) -> str:
        """Format style for a specific provider."""
        pass

# formatters/openai.py
from typing import Dict, Any
from .base import StyleFormatter

class OpenAIStyleFormatter(StyleFormatter):
    """Formatter for OpenAI models."""
    
    def format_style(self, style: Dict[str, Any]) -> str:
        """Format style for OpenAI models."""
        parts = []
        
        if "voice" in style:
            parts.append(f"Voice: {style['voice']}")
        if "tone" in style:
            parts.append(f"Tone: {style['tone']}")
        if "syntax" in style:
            parts.append(f"Speech patterns: {style['syntax']}")
        if "personality" in style:
            parts.append(f"Personality: {style['personality']}")
            
        return "\n".join(parts)

# formatters/anthropic.py
from typing import Dict, Any
from .base import StyleFormatter

class AnthropicStyleFormatter(StyleFormatter):
    """Formatter for Anthropic models."""
    
    def format_style(self, style: Dict[str, Any]) -> str:
        """Format style for Anthropic models."""
        parts = ["Character speaking style:"]
        
        for key, value in style.items():
            parts.append(f"- {key.title()}: {value}")
            
        return "\n".join(parts)

# formatters/__init__.py
from typing import Dict, Optional
from .base import StyleFormatter
from .openai import OpenAIStyleFormatter
from .anthropic import AnthropicStyleFormatter
from .ollama import OllamaStyleFormatter
from .generic import GenericStyleFormatter

class FormatterFactory:
    """Factory for style formatters."""
    
    @staticmethod
    def get_formatter(provider: str) -> StyleFormatter:
        """Get the appropriate formatter for a provider."""
        providers = {
            "openai": OpenAIStyleFormatter(),
            "anthropic": AnthropicStyleFormatter(),
            "ollama": OllamaStyleFormatter(),
            "generic": GenericStyleFormatter()
        }
        
        return providers.get(provider.lower(), GenericStyleFormatter())
```

### 3. Create Dedicated Tone Analyzer

Extract tone analysis into a dedicated class:

```python
# analyzers/tone_analyzer.py
from typing import Dict, Any, Optional
import json

class ToneAnalyzer:
    """Analyzes character output for tone consistency."""
    
    def __init__(self, model_manager):
        """Initialize tone analyzer."""
        self.model_manager = model_manager
    
    async def analyze_tone(self, character_name: str, output: str, 
                          expected_style: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze character output for tone consistency."""
        if not output.strip():
            return {"tone": "neutral", "consistency": 0.5}
        
        # Use analysis model for tone detection
        analysis_model = self._get_analysis_model()
        
        prompt = f"""Analyze the tone and style of this character dialogue:

Character: {character_name}
Output: "{output}"

Expected style: {json.dumps(expected_style, indent=2)}

Provide analysis in JSON format:
{{
  "tone": "description of current tone",
  "consistency": 0.0-1.0 (how consistent with expected style),
  "style_elements": ["observed", "style", "elements"],
  "deviations": ["any", "style", "deviations"],
  "recommendations": "suggestions for improvement"
}}"""

        try:
            response = await self.model_manager.generate_response(
                prompt,
                adapter_name=analysis_model,
                max_tokens=256,
                temperature=0.1
            )
            
            return json.loads(response)
            
        except Exception as e:
            # Log error
            return {"tone": "unknown", "consistency": 0.5}
    
    def _get_analysis_model(self) -> str:
        """Get the best model for tone analysis."""
        config = self.model_manager.config
        content_routing = config.get("content_routing", {})
        candidates = content_routing.get("analysis_models", ["mock"])
        
        # Get first enabled model
        available_models = self.model_manager.list_model_configs()
        for model in candidates:
            if available_models.get(model, {}).get("enabled", True):
                return model
        
        return "mock"

# analyzers/consistency_tracker.py
from typing import Dict, List, Any, Optional
from datetime import datetime

class ConsistencyTracker:
    """Tracks character tone consistency over time."""
    
    def __init__(self):
        """Initialize consistency tracker."""
        self.tone_history = {}
        self.consistency_scores = {}
    
    def add_tone(self, character_name: str, tone: str) -> None:
        """Add a tone entry for a character."""
        if character_name not in self.tone_history:
            self.tone_history[character_name] = []
        
        self.tone_history[character_name].append({
            "tone": tone,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only last 5 tone entries
        if len(self.tone_history[character_name]) > 5:
            self.tone_history[character_name] = self.tone_history[character_name][-5:]
    
    def get_recent_tone(self, character_name: str) -> Optional[str]:
        """Get the most recent tone for a character."""
        if character_name in self.tone_history and self.tone_history[character_name]:
            return self.tone_history[character_name][-1]["tone"]
        return None
    
    def update_consistency_score(self, character_name: str, score: float) -> None:
        """Update consistency score for a character."""
        if character_name not in self.consistency_scores:
            self.consistency_scores[character_name] = []
        
        self.consistency_scores[character_name].append({
            "score": score,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only last 10 scores
        if len(self.consistency_scores[character_name]) > 10:
            self.consistency_scores[character_name] = self.consistency_scores[character_name][-10:]
    
    def calculate_consistency_score(self, character_name: str) -> float:
        """Calculate consistency score based on recent history."""
        if character_name not in self.consistency_scores:
            return 0.5
        
        scores = [entry["score"] for entry in self.consistency_scores[character_name]]
        if not scores:
            return 0.5
        
        # Weight recent scores more heavily
        weighted_sum = 0.0
        weight_sum = 0.0
        
        for i, score in enumerate(scores):
            weight = 1.0 + (i * 0.1)  # More recent = higher weight
            weighted_sum += score * weight
            weight_sum += weight
        
        return weighted_sum / weight_sum if weight_sum > 0 else 0.5
```

### 4. Create Model Selection System

Implement a dedicated model selection system:

```python
# selection/model_selector.py
from typing import Dict, List, Any, Optional

class ModelSelector:
    """Selects the best model for a character."""
    
    def __init__(self, model_manager):
        """Initialize model selector."""
        self.model_manager = model_manager
        self.character_models = {}  # Track which model is used for each character
    
    def select_model(self, character_name: str, character_style: Dict[str, Any], 
                    content_type: str = "dialogue") -> str:
        """Select the best model for a specific character."""
        # Get character preferences if any
        preferred_models = character_style.get("preferred_models", [])
        
        # Get available models
        available_models = self.model_manager.list_model_configs()
        enabled_models = [
            name for name, config in available_models.items()
            if config.get("enabled", True)
        ]
        
        # Try preferred models first
        for model in preferred_models:
            if model in enabled_models:
                self._update_character_model(character_name, model)
                return model
        
        # Fallback to content routing
        selected_model = self._select_by_content_type(content_type, enabled_models)
        self._update_character_model(character_name, selected_model)
        
        return selected_model
    
    def _select_by_content_type(self, content_type: str, enabled_models: List[str]) -> str:
        """Select model based on content type."""
        config = self.model_manager.config
        content_routing = config.get("content_routing", {})
        
        if content_type == "dialogue":
            candidates = content_routing.get("creative_models", [])
        elif content_type == "action":
            candidates = content_routing.get("fast_models", [])
        else:
            candidates = content_routing.get("safe_models", [])
        
        # Filter for enabled models
        enabled_candidates = [
            name for name in candidates 
            if name in enabled_models
        ]
        
        if enabled_candidates:
            return enabled_candidates[0]
        
        # Ultimate fallback
        return "mock"
    
    def _update_character_model(self, character_name: str, model_name: str) -> None:
        """Update the currently used model for a character."""
        self.character_models[character_name] = model_name
    
    def get_current_model(self, character_name: str) -> Optional[str]:
        """Get the currently used model for a character."""
        return self.character_models.get(character_name)
    
    async def suggest_model_switch(self, character_name: str, 
                                  consistency_score: float) -> Optional[str]:
        """Suggest model switch if character consistency is poor."""
        if consistency_score > 0.7:
            return None  # Good consistency, no switch needed
        
        # Get current model
        current_model = self.get_current_model(character_name)
        if not current_model:
            return None
        
        # Get alternatives
        alternatives = self._get_alternative_models(current_model)
        
        for alt_model in alternatives:
            if self._is_suitable_for_character(alt_model, character_name):
                return alt_model
        
        return None
    
    def _get_alternative_models(self, current_model: str) -> List[str]:
        """Get alternative models to try."""
        # Implementation...
    
    def _is_suitable_for_character(self, model_name: str, character_name: str) -> bool:
        """Check if a model is suitable for a character."""
        # Implementation...
```

### 5. Implement Scene Anchoring System

Create a dedicated scene anchoring system:

```python
# anchoring/scene_anchor.py
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import time

class SceneAnchorManager:
    """Manages scene anchors for character consistency."""
    
    def __init__(self):
        """Initialize scene anchor manager."""
        self.scene_anchors = {}
    
    def create_anchor(self, character_name: str, style: Dict[str, Any], 
                     scene_context: str, model_name: str, recent_tone: str) -> str:
        """Create a scene anchor for a character."""
        # Create anchor prompt
        anchor = f"""=== SCENE ANCHOR for {character_name} ===
Recent tone: {recent_tone}
Character style: {json.dumps(style, indent=2)}
Scene context: {scene_context}

The character should maintain consistency with their established tone and style.
Model: {model_name}
"""
        
        # Store anchor
        if character_name not in self.scene_anchors:
            self.scene_anchors[character_name] = []
        
        self.scene_anchors[character_name].append({
            "timestamp": time.time(),
            "anchor": anchor,
            "model": model_name,
            "tone": recent_tone
        })
        
        # Keep only last 5 anchors
        if len(self.scene_anchors[character_name]) > 5:
            self.scene_anchors[character_name] = self.scene_anchors[character_name][-5:]
        
        return anchor
    
    def get_recent_anchors(self, character_name: str, count: int = 2) -> List[Dict[str, Any]]:
        """Get recent anchors for a character."""
        if character_name not in self.scene_anchors:
            return []
        
        return self.scene_anchors[character_name][-count:]
```

### 6. Refine Main Manager Class

Simplify the main manager to use the specialized components:

```python
# manager.py
from typing import Dict, List, Any, Optional
import os
import json

from .formatters import FormatterFactory
from .analyzers.tone_analyzer import ToneAnalyzer
from .analyzers.consistency_tracker import ConsistencyTracker
from .selection.model_selector import ModelSelector
from .anchoring.scene_anchor import SceneAnchorManager
from .anchoring.stitching import StitchingGenerator
from .loaders.style_loader import StyleLoader

class CharacterStyleManager:
    """Manages character style consistency across dynamic model switching."""
    
    def __init__(self, model_manager):
        """Initialize character style manager."""
        self.model_manager = model_manager
        
        # Initialize components
        self.formatter_factory = FormatterFactory()
        self.tone_analyzer = ToneAnalyzer(model_manager)
        self.consistency_tracker = ConsistencyTracker()
        self.model_selector = ModelSelector(model_manager)
        self.scene_anchor_manager = SceneAnchorManager()
        self.stitching_generator = StitchingGenerator()
        self.style_loader = StyleLoader()
        
        # Initialize data storage
        self.character_styles = {}
    
    def load_character_styles(self, story_path: str) -> Dict[str, Dict[str, Any]]:
        """Load character style blocks from story characters."""
        self.character_styles = self.style_loader.load_styles(story_path)
        return self.character_styles
    
    def get_character_style_prompt(self, character_name: str, model_name: str) -> str:
        """Get character style prompt adapted for specific model."""
        if character_name not in self.character_styles:
            return ""
            
        style = self.character_styles[character_name]
        
        model_config = self.model_manager.get_adapter_info(model_name)
        provider = model_config.get("provider", "").lower()
        
        formatter = self.formatter_factory.get_formatter(provider)
        return formatter.format_style(style)
    
    def select_character_model(self, character_name: str, content_type: str = "dialogue") -> str:
        """Select the best model for a specific character."""
        character_style = self.character_styles.get(character_name, {})
        return self.model_selector.select_model(character_name, character_style, content_type)
    
    async def analyze_character_tone(self, character_name: str, output: str) -> Dict[str, Any]:
        """Analyze character output for tone consistency."""
        character_style = self.character_styles.get(character_name, {})
        
        analysis = await self.tone_analyzer.analyze_tone(
            character_name, output, character_style)
        
        # Update tracking
        self.consistency_tracker.add_tone(character_name, analysis["tone"])
        self.consistency_tracker.update_consistency_score(character_name, analysis["consistency"])
        
        return analysis
    
    # Other methods delegating to specialized components...
```

### 7. Create Data Models

Implement proper data models:

```python
# models.py
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime

@dataclass
class CharacterStyle:
    """Represents a character's style information."""
    character_name: str
    voice: Optional[str] = None
    tone: Optional[str] = None
    syntax: Optional[str] = None
    personality: Optional[str] = None
    preferred_models: List[str] = field(default_factory=list)
    additional_attributes: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "character_name": self.character_name
        }
        
        if self.voice:
            result["voice"] = self.voice
        if self.tone:
            result["tone"] = self.tone
        if self.syntax:
            result["syntax"] = self.syntax
        if self.personality:
            result["personality"] = self.personality
        if self.preferred_models:
            result["preferred_models"] = self.preferred_models
        
        result.update(self.additional_attributes)
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CharacterStyle':
        """Create from dictionary."""
        character_name = data.pop("character_name", "Unknown")
        voice = data.pop("voice", None)
        tone = data.pop("tone", None)
        syntax = data.pop("syntax", None)
        personality = data.pop("personality", None)
        preferred_models = data.pop("preferred_models", [])
        
        return cls(
            character_name=character_name,
            voice=voice,
            tone=tone,
            syntax=syntax,
            personality=personality,
            preferred_models=preferred_models,
            additional_attributes=data
        )

@dataclass
class ToneAnalysis:
    """Represents the result of tone analysis."""
    tone: str
    consistency: float
    style_elements: List[str] = field(default_factory=list)
    deviations: List[str] = field(default_factory=list)
    recommendations: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tone": self.tone,
            "consistency": self.consistency,
            "style_elements": self.style_elements,
            "deviations": self.deviations,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ToneAnalysis':
        """Create from dictionary."""
        timestamp = datetime.fromisoformat(data.pop("timestamp")) if "timestamp" in data else datetime.now()
        return cls(
            tone=data.get("tone", "unknown"),
            consistency=data.get("consistency", 0.5),
            style_elements=data.get("style_elements", []),
            deviations=data.get("deviations", []),
            recommendations=data.get("recommendations"),
            timestamp=timestamp
        )
```

## Implementation Strategy

1. **Create Package Structure**: Set up the directory and file structure
2. **Implement Formatter Strategy**: Create formatters for different providers
3. **Create Tone Analysis Components**: Implement analyzer and consistency tracker
4. **Create Model Selection System**: Implement model selector
5. **Implement Scene Anchoring**: Create anchor and stitching components
6. **Refine Main Manager**: Update the main class to use specialized components
7. **Implement Data Models**: Create proper models for style and analysis data

## Benefits of Refactoring

1. **Improved Organization**: Smaller, focused components with clear responsibilities
2. **Enhanced Testability**: Components can be tested in isolation
3. **Better Extensibility**: Easy to add new formatters, analyzers, or selection strategies
4. **Improved Error Handling**: More robust error handling in specialized components
5. **Cleaner API**: Well-defined interfaces for different operations
6. **Type Safety**: Comprehensive type annotations throughout the codebase
7. **Performance**: Potential for caching and optimization in specific components

## Migration Plan

1. **Incremental Refactoring**: Implement the new package structure alongside the existing module
2. **Backward Compatibility**: Provide a compatibility layer for existing code
3. **Dual Operation**: Allow both old and new implementations to run in parallel during transition
4. **Gradual Adoption**: Update dependent code to use the new API incrementally
5. **Complete Migration**: Remove legacy implementation once all dependencies are updated

By following this refactoring plan, the character_style_manager will be transformed into a well-structured, maintainable package that adheres to modern Python best practices while preserving all existing functionality.
