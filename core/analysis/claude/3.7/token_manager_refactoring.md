# Token Manager Refactoring Recommendation

## Current Module Overview

**File**: `core/token_manager.py` (255 lines)  
**Purpose**: Manages token usage, estimation, and continuation for LLM interactions with dynamic model selection.

**Key Components**:
1. **TokenManager Class** - Main class handling token-related functionality
2. **Tokenization Functions** - Methods to estimate token counts for different models
3. **Model Selection** - Logic to select optimal models based on token requirements
4. **Scene Continuation** - System to handle truncated responses
5. **Usage Tracking** - Token usage monitoring and statistics

**Current Responsibilities**:
- Estimating token usage for various model providers
- Selecting optimal models based on token requirements
- Detecting and handling truncated responses
- Continuing scenes when models reach token limits
- Tracking token usage statistics
- Managing tokenizers for different models
- Trimming context to fit within token limits

## Issues Identified

1. **Direct Dependency**: Hard dependency on the model_manager instance
2. **Custom Imports**: Non-standard import path for utilities
3. **Limited Error Handling**: Basic error handling without proper recovery mechanisms
4. **Mixing Concerns**: Token estimation, tracking, and model selection mixed in one class
5. **Tokenizer Management**: Storing encoders in the instance with direct imports
6. **Static Configuration**: Some parameters are hardcoded rather than configurable
7. **Limited Caching**: Basic caching mechanism for continuations

## Refactoring Recommendations

### 1. Convert to Package Structure

Transform the file into a structured package:

```
core/
  tokens/
    __init__.py              # Public API
    manager.py               # Main manager (simplified)
    estimators/              # Token estimation
      __init__.py
      base.py
      openai.py
      anthropic.py
      generic.py
    selectors/               # Model selection
      __init__.py
      selector.py
      cost_optimizer.py
    continuations/           # Continuation handling
      __init__.py
      detector.py
      generator.py
    tracking/                # Usage tracking
      __init__.py
      tracker.py
      reporter.py
    utils/                   # Utilities
      __init__.py
      context_trimmer.py
```

### 2. Implement Estimator Strategy Pattern

Create a token estimation strategy pattern:

```python
# estimators/base.py
from abc import ABC, abstractmethod
from typing import Optional

class TokenEstimator(ABC):
    """Base class for token estimators."""
    
    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for given text."""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get the name of the estimator."""
        pass


# estimators/openai.py
import tiktoken
from typing import Optional
from .base import TokenEstimator

class OpenAITokenEstimator(TokenEstimator):
    """Token estimator for OpenAI models."""
    
    def __init__(self, model_name: str = "gpt-4"):
        """Initialize with model name."""
        self.model_name = model_name
        self._encoder = None
    
    def _get_encoder(self) -> Optional[tiktoken.Encoding]:
        """Get tokenizer for the model."""
        if self._encoder is None:
            try:
                self._encoder = tiktoken.encoding_for_model(self.model_name)
            except KeyError:
                # Fallback to general tokenizer
                self._encoder = tiktoken.get_encoding("cl100k_base")
        return self._encoder
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for given text."""
        encoder = self._get_encoder()
        if encoder:
            return len(encoder.encode(text))
        
        # Fallback estimation: ~4 chars per token
        return len(text) // 4
    
    def get_name(self) -> str:
        """Get the name of the estimator."""
        return f"openai_{self.model_name}"


# estimators/anthropic.py
import tiktoken
from typing import Optional
from .base import TokenEstimator

class AnthropicTokenEstimator(TokenEstimator):
    """Token estimator for Anthropic models."""
    
    def __init__(self, model_name: str = "claude-2"):
        """Initialize with model name."""
        self.model_name = model_name
        self._encoder = None
    
    def _get_encoder(self) -> Optional[tiktoken.Encoding]:
        """Get tokenizer for the model."""
        if self._encoder is None:
            try:
                # Use cl100k_base as Claude approximation
                self._encoder = tiktoken.get_encoding("cl100k_base")
            except Exception:
                self._encoder = None
        return self._encoder
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for given text."""
        encoder = self._get_encoder()
        if encoder:
            return len(encoder.encode(text))
        
        # Fallback estimation: ~4 chars per token
        return len(text) // 4
    
    def get_name(self) -> str:
        """Get the name of the estimator."""
        return f"anthropic_{self.model_name}"


# estimators/__init__.py
from typing import Dict, Optional
from .base import TokenEstimator
from .openai import OpenAITokenEstimator
from .anthropic import AnthropicTokenEstimator
from .generic import GenericTokenEstimator

class EstimatorFactory:
    """Factory for token estimators."""
    
    @staticmethod
    def create_estimator(provider: str, model_name: str) -> TokenEstimator:
        """Create a token estimator for a provider and model."""
        provider = provider.lower()
        
        if provider == "openai":
            return OpenAITokenEstimator(model_name)
        elif provider == "anthropic":
            return AnthropicTokenEstimator(model_name)
        else:
            return GenericTokenEstimator()
```

### 3. Create Model Selection System

Implement a dedicated model selection system:

```python
# selectors/selector.py
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ModelSelector:
    """Selects optimal models based on token requirements."""
    
    def __init__(self, model_manager):
        """Initialize with model manager."""
        self.model_manager = model_manager
    
    def select_for_token_count(self, prompt_tokens: int, response_tokens: int,
                              optimization_goal: str = "cost") -> Optional[str]:
        """Select the best model based on token requirements."""
        total_tokens = prompt_tokens + response_tokens
        
        # Get all available models and their token limits
        models = self.model_manager.list_model_configs()
        suitable_models = []
        
        for model_name, config in models.items():
            if not config.get("enabled", True):
                continue
                
            max_tokens = config.get("max_tokens", 4096)
            buffer_ratio = config.get("buffer_ratio", 0.2)  # 20% buffer by default
            
            if total_tokens <= max_tokens * (1 - buffer_ratio):
                suitable_models.append({
                    "name": model_name,
                    "max_tokens": max_tokens,
                    "cost": config.get("cost_per_token", 0.001),
                    "provider": config.get("provider", "unknown"),
                    "quality": config.get("quality_score", 5)
                })
        
        if not suitable_models:
            logger.warning(f"No models can handle {total_tokens} tokens")
            return None
        
        # Sort based on optimization goal
        if optimization_goal == "cost":
            suitable_models.sort(key=lambda x: (x["cost"], -x["max_tokens"]))
        elif optimization_goal == "quality":
            suitable_models.sort(key=lambda x: (-x["quality"], x["cost"]))
        else:  # balanced
            suitable_models.sort(key=lambda x: (x["cost"] / x["quality"], -x["max_tokens"]))
        
        selected = suitable_models[0]["name"]
        logger.info(f"Selected model {selected} for {total_tokens} tokens (goal: {optimization_goal})")
        return selected
    
    def check_capacity(self, model_name: str, prompt_tokens: int, 
                      response_tokens: int) -> Dict[str, Any]:
        """Check if a model has capacity for the requested tokens."""
        model_config = self.model_manager.get_adapter_info(model_name)
        max_tokens = model_config.get("max_tokens", 4096)
        buffer_ratio = model_config.get("buffer_ratio", 0.2)
        
        total_tokens = prompt_tokens + response_tokens
        available_tokens = max_tokens * (1 - buffer_ratio)
        has_capacity = total_tokens <= available_tokens
        
        return {
            "has_capacity": has_capacity,
            "total_tokens": total_tokens,
            "available_tokens": available_tokens,
            "max_tokens": max_tokens,
            "utilization": total_tokens / max_tokens if max_tokens > 0 else 1.0,
            "buffer_ratio": buffer_ratio
        }
    
    def recommend_switch(self, current_model: str, 
                        usage_pattern: Dict[str, Any]) -> Optional[str]:
        """Recommend model switching based on usage patterns."""
        models = self.model_manager.list_model_configs()
        enabled_models = {
            name: config for name, config in models.items()
            if config.get("enabled", True)
        }
        
        if not enabled_models or current_model not in enabled_models:
            return None
        
        current_config = enabled_models[current_model]
        
        # Check for cost optimization
        if usage_pattern.get("high_cost", False):
            cheaper_models = [
                name for name, config in enabled_models.items()
                if config.get("cost_per_token", 0.001) < current_config.get("cost_per_token", 0.001)
            ]
            if cheaper_models:
                return min(cheaper_models, key=lambda x: enabled_models[x].get("cost_per_token", 0.001))
        
        # Check for token capacity
        if usage_pattern.get("frequent_truncation", False):
            larger_models = [
                name for name, config in enabled_models.items()
                if config.get("max_tokens", 4096) > current_config.get("max_tokens", 4096)
            ]
            if larger_models:
                return max(larger_models, key=lambda x: enabled_models[x].get("max_tokens", 4096))
        
        return None
```

### 4. Create Continuation System

Implement a dedicated continuation system:

```python
# continuations/detector.py
from typing import Dict, Any, List

class TruncationDetector:
    """Detects truncated responses."""
    
    def __init__(self):
        """Initialize truncation detector."""
        pass
    
    def is_truncated(self, response: str) -> Dict[str, Any]:
        """Detect if a response was likely truncated."""
        # Check for common truncation indicators
        truncation_indicators = {
            "incomplete_sentence": response.endswith((' ', '  ', ',')),
            "unfinished_quotes": response.count('"') % 2 == 1 or response.count("'") % 2 == 1,
            "unmatched_brackets": (
                response.count('(') != response.count(')') or
                response.count('[') != response.count(']') or
                response.count('{') != response.count('}')
            ),
            "abrupt_ending": (
                len(response) > 100 and 
                not response.strip().endswith(('.', '!', '?', '"', "'"))
            )
        }
        
        is_truncated = any(truncation_indicators.values())
        confidence = sum(1 for v in truncation_indicators.values() if v) / len(truncation_indicators)
        
        return {
            "is_truncated": is_truncated,
            "confidence": confidence,
            "indicators": truncation_indicators
        }


# continuations/generator.py
from typing import Dict, Any, Optional
import hashlib
import logging

logger = logging.getLogger(__name__)

class ContinuationGenerator:
    """Generates continuations for truncated responses."""
    
    def __init__(self, model_manager, model_selector):
        """Initialize with model manager and selector."""
        self.model_manager = model_manager
        self.model_selector = model_selector
        self.continuation_cache = {}
    
    def _get_cache_key(self, story_id: str, partial_response: str) -> str:
        """Generate a cache key for the continuation."""
        response_hash = hashlib.md5(partial_response.encode()).hexdigest()
        return f"{story_id}_{response_hash}"
    
    async def continue_response(self, original_prompt: str, partial_response: str,
                              story_id: str, model_name: str) -> Dict[str, Any]:
        """Continue a truncated response."""
        cache_key = self._get_cache_key(story_id, partial_response)
        
        # Check cache
        if cache_key in self.continuation_cache:
            cached = self.continuation_cache[cache_key]
            return {
                "full_response": cached["full_response"],
                "continuation": cached["continuation"],
                "model_used": cached["model_used"],
                "from_cache": True
            }
        
        # Build continuation prompt
        continuation_prompt = self._build_continuation_prompt(partial_response)
        
        # Select appropriate model
        from ..estimators import EstimatorFactory
        model_config = self.model_manager.get_adapter_info(model_name)
        provider = model_config.get("provider", "unknown")
        estimator = EstimatorFactory.create_estimator(provider, model_name)
        
        prompt_tokens = estimator.estimate_tokens(continuation_prompt)
        capacity = self.model_selector.check_capacity(model_name, prompt_tokens, 1024)
        
        if not capacity["has_capacity"]:
            new_model = self.model_selector.select_for_token_count(prompt_tokens, 1024)
            if new_model:
                logger.info(f"Switching from {model_name} to {new_model} for continuation")
                model_name = new_model
        
        try:
            # Generate continuation
            continuation = await self.model_manager.generate_response(
                continuation_prompt,
                adapter_name=model_name,
                story_id=story_id,
                temperature=0.8,
                max_tokens=1024
            )
            
            # Combine responses
            full_response = partial_response + continuation
            
            # Cache the result
            result = {
                "full_response": full_response,
                "continuation": continuation,
                "model_used": model_name,
                "from_cache": False
            }
            self.continuation_cache[cache_key] = result
            
            logger.info(f"Generated continuation using {model_name} (+{len(continuation)} chars)")
            return result
            
        except Exception as e:
            logger.error(f"Continuation failed: {e}")
            return {
                "full_response": partial_response,
                "continuation": "",
                "model_used": model_name,
                "from_cache": False,
                "error": str(e)
            }
    
    def _build_continuation_prompt(self, partial_response: str) -> str:
        """Build a prompt for continuing a truncated response."""
        return f"""Continue this scene exactly where it left off:

Previous content:
{partial_response}

Continue naturally from where it ended, maintaining the same style and tone."""
```

### 5. Create Usage Tracking System

Implement a dedicated usage tracking system:

```python
# tracking/tracker.py
from typing import Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class TokenUsageTracker:
    """Tracks token usage per model."""
    
    def __init__(self):
        """Initialize token usage tracker."""
        self.usage = {}
        self.start_time = datetime.now()
    
    def track(self, model_name: str, prompt_tokens: int, 
             response_tokens: int, cost: float = 0.0) -> Dict[str, Any]:
        """Track token usage for a model."""
        if model_name not in self.usage:
            self.usage[model_name] = {
                "prompt_tokens": 0,
                "response_tokens": 0,
                "total_cost": 0.0,
                "requests": 0,
                "first_used": datetime.now().isoformat()
            }
        
        usage = self.usage[model_name]
        usage["prompt_tokens"] += prompt_tokens
        usage["response_tokens"] += response_tokens
        usage["total_cost"] += cost
        usage["requests"] += 1
        usage["last_used"] = datetime.now().isoformat()
        
        logger.info(f"Token usage: {model_name}: {prompt_tokens}+{response_tokens} tokens, ${cost:.4f}")
        
        return {
            "model": model_name,
            "prompt_tokens": prompt_tokens,
            "response_tokens": response_tokens,
            "cost": cost
        }
    
    def get_usage(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Get usage statistics."""
        if model_name:
            return self.usage.get(model_name, {
                "prompt_tokens": 0,
                "response_tokens": 0,
                "total_cost": 0.0,
                "requests": 0
            })
        
        total_stats = {
            "total_prompt_tokens": 0,
            "total_response_tokens": 0,
            "total_cost": 0.0,
            "total_requests": 0,
            "session_duration": (datetime.now() - self.start_time).total_seconds(),
            "models": self.usage.copy()
        }
        
        for model_stats in self.usage.values():
            total_stats["total_prompt_tokens"] += model_stats["prompt_tokens"]
            total_stats["total_response_tokens"] += model_stats["response_tokens"]
            total_stats["total_cost"] += model_stats["total_cost"]
            total_stats["total_requests"] += model_stats["requests"]
        
        return total_stats


# tracking/reporter.py
from typing import Dict, Any, List
from datetime import datetime
import json
from pathlib import Path

class UsageReporter:
    """Reports token usage statistics."""
    
    def __init__(self, tracker, output_dir: Optional[str] = None):
        """Initialize with a tracker and output directory."""
        self.tracker = tracker
        self.output_dir = Path(output_dir) if output_dir else None
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive usage report."""
        usage = self.tracker.get_usage()
        
        # Add derived metrics
        if usage["total_requests"] > 0:
            usage["avg_prompt_tokens_per_request"] = usage["total_prompt_tokens"] / usage["total_requests"]
            usage["avg_response_tokens_per_request"] = usage["total_response_tokens"] / usage["total_requests"]
            usage["avg_cost_per_request"] = usage["total_cost"] / usage["total_requests"]
        
        # Add timestamp
        usage["report_generated"] = datetime.now().isoformat()
        
        return usage
    
    def save_report(self, filename: Optional[str] = None) -> str:
        """Save usage report to file."""
        if not self.output_dir:
            raise ValueError("Output directory not set")
        
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"token_usage_{timestamp}.json"
        
        report = self.generate_report()
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        
        return str(output_path)
    
    def get_model_comparison(self) -> List[Dict[str, Any]]:
        """Compare usage across models."""
        usage = self.tracker.get_usage()
        models_data = []
        
        for model_name, stats in usage["models"].items():
            if stats["requests"] > 0:
                models_data.append({
                    "name": model_name,
                    "requests": stats["requests"],
                    "total_tokens": stats["prompt_tokens"] + stats["response_tokens"],
                    "total_cost": stats["total_cost"],
                    "avg_cost_per_request": stats["total_cost"] / stats["requests"],
                    "avg_tokens_per_request": (stats["prompt_tokens"] + stats["response_tokens"]) / stats["requests"]
                })
        
        # Sort by usage
        models_data.sort(key=lambda x: x["requests"], reverse=True)
        return models_data
```

### 6. Create Context Trimming Utility

Implement a dedicated context trimming utility:

```python
# utils/context_trimmer.py
from typing import Dict, Any, List, Optional
import logging
from ..estimators import TokenEstimator

logger = logging.getLogger(__name__)

class ContextTrimmer:
    """Trims context parts to fit within token limits."""
    
    def __init__(self, estimator: TokenEstimator):
        """Initialize with a token estimator."""
        self.estimator = estimator
    
    def trim_to_fit(self, context_parts: Dict[str, str], 
                   target_tokens: int) -> Dict[str, Any]:
        """Trim context parts to fit within token limits."""
        original_parts = context_parts.copy()
        
        # Calculate current token usage
        token_counts = {}
        total_tokens = 0
        
        for part_name, content in context_parts.items():
            tokens = self.estimator.estimate_tokens(content)
            token_counts[part_name] = tokens
            total_tokens += tokens
        
        if total_tokens <= target_tokens:
            return {
                "trimmed": False,
                "parts": context_parts,
                "token_counts": token_counts,
                "total_tokens": total_tokens
            }
        
        # Priority order for trimming (lower priority gets trimmed first)
        priority_order = {
            "recent_scenes": 1,
            "style": 2,
            "memory": 3,
            "canon": 4,
            "system": 5  # Highest priority, trim last
        }
        
        # Sort parts by priority
        sorted_parts = sorted(
            context_parts.keys(),
            key=lambda x: priority_order.get(x, 0)
        )
        
        # Apply progressive trimming
        trimmed_parts = original_parts.copy()
        trimmed_token_counts = token_counts.copy()
        trimming_applied = {}
        
        for part_name in sorted_parts:
            if total_tokens <= target_tokens:
                break
                
            original_text = trimmed_parts[part_name]
            original_tokens = trimmed_token_counts[part_name]
            
            # Start with modest trim, increase if needed
            for trim_ratio in [0.9, 0.75, 0.5, 0.25]:
                if total_tokens <= target_tokens:
                    break
                    
                trimmed_length = int(len(original_text) * trim_ratio)
                if trimmed_length < 10:  # Don't trim too much
                    continue
                    
                trimmed_parts[part_name] = original_text[:trimmed_length] + "..."
                new_tokens = self.estimator.estimate_tokens(trimmed_parts[part_name])
                
                # Update counts
                token_reduction = original_tokens - new_tokens
                total_tokens -= token_reduction
                trimmed_token_counts[part_name] = new_tokens
                
                trimming_applied[part_name] = {
                    "original_tokens": original_tokens,
                    "new_tokens": new_tokens,
                    "reduction": token_reduction,
                    "trim_ratio": trim_ratio
                }
                
                logger.info(f"Trimmed {part_name}: {original_tokens} -> {new_tokens} tokens")
        
        return {
            "trimmed": bool(trimming_applied),
            "parts": trimmed_parts,
            "token_counts": trimmed_token_counts,
            "total_tokens": total_tokens,
            "trimming_applied": trimming_applied,
            "original_tokens": sum(token_counts.values())
        }
```

### 7. Refine Main Manager Class

Implement a main manager class to coordinate between components:

```python
# manager.py
from typing import Dict, Any, Optional, List
import logging

from .estimators import EstimatorFactory, TokenEstimator
from .selectors.selector import ModelSelector
from .continuations.detector import TruncationDetector
from .continuations.generator import ContinuationGenerator
from .tracking.tracker import TokenUsageTracker
from .tracking.reporter import UsageReporter
from .utils.context_trimmer import ContextTrimmer

logger = logging.getLogger(__name__)

class TokenManager:
    """Manages token usage and model selection."""
    
    def __init__(self, model_manager):
        """Initialize token manager."""
        self.model_manager = model_manager
        
        # Initialize components
        self.estimator_factory = EstimatorFactory()
        self.estimators = {}
        self.model_selector = ModelSelector(model_manager)
        self.truncation_detector = TruncationDetector()
        self.continuation_generator = ContinuationGenerator(model_manager, self.model_selector)
        self.token_tracker = TokenUsageTracker()
        self.usage_reporter = UsageReporter(self.token_tracker)
    
    def _get_estimator(self, model_name: str) -> TokenEstimator:
        """Get or create token estimator for a model."""
        if model_name not in self.estimators:
            model_config = self.model_manager.get_adapter_info(model_name)
            provider = model_config.get("provider", "").lower()
            model_type = model_config.get("model_name", model_name)
            
            self.estimators[model_name] = self.estimator_factory.create_estimator(
                provider, model_type)
        
        return self.estimators[model_name]
    
    def estimate_tokens(self, text: str, model_name: str) -> int:
        """Estimate token count for given text and model."""
        estimator = self._get_estimator(model_name)
        return estimator.estimate_tokens(text)
    
    def select_optimal_model(self, prompt_length: int, response_length: int, 
                           optimization_goal: str = "cost") -> Optional[str]:
        """Select the best model based on token requirements."""
        return self.model_selector.select_for_token_count(
            prompt_length, response_length, optimization_goal)
    
    def check_truncation_risk(self, prompt: str, model_name: str, 
                            response_tokens: int = 2048) -> Dict[str, Any]:
        """Check if the prompt + response might exceed model limits."""
        prompt_tokens = self.estimate_tokens(prompt, model_name)
        
        capacity = self.model_selector.check_capacity(
            model_name, prompt_tokens, response_tokens)
        
        return {
            "at_risk": not capacity["has_capacity"],
            "prompt_tokens": prompt_tokens,
            "response_tokens": response_tokens,
            "capacity": capacity
        }
    
    def trim_context(self, context_parts: Dict[str, str], 
                    target_tokens: int, model_name: str) -> Dict[str, Any]:
        """Trim context parts to fit within token limits."""
        estimator = self._get_estimator(model_name)
        trimmer = ContextTrimmer(estimator)
        
        return trimmer.trim_to_fit(context_parts, target_tokens)
    
    def detect_truncation(self, response: str) -> Dict[str, Any]:
        """Detect if a response was likely truncated."""
        return self.truncation_detector.is_truncated(response)
    
    async def continue_scene(self, original_prompt: str, partial_response: str,
                          story_id: str, model_name: str) -> str:
        """Continue a truncated scene."""
        result = await self.continuation_generator.continue_response(
            original_prompt, partial_response, story_id, model_name)
        
        return result["full_response"]
    
    def track_usage(self, model_name: str, prompt_tokens: int,
                  response_tokens: int, cost: float = 0.0) -> Dict[str, Any]:
        """Track token usage."""
        return self.token_tracker.track(model_name, prompt_tokens, response_tokens, cost)
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get token usage statistics."""
        return self.token_tracker.get_usage()
    
    def generate_usage_report(self) -> Dict[str, Any]:
        """Generate usage report."""
        return self.usage_reporter.generate_report()
    
    def recommend_model_switch(self, current_model: str, 
                             usage_pattern: Dict[str, Any]) -> Optional[str]:
        """Recommend model switching based on usage patterns."""
        return self.model_selector.recommend_switch(current_model, usage_pattern)
```

### 8. Create Public API

Provide a clean public API:

```python
# __init__.py
from .manager import TokenManager

# Factory function
def create_token_manager(model_manager):
    """Create a token manager."""
    return TokenManager(model_manager)

# Re-export key classes
from .estimators import TokenEstimator, EstimatorFactory
from .selectors.selector import ModelSelector
from .continuations.detector import TruncationDetector
from .continuations.generator import ContinuationGenerator
from .tracking.tracker import TokenUsageTracker
from .tracking.reporter import UsageReporter
from .utils.context_trimmer import ContextTrimmer

# Constants
DEFAULT_BUFFER_RATIO = 0.2
DEFAULT_CONTINUATION_MAX_TOKENS = 1024
```

## Implementation Strategy

1. **Create Package Structure**: Set up the directory and file structure
2. **Implement Estimator Components**: Create the token estimation strategy pattern
3. **Implement Selector Components**: Create the model selection system
4. **Implement Continuation Components**: Create the continuation detection and generation system
5. **Implement Tracking Components**: Create the token usage tracking system
6. **Implement Utility Components**: Create the context trimming utility
7. **Implement Main Manager**: Create the main token manager class
8. **Implement Public API**: Provide a clean public API

## Benefits of Refactoring

1. **Improved Organization**: Clear separation of concerns with specialized components
2. **Enhanced Testability**: Components can be tested in isolation
3. **Better Error Handling**: More robust error handling throughout the system
4. **Improved Extensibility**: Easy to add new estimators, selectors, or tracking mechanisms
5. **Better Configurability**: Configuration options instead of hardcoded values
6. **Better Caching**: More sophisticated caching mechanisms
7. **Clear Interfaces**: Well-defined interfaces between components

## Migration Plan

1. **Incremental Refactoring**: Create the new package structure alongside the existing file
2. **Component-by-Component Implementation**: Implement and test each component independently
3. **Backward Compatibility Layer**: Ensure existing code continues to work during migration
4. **Integration Testing**: Test the complete system with the new components
5. **Final Cleanup**: Remove the original file once all dependencies are updated

By following this refactoring plan, the token_manager.py module will be transformed into a well-structured, maintainable package that adheres to modern Python best practices while preserving all existing functionality.
