"""
Domain Ports - Interface definitions for hexagonal architecture

This module defines the ports (interfaces) that the domain layer uses
to interact with external systems. These interfaces are implemented
by adapters in the infrastructure layer.

Following the dependency inversion principle:
- Domain defines the interfaces it needs
- Infrastructure implements these interfaces
- Domain never imports from infrastructure
"""

from .configuration_port import IConfigurationPort
from .memory_port import IMemoryPort
from .performance_interface_port import IPerformanceInterfacePort
from .performance_port import IPerformancePort
from .persistence_port import IPersistencePort
from .registry_port import IRegistryPort
from .storage_port import IStoragePort
from .storypack_port import IStorypackProcessorPort


__all__ = [
    "IConfigurationPort",
    "IMemoryPort",
    "IPerformanceInterfacePort",
    "IPerformancePort",
    "IPersistencePort",
    "IRegistryPort",
    "IStoragePort",
    "IStorypackProcessorPort",
]
