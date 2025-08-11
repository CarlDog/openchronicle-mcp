"""
Registry Adapter - Implementation of IRegistryPort

This adapter wraps the existing infrastructure registry functions
to implement the domain interface, maintaining the dependency inversion principle.
"""

from typing import Any, Dict, List, Optional

from src.openchronicle.domain.ports.registry_port import IRegistryPort


class RegistryAdapter(IRegistryPort):
    """Concrete implementation of registry operations using existing infrastructure."""

    def __init__(self):
        """Initialize registry adapter."""
        # Import here to avoid circular dependencies
        try:
            from src.openchronicle.infrastructure.registry.registry_manager import RegistryManager
            from src.openchronicle.infrastructure.registry.schema_validation import validate_provider_config
            self.registry_manager = RegistryManager()
            self.validate_config_func = validate_provider_config
        except ImportError as e:
            print(f"Registry infrastructure not available: {e}")
            self.registry_manager = None
            self.validate_config_func = None

    def get_provider_config(self, provider_name: str) -> Optional[Dict[str, Any]]:
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
        except Exception as e:
            print(f"Error getting provider config for {provider_name}: {e}")
            return None

    def list_providers(self) -> List[str]:
        """
        List all available providers.
        
        Returns:
            List of provider names
        """
        if not self.registry_manager:
            return []
            
        try:
            return self.registry_manager.list_providers()
        except Exception as e:
            print(f"Error listing providers: {e}")
            return []

    def validate_config(self, provider_name: str, config: Dict[str, Any]) -> bool:
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
            return True
        except Exception as e:
            print(f"Config validation failed for {provider_name}: {e}")
            return False

    def register_provider(self, provider_name: str, config: Dict[str, Any]) -> bool:
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
        except Exception as e:
            print(f"Error registering provider {provider_name}: {e}")
            return False

    def update_provider_config(self, provider_name: str, config: Dict[str, Any]) -> bool:
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
        except Exception as e:
            print(f"Error updating provider config for {provider_name}: {e}")
            return False
