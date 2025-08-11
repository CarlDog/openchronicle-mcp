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

from .persistence_port import IPersistencePort
from .memory_port import IMemoryPort
from .storage_port import IStoragePort
from .registry_port import IRegistryPort
from .performance_port import IPerformancePort

__all__ = [
    "IPersistencePort",
    "IMemoryPort", 
    "IStoragePort",
    "IRegistryPort",
    "IPerformancePort"
]
