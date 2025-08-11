"""
Registry adapter implementing domain ports.
Infrastructure implementation of registry operations.
"""
from typing import Dict, Any, Optional, List
from src.openchronicle.domain.ports.registry_port import IRegistryPort

# Safe import of infrastructure component
try:
    from src.openchronicle.infrastructure.registry.registry_manager import RegistryManager
except ImportError:
    RegistryManager = None


class RegistryAdapter(IRegistryPort):
    """Infrastructure adapter for registry operations."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize registry adapter."""
        if RegistryManager is None:
            raise RuntimeError("RegistryManager not available. Check infrastructure.registry imports.")
        
        self.registry_manager = RegistryManager(
            config_path=config_path,
            auto_discover=True
        )
    
    async def discover_models(self) -> List[Dict[str, Any]]:
        """Discover available models."""
        try:
            # Call the registry manager's discovery method
            return await self.registry_manager.discover_models()
        except Exception as e:
            # Graceful fallback
            return []
    
    async def get_model_config(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific model."""
        try:
            return await self.registry_manager.get_model_config(model_name)
        except Exception:
            return None
    
    async def register_model(self, model_config: Dict[str, Any]) -> bool:
        """Register a new model configuration."""
        try:
            return await self.registry_manager.register_model(model_config)
        except Exception:
            return False
    
    def get_registry_manager(self):
        """Get underlying registry manager (for migration compatibility)."""
        return self.registry_manager
