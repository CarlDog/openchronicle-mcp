"""
Adapter Interfaces - Common interfaces and type definitions for model adapters

This module defines the core interfaces that all model adapters must implement,
providing a consistent contract across different AI providers while allowing
for provider-specific customizations.

Key Components:
- ModelAdapterInterface: Core interface all adapters must implement
- AdapterConfig: Configuration structure with validation
- AdapterResponse: Standardized response format
- AdapterError: Custom exception hierarchy
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class AdapterConfig:
    """Configuration structure for model adapters with validation"""
    
    # Core configuration
    provider_name: str
    model_name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    
    # Generation parameters
    max_tokens: int = 1000
    temperature: float = 0.7
    top_p: float = 0.9
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    
    # Request configuration
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Provider-specific settings
    custom_headers: Dict[str, str] = field(default_factory=dict)
    provider_specific: Dict[str, Any] = field(default_factory=dict)
    
    # Advanced features
    supports_streaming: bool = False
    supports_function_calling: bool = False
    supports_vision: bool = False
    supports_embeddings: bool = False
    
    def validate(self) -> bool:
        """Validate configuration parameters"""
        if not self.provider_name:
            raise ValueError("provider_name is required")
        
        if not self.model_name:
            raise ValueError("model_name is required")
        
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0")
        
        if not 0.0 <= self.top_p <= 1.0:
            raise ValueError("top_p must be between 0.0 and 1.0")
        
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        
        return True


@dataclass
class AdapterResponse:
    """Standardized response format from model adapters"""
    
    # Core response data
    content: str
    model_name: str
    provider_name: str
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    tokens_used: Optional[int] = None
    finish_reason: Optional[str] = None
    
    # Cost tracking
    cost_estimate: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    
    # Performance metrics
    response_time: Optional[float] = None
    retries_used: int = 0
    
    # Provider-specific data
    raw_response: Optional[Dict[str, Any]] = None
    provider_metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Error information
    error: Optional[str] = None
    warning: Optional[str] = None


class AdapterError(Exception):
    """Base exception for adapter-related errors"""
    
    def __init__(self, message: str, provider: str = None, error_code: str = None):
        super().__init__(message)
        self.provider = provider
        self.error_code = error_code
        self.timestamp = datetime.now()


class AdapterConnectionError(AdapterError):
    """Raised when adapter cannot connect to provider"""
    pass


class AdapterAuthenticationError(AdapterError):
    """Raised when authentication with provider fails"""
    pass


class AdapterRateLimitError(AdapterError):
    """Raised when provider rate limits are exceeded"""
    pass


class AdapterConfigurationError(AdapterError):
    """Raised when adapter configuration is invalid"""
    pass


class AdapterTimeoutError(AdapterError):
    """Raised when requests to provider timeout"""
    pass


class ModelAdapterInterface(ABC):
    """
    Core interface that all model adapters must implement
    
    This interface defines the minimum required functionality for all adapters,
    using the Template Method pattern to provide common behavior while allowing
    provider-specific customizations.
    """
    
    def __init__(self, config: AdapterConfig):
        """Initialize adapter with configuration"""
        self.config = config
        self.config.validate()
        self.provider_name = config.provider_name
        self.model_name = config.model_name
        self.is_initialized = False
        self.client = None
        self.logger = logging.getLogger(f"adapter.{self.provider_name}")
    
    # Abstract methods that must be implemented by subclasses
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the adapter and establish connection"""
        pass
    
    @abstractmethod
    async def generate_response(
        self, 
        prompt: str, 
        **kwargs
    ) -> AdapterResponse:
        """Generate a response from the model"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup resources and close connections"""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the provider name (e.g., 'openai', 'anthropic')"""
        pass
    
    @abstractmethod
    def get_supported_models(self) -> List[str]:
        """Get list of models supported by this adapter"""
        pass
    
    # Optional methods with default implementations
    
    async def generate_streaming_response(
        self, 
        prompt: str, 
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response (default: not supported)"""
        if not self.config.supports_streaming:
            raise NotImplementedError(f"{self.provider_name} does not support streaming")
        
        # Fallback to non-streaming
        response = await self.generate_response(prompt, **kwargs)
        yield response.content
    
    async def generate_embeddings(
        self, 
        texts: List[str], 
        **kwargs
    ) -> List[List[float]]:
        """Generate embeddings (default: not supported)"""
        if not self.config.supports_embeddings:
            raise NotImplementedError(f"{self.provider_name} does not support embeddings")
        
        raise NotImplementedError("Embeddings not implemented for this adapter")
    
    async def health_check(self) -> bool:
        """Check if adapter is healthy and responsive"""
        try:
            # Simple health check - try to generate a minimal response
            response = await self.generate_response(
                "Hello", 
                max_tokens=1, 
                temperature=0
            )
            return response.content is not None and response.error is None
        except Exception as e:
            self.logger.warning(f"Health check failed: {e}")
            return False
    
    def get_config(self) -> AdapterConfig:
        """Get adapter configuration"""
        return self.config
    
    def update_config(self, **kwargs) -> None:
        """Update adapter configuration"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        self.config.validate()
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics (override in subclasses for actual tracking)"""
        return {
            "provider": self.provider_name,
            "model": self.model_name,
            "initialized": self.is_initialized,
            "supports_streaming": self.config.supports_streaming,
            "supports_embeddings": self.config.supports_embeddings
        }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(provider={self.provider_name}, model={self.model_name})"
    
    def __str__(self) -> str:
        return f"{self.provider_name}/{self.model_name}"


class StreamingAdapterInterface(ModelAdapterInterface):
    """Extended interface for adapters that support streaming"""
    
    @abstractmethod
    async def generate_streaming_response(
        self, 
        prompt: str, 
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response - must be implemented"""
        pass


class EmbeddingAdapterInterface(ModelAdapterInterface):
    """Extended interface for adapters that support embeddings"""
    
    @abstractmethod
    async def generate_embeddings(
        self, 
        texts: List[str], 
        **kwargs
    ) -> List[List[float]]:
        """Generate embeddings - must be implemented"""
        pass


class VisionAdapterInterface(ModelAdapterInterface):
    """Extended interface for adapters that support vision/image inputs"""
    
    @abstractmethod
    async def generate_response_with_image(
        self, 
        prompt: str, 
        image_data: Union[str, bytes], 
        **kwargs
    ) -> AdapterResponse:
        """Generate response with image input - must be implemented"""
        pass


# Type aliases for convenience
AdapterClass = type[ModelAdapterInterface]
ConfigDict = Dict[str, Any]
ResponseDict = Dict[str, Any]

# Export all public interfaces
__all__ = [
    # Core interfaces
    'ModelAdapterInterface',
    'StreamingAdapterInterface', 
    'EmbeddingAdapterInterface',
    'VisionAdapterInterface',
    
    # Data structures
    'AdapterConfig',
    'AdapterResponse',
    
    # Exceptions
    'AdapterError',
    'AdapterConnectionError',
    'AdapterAuthenticationError', 
    'AdapterRateLimitError',
    'AdapterConfigurationError',
    'AdapterTimeoutError',
    
    # Type aliases
    'AdapterClass',
    'ConfigDict',
    'ResponseDict'
]
