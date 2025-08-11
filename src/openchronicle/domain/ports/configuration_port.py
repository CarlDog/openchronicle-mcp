"""
Configuration port for domain layer.
Abstract interface for configuration management without infrastructure dependencies.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class IConfigurationPort(ABC):
    """Port for configuration management in domain layer."""
    
    @abstractmethod
    async def get_config(self, key: str) -> Optional[Any]:
        """Get configuration value by key."""
        pass
    
    @abstractmethod
    async def set_config(self, key: str, value: Any) -> bool:
        """Set configuration value."""
        pass
    
    @abstractmethod
    async def get_all_configs(self) -> Dict[str, Any]:
        """Get all configuration values."""
        pass
