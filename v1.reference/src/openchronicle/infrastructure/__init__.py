"""
OpenChronicle Infrastructure Layer.

This layer contains concrete implementations of the interfaces defined in the
application layer. It handles external systems, data persistence, caching,
and integrations with third-party services.

The infrastructure layer:
- Implements repository interfaces for data persistence
- Provides LLM adapter implementations for various providers
- Manages caching strategies for performance optimization
- Handles database connections and session management
- Integrates with external APIs and services

Key Components:
- Repositories: Concrete data persistence implementations
- Adapters: LLM provider integrations (OpenAI, Anthropic, Ollama, etc.)
- Cache: Performance optimization with various caching strategies
- Database: Connection management and schema definitions
- Memory: Domain state management (neutral terminology)

Architecture Principles:
- Dependency Inversion: Implements interfaces from application layer
- Plugin Architecture: Easy to add new providers and storage backends
- Configuration-Driven: Flexible setup through configuration files
- Performance-Focused: Caching and optimization built-in
"""

import warnings
from typing import Optional

from openchronicle.shared.exceptions import ApplicationError
from openchronicle.shared.exceptions import ConfigurationError
from openchronicle.shared.exceptions import InfrastructureError
from openchronicle.shared.exceptions import ModelError

from .adapters import AnthropicAdapter
from .adapters import BaseModelAdapter
from .adapters import MockModelAdapter
from .adapters import ModelConfig
from .adapters import ModelManagementAdapter
from .adapters import OllamaAdapter
from .adapters import OpenAIAdapter
from .adapters import create_adapter
from .cache import BaseCache
from .cache import CacheEntry
from .cache import FileSystemCache
from .cache import InMemoryCache
from .cache import ModelResponseCache
from .cache import create_cache
from .memory import MemoryOrchestrator


# Note: Domain-specific repositories are implemented in plugins; core remains neutral.


class InfrastructureConfig:
    """Configuration class for infrastructure components."""

    def __init__(
        self,
        storage_backend: str = "filesystem",
        storage_path: str = "storage",
        cache_type: str = "memory",
        cache_config: Optional[dict] = None,
        model_configs: Optional[dict] = None,
        database_url: Optional[str] = None,
    ):
        self.storage_backend = storage_backend
        self.storage_path = storage_path
        self.cache_type = cache_type
        self.cache_config = cache_config or {}
        self.model_configs = model_configs or {}
        self.database_url = database_url


class InfrastructureContainer:
    """
    Dependency injection container for infrastructure components.

    This class provides a centralized way to configure and access
    all infrastructure implementations. It acts as a factory and
    registry for repositories, adapters, and services.
    """

    def __init__(self, config: InfrastructureConfig):
        self.config = config
        self._repositories = {}
        self._adapters = {}
        self._cache = None
        self._memory_manager = None
        self._model_manager = None

    # Repository factories
    def get_story_repository(self):
        """
        DEPRECATED: Domain repositories moved to plugins.

            Core no longer provides or imports plugin repositories. Resolve the
            repository via the plugin container/DI and call it directly.
        """
        warnings.warn(
            "get_story_repository is deprecated and removed from core. Use the appropriate domain plugin via DI.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise ImportError(
            "Core no longer exposes domain repositories. Use the appropriate domain plugin adapter via DI."
        )

    def get_character_repository(self):
        """
        DEPRECATED: Domain-specific repositories moved to plugins.
        """
        warnings.warn(
            "get_character_repository is deprecated and removed from core. Use the appropriate domain plugin via DI.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise ImportError(
            "Core no longer exposes domain-specific repositories. Use the appropriate domain plugin adapter via DI."
        )

    def get_scene_repository(self):
        """
        DEPRECATED: Domain-specific repositories moved to plugins.
        """
        warnings.warn(
            "get_scene_repository is deprecated and removed from core. Use the appropriate domain plugin via DI.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise ImportError(
            "Core no longer exposes domain-specific repositories. Use the appropriate domain plugin adapter via DI."
        )

    # Memory manager factory
    def get_memory_manager(self):
        """Get memory manager instance."""
        if self._memory_manager is None:
            # Always use MemoryOrchestrator as the main memory interface
            self._memory_manager = MemoryOrchestrator()

        return self._memory_manager

    # Cache factory
    def get_cache(self):
        """Get cache instance."""
        if self._cache is None:
            self._cache = create_cache(self.config.cache_type, **self.config.cache_config)

        return self._cache

    def get_model_response_cache(self):
        """Get specialized model response cache."""
        base_cache = self.get_cache()
        return ModelResponseCache(base_cache)

    # Model manager factory
    def get_model_manager(self):
        """Get model manager instance."""
        if self._model_manager is None:
            self._model_manager = ModelManagementAdapter()

            # Register adapters from configuration
            for name, adapter_config in self.config.model_configs.items():
                try:
                    model_config = ModelConfig(**adapter_config)
                    adapter = create_adapter(model_config.provider, model_config)
                    self._model_manager.register_adapter(name, adapter)
                except (ModelError, ConfigurationError) as e:
                    print(f"Configuration error registering adapter {name}: {e}")
                except (AttributeError, KeyError) as e:
                    print(f"Data structure error registering adapter {name}: {e}")
                except Exception as e:
                    print(f"Unexpected error registering adapter {name}: {e}")
                    # Consider logging the full traceback for debugging

        return self._model_manager

    # Adapter management
    def register_model_adapter(self, name: str, provider: str, config: dict):
        """Register a new model adapter."""
        model_config = ModelConfig(name=name, provider=provider, **config)
        adapter = create_adapter(provider, model_config)

        model_manager = self.get_model_manager()
        model_manager.register_adapter(name, adapter)

    def get_model_adapter(self, name: str):
        """Get specific model adapter."""
        model_manager = self.get_model_manager()
        return model_manager.adapters.get(name)

    # Health checks
    async def health_check(self) -> dict:
        """Perform health checks on all infrastructure components."""
        results = {"timestamp": "current", "status": "healthy", "components": {}}

        try:
            # Test repositories
            story_repo = self.get_story_repository()
            results["components"]["story_repository"] = {
                "status": "healthy",
                "type": type(story_repo).__name__,
            }
        except (InfrastructureError, ApplicationError) as e:
            results["components"]["story_repository"] = {
                "status": "unhealthy",
                "error": f"Infrastructure error: {str(e)}",
            }
            results["status"] = "degraded"
        except (AttributeError, KeyError) as e:
            results["components"]["story_repository"] = {
                "status": "unhealthy",
                "error": f"Data structure error: {str(e)}",
            }
            results["status"] = "degraded"
        except Exception as e:
            results["components"]["story_repository"] = {
                "status": "unhealthy",
                "error": f"Unexpected error: {str(e)}",
            }
            results["status"] = "degraded"

        try:
            # Test memory manager
            memory_manager = self.get_memory_manager()
            results["components"]["memory_manager"] = {
                "status": "healthy",
                "type": type(memory_manager).__name__,
            }
        except (InfrastructureError, ApplicationError) as e:
            results["components"]["memory_manager"] = {
                "status": "unhealthy",
                "error": f"Infrastructure error: {str(e)}",
            }
            results["status"] = "degraded"
        except (AttributeError, KeyError) as e:
            results["components"]["memory_manager"] = {
                "status": "unhealthy",
                "error": f"Data structure error: {str(e)}",
            }
            results["status"] = "degraded"
        except Exception as e:
            results["components"]["memory_manager"] = {
                "status": "unhealthy",
                "error": f"Unexpected error: {str(e)}",
            }
            results["status"] = "degraded"

        try:
            # Test cache
            cache = self.get_cache()
            await cache.set("health_check", "test", ttl=1)
            cached_value = await cache.get("health_check")

            results["components"]["cache"] = {
                "status": "healthy" if cached_value == "test" else "degraded",
                "type": type(cache).__name__,
            }
        except (InfrastructureError, ApplicationError) as e:
            results["components"]["cache"] = {"status": "unhealthy", "error": f"Infrastructure error: {str(e)}"}
            results["status"] = "degraded"
        except (AttributeError, KeyError) as e:
            results["components"]["cache"] = {"status": "unhealthy", "error": f"Data structure error: {str(e)}"}
            results["status"] = "degraded"
        except Exception as e:
            results["components"]["cache"] = {"status": "unhealthy", "error": f"Unexpected error: {str(e)}"}
            results["status"] = "degraded"

        try:
            # Test model manager
            model_manager = self.get_model_manager()
            adapter_count = len(model_manager.adapters)

            results["components"]["model_manager"] = {
                "status": "healthy",
                "adapter_count": adapter_count,
                "available_models": list(model_manager.adapters.keys()),
            }
        except (InfrastructureError, ModelError) as e:
            results["components"]["model_manager"] = {
                "status": "unhealthy",
                "error": f"Infrastructure/Model error: {str(e)}",
            }
            results["status"] = "degraded"
        except (AttributeError, KeyError) as e:
            results["components"]["model_manager"] = {
                "status": "unhealthy",
                "error": f"Data structure error: {str(e)}",
            }
            results["status"] = "degraded"
        except Exception as e:
            results["components"]["model_manager"] = {
                "status": "unhealthy",
                "error": f"Unexpected error: {str(e)}",
            }
            results["status"] = "degraded"

        return results


# Factory function for easy setup
def create_infrastructure(
    storage_backend: str = "filesystem",
    storage_path: str = "storage",
    cache_type: str = "memory",
    model_configs: Optional[dict] = None,
) -> InfrastructureContainer:
    """Factory function to create configured infrastructure container."""

    # Default model configurations
    if model_configs is None:
        model_configs = {"mock": {"provider": "mock", "model_id": "mock-model", "name": "mock"}}

    config = InfrastructureConfig(
        storage_backend=storage_backend,
        storage_path=storage_path,
        cache_type=cache_type,
        model_configs=model_configs,
    )

    return InfrastructureContainer(config)


# Version information
__version__ = "1.0.0"
__author__ = "OpenChronicle Team"


# Export main components
__all__ = [
    # Adapters
    "ModelConfig",
    "BaseModelAdapter",
    "MockModelAdapter",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "OllamaAdapter",
    "ModelManagementAdapter",
    "create_adapter",
    # Memory
    "MemoryOrchestrator",
    # Cache
    "CacheEntry",
    "BaseCache",
    "InMemoryCache",
    "FileSystemCache",
    "ModelResponseCache",
    "create_cache",
    # Configuration and container
    "InfrastructureConfig",
    "InfrastructureContainer",
    "create_infrastructure",
    # Metadata
    "__version__",
    "__author__",
]
