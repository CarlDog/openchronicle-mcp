"""
Token Management - Tokenizer Component

Extracted from token_manager.py
Handles tokenizer management and token estimation for different models.
"""

import tiktoken
from typing import Dict, Optional
import os
import sys
from pathlib import Path

# Import logging system with fallback for missing module
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'utilities'))
try:
    from logging_system import log_warning, log_error
except ImportError:
    # Fallback for testing or when logging_system is not available
    def log_warning(message): print(f"WARNING: {message}")
    def log_error(message): print(f"ERROR: {message}")

from ..shared import TokenManagerException, ErrorHandler


class TokenizerManager:
    """Manages tokenizers for different models."""
    
    def __init__(self, default_model: Optional[str] = None, cache_size: int = 1000):
        self.default_model = default_model or "gpt-3.5-turbo"
        self.cache_size = cache_size
        self.encoders = {}
        self.model_fallbacks = {
            'openai': 'cl100k_base',
            'anthropic': 'cl100k_base', 
            'groq': 'cl100k_base',
            'default': 'cl100k_base'
        }
    
    def get_tokenizer(self, model_name: str, provider: Optional[str] = None):
        """Get tokenizer for a specific model."""
        if model_name not in self.encoders:
            try:
                # Try to get model-specific tokenizer
                if provider and provider.lower() == "openai":
                    self.encoders[model_name] = tiktoken.encoding_for_model(model_name)
                elif provider and provider.lower() == "anthropic":
                    # Use claude tokenizer approximation
                    self.encoders[model_name] = tiktoken.get_encoding("cl100k_base")
                else:
                    # Fallback to general tokenizer
                    fallback_encoding = self.model_fallbacks.get(
                        provider.lower() if provider else 'default', 
                        'cl100k_base'
                    )
                    self.encoders[model_name] = tiktoken.get_encoding(fallback_encoding)
                    
            except Exception as e:
                log_warning(f"Failed to get tokenizer for {model_name}: {e}")
                self.encoders[model_name] = tiktoken.get_encoding("cl100k_base")
                
        return self.encoders[model_name]
    
    def estimate_tokens(self, text: str, model_name: str, provider: Optional[str] = None) -> int:
        """Estimate token count for given text and model."""
        try:
            tokenizer = self.get_tokenizer(model_name, provider)
            return len(tokenizer.encode(text))
        except Exception as e:
            log_error(f"Token estimation failed for {model_name}: {e}")
            # Fallback estimation: ~4 chars per token
            return len(text) // 4
    
    def estimate_tokens_batch(self, texts: list[str], model_name: str, provider: Optional[str] = None) -> list[int]:
        """Estimate token counts for multiple texts."""
        try:
            tokenizer = self.get_tokenizer(model_name, provider)
            return [len(tokenizer.encode(text)) for text in texts]
        except Exception as e:
            log_error(f"Batch token estimation failed for {model_name}: {e}")
            # Fallback estimation
            return [len(text) // 4 for text in texts]
    
    def clear_cache(self):
        """Clear tokenizer cache."""
        self.encoders.clear()
    
    def get_cached_models(self) -> list[str]:
        """Get list of models with cached tokenizers."""
        return list(self.encoders.keys())


class TokenEstimator:
    """Provides token estimation utilities."""
    
    def __init__(self, tokenizer_manager: TokenizerManager):
        self.tokenizer_manager = tokenizer_manager
    
    def estimate_response_tokens(self, prompt: str, model_name: str, 
                                provider: Optional[str] = None,
                                response_ratio: float = 0.3) -> int:
        """Estimate likely response token count based on prompt."""
        prompt_tokens = self.tokenizer_manager.estimate_tokens(prompt, model_name, provider)
        
        # Estimate response based on prompt length and typical ratios
        base_estimate = int(prompt_tokens * response_ratio)
        
        # Minimum reasonable response
        min_response = 50
        
        # Maximum reasonable response (avoid runaway generation)
        max_response = 2048
        
        return max(min_response, min(base_estimate, max_response))
    
    def estimate_continuation_tokens(self, original_text: str, partial_response: str,
                                   model_name: str, provider: Optional[str] = None) -> int:
        """Estimate tokens needed to continue a partial response."""
        partial_tokens = self.tokenizer_manager.estimate_tokens(partial_response, model_name, provider)
        
        # Estimate remaining tokens needed (typically 20-50% more)
        continuation_ratio = 0.35
        estimated_remaining = int(partial_tokens * continuation_ratio)
        
        # Reasonable bounds
        min_continuation = 20
        max_continuation = 1024
        
        return max(min_continuation, min(estimated_remaining, max_continuation))
    
    def estimate_context_budget(self, total_limit: int, response_tokens: int, 
                              buffer_ratio: float = 0.1) -> int:
        """Calculate available tokens for context given response requirements."""
        buffer_tokens = int(total_limit * buffer_ratio)
        available_for_context = total_limit - response_tokens - buffer_tokens
        
        return max(0, available_for_context)
    
    def check_text_fits_limit(self, text: str, model_name: str, token_limit: int,
                             provider: Optional[str] = None) -> bool:
        """Check if text fits within token limit."""
        estimated_tokens = self.tokenizer_manager.estimate_tokens(text, model_name, provider)
        return estimated_tokens <= token_limit
