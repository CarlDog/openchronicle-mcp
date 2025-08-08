"""
Token Management - Optimization Component

Extracted from token_manager.py
Handles token optimization, model selection, and context trimming.
"""

from typing import Dict, List, Optional, Any
import os
import sys
from pathlib import Path

# Import logging system with fallback
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'utilities'))
try:
    from logging_system import log_warning, log_error, log_info
except ImportError:
    # Fallback for testing or when logging_system is not available
    def log_warning(message): print(f"WARNING: {message}")
    def log_error(message): print(f"ERROR: {message}")
    def log_info(message): print(f"INFO: {message}")

from ..shared import TokenOptimizationResult, TokenManagerException, ErrorHandler
from .tokenizer_manager import TokenizerManager, TokenEstimator


class ModelSelector:
    """Selects optimal models based on token requirements."""
    
    def __init__(self, model_manager, tokenizer_manager: TokenizerManager):
        self.model_manager = model_manager
        self.tokenizer_manager = tokenizer_manager
    
    def select_optimal_model_for_length(self, prompt_length: int, response_length: int) -> Optional[str]:
        """Select the best model based on token requirements."""
        total_tokens = prompt_length + response_length
        
        # Get all available models and their token limits
        try:
            models = self.model_manager.list_model_configs()
        except Exception as e:
            log_error(f"Failed to get model configs: {e}")
            return None
            
        suitable_models = []
        
        for model_name, config in models.items():
            if not config.get("enabled", True):
                continue
                
            max_tokens = config.get("max_tokens", 4096)
            if total_tokens <= max_tokens * 0.8:  # Leave 20% buffer
                suitable_models.append({
                    "name": model_name,
                    "max_tokens": max_tokens,
                    "cost": config.get("cost_per_token", 0.001),
                    "provider": config.get("provider", "unknown")
                })
        
        if not suitable_models:
            log_warning(f"No models can handle {total_tokens} tokens")
            return None
            
        # Sort by cost efficiency, then by token capacity
        suitable_models.sort(key=lambda x: (x["cost"], -x["max_tokens"]))
        
        selected = suitable_models[0]["name"]
        log_info(f"Selected model {selected} for {total_tokens} tokens")
        return selected
    
    def select_optimal_model(self, token_count: int, requirements: Dict[str, Any]) -> str:
        """Select optimal model based on token count and requirements."""
        # Estimate response length (default to 25% of token count)
        response_length = requirements.get('response_length', token_count // 4)
        
        # Use existing method for selection
        optimal = self.select_optimal_model_for_length(token_count, response_length)
        
        # If no model found, return a default
        if optimal is None:
            log_warning(f"No optimal model found for {token_count} tokens, using default")
            return "gpt-3.5-turbo"  # Fallback default
        
        return optimal
    
    def get_model_capabilities(self, model_name: str) -> Dict[str, Any]:
        """Get detailed capabilities for a model."""
        try:
            config = self.model_manager.get_adapter_info(model_name)
            return {
                'max_tokens': config.get('max_tokens', 4096),
                'cost_per_token': config.get('cost_per_token', 0.001),
                'provider': config.get('provider', 'unknown'),
                'supports_streaming': config.get('supports_streaming', False),
                'supports_functions': config.get('supports_functions', False)
            }
        except Exception as e:
            log_error(f"Failed to get capabilities for {model_name}: {e}")
            return {}
    
    def recommend_model_upgrade(self, current_model: str, required_tokens: int) -> Optional[str]:
        """Recommend a better model for higher token requirements."""
        current_caps = self.get_model_capabilities(current_model)
        current_limit = current_caps.get('max_tokens', 4096)
        
        if required_tokens <= current_limit:
            return None  # Current model is sufficient
        
        # Find models with higher limits
        try:
            models = self.model_manager.list_model_configs()
        except Exception:
            return None
        
        better_models = []
        for model_name, config in models.items():
            if not config.get("enabled", True):
                continue
            
            model_limit = config.get("max_tokens", 4096)
            if model_limit > current_limit and required_tokens <= model_limit * 0.8:
                better_models.append({
                    "name": model_name,
                    "max_tokens": model_limit,
                    "cost": config.get("cost_per_token", 0.001)
                })
        
        if not better_models:
            return None
        
        # Return the most cost-effective upgrade
        better_models.sort(key=lambda x: x["cost"])
        return better_models[0]["name"]


class ContextTrimmer:
    """Handles intelligent context trimming."""
    
    def __init__(self, tokenizer_manager: TokenizerManager):
        self.tokenizer_manager = tokenizer_manager
        self.trim_strategies = {
            'proportional': self._trim_proportional,
            'priority': self._trim_by_priority,
            'smart': self._trim_smart
        }
    
    def trim_context_intelligently(self, context_parts: Dict[str, str], 
                                  target_tokens: int, model_name: str,
                                  provider: Optional[str] = None,
                                  strategy: str = 'smart') -> Dict[str, str]:
        """Trim context parts to fit within token limits."""
        current_tokens = sum(
            self.tokenizer_manager.estimate_tokens(part, model_name, provider) 
            for part in context_parts.values()
        )
        
        if current_tokens <= target_tokens:
            return context_parts
        
        trimmer = self.trim_strategies.get(strategy, self._trim_smart)
        return trimmer(context_parts, target_tokens, model_name, provider)
    
    def _trim_by_priority(self, context_parts: Dict[str, str], target_tokens: int, 
                         model_name: str, provider: Optional[str] = None) -> Dict[str, str]:
        """Trim context based on priority order."""
        # Priority order for trimming (keep most important)
        trim_order = ["canon", "memory", "style", "recent_scenes", "background", "notes"]
        trimmed_parts = context_parts.copy()
        
        current_tokens = sum(
            self.tokenizer_manager.estimate_tokens(part, model_name, provider) 
            for part in trimmed_parts.values()
        )
        
        for part_name in trim_order:
            if part_name in trimmed_parts and current_tokens > target_tokens:
                original_text = trimmed_parts[part_name]
                original_tokens = self.tokenizer_manager.estimate_tokens(original_text, model_name, provider)
                
                # Trim to 70% of original length
                trim_ratio = 0.7
                trimmed_length = int(len(original_text) * trim_ratio)
                trimmed_parts[part_name] = original_text[:trimmed_length] + "..."
                
                new_tokens = self.tokenizer_manager.estimate_tokens(trimmed_parts[part_name], model_name, provider)
                current_tokens = current_tokens - original_tokens + new_tokens
                
                log_info(f"Trimmed {part_name}: {original_tokens} -> {new_tokens} tokens")
                
                if current_tokens <= target_tokens:
                    break
        
        return trimmed_parts
    
    def _trim_proportional(self, context_parts: Dict[str, str], target_tokens: int,
                          model_name: str, provider: Optional[str] = None) -> Dict[str, str]:
        """Trim all parts proportionally."""
        current_tokens = sum(
            self.tokenizer_manager.estimate_tokens(part, model_name, provider) 
            for part in context_parts.values()
        )
        
        if current_tokens <= target_tokens:
            return context_parts
        
        # Calculate reduction ratio
        reduction_ratio = target_tokens / current_tokens
        
        trimmed_parts = {}
        for part_name, part_text in context_parts.items():
            new_length = int(len(part_text) * reduction_ratio)
            trimmed_parts[part_name] = part_text[:new_length] if new_length < len(part_text) else part_text
        
        return trimmed_parts
    
    def _trim_smart(self, context_parts: Dict[str, str], target_tokens: int,
                   model_name: str, provider: Optional[str] = None) -> Dict[str, str]:
        """Smart trimming that preserves important content."""
        # Combine priority-based and proportional strategies
        # First try priority trimming
        result = self._trim_by_priority(context_parts, target_tokens, model_name, provider)
        
        # If still over limit, apply proportional trimming
        current_tokens = sum(
            self.tokenizer_manager.estimate_tokens(part, model_name, provider) 
            for part in result.values()
        )
        
        if current_tokens > target_tokens:
            result = self._trim_proportional(result, target_tokens, model_name, provider)
        
        return result


class TruncationDetector:
    """Detects and handles response truncation."""
    
    def detect_truncation(self, response: str) -> bool:
        """Detect if a response was likely truncated."""
        if not response or len(response) < 10:
            return False
        
        # Check for common truncation indicators
        truncation_indicators = [
            # Incomplete sentences
            response.endswith((' ', '  ', ',')),
            # Unfinished quotes
            response.count('"') % 2 == 1,
            response.count("'") % 2 == 1,
            # Incomplete brackets/parentheses
            response.count('(') != response.count(')'),
            response.count('[') != response.count(']'),
            response.count('{') != response.count('}'),
            # Abrupt ending
            len(response) > 100 and not response.strip().endswith(('.', '!', '?', '"', "'"))
        ]
        
        return any(truncation_indicators)
    
    def check_truncation_risk(self, prompt: str, model_name: str, 
                             max_response_tokens: int = 2048,
                             provider: Optional[str] = None,
                             tokenizer_manager: Optional[TokenizerManager] = None) -> bool:
        """Check if the prompt + response might exceed model limits."""
        if not tokenizer_manager:
            return False
        
        prompt_tokens = tokenizer_manager.estimate_tokens(prompt, model_name, provider)
        
        # Estimate model limits (fallback if not available)
        try:
            # This would need to be passed in or accessed differently
            max_tokens = 4096  # Default fallback
        except Exception:
            max_tokens = 4096
        
        total_needed = prompt_tokens + max_response_tokens
        return total_needed > max_tokens * 0.9  # 90% threshold
    
    def suggest_truncation_fixes(self, response: str, truncation_type: str = "auto") -> List[str]:
        """Suggest ways to fix truncated responses."""
        suggestions = []
        
        if self.detect_truncation(response):
            suggestions.append("Response appears truncated")
            suggestions.append("Consider using model with higher token limit")
            suggestions.append("Reduce prompt length to allow more response tokens")
            
            if response.count('"') % 2 == 1:
                suggestions.append("Incomplete quote detected - may need continuation")
            
            if not response.strip().endswith(('.', '!', '?', '"', "'")):
                suggestions.append("Response ends abruptly - likely needs continuation")
        
        return suggestions
