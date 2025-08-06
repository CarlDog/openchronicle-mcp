"""
Model Management Interface Segregation

Following SOLID principles, this module splits the large ModelOrchestrator
into focused, single-responsibility interfaces.

Phase 2 Week 11-12: Interface Segregation & Architecture Cleanup
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from datetime import datetime

# === Core Data Structures ===

@dataclass
class ModelResponse:
    """Standardized model response structure."""
    content: str
    adapter_name: str
    model_name: str
    metadata: Dict[str, Any]
    timestamp: datetime
    success: bool
    error_message: Optional[str] = None

@dataclass
class AdapterStatus:
    """Adapter health and status information."""
    name: str
    is_available: bool
    is_healthy: bool
    last_health_check: datetime
    error_count: int
    success_count: int
    average_response_time: float
    metadata: Dict[str, Any]

@dataclass
class ModelConfiguration:
    """Model configuration structure."""
    provider_name: str
    model_name: str
    enabled: bool
    config: Dict[str, Any]
    fallback_chain: List[str]
    metadata: Dict[str, Any]

# === Interface Segregation ===

class IModelResponseGenerator(ABC):
    """
    Interface for model response generation.
    
    Single responsibility: Handle AI response generation and fallback logic.
    """
    
    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        adapter_name: str,
        model_params: Optional[Dict[str, Any]] = None,
        use_fallback: bool = True
    ) -> ModelResponse:
        """Generate response using specified adapter with fallback support."""
        pass
    
    @abstractmethod
    async def generate_with_fallback_chain(
        self,
        prompt: str,
        adapter_chain: List[str],
        model_params: Optional[Dict[str, Any]] = None
    ) -> ModelResponse:
        """Generate response trying each adapter in the chain until success."""
        pass
    
    @abstractmethod
    def get_fallback_chain(self, adapter_name: str) -> List[str]:
        """Get fallback chain for specified adapter."""
        pass

class IModelLifecycleManager(ABC):
    """
    Interface for model adapter lifecycle management.
    
    Single responsibility: Manage adapter initialization, health, and cleanup.
    """
    
    @abstractmethod
    async def initialize_adapter(self, adapter_name: str, max_retries: int = 2) -> bool:
        """Initialize a specific adapter with retry logic."""
        pass
    
    @abstractmethod
    async def initialize_all_adapters(self, max_concurrent: int = 3) -> Dict[str, bool]:
        """Initialize all configured adapters with concurrency control."""
        pass
    
    @abstractmethod
    async def health_check_adapter(self, adapter_name: str) -> AdapterStatus:
        """Perform health check on specific adapter."""
        pass
    
    @abstractmethod
    async def health_check_all_adapters(self) -> Dict[str, AdapterStatus]:
        """Perform health checks on all adapters."""
        pass
    
    @abstractmethod
    async def shutdown_adapter(self, adapter_name: str) -> bool:
        """Gracefully shutdown specific adapter."""
        pass
    
    @abstractmethod
    async def restart_adapter(self, adapter_name: str) -> bool:
        """Restart specific adapter with health validation."""
        pass
    
    @abstractmethod
    def is_adapter_available(self, adapter_name: str) -> bool:
        """Check if adapter is available for use."""
        pass
    
    @abstractmethod
    def is_adapter_healthy(self, adapter_name: str) -> bool:
        """Check if adapter is healthy and responsive."""
        pass

class IModelConfigurationManager(ABC):
    """
    Interface for model configuration management.
    
    Single responsibility: Handle model configuration CRUD operations.
    """
    
    @abstractmethod
    def get_model_configuration(self, provider_name: str) -> Optional[ModelConfiguration]:
        """Get configuration for specific model provider."""
        pass
    
    @abstractmethod
    def add_model_configuration(self, config: ModelConfiguration) -> bool:
        """Add new model configuration."""
        pass
    
    @abstractmethod
    def update_model_configuration(self, provider_name: str, updates: Dict[str, Any]) -> bool:
        """Update existing model configuration."""
        pass
    
    @abstractmethod
    def remove_model_configuration(self, provider_name: str) -> bool:
        """Remove model configuration."""
        pass
    
    @abstractmethod
    def validate_model_configuration(self, config: ModelConfiguration) -> bool:
        """Validate model configuration structure and values."""
        pass
    
    @abstractmethod
    def enable_model(self, provider_name: str) -> bool:
        """Enable specific model for use."""
        pass
    
    @abstractmethod
    def disable_model(self, provider_name: str) -> bool:
        """Disable specific model."""
        pass
    
    @abstractmethod
    def get_enabled_models(self) -> List[str]:
        """Get list of enabled model names."""
        pass
    
    @abstractmethod
    def get_available_models(self) -> Dict[str, ModelConfiguration]:
        """Get all available model configurations."""
        pass
    
    @abstractmethod
    def export_configuration(self, output_path: Optional[str] = None) -> str:
        """Export current configuration to file."""
        pass
    
    @abstractmethod
    def import_configuration(self, config_path: str) -> bool:
        """Import configuration from file."""
        pass

class IModelPerformanceMonitor(ABC):
    """
    Interface for model performance monitoring and analytics.
    
    Single responsibility: Track metrics, analytics, and performance monitoring.
    """
    
    @abstractmethod
    def record_response_time(self, adapter_name: str, response_time: float) -> None:
        """Record response time for performance tracking."""
        pass
    
    @abstractmethod
    def record_success(self, adapter_name: str, prompt_length: int, response_length: int) -> None:
        """Record successful operation metrics."""
        pass
    
    @abstractmethod
    def record_failure(self, adapter_name: str, error_type: str, error_message: str) -> None:
        """Record failure metrics for analysis."""
        pass
    
    @abstractmethod
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get overall performance statistics."""
        pass
    
    @abstractmethod
    def get_adapter_metrics(self, adapter_name: str) -> Dict[str, Any]:
        """Get performance metrics for specific adapter."""
        pass
    
    @abstractmethod
    def get_success_rate(self, adapter_name: str, window_hours: int = 24) -> float:
        """Get success rate for adapter in time window."""
        pass
    
    @abstractmethod
    def get_average_response_time(self, adapter_name: str, window_hours: int = 24) -> float:
        """Get average response time for adapter in time window."""
        pass
    
    @abstractmethod
    def get_error_analysis(self, adapter_name: str, window_hours: int = 24) -> Dict[str, Any]:
        """Get error analysis for adapter in time window."""
        pass
    
    @abstractmethod
    def start_monitoring(self) -> None:
        """Start background performance monitoring."""
        pass
    
    @abstractmethod
    def stop_monitoring(self) -> None:
        """Stop background performance monitoring."""
        pass
    
    @abstractmethod
    def generate_performance_report(self, output_path: Optional[str] = None) -> str:
        """Generate comprehensive performance report."""
        pass

# === Composite Interface (Facade Pattern) ===

class IModelOrchestrator(ABC):
    """
    Composite interface that provides access to all model management capabilities.
    
    This serves as a facade for the segregated interfaces, maintaining
    backward compatibility while enabling focused interface usage.
    """
    
    @property
    @abstractmethod
    def response_generator(self) -> IModelResponseGenerator:
        """Access to response generation interface."""
        pass
    
    @property
    @abstractmethod
    def lifecycle_manager(self) -> IModelLifecycleManager:
        """Access to lifecycle management interface."""
        pass
    
    @property
    @abstractmethod
    def configuration_manager(self) -> IModelConfigurationManager:
        """Access to configuration management interface."""
        pass
    
    @property
    @abstractmethod
    def performance_monitor(self) -> IModelPerformanceMonitor:
        """Access to performance monitoring interface."""
        pass
    
    # Convenience methods that delegate to appropriate interfaces
    @abstractmethod
    async def generate_response(self, prompt: str, adapter_name: str, **kwargs) -> ModelResponse:
        """Convenience method for response generation."""
        pass
    
    @abstractmethod
    async def initialize_adapter(self, adapter_name: str) -> bool:
        """Convenience method for adapter initialization."""
        pass
    
    @abstractmethod
    def get_adapter_status(self, adapter_name: str) -> AdapterStatus:
        """Convenience method for adapter status."""
        pass
    
    @abstractmethod
    def add_model_config(self, provider_name: str, config: Dict[str, Any]) -> bool:
        """Convenience method for adding model configuration."""
        pass

# === Service Discovery Interface ===

class IModelServiceDiscovery(ABC):
    """
    Interface for discovering and resolving model management services.
    
    Enables dependency injection and service location patterns.
    """
    
    @abstractmethod
    def get_response_generator(self) -> IModelResponseGenerator:
        """Get response generator service."""
        pass
    
    @abstractmethod
    def get_lifecycle_manager(self) -> IModelLifecycleManager:
        """Get lifecycle manager service."""
        pass
    
    @abstractmethod
    def get_configuration_manager(self) -> IModelConfigurationManager:
        """Get configuration manager service."""
        pass
    
    @abstractmethod
    def get_performance_monitor(self) -> IModelPerformanceMonitor:
        """Get performance monitor service."""
        pass
    
    @abstractmethod
    def register_service(self, interface_type: type, implementation: Any) -> None:
        """Register service implementation for interface."""
        pass
    
    @abstractmethod
    def resolve_service(self, interface_type: type) -> Any:
        """Resolve service implementation for interface."""
        pass

# === Interface Factory ===

class ModelInterfaceFactory:
    """
    Factory for creating segregated model management interfaces.
    
    Provides centralized creation and configuration of interface implementations.
    """
    
    @staticmethod
    def create_response_generator(config: Dict[str, Any]) -> IModelResponseGenerator:
        """Create response generator implementation."""
        from .response_generator import ResponseGenerator
        return ResponseGenerator(config)
    
    @staticmethod
    def create_lifecycle_manager(config: Dict[str, Any]) -> IModelLifecycleManager:
        """Create lifecycle manager implementation."""
        from .lifecycle_manager import LifecycleManager
        return LifecycleManager(config)
    
    @staticmethod
    def create_configuration_manager(config: Dict[str, Any]) -> IModelConfigurationManager:
        """Create configuration manager implementation."""
        from .configuration_manager import ConfigurationManager
        return ConfigurationManager(config)
    
    @staticmethod
    def create_performance_monitor(config: Dict[str, Any]) -> IModelPerformanceMonitor:
        """Create performance monitor implementation."""
        from .performance_monitor import PerformanceMonitor
        return PerformanceMonitor(config)
    
    @staticmethod
    def create_orchestrator(config: Dict[str, Any]) -> IModelOrchestrator:
        """Create complete orchestrator with all interfaces."""
        from .model_orchestrator import ModelOrchestrator
        return ModelOrchestrator(config)
