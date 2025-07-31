"""
Base adapter classes for AI model providers.

This module implements the template method pattern to eliminate massive code duplication
from the original monolithic model_adapter.py. The BaseAPIAdapter provides common
functionality that was previously duplicated across 15+ adapter implementations.

Key Features:
- Template method pattern eliminates ~1,500 lines of duplicated code
- Common API key and base URL resolution logic
- Standardized initialization and error handling
- Each provider adapter now only needs to implement 4-5 methods
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime, UTC

# Import logging system
from utilities.logging_system import log_model_interaction, log_system_event, log_info, log_error

# Import exceptions
from .exceptions import (
    AdapterInitializationError, 
    AdapterConfigurationError, 
    AdapterConnectionError
)

logger = logging.getLogger(__name__)


def get_api_key_with_fallback(config: Dict[str, Any], provider: str, env_var: str) -> Optional[str]:
    """
    Get API key with fallback priority: config > keystore > environment variable
    
    Args:
        config: Adapter configuration dictionary
        provider: Provider name for keystore (e.g., 'openai', 'anthropic')
        env_var: Environment variable name (e.g., 'OPENAI_API_KEY')
    
    Returns:
        API key string or None if not found
    """
    # Import keystore dynamically to avoid import errors
    try:
        from utilities.api_key_manager import get_api_key
    except ImportError:
        get_api_key = None
    
    # First priority: explicit config
    api_key = config.get("api_key")
    if api_key:
        return api_key
    
    # Second priority: secure keystore
    if get_api_key:
        try:
            keystore_key = get_api_key(provider)
            if keystore_key:
                return keystore_key
        except Exception:
            pass  # Fallback to environment variable
    
    # Third priority: environment variable
    return os.getenv(env_var)


class ModelAdapter(ABC):
    """Abstract base class for all model adapters."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model_name = config.get("model_name", "unknown")
        # Only set max_tokens for text models, not image models
        if config.get("type") != "image":
            self.max_tokens = config.get("max_tokens", 2048)
        self.temperature = config.get("temperature", 0.7)
        self.initialized = False
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the model adapter."""
        pass
    
    @abstractmethod
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate a response from the model."""
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the model."""
        pass
    
    def log_interaction(self, story_id: str, prompt: str, response: str, metadata: Optional[Dict[str, Any]] = None):
        """Log the interaction for debugging/analysis."""
        log_model_interaction(
            story_id=story_id,
            model=self.model_name,
            prompt_length=len(prompt),
            response_length=len(response),
            metadata=metadata or {}
        )


class BaseAPIAdapter(ModelAdapter):
    """
    Base adapter for API-based providers using template method pattern with registry integration.
    
    This class eliminates ~90% of code duplication by providing common functionality
    that was previously copied across all adapter implementations:
    - API key resolution with fallback logic
    - Base URL configuration with environment variable support
    - Registry-aware configuration loading
    - Standardized initialization pattern
    - Common error handling and logging
    - Performance limits and validation from registry
    
    Subclasses only need to implement:
    - get_provider_name()
    - get_api_key_env_var() 
    - get_base_url_env_var()
    - get_default_base_url()
    - _create_client()
    - generate_response()
    """
    
    def __init__(self, config: Dict[str, Any], model_manager=None):
        super().__init__(config)
        self.provider_name = self.get_provider_name()
        self.model_manager = model_manager
        
        # Registry integration - use registry config if available
        self.registry_manager = config.get("registry_manager")
        self.provider_config = config.get("provider_config", {})
        self.validation_rules = config.get("validation_rules", {})
        self.performance_limits = config.get("performance_limits", {})
        
        # Common setup using template pattern - eliminates duplication
        self.api_key = self._setup_api_key(config)
        self.base_url = self._setup_base_url(config)  
        self.timeout = config.get("timeout", self.provider_config.get("timeout", 30))
        self.client = None
        
        log_info(f"Initialized {self.provider_name} adapter for model {self.model_name}")
        if self.registry_manager:
            log_info(f"Registry-aware adapter for {self.provider_name} with enhanced configuration")
    
    def _setup_api_key(self, config: Dict[str, Any]) -> Optional[str]:
        """Common API key setup logic - used by ALL API adapters."""
        if not self.requires_api_key():
            return None
            
        api_key = get_api_key_with_fallback(
            config, 
            self.provider_name, 
            self.get_api_key_env_var()
        )
        
        if self.requires_api_key() and not api_key:
            raise AdapterConfigurationError(
                self.provider_name,
                f"API key required but not found. Please set {self.get_api_key_env_var()} environment variable or configure in registry."
            )
        
        return api_key
    
    def _setup_base_url(self, config: Dict[str, Any]) -> str:
        """
        Common base URL resolution logic - used by ALL adapters.
        
        This single implementation replaces the duplicated _get_base_url methods
        that existed in every adapter class.
        """
        # Check explicit config first
        if "base_url" in config:
            return config["base_url"]
        
        # Use model manager if available
        if self.model_manager:
            try:
                return self.model_manager.get_provider_base_url(self.provider_name)
            except Exception:
                pass
        
        # Check environment variable
        env_var = self.get_base_url_env_var()
        if env_var:
            env_url = os.getenv(env_var)
            if env_url:
                return env_url
        
        # Fallback to default
        default_url = self.get_default_base_url()
        if default_url:
            return default_url
            
        raise AdapterConfigurationError(
            self.provider_name,
            f"No base URL configured. Please set {env_var} environment variable or configure in registry."
        )
    
    async def initialize(self) -> bool:
        """
        Template method for initialization - subclasses implement _create_client only.
        
        This eliminates the duplicated initialization logic across all adapters.
        Enhanced with registry-aware validation and health checks.
        """
        if self.requires_api_key() and not self.api_key:
            raise AdapterInitializationError(
                self.provider_name,
                "API key required but not available"
            )

        try:
            self.client = await self._create_client()
            
            # Registry-aware validation
            if self.registry_manager and hasattr(self.registry_manager, 'validate_adapter_config'):
                is_valid, validation_message = await self.registry_manager.validate_adapter_config(self.provider_name, self.config)
                if not is_valid:
                    log_error(f"Registry validation failed for {self.provider_name}: {validation_message}")
                    # Continue with initialization but log the issue
            
            self.initialized = True
            log_info(f"{self.provider_name} adapter initialized successfully")
            
            # Registry-aware health check on initialization
            if self.registry_manager and hasattr(self.registry_manager, 'should_health_check'):
                if self.registry_manager.should_health_check(self.provider_name):
                    try:
                        await self._perform_health_check()
                    except Exception as e:
                        log_error(f"Health check failed for {self.provider_name}: {e}")
                        # Continue with initialization even if health check fails
            
            return True
            
        except ImportError as e:
            raise AdapterInitializationError(
                self.provider_name,
                f"Required package not installed: {e}"
            )
        except Exception as e:
            log_error(f"Failed to initialize {self.provider_name} adapter: {e}")
            raise AdapterInitializationError(self.provider_name, str(e))
    
    def get_model_info(self) -> Dict[str, Any]:
        """Standard model info implementation - can be overridden if needed."""
        info = {
            "provider": self.provider_name.title(),
            "model_name": self.model_name,
            "temperature": self.temperature,
            "initialized": self.initialized,
            "base_url": getattr(self, 'base_url', None)
        }
        
        # Only include max_tokens for text models
        if hasattr(self, 'max_tokens'):
            info["max_tokens"] = self.max_tokens
            
        return info
    
    async def _perform_health_check(self) -> bool:
        """
        Basic health check - can be overridden by subclasses for provider-specific checks.
        
        Returns:
            bool: True if healthy, False otherwise
        """
        try:
            # Basic check - ensure client is initialized
            if not self.client:
                return False
                
            # For most providers, if we can initialize the client, we're healthy
            # Subclasses can override for more sophisticated health checks
            log_info(f"Health check passed for {self.provider_name}")
            return True
            
        except Exception as e:
            log_error(f"Health check failed for {self.provider_name}: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Public health check method."""
        return await self._perform_health_check()
    
    def get_performance_limits(self) -> Dict[str, Any]:
        """Get performance limits from registry if available."""
        if self.performance_limits:
            return self.performance_limits
        return {
            "max_requests_per_minute": 60,
            "max_tokens_per_request": self.max_tokens if hasattr(self, 'max_tokens') else 4096,
            "timeout": self.timeout
        }
    
    def get_validation_rules(self) -> Dict[str, Any]:
        """Get validation rules from registry if available."""
        return self.validation_rules if self.validation_rules else {}

    # Abstract methods that subclasses must implement
    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider name (e.g., 'openai', 'anthropic')."""
        pass
    
    @abstractmethod
    def requires_api_key(self) -> bool:
        """Return True if this provider requires an API key."""
        pass
    
    @abstractmethod
    def get_api_key_env_var(self) -> str:
        """Return the environment variable name for the API key."""
        pass
    
    @abstractmethod
    def get_base_url_env_var(self) -> Optional[str]:
        """Return the environment variable name for the base URL."""
        pass
    
    @abstractmethod
    def get_default_base_url(self) -> Optional[str]:
        """Return the default base URL for this provider."""
        pass
    
    @abstractmethod
    async def _create_client(self) -> Any:
        """Create and return the provider-specific client object."""
        pass


class ImageAdapter(ModelAdapter):
    """Abstract base class for image generation adapters."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Image adapters don't use max_tokens
        if hasattr(self, 'max_tokens'):
            delattr(self, 'max_tokens')
    
    @abstractmethod
    async def generate_image(self, prompt: str, **kwargs) -> str:
        """Generate an image and return the URL or path."""
        pass
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Delegate to generate_image for consistency."""
        return await self.generate_image(prompt, **kwargs)


class LocalAdapter(ModelAdapter):
    """Base class for local model adapters (like Transformers)."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.device = config.get("device", "auto")
        self.model_path = config.get("model_path")
    
    @abstractmethod
    async def load_model(self) -> bool:
        """Load the local model into memory."""
        pass
