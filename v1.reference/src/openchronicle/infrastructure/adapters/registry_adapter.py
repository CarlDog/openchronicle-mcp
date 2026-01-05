"""
Registry Adapter - Infrastructure Implementation

Implements the registry port interface using the concrete registry manager.
This adapter sits in the infrastructure layer and implements the domain port.
"""

from typing import Any
from typing import Optional

from openchronicle.domain.ports.registry_port import IRegistryPort
from openchronicle.shared.logging_system import log_error
from openchronicle.shared.logging_system import log_warning


# Safe import of infrastructure component
try:
    from openchronicle.infrastructure.registry.registry_manager import RegistryManager
except ImportError:
    RegistryManager = None


class RegistryAdapter(IRegistryPort):
    """
    Infrastructure adapter that implements the registry port interface.

    This adapter bridges the domain port interface with the concrete
    infrastructure implementation (RegistryManager).
    """

    def __init__(self, models_dir: str = "config/models/", settings_file: str = "config/registry_settings.json"):
        """
        Initialize the registry adapter.

        Args:
            models_dir: Directory containing model configurations
            settings_file: Path to registry settings file
        """
        if RegistryManager is None:
            raise RuntimeError("RegistryManager not available. Check infrastructure.registry imports.")

        self._manager = RegistryManager(models_dir=models_dir, settings_file=settings_file)

    def get_provider_config(self, provider_name: str) -> Optional[dict[str, Any]]:
        """Get configuration for a specific provider."""
        try:
            return self._manager.get_provider_config(provider_name)
        except (RuntimeError, AttributeError, OSError, ValueError, KeyError, TypeError) as e:
            log_warning(f"get_provider_config failed for '{provider_name}': {e}")
            return None

    def list_providers(self) -> list[str]:
        """List all available providers."""
        try:
            return self._manager.list_providers()
        except (RuntimeError, AttributeError, OSError, ValueError, KeyError, TypeError) as e:
            log_warning(f"list_providers failed: {e}")
            return []

    def validate_config(self, provider_name: str, config: dict[str, Any]) -> bool:
        """
        Validate provider configuration.

        Args:
            provider_name: Name of the provider
            config: Configuration to validate

        Returns:
            True if valid

        Raises:
            ValueError: If configuration is invalid
        """

        def _raise_missing_fields_error(missing_fields):
            raise ValueError(f"Missing required fields: {missing_fields}")

        try:
            # Basic validation for required fields
            required_fields = ["name", "type"]
            missing_fields = [field for field in required_fields if field not in config]
            if missing_fields:
                _raise_missing_fields_error(missing_fields)
        except (ValueError, TypeError) as e:
            log_error(f"validate_config failed for '{provider_name}': {e}")
            raise
        else:
            return True

    def register_provider(self, provider_name: str, config: dict[str, Any]) -> bool:
        """Register a new provider."""
        try:
            return self._manager.register_provider(provider_name, config)
        except (RuntimeError, AttributeError, OSError, ValueError, KeyError, TypeError) as e:
            log_error(f"register_provider failed for '{provider_name}': {e}")
            return False

    def update_provider_config(self, provider_name: str, config: dict[str, Any]) -> bool:
        """Update provider configuration."""
        try:
            return self._manager.update_provider_config(provider_name, config)
        except (RuntimeError, AttributeError, OSError, ValueError, KeyError, TypeError) as e:
            log_error(f"update_provider_config failed for '{provider_name}': {e}")
            return False

    def discover_providers(self) -> dict[str, list[dict[str, Any]]]:
        """Discover all providers and their configurations."""
        try:
            return self._manager.discover_providers()
        except (RuntimeError, AttributeError, OSError, ValueError, KeyError, TypeError) as e:
            log_warning(f"discover_providers failed: {e}")
            return {}
