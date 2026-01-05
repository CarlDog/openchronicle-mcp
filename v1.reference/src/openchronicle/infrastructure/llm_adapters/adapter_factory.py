"""
Dynamic adapter factory with Phase 2.0 configuration system.

This factory uses the dynamic configuration system that automatically
discovers providers from individual JSON files in config/models/.

Following OpenChronicle naming convention: adapter_factory.py
"""

import logging
from typing import Any

from ..model_registry.registry_manager import RegistryManager
from .adapter_exceptions import AdapterInitializationError
from .adapter_exceptions import AdapterNotFoundError
from .api_adapter_base import BaseAPIAdapter


logger = logging.getLogger(__name__)


class AdapterFactory:
    """
    Dynamic adapter factory with content-driven provider discovery.

    This factory integrates with the Phase 2.0 dynamic configuration system,
    automatically discovering providers from individual configuration files
    and enabling runtime provider management.

    Key Features:
    - Content-driven provider discovery using RegistryManager
    - Runtime provider addition/removal
    - Multi-model support per provider
    - Enhanced error handling and logging
    """

    def __init__(self, registry_path: str = "config/model_registry.json"):
        """
        Initialize the adapter factory with consolidated registry.

        Args:
            registry_path: Path to the main model registry configuration file
        """
        self.registry = RegistryManager(registry_path)
        self.providers: dict[str, type[BaseAPIAdapter]] = {}
        self.adapter_instances: dict[str, BaseAPIAdapter] = {}

        self._register_default_adapters()
        self._discover_available_providers()

        logger.info(f"AdapterFactory initialized with {len(self.get_available_providers())} providers")
        logger.info(f"Available configurations: {len(self.get_available_configurations())}")

    def _register_default_adapters(self) -> None:
        """Register default adapter class mappings."""
        try:
            # Import adapters dynamically to avoid circular imports
            from .providers.anthropic_adapter import AnthropicAdapter
            from .providers.ollama_adapter import OllamaAdapter
            from .providers.openai_adapter import OpenAIAdapter

            self.providers.update(
                {
                    "openai": OpenAIAdapter,
                    "ollama": OllamaAdapter,
                    "anthropic": AnthropicAdapter,
                }
            )

            # Try to register additional adapters if available
            try:
                from .providers.gemini_adapter import GeminiAdapter

                self.providers["gemini"] = GeminiAdapter
            except ImportError:
                logger.debug("Gemini adapter not available")

            try:
                from .providers.groq_adapter import GroqAdapter

                self.providers["groq"] = GroqAdapter
            except ImportError:
                logger.debug("Groq adapter not available")

            try:
                from .providers.transformers_adapter import TransformersAdapter

                self.providers["transformers"] = TransformersAdapter
            except ImportError:
                logger.debug("Transformers adapter not available")

            logger.info(f"Registered {len(self.providers)} adapter classes")

        except ImportError as e:
            logger.warning(f"Could not import some adapters: {e}")

    def _discover_available_providers(self) -> None:
        """Discover available providers from configurations without adapter implementations."""
        try:
            # Get all provider types from configurations
            config_providers = set()
            providers_data = self.registry.discover_providers()

            for provider_name, _configs in providers_data.items():
                config_providers.add(provider_name)

            # Log providers without adapter implementations
            missing_adapters = config_providers - set(self.providers.keys())
            if missing_adapters:
                logger.info(
                    f"Found configurations for providers without adapter implementations: {list(missing_adapters)}"
                )
        except (OSError, ValueError, TypeError) as e:
            logger.warning(f"Error discovering providers: {e}")

    def register_adapter(self, provider: str, adapter_class: type[BaseAPIAdapter]) -> None:
        """
        Register a new adapter class for a provider.

        Args:
            provider: Provider name (e.g., 'openai', 'anthropic')
            adapter_class: Adapter class implementing BaseAPIAdapter
        """
        if not issubclass(adapter_class, BaseAPIAdapter):
            raise TypeError("Adapter class must inherit from BaseAPIAdapter")

        self.providers[provider] = adapter_class
        logger.info(f"Registered custom adapter for provider: {provider}")

    def get_available_providers(self) -> list[str]:
        """Get list of providers with registered adapter classes."""
        return list(self.providers.keys())

    def get_available_configurations(self) -> list[str]:
        """Get list of all available configuration names."""
        try:
            all_configs = []
            providers = self.registry.discover_providers()
            for provider_name, configs in providers.items():
                for config in configs:
                    config_name = config.get("config_name", f"{provider_name}_default")
                    all_configs.append(config_name)
        except (OSError, ValueError, TypeError) as e:
            logger.warning(f"Error getting configurations: {e}")
            return []
        else:
            return all_configs

    def get_provider_models(self, provider: str) -> list[dict[str, Any]]:
        """
        Get all model configurations for a specific provider.

        Args:
            provider: Provider name

        Returns:
            List of model configurations for the provider
        """
        try:
            return self.registry.get_provider_models(provider)
        except (OSError, ValueError, TypeError) as e:
            logger.warning(f"Could not get models for provider {provider}: {e}")
            return []

    def create_adapter(
        self,
        config_name_or_provider: str,
        custom_config: dict[str, Any] | None = None,
    ) -> BaseAPIAdapter:
        """
        Create an adapter instance from configuration name or provider.

        Args:
            config_name_or_provider: Configuration name or provider name
            custom_config: Optional configuration overrides

        Returns:
            Initialized adapter instance

        Raises:
            AdapterNotFoundError: If configuration/provider not found
            AdapterInitializationError: If adapter initialization fails
        """
        # Try as configuration name first (more specific)
        if config_name_or_provider in self.get_available_configurations():
            return self._create_adapter_from_config(config_name_or_provider, custom_config)

        # Try as provider name
        if config_name_or_provider in self.get_available_providers():
            return self._create_adapter_from_provider(config_name_or_provider, custom_config)

        # If neither found, provide helpful error
        available_configs = self.get_available_configurations()
        available_providers = self.get_available_providers()
        raise AdapterNotFoundError(
            f"'{config_name_or_provider}' not found. "
            f"Available configs: {available_configs[:3]}... "
            f"Available providers: {available_providers}"
        )

    def _create_adapter_from_config(
        self, config_name: str, custom_config: dict[str, Any] | None = None
    ) -> BaseAPIAdapter:
        """Create adapter from specific configuration name."""
        try:
            # Get the configuration
            config = self.registry.get_model_config(config_name)
            if not config:
                raise AdapterNotFoundError(f"Configuration '{config_name}' not found")

            # Extract provider from config
            provider = config.get("provider")
            if not provider:
                raise AdapterInitializationError(f"No provider specified in configuration '{config_name}'")

            # Check if we have an adapter class for this provider
            if provider not in self.providers:
                raise AdapterNotFoundError(f"No adapter class registered for provider '{provider}'")

            # Merge custom config if provided
            final_config = config.copy()
            if custom_config:
                final_config.update(custom_config)

            # Create adapter instance
            adapter_class = self.providers[provider]
            adapter = adapter_class(config_name, final_config)

            logger.info(f"Created {provider} adapter from config: {config_name}")
        except (AdapterNotFoundError, AdapterInitializationError, ValueError, TypeError) as e:
            logger.exception(f"Failed to create adapter from config '{config_name}'")
            raise AdapterInitializationError(f"Adapter creation failed: {e}") from e
        else:
            return adapter

    def _create_adapter_from_provider(
        self, provider: str, custom_config: dict[str, Any] | None = None
    ) -> BaseAPIAdapter:
        """Create adapter using provider default configuration."""
        try:
            # Get default configuration for provider
            provider_configs = self.get_provider_models(provider)
            if not provider_configs:
                # Create minimal config if none exists
                config = {
                    "provider": provider,
                    "display_name": f"Default {provider.title()}",
                    "enabled": True,
                }
            else:
                # Use first available config as default
                config = provider_configs[0].copy()

            # Merge custom config if provided
            if custom_config:
                config.update(custom_config)

            # Create adapter instance
            adapter_class = self.providers[provider]
            adapter = adapter_class(f"default_{provider}", config)

            logger.info(f"Created default {provider} adapter")
        except (KeyError, AdapterNotFoundError, AdapterInitializationError, ValueError, TypeError) as e:
            logger.exception(f"Failed to create adapter for provider '{provider}'")
            raise AdapterInitializationError(f"Adapter creation failed: {e}") from e
        else:
            return adapter

    def has_provider(self, provider_name: str) -> bool:
        """Check if a provider is available."""
        return provider_name in self.get_available_providers() or provider_name in self.get_available_configurations()

    def validate_configuration(self, provider_name: str, config: dict[str, Any]) -> bool:
        """Validate configuration for a provider."""
        return self.has_provider(provider_name)

    def get_adapter_info(self, config_name: str) -> dict[str, Any] | None:
        """Get adapter information including configuration requirements."""
        try:
            return self.registry.get_model_config(config_name)
        except (OSError, ValueError, TypeError):
            return None

    def get_fallback_chain(self, provider: str) -> list[str]:
        """Get fallback chain for a provider."""
        try:
            # For now, return simple fallback to just the provider
            # This could be enhanced later with actual fallback configuration
            return [provider] if provider in self.providers else []
        except (OSError, ValueError, TypeError):
            return []

    def add_runtime_config(self, config_name: str, config: dict[str, Any]) -> bool:
        """Add a new configuration at runtime."""
        try:
            success = self.registry.add_model_config(config_name, config)
            if success:
                logger.info(f"Added runtime configuration: {config_name}")
        except (OSError, ValueError, TypeError) as e:
            logger.exception(f"Failed to add runtime config '{config_name}'")
            return False
        else:
            return success

    def remove_runtime_config(self, config_name: str) -> bool:
        """Remove a configuration at runtime."""
        try:
            success = self.registry.remove_model_config(config_name)
            if success:
                logger.info(f"Removed runtime configuration: {config_name}")
        except (OSError, ValueError, TypeError) as e:
            logger.exception(f"Failed to remove runtime config '{config_name}'")
            return False
        else:
            return success

    def refresh_configurations(self) -> dict[str, Any]:
        """Refresh configurations from disk."""
        return self.registry.refresh_providers()

    @property
    def status(self) -> dict[str, Any]:
        """Get factory status information."""
        return {
            "mode": "dynamic",
            "total_providers": len(self.get_available_providers()),
            "total_configs": len(self.get_available_configurations()),
            "config_directory": str(self.registry.models_dir),
            "registered_adapters": list(self.providers.keys()),
        }
