"""
Model Management Interface Segregation

Following SOLID principles, this module splits the large ModelOrchestrator
into focused, single-responsibility interfaces.

Phase 2 Week 11-12: Interface Segregation & Architecture Cleanup
"""

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


# === Core Data Structures ===


@dataclass
class ModelResponse:
    """Standardized model response structure."""

    content: str
    adapter_name: str
    model_name: str
    metadata: dict[str, Any]
    timestamp: datetime
    success: bool
    error_message: str | None = None


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
    metadata: dict[str, Any]


@dataclass
class ModelConfiguration:
    """Model configuration structure."""

    provider_name: str
    model_name: str
    enabled: bool
    config: dict[str, Any]
    fallback_chain: list[str]
    metadata: dict[str, Any]


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
        model_params: dict[str, Any] | None = None,
        use_fallback: bool = True,
    ) -> ModelResponse:
        """Generate response using specified adapter with fallback support."""

    @abstractmethod
    async def generate_with_fallback_chain(
        self,
        prompt: str,
        adapter_chain: list[str],
        model_params: dict[str, Any] | None = None,
    ) -> ModelResponse:
        """Generate response trying each adapter in the chain until success."""

    @abstractmethod
    def get_fallback_chain(self, adapter_name: str) -> list[str]:
        """Get fallback chain for specified adapter."""


class IModelLifecycleManager(ABC):
    """
    Interface for model adapter lifecycle management.

    Single responsibility: Manage adapter initialization, health, and cleanup.
    """

    @abstractmethod
    async def initialize_adapter(self, adapter_name: str, max_retries: int = 2) -> bool:
        """Initialize a specific adapter with retry logic."""

    @abstractmethod
    async def initialize_all_adapters(self, max_concurrent: int = 3) -> dict[str, bool]:
        """Initialize all configured adapters with concurrency control."""

    @abstractmethod
    async def health_check_adapter(self, adapter_name: str) -> AdapterStatus:
        """Perform health check on specific adapter."""

    @abstractmethod
    async def health_check_all_adapters(self) -> dict[str, AdapterStatus]:
        """Perform health checks on all adapters."""

    @abstractmethod
    async def shutdown_adapter(self, adapter_name: str) -> bool:
        """Gracefully shutdown specific adapter."""

    @abstractmethod
    async def restart_adapter(self, adapter_name: str) -> bool:
        """Restart specific adapter with health validation."""

    @abstractmethod
    def is_adapter_available(self, adapter_name: str) -> bool:
        """Check if adapter is available for use."""

    @abstractmethod
    def is_adapter_healthy(self, adapter_name: str) -> bool:
        """Check if adapter is healthy and responsive."""


class IModelConfigurationManager(ABC):
    """
    Interface for model configuration management.

    Single responsibility: Handle model configuration CRUD operations.
    """

    @abstractmethod
    def get_model_configuration(
        self, provider_name: str
    ) -> ModelConfiguration | None:
        """Get configuration for specific model provider."""

    @abstractmethod
    def add_model_configuration(self, config: ModelConfiguration) -> bool:
        """Add new model configuration."""

    @abstractmethod
    def update_model_configuration(
        self, provider_name: str, updates: dict[str, Any]
    ) -> bool:
        """Update existing model configuration."""

    @abstractmethod
    def remove_model_configuration(self, provider_name: str) -> bool:
        """Remove model configuration."""

    @abstractmethod
    def validate_model_configuration(self, config: ModelConfiguration) -> bool:
        """Validate model configuration structure and values."""

    @abstractmethod
    def enable_model(self, provider_name: str) -> bool:
        """Enable specific model for use."""

    @abstractmethod
    def disable_model(self, provider_name: str) -> bool:
        """Disable specific model."""

    @abstractmethod
    def get_enabled_models(self) -> list[str]:
        """Get list of enabled model names."""

    @abstractmethod
    def get_available_models(self) -> dict[str, ModelConfiguration]:
        """Get all available model configurations."""

    @abstractmethod
    def export_configuration(self, output_path: str | None = None) -> str:
        """Export current configuration to file."""

    @abstractmethod
    def import_configuration(self, config_path: str) -> bool:
        """Import configuration from file."""


class IModelPerformanceMonitor(ABC):
    """
    Interface for model performance monitoring and analytics.

    Single responsibility: Track metrics, analytics, and performance monitoring.
    """

    @abstractmethod
    def record_response_time(self, adapter_name: str, response_time: float) -> None:
        """Record response time for performance tracking."""

    @abstractmethod
    def record_success(
        self, adapter_name: str, prompt_length: int, response_length: int
    ) -> None:
        """Record successful operation metrics."""

    @abstractmethod
    def record_failure(
        self, adapter_name: str, error_type: str, error_message: str
    ) -> None:
        """Record failure metrics for analysis."""

    @abstractmethod
    def get_performance_stats(self) -> dict[str, Any]:
        """Get overall performance statistics."""

    @abstractmethod
    def get_adapter_metrics(self, adapter_name: str) -> dict[str, Any]:
        """Get performance metrics for specific adapter."""

    @abstractmethod
    def get_success_rate(self, adapter_name: str, window_hours: int = 24) -> float:
        """Get success rate for adapter in time window."""

    @abstractmethod
    def get_average_response_time(
        self, adapter_name: str, window_hours: int = 24
    ) -> float:
        """Get average response time for adapter in time window."""

    @abstractmethod
    def get_error_analysis(
        self, adapter_name: str, window_hours: int = 24
    ) -> dict[str, Any]:
        """Get error analysis for adapter in time window."""

    @abstractmethod
    def start_monitoring(self) -> None:
        """Start background performance monitoring."""

    @abstractmethod
    def stop_monitoring(self) -> None:
        """Stop background performance monitoring."""

    @abstractmethod
    def generate_performance_report(self, output_path: str | None = None) -> str:
        """Generate comprehensive performance report."""


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

    @property
    @abstractmethod
    def lifecycle_manager(self) -> IModelLifecycleManager:
        """Access to lifecycle management interface."""

    @property
    @abstractmethod
    def configuration_manager(self) -> IModelConfigurationManager:
        """Access to configuration management interface."""

    @property
    @abstractmethod
    def performance_monitor(self) -> IModelPerformanceMonitor:
        """Access to performance monitoring interface."""

    # Convenience methods that delegate to appropriate interfaces
    @abstractmethod
    async def generate_response(
        self, prompt: str, adapter_name: str, **kwargs
    ) -> ModelResponse:
        """Convenience method for response generation."""

    @abstractmethod
    async def initialize_adapter(self, adapter_name: str) -> bool:
        """Convenience method for adapter initialization."""

    @abstractmethod
    def get_adapter_status(self, adapter_name: str) -> AdapterStatus:
        """Convenience method for adapter status."""

    @abstractmethod
    def add_model_config(self, provider_name: str, config: dict[str, Any]) -> bool:
        """Convenience method for adding model configuration."""


# === Service Discovery Interface ===


class IModelServiceDiscovery(ABC):
    """
    Interface for discovering and resolving model management services.

    Enables dependency injection and service location patterns.
    """

    @abstractmethod
    def get_response_generator(self) -> IModelResponseGenerator:
        """Get response generator service."""

    @abstractmethod
    def get_lifecycle_manager(self) -> IModelLifecycleManager:
        """Get lifecycle manager service."""

    @abstractmethod
    def get_configuration_manager(self) -> IModelConfigurationManager:
        """Get configuration manager service."""

    @abstractmethod
    def get_performance_monitor(self) -> IModelPerformanceMonitor:
        """Get performance monitor service."""

    @abstractmethod
    def register_service(self, interface_type: type, implementation: Any) -> None:
        """Register service implementation for interface."""

    @abstractmethod
    def resolve_service(self, interface_type: type) -> Any:
        """Resolve service implementation for interface."""


# === Interface Factory ===


class ModelInterfaceFactory:
    """
    Factory for creating segregated model management interfaces.

    Provides centralized creation and configuration of interface implementations.
    """

    @staticmethod
    def create_response_generator(config: dict[str, Any]) -> IModelResponseGenerator:
        """Create response generator implementation."""
        from .response_generator import ResponseGenerator

        return ResponseGenerator(config)

    @staticmethod
    def create_lifecycle_manager(config: dict[str, Any]) -> IModelLifecycleManager:
        """Create lifecycle manager implementation."""
        from .lifecycle_manager import LifecycleManager

        return LifecycleManager(config)

    @staticmethod
    def create_configuration_manager(
        config: dict[str, Any],
    ) -> IModelConfigurationManager:
        """Create configuration manager implementation."""
        from .configuration_manager import ConfigurationManager

        return ConfigurationManager(config)

    @staticmethod
    def create_performance_monitor(config: dict[str, Any]) -> IModelPerformanceMonitor:
        """Create performance monitor implementation using dependency injection."""
        # Import here to avoid circular dependencies
        try:
            from src.openchronicle.infrastructure.persistence_adapters.performance_adapter import PerformanceAdapter
            return PerformanceAdapter()
        except ImportError:
            # Fallback mock implementation for development/testing
            from src.openchronicle.domain.models.mock_implementations import MockPerformanceMonitor
            return MockPerformanceMonitor(config)

    @staticmethod
    def create_orchestrator(config: dict[str, Any]) -> IModelOrchestrator:
        """Create complete orchestrator with all interfaces."""
        from .model_orchestrator import ModelOrchestrator

        return ModelOrchestrator(config)
