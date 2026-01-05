"""
Registry Adapter - Implementation of IRegistryPort

This adapter wraps the existing infrastructure registry functions
to implement the domain interface, maintaining the dependency inversion principle.
"""

from typing import Any
from typing import Optional

from openchronicle.domain.ports.registry_port import IRegistryPort
from openchronicle.shared.logging_system import log_error
from openchronicle.shared.logging_system import log_info
from openchronicle.shared.logging_system import log_warning


class RegistryAdapter(IRegistryPort):
    """Concrete implementation of registry operations using existing infrastructure."""

    def __init__(self):
        """Initialize registry adapter."""
        # Import here to avoid circular dependencies
        try:
            from openchronicle.infrastructure.registry.registry_manager import RegistryManager
            from openchronicle.infrastructure.registry.schema_validation import validate_provider_config

            self.registry_manager = RegistryManager()
            self.validate_config_func = validate_provider_config
        except ImportError as e:
            log_warning(
                f"Registry infrastructure not available: {e}",
                context_tags=["registry", "adapter", "import", "warning"],
            )
            self.registry_manager = None
            self.validate_config_func = None

    def get_provider_config(self, provider_name: str) -> Optional[dict[str, Any]]:
        """
        Get configuration for a specific provider.

        Args:
            provider_name: Name of the provider

        Returns:
            Provider configuration if found, None otherwise
        """
        if not self.registry_manager:
            return None

        try:
            return self.registry_manager.get_provider_config(provider_name)
        except KeyError:
            log_warning(
                f"Provider config not found: {provider_name}",
                context_tags=["registry", "provider", "lookup", "missing"],
            )
            return None
        except (AttributeError, TypeError) as e:
            log_error(
                f"Configuration access error for {provider_name}: {e}",
                context_tags=["registry", "provider", "lookup", "error"],
            )
            return None
        except Exception as e:
            log_error(
                f"Unexpected error getting provider config for {provider_name}: {e}",
                context_tags=["registry", "provider", "lookup", "error"],
            )
            return None

    def list_providers(self) -> list[str]:
        """
        List all available providers.

        Returns:
            List of provider names
        """
        if not self.registry_manager:
            return []

        try:
            return self.registry_manager.list_providers()
        except (AttributeError, TypeError) as e:
            log_error(
                f"Registry access error listing providers: {e}",
                context_tags=["registry", "provider", "list", "error"],
            )
            return []
        except Exception as e:
            log_error(
                f"Unexpected error listing providers: {e}",
                context_tags=["registry", "provider", "list", "error"],
            )
            return []

    def validate_config(self, provider_name: str, config: dict[str, Any]) -> bool:
        """
        Validate provider configuration.

        Args:
            provider_name: Name of the provider
            config: Configuration to validate

        Returns:
            True if valid, False otherwise
        """
        if not self.validate_config_func:
            return True  # Assume valid if validation not available

        try:
            self.validate_config_func(config)
        except ValueError as e:  # Explicit validation error
            log_warning(
                f"Config validation failed for {provider_name}: {e}",
                context_tags=["registry", "provider", "validation", "invalid"],
            )
            return False
        except Exception as e:
            log_error(
                f"Unexpected validation error for {provider_name}: {e}",
                context_tags=["registry", "provider", "validation", "error"],
            )
            return False
        else:
            return True
            return False

    def register_provider(self, provider_name: str, config: dict[str, Any]) -> bool:
        """
        Register a new provider.

        Args:
            provider_name: Name of the provider
            config: Provider configuration

        Returns:
            True if successful, False otherwise
        """
        if not self.registry_manager:
            return False

        try:
            return self.registry_manager.register_provider(provider_name, config)
        except ValueError as e:
            log_warning(
                f"Provider registration validation failed {provider_name}: {e}",
                context_tags=["registry", "provider", "register", "invalid"],
            )
            return False
        except Exception as e:
            log_error(
                f"Error registering provider {provider_name}: {e}",
                context_tags=["registry", "provider", "register", "error"],
            )
            return False

    def update_provider_config(self, provider_name: str, config: dict[str, Any]) -> bool:
        """
        Update provider configuration.

        Args:
            provider_name: Name of the provider
            config: Updated configuration

        Returns:
            True if successful, False otherwise
        """
        if not self.registry_manager:
            return False

        try:
            return self.registry_manager.update_provider_config(provider_name, config)
        except ValueError as e:
            log_warning(
                f"Provider update validation failed {provider_name}: {e}",
                context_tags=["registry", "provider", "update", "invalid"],
            )
            return False

    def discover_providers(self) -> dict[str, list[dict[str, Any]]]:
        """Discover all providers with their model configurations."""
        if not self.registry_manager:
            return {}
        try:
            return self.registry_manager.discover_providers()  # type: ignore[attr-defined]
        except AttributeError:
            log_warning(
                "Underlying registry manager lacks discover_providers; returning empty mapping",
                context_tags=["registry", "provider", "discover", "missing"],
            )
            return {}
        except Exception as e:
            log_error(
                f"Error discovering providers: {e}",
                context_tags=["registry", "provider", "discover", "error"],
            )
            return {}
