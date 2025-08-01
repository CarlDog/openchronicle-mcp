"""
Unified adapter factory with registry integration.

This factory consolidates adapter creation logic from both the original adapters/factory.py
and model_management/adapter_factory.py, providing a single, clean interface for
adapter creation with full registry integration.

Following OpenChronicle naming convention: adapter_factory.py
"""

import logging
from typing import Dict, Any, Type, Optional, List, Union

from .api_adapter_base import BaseAPIAdapter, LocalModelAdapter
from .adapter_exceptions import AdapterNotFoundError, AdapterInitializationError
from ..model_registry.registry_manager import RegistryManager

logger = logging.getLogger(__name__)


class AdapterFactory:
    """
    Unified factory for creating model adapters with registry integration.
    
    This factory consolidates adapter creation logic and creates adapter instances
    based on registry configuration, automatically injecting provider-specific
    settings and validation rules.
    
    Key Features:
    - Registry-aware adapter creation
    - Provider configuration injection
    - Dynamic adapter registration
    - Fallback chain support
    - Enhanced error handling and logging
    """
    
    def __init__(self, registry_manager: RegistryManager):
        """
        Initialize the adapter factory with registry integration.
        
        Args:
            registry_manager: Registry manager for configuration and validation
        """
        self.registry = registry_manager
        self.providers: Dict[str, Type[BaseAPIAdapter]] = {}
        self._register_default_adapters()
        
        logger.info(f"AdapterFactory initialized with {len(self.providers)} providers")
    
    def _register_default_adapters(self) -> None:
        """Register default adapter mappings from available providers."""
        try:
            # Import adapters dynamically to avoid circular imports
            from .providers.openai_adapter import OpenAIAdapter
            from .providers.ollama_adapter import OllamaAdapter  
            from .providers.anthropic_adapter import AnthropicAdapter
            
            self.providers.update({
                'openai': OpenAIAdapter,
                'ollama': OllamaAdapter,
                'anthropic': AnthropicAdapter,
            })
            
            logger.info(f"Registered {len(self.providers)} default adapters: {list(self.providers.keys())}")
            
        except ImportError as e:
            logger.warning(f"Could not import some adapters: {e}")
            # Try to register what we can
            try:
                from .providers.openai_adapter import OpenAIAdapter
                self.providers['openai'] = OpenAIAdapter
                logger.info("Registered OpenAI adapter")
            except ImportError:
                pass
                
            try:
                from .providers.ollama_adapter import OllamaAdapter
                self.providers['ollama'] = OllamaAdapter
                logger.info("Registered Ollama adapter")
            except ImportError:
                pass
                
            try:
                from .providers.anthropic_adapter import AnthropicAdapter
                self.providers['anthropic'] = AnthropicAdapter
                logger.info("Registered Anthropic adapter")
            except ImportError:
                pass
    
    def register_adapter(self, provider: str, adapter_class: Type[BaseAPIAdapter]) -> None:
        """
        Register a new adapter class for a provider.
        
        Args:
            provider: Provider name (e.g., 'openai', 'anthropic')
            adapter_class: Adapter class implementing BaseAPIAdapter
        """
        self.providers[provider] = adapter_class
        logger.info(f"Registered custom adapter for provider: {provider}")
    
    def get_available_providers(self) -> List[str]:
        """Get list of available provider names."""
        return list(self.providers.keys())
    
    def create_adapter(
        self, 
        provider: str, 
        model_name: str,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> BaseAPIAdapter:
        """
        Create adapter instance from provider and model information.
        
        Args:
            provider: Provider name (e.g., 'openai', 'anthropic')
            model_name: Model name to use
            custom_config: Optional custom configuration to override registry
            
        Returns:
            Initialized adapter instance
            
        Raises:
            AdapterNotFoundError: If provider is not registered
            AdapterInitializationError: If adapter fails to initialize
        """
        if provider not in self.providers:
            available = list(self.providers.keys())
            raise AdapterNotFoundError(f"Unknown provider: {provider}. Available: {available}")
        
        adapter_class = self.providers[provider]
        
        try:
            # Get enhanced config with registry integration
            config = self._get_enhanced_config(provider, model_name, custom_config)
            
            # Create adapter instance
            adapter = adapter_class(model_name, config)
            
            logger.info(f"Created {provider} adapter for model: {model_name}")
            return adapter
            
        except Exception as e:
            logger.error(f"Failed to create {provider} adapter: {e}")
            raise AdapterInitializationError(provider, f"Adapter creation failed: {e}")
    
    def create_adapter_from_config(
        self, 
        model_config: Dict[str, Any],
        model_manager: Optional[Any] = None
    ) -> BaseAPIAdapter:
        """
        Create adapter instance from model configuration dictionary.
        
        This method provides backward compatibility with the original factory interface.
        
        Args:
            model_config: Model configuration from registry or elsewhere
            model_manager: Optional reference to model manager (for compatibility)
            
        Returns:
            Initialized adapter instance
        """
        # Extract provider and model name from config
        provider = model_config.get("name") or model_config.get("provider")
        model_name = model_config.get("model_name") or model_config.get("model")
        
        if not provider:
            raise AdapterInitializationError(None, "No provider specified in config")
        
        if not model_name:
            raise AdapterInitializationError(provider, "No model name specified in config")
        
        return self.create_adapter(provider, model_name, model_config)
    
    def _get_enhanced_config(
        self, 
        provider: str, 
        model_name: str, 
        custom_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create enhanced configuration by merging registry config with custom config.
        
        Args:
            provider: Provider name
            model_name: Model name
            custom_config: Custom configuration to merge
            
        Returns:
            Enhanced configuration dictionary
        """
        # Start with registry configuration
        try:
            registry_config = self.registry.get_provider_config(provider)
        except Exception as e:
            logger.warning(f"Could not get registry config for {provider}: {e}")
            registry_config = {}
        
        # Create base configuration
        config = {
            "provider": provider,
            "model_name": model_name,
            **registry_config
        }
        
        # Merge custom configuration if provided
        if custom_config:
            config.update(custom_config)
        
        # Add registry-specific enhancements
        config = self._add_registry_enhancements(config, provider, model_name)
        
        return config
    
    def _add_registry_enhancements(
        self, 
        config: Dict[str, Any], 
        provider: str, 
        model_name: str
    ) -> Dict[str, Any]:
        """
        Add registry-specific enhancements to configuration.
        
        Args:
            config: Base configuration
            provider: Provider name
            model_name: Model name
            
        Returns:
            Enhanced configuration with registry features
        """
        try:
            # Add model-specific configuration from registry
            model_config = self.registry.get_model_config(provider, model_name)
            if model_config:
                config.update(model_config)
            
            # Add provider validation rules
            validation_rules = self.registry.get_validation_rules(provider)
            if validation_rules:
                config["validation_rules"] = validation_rules
            
            # Add health check configuration
            health_config = self.registry.get_health_check_config(provider)
            if health_config:
                config["health_check"] = health_config
            
            # Add rate limiting configuration
            rate_limit_config = self.registry.get_rate_limit_config(provider)
            if rate_limit_config:
                config["rate_limits"] = rate_limit_config
                
        except Exception as e:
            logger.warning(f"Could not enhance config with registry data: {e}")
        
        return config
    
    def get_fallback_chain(self, provider: str) -> List[str]:
        """
        Get fallback chain for a provider from registry.
        
        Args:
            provider: Provider name
            
        Returns:
            List of provider names in fallback order
        """
        try:
            return self.registry.get_fallback_chain(provider)
        except Exception as e:
            logger.warning(f"Could not get fallback chain for {provider}: {e}")
            return [provider]  # Return single provider as fallback
    
    def create_fallback_adapters(
        self, 
        provider: str, 
        model_name: str,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> List[BaseAPIAdapter]:
        """
        Create adapters for entire fallback chain.
        
        Args:
            provider: Primary provider name
            model_name: Model name
            custom_config: Custom configuration
            
        Returns:
            List of adapters in fallback order
        """
        fallback_chain = self.get_fallback_chain(provider)
        adapters = []
        
        for fallback_provider in fallback_chain:
            try:
                adapter = self.create_adapter(fallback_provider, model_name, custom_config)
                adapters.append(adapter)
            except Exception as e:
                logger.warning(f"Could not create fallback adapter for {fallback_provider}: {e}")
        
        return adapters
    
    def validate_provider_config(self, provider: str) -> bool:
        """
        Validate that a provider is properly configured.
        
        Args:
            provider: Provider name to validate
            
        Returns:
            True if provider is valid and configured
        """
        if provider not in self.providers:
            return False
        
        try:
            # Check if registry has configuration for this provider
            config = self.registry.get_provider_config(provider)
            return bool(config)
        except Exception:
            return False
    
    def get_adapter_info(self, provider: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific adapter.
        
        Args:
            provider: Provider name
            
        Returns:
            Adapter information dictionary or None if not found
        """
        if provider not in self.providers:
            return None
        
        adapter_class = self.providers[provider]
        
        return {
            "provider": provider,
            "adapter_class": adapter_class.__name__,
            "module": adapter_class.__module__,
            "is_local": issubclass(adapter_class, LocalModelAdapter),
            "registry_configured": self.validate_provider_config(provider)
        }
    
    def get_factory_status(self) -> Dict[str, Any]:
        """
        Get comprehensive factory status information.
        
        Returns:
            Factory status dictionary
        """
        return {
            "total_providers": len(self.providers),
            "available_providers": list(self.providers.keys()),
            "registry_status": self.registry.get_status() if hasattr(self.registry, 'get_status') else "unknown",
            "provider_info": {
                provider: self.get_adapter_info(provider) 
                for provider in self.providers.keys()
            }
        }
