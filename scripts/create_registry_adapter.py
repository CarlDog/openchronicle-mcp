"""
Create registry adapter to fix domain layer violation.
This fixes the main architecture violation in configuration_manager.py
"""
from pathlib import Path


def create_registry_adapter():
    """Create infrastructure adapter for registry operations."""
    
    root_path = Path(__file__).parent.parent
    
    # 1. Create infrastructure adapter
    adapter_path = root_path / "src" / "openchronicle" / "infrastructure" / "adapters" / "registry_adapter.py"
    adapter_path.parent.mkdir(exist_ok=True)
    
    adapter_content = '''"""
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
'''
    
    adapter_path.write_text(adapter_content, encoding='utf-8')
    print(f"✅ Created registry adapter: {adapter_path.relative_to(root_path)}")
    
    # 2. Update domain configuration manager
    config_manager_path = root_path / "src" / "openchronicle" / "domain" / "models" / "configuration_manager.py"
    
    if config_manager_path.exists():
        content = config_manager_path.read_text(encoding='utf-8')
        
        # Replace the infrastructure import
        old_import = """# Local import to avoid hard dependency at module import time
try:
    from src.openchronicle.infrastructure.registry.registry_manager import (
        RegistryManager,
    )
except Exception:  # pragma: no cover - optional in some environments
    RegistryManager = None  # type: ignore"""
    
        new_import = """# Use domain port for registry operations (hexagonal architecture compliance)
from src.openchronicle.domain.ports.registry_port import IRegistryPort
from typing import Optional"""
        
        if old_import in content:
            content = content.replace(old_import, new_import)
            
            # Update the class to use dependency injection
            old_init_pattern = """        # Use existing RegistryManager for dynamic discovery
        if RegistryManager is None:
            raise ImportError(
                "RegistryManager not available. Ensure infrastructure.registry is importable."
            )
        self.registry_manager = RegistryManager(
            config_path=config_path,
            auto_discover=auto_discover,
        )"""
        
            new_init_pattern = """        # Use dependency injection for registry operations (hexagonal architecture)
        if registry_port is None:
            raise ValueError(
                "registry_port is required. Inject IRegistryPort implementation."
            )
        self.registry_port = registry_port"""
        
            content = content.replace(old_init_pattern, new_init_pattern)
            
            # Update method signatures to accept registry_port
            old_signature = "    def __init__(self, config_path: str = None, auto_discover: bool = True):"
            new_signature = "    def __init__(self, registry_port: IRegistryPort, config_path: str = None, auto_discover: bool = True):"
            
            content = content.replace(old_signature, new_signature)
            
            config_manager_path.write_text(content, encoding='utf-8')
            print(f"✅ Updated configuration manager to use dependency injection")
        else:
            print(f"⚠️ Could not find import pattern to replace in {config_manager_path}")
    
    # 3. Create dependency injection setup
    di_setup_path = root_path / "src" / "openchronicle" / "infrastructure" / "di_setup.py"
    
    di_content = '''"""
Dependency injection setup for hexagonal architecture.
Wire domain ports to infrastructure adapters.
"""
from src.openchronicle.domain.ports.registry_port import IRegistryPort
from src.openchronicle.infrastructure.adapters.registry_adapter import RegistryAdapter


class DIContainer:
    """Simple dependency injection container."""
    
    def __init__(self):
        self._registry_port = None
    
    def get_registry_port(self, config_path: str = None) -> IRegistryPort:
        """Get registry port implementation."""
        if self._registry_port is None:
            self._registry_port = RegistryAdapter(config_path=config_path)
        return self._registry_port


# Global DI container instance
_container = DIContainer()


def get_registry_port(config_path: str = None) -> IRegistryPort:
    """Get registry port from DI container."""
    return _container.get_registry_port(config_path)
'''
    
    di_setup_path.write_text(di_content, encoding='utf-8')
    print(f"✅ Created dependency injection setup: {di_setup_path.relative_to(root_path)}")
    
    print("\n🎯 Next Steps:")
    print("1. Update code that creates ConfigurationManager to inject registry_port")
    print("2. Run validation: python scripts/validate_hexagonal_tests.py")
    print("3. Test that configuration discovery still works")


if __name__ == "__main__":
    create_registry_adapter()
