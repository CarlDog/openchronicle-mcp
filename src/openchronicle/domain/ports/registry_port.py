"""
Registry Port - Interface for registry operations

Defines the contract for all registry operations that the domain layer needs.
This interface is implemented by infrastructure adapters.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IRegistryPort(ABC):
    """Interface for registry operations."""

    @abstractmethod
    def get_provider_config(self, provider_name: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific provider.
        
        Args:
            provider_name: Name of the provider
            
        Returns:
            Provider configuration if found, None otherwise
        """
        pass

    @abstractmethod
    def list_providers(self) -> List[str]:
        """
        List all available providers.
        
        Returns:
            List of provider names
        """
        pass

    @abstractmethod
    def validate_config(self, provider_name: str, config: Dict[str, Any]) -> bool:
        """
        Validate provider configuration.
        
        Args:
            provider_name: Name of the provider
            config: Configuration to validate
            
        Returns:
            True if valid, False otherwise
        """
        pass

    @abstractmethod
    def register_provider(self, provider_name: str, config: Dict[str, Any]) -> bool:
        """
        Register a new provider.
        
        Args:
            provider_name: Name of the provider
            config: Provider configuration
            
        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def update_provider_config(self, provider_name: str, config: Dict[str, Any]) -> bool:
        """
        Update provider configuration.
        
        Args:
            provider_name: Name of the provider
            config: Updated configuration
            
        Returns:
            True if successful, False otherwise
        """
        pass
