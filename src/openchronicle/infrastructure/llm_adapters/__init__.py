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

from .adapter_exceptions import AdapterConfigurationError
from .adapter_exceptions import AdapterConnectionError
from .adapter_exceptions import AdapterError
from .adapter_exceptions import AdapterInitializationError
from .adapter_exceptions import AdapterNotFoundError
from .adapter_exceptions import AdapterRateLimitError
from .adapter_exceptions import AdapterResponseError
from .adapter_exceptions import AdapterTimeoutError
from .adapter_factory import AdapterFactory
from .api_adapter_base import BaseAPIAdapter
from .api_adapter_base import LocalModelAdapter
from .providers.anthropic_adapter import AnthropicAdapter
from .providers.ollama_adapter import OllamaAdapter

# Provider imports
from .providers.openai_adapter import OpenAIAdapter


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
