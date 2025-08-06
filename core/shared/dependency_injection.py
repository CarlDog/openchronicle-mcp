"""
Lightweight Dependency Injection Container for OpenChronicle

Part of Phase 2, Week 5-6: Dependency Injection Framework
Replaces manual dependency wiring with clean DI container pattern.

Following the OpenChronicle "No Backwards Compatibility" policy:
- Complete replacement of manual dependency wiring
- No compatibility layers for old patterns
- All orchestrators updated to use DI container
"""

import logging
from abc import ABC, abstractmethod
from typing import TypeVar, Type, Dict, Any, Optional, Callable, Union
from dataclasses import dataclass
from pathlib import Path

# Import utilities
from utilities.logging_system import log_system_event, log_info, log_error, log_warning

# Type hints
T = TypeVar('T')
ServiceFactory = Callable[[], Any]
ServiceInstance = Union[type, ServiceFactory, Any]


@dataclass
class ServiceRegistration:
    """Service registration metadata."""
    interface: Type
    implementation: ServiceInstance
    singleton: bool = False
    lazy: bool = True
    description: str = ""


class ServiceLifetime:
    """Service lifetime constants."""
    TRANSIENT = "transient"
    SINGLETON = "singleton"


class IContainer(ABC):
    """Interface for dependency injection container."""
    
    @abstractmethod
    def register(self, interface: Type[T], implementation: ServiceInstance, lifetime: str = ServiceLifetime.TRANSIENT) -> 'IContainer':
        pass
    
    @abstractmethod
    def resolve(self, interface: Type[T]) -> T:
        pass


class DIContainer(IContainer):
    """
    Lightweight Dependency Injection Container.
    
    Provides clean service registration and resolution with support for:
    - Singleton and transient lifecycles
    - Interface-based registration
    - Factory method support
    - Lazy loading
    - Circular dependency detection
    """
    
    def __init__(self):
        """Initialize the DI container."""
        self._services: Dict[Type, ServiceRegistration] = {}
        self._singletons: Dict[Type, Any] = {}
        self._resolution_stack: set = set()
        
        log_system_event("di_container_init", "Dependency injection container initialized")
    
    def register(
        self, 
        interface: Type[T], 
        implementation: ServiceInstance, 
        lifetime: str = ServiceLifetime.TRANSIENT,
        description: str = ""
    ) -> 'DIContainer':
        """
        Register a service with the container.
        
        Args:
            interface: The interface/type to register
            implementation: Class, factory, or instance to provide
            lifetime: ServiceLifetime.SINGLETON or ServiceLifetime.TRANSIENT
            description: Optional description for logging
            
        Returns:
            Self for fluent chaining
        """
        singleton = (lifetime == ServiceLifetime.SINGLETON)
        
        registration = ServiceRegistration(
            interface=interface,
            implementation=implementation,
            singleton=singleton,
            description=description
        )
        
        self._services[interface] = registration
        
        # Log registration with proper interface name handling
        interface_name = interface.__name__ if hasattr(interface, '__name__') else str(interface)
        log_info(f"Registered service: {interface_name} -> {implementation} ({lifetime})")
        
        return self
    
    def register_singleton(self, interface: Type[T], implementation: ServiceInstance, description: str = "") -> 'DIContainer':
        """Register a singleton service."""
        return self.register(interface, implementation, ServiceLifetime.SINGLETON, description)
    
    def register_transient(self, interface: Type[T], implementation: ServiceInstance, description: str = "") -> 'DIContainer':
        """Register a transient service."""
        return self.register(interface, implementation, ServiceLifetime.TRANSIENT, description)
    
    def resolve(self, interface: Type[T]) -> T:
        """
        Resolve a service from the container.
        
        Args:
            interface: The interface/type to resolve
            
        Returns:
            Instance of the requested service
            
        Raises:
            ValueError: If service not registered or circular dependency detected
        """
        # Check for circular dependencies
        if interface in self._resolution_stack:
            cycle = " -> ".join([cls.__name__ for cls in self._resolution_stack]) + f" -> {interface.__name__}"
            raise ValueError(f"Circular dependency detected: {cycle}")
        
        # Check if service is registered
        if interface not in self._services:
            available = [cls.__name__ for cls in self._services.keys()]
            raise ValueError(f"Service {interface.__name__} not registered. Available: {available}")
        
        registration = self._services[interface]
        
        # Return singleton if already created
        if registration.singleton and interface in self._singletons:
            return self._singletons[interface]
        
        # Add to resolution stack for circular dependency detection
        self._resolution_stack.add(interface)
        
        try:
            instance = self._create_instance(registration)
            
            # Store singleton
            if registration.singleton:
                self._singletons[interface] = instance
            
            return instance
            
        finally:
            # Remove from resolution stack
            self._resolution_stack.discard(interface)
    
    def resolve_optional(self, interface: Type[T]) -> Optional[T]:
        """
        Resolve a service optionally (returns None if not registered).
        
        Args:
            interface: The interface/type to resolve
            
        Returns:
            Instance of the requested service or None if not registered
        """
        try:
            return self.resolve(interface)
        except ValueError:
            return None
    
    def _create_instance(self, registration: ServiceRegistration) -> Any:
        """Create instance from registration."""
        implementation = registration.implementation
        
        # If it's already an instance, return it
        if not callable(implementation) and not isinstance(implementation, type):
            return implementation
        
        # If it's a factory function, call it
        if callable(implementation) and not isinstance(implementation, type):
            return implementation()
        
        # If it's a class, instantiate it
        if isinstance(implementation, type):
            return implementation()
        
        raise ValueError(f"Unknown implementation type: {type(implementation)}")
    
    def is_registered(self, interface: Type) -> bool:
        """Check if a service is registered."""
        return interface in self._services
    
    def get_registrations(self) -> Dict[str, Dict[str, Any]]:
        """Get all service registrations for debugging."""
        result = {}
        for interface, registration in self._services.items():
            result[interface.__name__] = {
                "implementation": getattr(registration.implementation, '__name__', str(registration.implementation)),
                "singleton": registration.singleton,
                "description": registration.description,
                "instance_created": interface in self._singletons
            }
        return result
    
    def clear(self):
        """Clear all registrations (mainly for testing)."""
        self._services.clear()
        self._singletons.clear()
        self._resolution_stack.clear()
        
        log_system_event("di_container_cleared", "DI container cleared")


# Global container instance
_global_container: Optional[DIContainer] = None


def get_container() -> DIContainer:
    """Get the global DI container instance."""
    global _global_container
    if _global_container is None:
        _global_container = DIContainer()
    return _global_container


def reset_container():
    """Reset the global container (mainly for testing)."""
    global _global_container
    _global_container = None


if __name__ == "__main__":
    # Example usage and testing
    container = DIContainer()
    
    # Example: Register a simple service
    class ILogger(ABC):
        @abstractmethod
        def log(self, message: str): pass
    
    class ConsoleLogger(ILogger):
        def log(self, message: str):
            print(f"LOG: {message}")
    
    class Service:
        def __init__(self):
            pass
    
    # Register services
    container.register_singleton(ILogger, ConsoleLogger, "Console logger")
    container.register_transient(Service, Service, "Example service")
    
    # Resolve and use
    logger = container.resolve(ILogger)
    logger.log("DI Container working!")
    
    service = container.resolve(Service)
    print(f"Service created: {service}")
    
    print("Registrations:", container.get_registrations())
