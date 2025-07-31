"""
Adapter factory with registry integration.

This factory creates adapter instances based on registry configuration,
providing clean separation between configuration and implementation.
"""

import logging
from typing import Dict, Any, Type, Optional, List

from ..adapters.base import ModelAdapter, BaseAPIAdapter
from ..adapters.exceptions import AdapterNotFoundError, AdapterInitializationError
from ..model_management.registry import RegistryManager

logger = logging.getLogger(__name__)


class AdapterFactory:
    """
    Factory for creating model adapters with registry integration.
    
    This factory creates adapter instances based on registry configuration,
    automatically injecting provider-specific settings and validation rules.
    """
    
    # Map provider names to adapter classes
    ADAPTER_MAP: Dict[str, Type[ModelAdapter]] = {}
    
    def __init__(self, registry_manager: RegistryManager):
        self.registry = registry_manager
        self._register_default_adapters()
    
    def _register_default_adapters(self) -> None:
        """Register default adapter mappings."""
        try:
            # Import adapters dynamically to avoid circular imports
            from ..adapters.providers.openai import OpenAIAdapter
            from ..adapters.providers.ollama import OllamaAdapter
            from ..adapters.providers.anthropic import AnthropicAdapter
            
            self.ADAPTER_MAP.update({
                'openai': OpenAIAdapter,
                'ollama': OllamaAdapter,
                'anthropic': AnthropicAdapter,
            })
            
            logger.info(f"Registered {len(self.ADAPTER_MAP)} default adapters")
            
        except ImportError as e:
            logger.warning(f"Could not import some adapters: {e}")
    
    def register_adapter(self, provider: str, adapter_class: Type[ModelAdapter]) -> None:
        """Register a new adapter class for a provider."""
        self.ADAPTER_MAP[provider] = adapter_class
        logger.info(f"Registered adapter for provider: {provider}")
    
    def create_adapter(
        self, 
        model_config: Dict[str, Any],
        model_manager: Optional[Any] = None
    ) -> ModelAdapter:
        """
        Create adapter instance from model configuration.
        
        Args:
            model_config: Model configuration from registry
            model_manager: Optional reference to model manager
            
        Returns:
            Initialized adapter instance
            
        Raises:
            AdapterNotFoundError: If provider is not registered
            AdapterInitializationError: If adapter fails to initialize
        """
        provider = model_config.get("name") or model_config.get("provider")
        if not provider:
            raise AdapterInitializationError("unknown", "No provider specified in config")
        
        if provider not in self.ADAPTER_MAP:
            available = list(self.ADAPTER_MAP.keys())
            raise AdapterNotFoundError(f"Unknown provider: {provider}. Available: {available}")
        
        adapter_class = self.ADAPTER_MAP[provider]
        
        try:
            # Create enhanced config with registry integration
            enhanced_config = self._enhance_config_with_registry(model_config, provider)
            
            # Create adapter instance
            adapter = adapter_class(enhanced_config)
            
            logger.info(f"Created {provider} adapter for model {enhanced_config.get('model_name', 'unknown')}")
            return adapter
            
        except Exception as e:
            raise AdapterInitializationError(provider, f"Failed to create adapter: {e}")
    
    def _enhance_config_with_registry(self, model_config: Dict[str, Any], provider: str) -> Dict[str, Any]:
        """
        Enhance model config with registry provider configuration.
        
        This injects provider-specific settings from the registry into the
        model configuration, enabling registry-aware adapters.
        """
        enhanced_config = model_config.copy()
        
        try:
            # Get provider configuration from registry
            provider_config = self.registry.get_provider_config(provider)
            
            # Add provider-specific settings
            enhanced_config.update({
                "provider_config": provider_config,
                "registry_manager": self.registry,
                "provider": provider
            })
            
            # Add default values if not specified
            if "timeout" not in enhanced_config:
                enhanced_config["timeout"] = provider_config.get("timeout", 30)
            
            # Add performance limits
            performance_limits = self.registry.get_performance_limits(provider)
            enhanced_config["performance_limits"] = performance_limits
            
            # Add validation rules
            validation_rules = self.registry.get_validation_rules(provider)
            enhanced_config["validation_rules"] = validation_rules
            
            logger.debug(f"Enhanced config for {provider} with registry settings")
            
        except Exception as e:
            logger.warning(f"Could not enhance config with registry for {provider}: {e}")
            # Continue with original config if registry enhancement fails
        
        return enhanced_config
    
    def get_available_providers(self) -> List[str]:
        """Get list of available adapter providers."""
        return list(self.ADAPTER_MAP.keys())
    
    def is_provider_available(self, provider: str) -> bool:
        """Check if a provider adapter is available."""
        return provider in self.ADAPTER_MAP
    
    def validate_provider_config(self, provider: str) -> Dict[str, Any]:
        """
        Validate provider configuration against registry rules.
        
        Returns:
            Validation result with status and any issues
        """
        result = {
            "provider": provider,
            "adapter_available": self.is_provider_available(provider),
            "registry_config_available": False,
            "validation_passed": False,
            "issues": []
        }
        
        # Check if adapter exists
        if not result["adapter_available"]:
            result["issues"].append(f"No adapter registered for provider '{provider}'")
            return result
        
        # Check registry configuration
        try:
            provider_config = self.registry.get_provider_config(provider)
            result["registry_config_available"] = True
            
            # Validate required fields
            validation_rules = self.registry.get_validation_rules(provider)
            
            if validation_rules.get("requires_api_key", True):
                api_key_env = provider_config.get("api_key_env")
                if not api_key_env:
                    result["issues"].append("Provider requires API key but no api_key_env specified")
            
            # Check base URL configuration
            if not provider_config.get("default_base_url") and not provider_config.get("base_url_env"):
                result["issues"].append("No base URL configuration found")
            
            result["validation_passed"] = len(result["issues"]) == 0
            
        except ValueError as e:
            result["issues"].append(f"Registry configuration error: {e}")
        
        return result
