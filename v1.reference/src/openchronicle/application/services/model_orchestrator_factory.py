"""
Model Orchestrator Factory - Application Layer

Provides factory methods for creating properly configured ModelOrchestrator
instances with correct dependency injection for different environments.
"""

from typing import Any

from openchronicle.domain.models.model_orchestrator import ModelOrchestrator
from openchronicle.domain.ports.registry_port import IRegistryPort


class ModelOrchestratorFactory:
    """
    Factory for creating ModelOrchestrator instances with proper dependency injection.

    This factory handles the wiring of infrastructure dependencies to domain objects,
    maintaining clean hexagonal architecture boundaries.
    """

    @staticmethod
    def create_production_orchestrator(config: dict[str, Any] | None = None) -> ModelOrchestrator:
        """
        Create a ModelOrchestrator for production use.

        Args:
            config: Optional configuration dictionary

        Returns:
            Configured ModelOrchestrator with production registry adapter
        """
        from openchronicle.infrastructure.adapters.registry_adapter import RegistryAdapter

        # Create production registry adapter
        registry_port = RegistryAdapter(models_dir="config/models/", settings_file="config/registry_settings.json")

        return ModelOrchestrator(config=config, registry_port=registry_port)

    @staticmethod
    def create_test_orchestrator(config: dict[str, Any] | None = None) -> ModelOrchestrator:
        """
        Create a ModelOrchestrator for testing.

        Args:
            config: Optional configuration dictionary

        Returns:
            Configured ModelOrchestrator with mock registry adapter
        """
        from openchronicle.infrastructure.adapters.mock_registry_adapter import MockRegistryAdapter

        # Create mock registry adapter for testing
        registry_port = MockRegistryAdapter()

        return ModelOrchestrator(config=config, registry_port=registry_port)

    @staticmethod
    def create_orchestrator_with_registry(
        registry_port: IRegistryPort, config: dict[str, Any] | None = None
    ) -> ModelOrchestrator:
        """
        Create a ModelOrchestrator with a specific registry port implementation.

        Args:
            registry_port: The registry port implementation to use
            config: Optional configuration dictionary

        Returns:
            Configured ModelOrchestrator with the provided registry port
        """
        return ModelOrchestrator(config=config, registry_port=registry_port)
