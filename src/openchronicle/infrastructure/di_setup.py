"""
Dependency injection setup for hexagonal architecture.
Wire domain ports to infrastructure adapters.
"""
from openchronicle.domain.ports.registry_port import IRegistryPort
from openchronicle.domain.ports.persistence_port import IPersistencePort
from openchronicle.infrastructure.adapters.registry_adapter import RegistryAdapter
from openchronicle.infrastructure.adapters.persistence_adapter import PersistenceAdapter


class DIContainer:
    """Simple dependency injection container."""
    
    def __init__(self):
        self._registry_port = None
        self._persistence_port = None
    
    def get_registry_port(self, config_path: str = None) -> IRegistryPort:
        """Get registry port implementation."""
        if self._registry_port is None:
            self._registry_port = RegistryAdapter(config_path=config_path)
        return self._registry_port
    
    def get_persistence_port(self, storage_path: str = None) -> IPersistencePort:
        """Get persistence port implementation."""
        if self._persistence_port is None:
            self._persistence_port = PersistenceAdapter(storage_path=storage_path)
        return self._persistence_port


# Global DI container instance
_container = DIContainer()


def get_registry_port(config_path: str = None) -> IRegistryPort:
    """Get registry port from DI container."""
    return _container.get_registry_port(config_path)


def get_persistence_port(storage_path: str = None) -> IPersistencePort:
    """Get persistence port from DI container."""
    return _container.get_persistence_port(storage_path)
