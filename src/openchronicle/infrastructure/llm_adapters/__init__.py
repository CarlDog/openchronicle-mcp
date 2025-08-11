"""
Model adapters package.

Consolidated adapter system following OpenChronicle organizational standards.
This package provides a clean, modular approach to AI model integration with
registry-based configuration and the template method pattern.

Key Components:
- api_adapter_base.py: Base adapter classes with template method pattern
- adapter_factory.py: Unified factory for adapter creation
- adapter_exceptions.py: Comprehensive exception hierarchy
- providers/: Individual provider implementations

Features:
- 90% code duplication reduction through template method pattern
- Registry-integrated configuration management
- Clean error handling and logging
- Fallback chain support
- Consistent naming convention following OpenChronicle standards
"""

from .api_adapter_base import BaseAPIAdapter, LocalModelAdapter
from .adapter_factory import AdapterFactory
from .adapter_exceptions import (
    AdapterError,
    AdapterNotFoundError,
    AdapterInitializationError,
    AdapterConfigurationError,
    AdapterConnectionError,
    AdapterResponseError,
    AdapterTimeoutError,
    AdapterRateLimitError,
)

# Provider imports
from .providers.openai_adapter import OpenAIAdapter
from .providers.anthropic_adapter import AnthropicAdapter
from .providers.ollama_adapter import OllamaAdapter

__all__ = [
    # Base classes
    "BaseAPIAdapter",
    "LocalModelAdapter",
    # Factory
    "AdapterFactory",
    # Exceptions
    "AdapterError",
    "AdapterNotFoundError",
    "AdapterInitializationError",
    "AdapterConfigurationError",
    "AdapterConnectionError",
    "AdapterResponseError",
    "AdapterTimeoutError",
    "AdapterRateLimitError",
    # Provider adapters
    "OpenAIAdapter",
    "AnthropicAdapter",
    "OllamaAdapter",
]

# Version info
__version__ = "2.0.0"
__author__ = "OpenChronicle Development Team"
