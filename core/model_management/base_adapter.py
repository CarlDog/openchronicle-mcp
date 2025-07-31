"""
Base Adapter Framework - Template Method Pattern Implementation

This module implements the Template Method pattern to eliminate 90% of code duplication
across OpenChronicle's 15+ model adapters. Each adapter now only needs to implement
3-5 provider-specific methods instead of 20+ duplicate methods.

Key Classes:
- BaseAdapter: Core template with common functionality
- BaseAPIAdapter: Template for API-based providers (OpenAI, Anthropic, etc.)
- BaseLocalAdapter: Template for local providers (Ollama, Transformers)

Benefits:
- Reduces adapter implementation from 100+ lines to 20-30 lines
- Standardizes error handling, logging, and retry logic
- Provides consistent health checking and metrics
- Simplifies testing with mock-friendly architecture
"""

import asyncio
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union, AsyncGenerator
import os

# Import shared utilities
from ..shared.json_utilities import JSONUtilities
from .adapter_interfaces import (
    ModelAdapterInterface, AdapterConfig, AdapterResponse,
    AdapterError, AdapterConnectionError, AdapterAuthenticationError,
    AdapterRateLimitError, AdapterTimeoutError, AdapterConfigurationError
)

logger = logging.getLogger(__name__)


class BaseAdapter(ModelAdapterInterface):
    """
    Base adapter implementing the Template Method pattern
    
    This class provides the common structure and behavior for all adapters,
    requiring only provider-specific methods to be implemented by subclasses.
    
    Template Methods (implemented here):
    - initialize() - Common initialization with hooks
    - generate_response() - Common response generation with error handling
    - cleanup() - Common cleanup with hooks
    - health_check() - Standardized health checking
    
    Abstract Methods (must be implemented):
    - get_provider_name() - Provider identification
    - get_supported_models() - Model listing
    - _create_client() - Provider-specific client creation
    - _generate_response_impl() - Provider-specific generation
    """
    
    def __init__(self, config: AdapterConfig):
        """Initialize base adapter with configuration"""
        super().__init__(config)
        
        # Common state
        self.json_util = JSONUtilities()
        self.metrics = {
            'requests_made': 0,
            'requests_failed': 0,
            'total_tokens': 0,
            'total_cost': 0.0,
            'avg_response_time': 0.0,
            'last_request_time': None
        }
        
        # Retry configuration
        self.retry_delays = [1, 2, 4, 8, 16]  # Exponential backoff
        
        # Provider-specific initialization hook
        self._provider_init()
    
    def _provider_init(self) -> None:
        """Hook for provider-specific initialization (override if needed)"""
        pass
    
    # Template Methods (implemented in base class)
    
    async def initialize(self) -> None:
        """
        Template method for adapter initialization
        
        Common sequence:
        1. Pre-initialization hook
        2. Create client
        3. Validate connection
        4. Post-initialization hook
        5. Mark as initialized
        """
        if self.is_initialized:
            return
        
        try:
            self.logger.info(f"Initializing {self.provider_name} adapter for {self.model_name}")
            
            # Hook: Pre-initialization
            await self._pre_initialize()
            
            # Create provider-specific client
            self.client = await self._create_client()
            
            # Validate connection
            await self._validate_connection()
            
            # Hook: Post-initialization
            await self._post_initialize()
            
            self.is_initialized = True
            self.logger.info(f"{self.provider_name} adapter initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize {self.provider_name} adapter: {e}")
            raise AdapterConnectionError(
                f"Initialization failed: {e}",
                provider=self.provider_name
            )
    
    async def generate_response(
        self, 
        prompt: str, 
        **kwargs
    ) -> AdapterResponse:
        """
        Template method for response generation
        
        Common sequence:
        1. Validate inputs and state
        2. Prepare request parameters
        3. Execute with retry logic
        4. Process response
        5. Update metrics
        """
        if not self.is_initialized:
            await self.initialize()
        
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        
        start_time = time.time()
        retries_used = 0
        last_error = None
        
        # Merge configuration with request parameters
        request_params = self._prepare_request_params(prompt, **kwargs)
        
        # Retry loop with exponential backoff
        for attempt in range(self.config.max_retries + 1):
            try:
                self.logger.debug(f"Generating response (attempt {attempt + 1})")
                
                # Provider-specific implementation
                response = await self._generate_response_impl(prompt, request_params)
                
                # Process and validate response
                processed_response = self._process_response(
                    response, start_time, retries_used
                )
                
                # Update metrics
                self._update_metrics(processed_response, start_time)
                
                return processed_response
                
            except (AdapterRateLimitError, AdapterTimeoutError) as e:
                retries_used = attempt
                last_error = e
                
                if attempt < self.config.max_retries:
                    delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                    self.logger.warning(
                        f"Request failed (attempt {attempt + 1}), retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(f"Request failed after {attempt + 1} attempts: {e}")
                    break
            
            except Exception as e:
                # Non-retryable errors
                self.logger.error(f"Non-retryable error: {e}")
                self.metrics['requests_failed'] += 1
                raise AdapterError(f"Generation failed: {e}", provider=self.provider_name)
        
        # All retries exhausted
        self.metrics['requests_failed'] += 1
        if last_error:
            raise last_error
        else:
            raise AdapterError(
                f"Request failed after {self.config.max_retries + 1} attempts",
                provider=self.provider_name
            )
    
    async def cleanup(self) -> None:
        """
        Template method for cleanup
        
        Common sequence:
        1. Pre-cleanup hook
        2. Close client connections
        3. Reset state
        4. Post-cleanup hook
        """
        if not self.is_initialized:
            return
        
        try:
            self.logger.info(f"Cleaning up {self.provider_name} adapter")
            
            # Hook: Pre-cleanup
            await self._pre_cleanup()
            
            # Close client connections
            if self.client and hasattr(self.client, 'close'):
                try:
                    await self.client.close()
                except Exception as e:
                    self.logger.warning(f"Error closing client: {e}")
            
            # Reset state
            self.client = None
            self.is_initialized = False
            
            # Hook: Post-cleanup
            await self._post_cleanup()
            
            self.logger.info(f"{self.provider_name} adapter cleaned up successfully")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    # Abstract methods (must be implemented by subclasses)
    
    @abstractmethod
    async def _create_client(self) -> Any:
        """Create provider-specific client"""
        pass
    
    @abstractmethod
    async def _generate_response_impl(
        self, 
        prompt: str, 
        params: Dict[str, Any]
    ) -> Any:
        """Provider-specific response generation"""
        pass
    
    # Hook methods (can be overridden by subclasses)
    
    async def _pre_initialize(self) -> None:
        """Hook called before initialization"""
        pass
    
    async def _post_initialize(self) -> None:
        """Hook called after successful initialization"""
        pass
    
    async def _pre_cleanup(self) -> None:
        """Hook called before cleanup"""
        pass
    
    async def _post_cleanup(self) -> None:
        """Hook called after cleanup"""
        pass
    
    async def _validate_connection(self) -> None:
        """Validate connection to provider (can be overridden)"""
        # Default: try a simple health check
        try:
            await self.health_check()
        except Exception as e:
            raise AdapterConnectionError(
                f"Connection validation failed: {e}",
                provider=self.provider_name
            )
    
    # Helper methods (implemented in base class)
    
    def _prepare_request_params(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Prepare request parameters by merging config with kwargs"""
        params = {
            'max_tokens': kwargs.get('max_tokens', self.config.max_tokens),
            'temperature': kwargs.get('temperature', self.config.temperature),
            'top_p': kwargs.get('top_p', self.config.top_p),
            'frequency_penalty': kwargs.get('frequency_penalty', self.config.frequency_penalty),
            'presence_penalty': kwargs.get('presence_penalty', self.config.presence_penalty),
        }
        
        # Add provider-specific parameters
        params.update(self.config.provider_specific)
        
        # Override with any additional kwargs
        params.update(kwargs)
        
        return params
    
    def _process_response(
        self, 
        raw_response: Any, 
        start_time: float, 
        retries_used: int
    ) -> AdapterResponse:
        """Process raw response into standardized format"""
        response_time = time.time() - start_time
        
        # Extract content (must be implemented by subclasses)
        content = self._extract_content(raw_response)
        
        # Create standardized response
        response = AdapterResponse(
            content=content,
            model_name=self.model_name,
            provider_name=self.provider_name,
            response_time=response_time,
            retries_used=retries_used,
            raw_response=raw_response if isinstance(raw_response, dict) else None
        )
        
        # Extract additional metadata (can be overridden)
        self._extract_metadata(raw_response, response)
        
        return response
    
    @abstractmethod
    def _extract_content(self, raw_response: Any) -> str:
        """Extract content from raw response (must be implemented)"""
        pass
    
    def _extract_metadata(self, raw_response: Any, response: AdapterResponse) -> None:
        """Extract metadata from raw response (can be overridden)"""
        # Default: basic metadata extraction
        if hasattr(raw_response, 'usage'):
            usage = raw_response.usage
            if hasattr(usage, 'total_tokens'):
                response.tokens_used = usage.total_tokens
            if hasattr(usage, 'prompt_tokens'):
                response.input_tokens = usage.prompt_tokens
            if hasattr(usage, 'completion_tokens'):
                response.output_tokens = usage.completion_tokens
    
    def _update_metrics(self, response: AdapterResponse, start_time: float) -> None:
        """Update adapter metrics"""
        self.metrics['requests_made'] += 1
        
        if response.tokens_used:
            self.metrics['total_tokens'] += response.tokens_used
        
        if response.cost_estimate:
            self.metrics['total_cost'] += response.cost_estimate
        
        # Update average response time
        if self.metrics['requests_made'] == 1:
            self.metrics['avg_response_time'] = response.response_time
        else:
            # Running average
            old_avg = self.metrics['avg_response_time']
            count = self.metrics['requests_made']
            self.metrics['avg_response_time'] = (
                (old_avg * (count - 1) + response.response_time) / count
            )
        
        self.metrics['last_request_time'] = response.timestamp
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get detailed usage statistics"""
        base_stats = super().get_usage_stats()
        base_stats.update(self.metrics)
        return base_stats


class BaseAPIAdapter(BaseAdapter):
    """
    Base class for API-based adapters (OpenAI, Anthropic, etc.)
    
    Provides common functionality for adapters that use HTTP APIs:
    - API key management
    - Base URL configuration
    - Common authentication patterns
    - Standard error handling for API responses
    """
    
    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        
        # API-specific configuration
        self.api_key = self._get_api_key()
        self.base_url = self._get_base_url()
        
        # Validate API configuration
        self._validate_api_config()
    
    def _get_api_key(self) -> Optional[str]:
        """Get API key from config or environment"""
        if self.config.api_key:
            return self.config.api_key
        
        # Try environment variable
        env_var = self.get_api_key_env_var()
        if env_var:
            api_key = os.getenv(env_var)
            if api_key:
                return api_key
        
        # Some providers don't require API keys (e.g., local models)
        if self.requires_api_key():
            raise AdapterConfigurationError(
                f"API key required for {self.provider_name}",
                provider=self.provider_name
            )
        
        return None
    
    def _get_base_url(self) -> Optional[str]:
        """Get base URL from config or default"""
        if self.config.base_url:
            return self.config.base_url
        
        return self.get_default_base_url()
    
    def _validate_api_config(self) -> None:
        """Validate API-specific configuration"""
        if self.requires_api_key() and not self.api_key:
            raise AdapterConfigurationError(
                f"API key required for {self.provider_name}",
                provider=self.provider_name
            )
    
    # Abstract methods for API adapters
    
    @abstractmethod
    def get_api_key_env_var(self) -> str:
        """Get environment variable name for API key"""
        pass
    
    def get_default_base_url(self) -> Optional[str]:
        """Get default base URL (can be overridden)"""
        return None
    
    def requires_api_key(self) -> bool:
        """Whether this adapter requires an API key (can be overridden)"""
        return True


class BaseLocalAdapter(BaseAdapter):
    """
    Base class for local adapters (Ollama, Transformers, etc.)
    
    Provides common functionality for adapters that run models locally:
    - Model path management
    - Resource monitoring
    - Local configuration patterns
    """
    
    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        
        # Local-specific configuration
        self.model_path = self._get_model_path()
        self.device = self._get_device()
        
        # Validate local configuration
        self._validate_local_config()
    
    def _get_model_path(self) -> Optional[str]:
        """Get model path from config"""
        return self.config.provider_specific.get('model_path')
    
    def _get_device(self) -> str:
        """Get device configuration (CPU/GPU)"""
        return self.config.provider_specific.get('device', 'cpu')
    
    def _validate_local_config(self) -> None:
        """Validate local-specific configuration"""
        if self.requires_model_path() and not self.model_path:
            raise AdapterConfigurationError(
                f"Model path required for {self.provider_name}",
                provider=self.provider_name
            )
    
    def requires_model_path(self) -> bool:
        """Whether this adapter requires a model path (can be overridden)"""
        return True
    
    async def health_check(self) -> bool:
        """Local health check (check model availability)"""
        try:
            # Check if model path exists (for file-based models)
            if self.model_path and not os.path.exists(self.model_path):
                return False
            
            # Call parent health check
            return await super().health_check()
        except Exception:
            return False


# Export all base classes
__all__ = [
    'BaseAdapter',
    'BaseAPIAdapter', 
    'BaseLocalAdapter'
]
