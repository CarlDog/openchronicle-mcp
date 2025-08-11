"""
Provider adapters following OpenChronicle naming conventions.

This package contains individual provider implementations that demonstrate
the power of the template method pattern. Each adapter is reduced from
100+ lines to 30-40 lines of provider-specific logic.

Available Providers:
- openai_adapter.py: OpenAI GPT models
- anthropic_adapter.py: Anthropic Claude models
- ollama_adapter.py: Local Ollama models

All providers follow the same interface defined by BaseAPIAdapter,
ensuring consistency and maintainability across the entire system.
"""

from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter
from .ollama_adapter import OllamaAdapter

__all__ = [
    "OpenAIAdapter",
    "AnthropicAdapter",
    "OllamaAdapter",
]
