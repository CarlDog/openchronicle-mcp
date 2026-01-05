"""
Mock Registry Adapter - Test Implementation

Provides a mock implementation of the registry port interface for testing.
This allows tests to run without requiring the actual infrastructure.
"""

from typing import Any
from typing import Optional

from openchronicle.domain.ports.registry_port import IRegistryPort


class MockRegistryAdapter(IRegistryPort):
    """
    Mock implementation of the registry port interface for testing.

    Provides predictable responses without requiring actual infrastructure.
    """

    def __init__(self):
        """Initialize the mock registry adapter."""
        self._providers = {
            "mock_provider": {"enabled": True, "models": ["mock_model_1", "mock_model_2"]},
            "test_provider": {"enabled": True, "models": ["test_model"]},
        }

    def get_provider_config(self, provider_name: str) -> Optional[dict[str, Any]]:
        """Get configuration for a specific provider."""
        return self._providers.get(provider_name)

    def list_providers(self) -> list[str]:
        """List all available providers."""
        return list(self._providers.keys())

    def validate_config(self, provider_name: str, config: dict[str, Any]) -> bool:
        """Validate provider configuration."""
        # Mock validation - just check for basic structure
        required_fields = ["enabled"]
        return all(field in config for field in required_fields)

    def register_provider(self, provider_name: str, config: dict[str, Any]) -> bool:
        """Register a new provider."""
        self._providers[provider_name] = config
        return True

    def update_provider_config(self, provider_name: str, config: dict[str, Any]) -> bool:
        """Update provider configuration."""
        if provider_name in self._providers:
            self._providers[provider_name].update(config)
            return True
        return False

    def discover_providers(self) -> dict[str, list[dict[str, Any]]]:
        """Discover all providers and their configurations."""
        return {
            provider_name: [{"name": model, "type": "mock"} for model in config.get("models", [])]
            for provider_name, config in self._providers.items()
        }
