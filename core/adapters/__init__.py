"""
Adapter package for AI model providers.

This package provides a clean, modular architecture for AI model adapters,
eliminating the massive code duplication from the original monolithic model_adapter.py.

Each provider adapter is now ~20-30 lines instead of ~100 lines through the use
of template method pattern and inheritance from BaseAPIAdapter.
"""

from .base import ModelAdapter, BaseAPIAdapter, ImageAdapter
from .exceptions import AdapterError, AdapterNotFoundError, AdapterInitializationError

# Provider adapters will be imported here once implemented
# from .providers.openai import OpenAIAdapter
# from .providers.ollama import OllamaAdapter
# from .providers.anthropic import AnthropicAdapter

__all__ = [
    # Base classes
    'ModelAdapter',
    'BaseAPIAdapter', 
    'ImageAdapter',
    
    # Exceptions
    'AdapterError',
    'AdapterNotFoundError',
    'AdapterInitializationError',
    
    # Provider adapters (to be added)
    # 'OpenAIAdapter',
    # 'OllamaAdapter',
    # 'AnthropicAdapter',
]
