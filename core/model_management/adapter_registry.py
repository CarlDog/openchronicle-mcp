"""
Adapter Registry and Factory - Dynamic adapter management system

This module implements the Factory pattern for creating and managing model adapters,
supporting dynamic registration, discovery, and lifecycle management.

Key Components:
- AdapterRegistry: Central registry for all available adapters
- AdapterFactory: Factory for creating adapter instances
- AdapterLoader: Dynamic loading of adapter modules
- AdapterValidator: Validation of adapter implementations

Features:
- Dynamic adapter discovery and registration
- Plugin-style adapter loading from multiple sources
- Adapter lifecycle management (create, initialize, cleanup)
- Configuration validation and defaults
- Health monitoring and metrics collection
"""

import importlib
import inspect
import logging
from typing import Dict, Any, Optional, List, Type, Union, Set
from pathlib import Path
from dataclasses import dataclass
import asyncio

from .adapter_interfaces import (
    ModelAdapterInterface, AdapterConfig, AdapterError,
    AdapterConfigurationError, AdapterClass
)
from .base_adapter import BaseAdapter, BaseAPIAdapter, BaseLocalAdapter
from ..shared.json_utilities import JSONUtilities

logger = logging.getLogger(__name__)


@dataclass
class AdapterInfo:
    """Information about a registered adapter"""
    name: str
    adapter_class: AdapterClass
    description: str
    supported_models: List[str]
    capabilities: Dict[str, bool]
    default_config: Dict[str, Any]
    module_path: str
    version: str = "1.0.0"


class AdapterValidator:
    """Validates adapter implementations against required interfaces"""
    
    @staticmethod
    def validate_adapter_class(adapter_class: Type) -> bool:
        """Validate that a class is a proper adapter implementation"""
        # Check inheritance
        if not issubclass(adapter_class, ModelAdapterInterface):
            raise ValueError(f"Adapter must inherit from ModelAdapterInterface")
        
        # Check required abstract methods are implemented
        required_methods = [
            'initialize',
            'generate_response', 
            'cleanup',
            'get_provider_name',
            'get_supported_models'
        ]
        
        for method_name in required_methods:
            if not hasattr(adapter_class, method_name):
                raise ValueError(f"Adapter missing required method: {method_name}")
            
            method = getattr(adapter_class, method_name)
            if getattr(method, '__isabstractmethod__', False):
                raise ValueError(f"Abstract method not implemented: {method_name}")
        
        return True
    
    @staticmethod
    def validate_adapter_config(config: AdapterConfig, adapter_class: AdapterClass) -> bool:
        """Validate configuration for a specific adapter"""
        # Basic config validation
        config.validate()
        
        # Check if adapter supports the requested model
        try:
            # Create temporary instance to check supported models
            temp_adapter = adapter_class(config)
            supported_models = temp_adapter.get_supported_models()
            
            if config.model_name not in supported_models:
                logger.warning(
                    f"Model {config.model_name} not in supported list for {config.provider_name}: "
                    f"{supported_models}"
                )
                # Don't raise error - might be a new model
        
        except Exception as e:
            logger.warning(f"Could not validate model support: {e}")
        
        return True


class AdapterLoader:
    """Dynamically loads adapter modules and classes"""
    
    def __init__(self):
        self.json_util = JSONUtilities()
    
    def load_adapter_from_module(
        self, 
        module_path: str, 
        class_name: str = None
    ) -> Optional[AdapterClass]:
        """Load adapter class from module path"""
        try:
            # Import the module
            module = importlib.import_module(module_path)
            
            if class_name:
                # Load specific class
                if not hasattr(module, class_name):
                    raise ImportError(f"Class {class_name} not found in {module_path}")
                
                adapter_class = getattr(module, class_name)
            else:
                # Auto-discover adapter class
                adapter_class = self._discover_adapter_class(module)
            
            # Validate the adapter
            AdapterValidator.validate_adapter_class(adapter_class)
            
            return adapter_class
            
        except Exception as e:
            logger.error(f"Failed to load adapter from {module_path}: {e}")
            return None
    
    def _discover_adapter_class(self, module) -> AdapterClass:
        """Auto-discover adapter class in module"""
        # Look for classes that inherit from ModelAdapterInterface
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (issubclass(obj, ModelAdapterInterface) and 
                obj != ModelAdapterInterface and
                not obj.__name__.startswith('Base')):
                return obj
        
        raise ImportError("No adapter class found in module")
    
    def scan_directory_for_adapters(self, directory_path: str) -> List[AdapterClass]:
        """Scan directory for adapter modules"""
        adapters = []
        directory = Path(directory_path)
        
        if not directory.exists():
            logger.warning(f"Adapter directory not found: {directory_path}")
            return adapters
        
        # Scan Python files
        for py_file in directory.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            
            try:
                # Convert file path to module path
                relative_path = py_file.relative_to(Path.cwd())
                module_path = str(relative_path).replace("/", ".").replace("\\", ".")[:-3]
                
                adapter_class = self.load_adapter_from_module(module_path)
                if adapter_class:
                    adapters.append(adapter_class)
                    
            except Exception as e:
                logger.warning(f"Could not load adapter from {py_file}: {e}")
        
        return adapters


class AdapterRegistry:
    """Central registry for all available adapters"""
    
    def __init__(self):
        self.adapters: Dict[str, AdapterInfo] = {}
        self.loader = AdapterLoader()
        self.validator = AdapterValidator()
        self.json_util = JSONUtilities()
    
    def register_adapter(
        self,
        adapter_class: AdapterClass,
        name: str = None,
        description: str = "",
        default_config: Dict[str, Any] = None
    ) -> None:
        """Register an adapter class"""
        # Validate adapter
        self.validator.validate_adapter_class(adapter_class)
        
        # Get adapter name
        if not name:
            # Create temporary instance to get provider name
            temp_config = AdapterConfig(
                provider_name="temp",
                model_name="temp"
            )
            try:
                temp_adapter = adapter_class(temp_config)
                name = temp_adapter.get_provider_name()
            except Exception:
                name = adapter_class.__name__.lower().replace("adapter", "")
        
        # Get supported models
        try:
            temp_config = AdapterConfig(
                provider_name=name,
                model_name="temp"
            )
            temp_adapter = adapter_class(temp_config)
            supported_models = temp_adapter.get_supported_models()
        except Exception as e:
            logger.warning(f"Could not get supported models for {name}: {e}")
            supported_models = []
        
        # Determine capabilities
        capabilities = {
            'streaming': hasattr(adapter_class, 'generate_streaming_response'),
            'embeddings': hasattr(adapter_class, 'generate_embeddings'),
            'vision': hasattr(adapter_class, 'generate_response_with_image'),
            'function_calling': False  # To be determined per adapter
        }
        
        # Create adapter info
        adapter_info = AdapterInfo(
            name=name,
            adapter_class=adapter_class,
            description=description or f"{name} model adapter",
            supported_models=supported_models,
            capabilities=capabilities,
            default_config=default_config or {},
            module_path=adapter_class.__module__
        )
        
        self.adapters[name] = adapter_info
        logger.info(f"Registered adapter: {name}")
    
    def unregister_adapter(self, name: str) -> bool:
        """Unregister an adapter"""
        if name in self.adapters:
            del self.adapters[name]
            logger.info(f"Unregistered adapter: {name}")
            return True
        return False
    
    def get_adapter_info(self, name: str) -> Optional[AdapterInfo]:
        """Get information about a registered adapter"""
        return self.adapters.get(name)
    
    def list_adapters(self) -> List[str]:
        """List all registered adapter names"""
        return list(self.adapters.keys())
    
    def list_adapters_with_capability(self, capability: str) -> List[str]:
        """List adapters that support a specific capability"""
        return [
            name for name, info in self.adapters.items()
            if info.capabilities.get(capability, False)
        ]
    
    def find_adapters_for_model(self, model_name: str) -> List[str]:
        """Find adapters that support a specific model"""
        matching_adapters = []
        
        for name, info in self.adapters.items():
            # Check exact match first
            if model_name in info.supported_models:
                matching_adapters.append(name)
            # Check partial matches (for model families)
            elif any(model_name.startswith(supported) for supported in info.supported_models):
                matching_adapters.append(name)
        
        return matching_adapters
    
    def load_adapters_from_directory(self, directory_path: str) -> int:
        """Load all adapters from a directory"""
        adapter_classes = self.loader.scan_directory_for_adapters(directory_path)
        
        count = 0
        for adapter_class in adapter_classes:
            try:
                self.register_adapter(adapter_class)
                count += 1
            except Exception as e:
                logger.error(f"Failed to register adapter {adapter_class}: {e}")
        
        logger.info(f"Loaded {count} adapters from {directory_path}")
        return count
    
    def export_registry(self) -> Dict[str, Any]:
        """Export registry information"""
        return {
            'adapters': {
                name: {
                    'name': info.name,
                    'description': info.description,
                    'supported_models': info.supported_models,
                    'capabilities': info.capabilities,
                    'default_config': info.default_config,
                    'module_path': info.module_path,
                    'version': info.version
                }
                for name, info in self.adapters.items()
            },
            'total_adapters': len(self.adapters)
        }
    
    def save_registry_to_file(self, file_path: str) -> None:
        """Save registry to JSON file"""
        registry_data = self.export_registry()
        self.json_util.save_to_file(file_path, registry_data)
        logger.info(f"Registry saved to {file_path}")


class AdapterFactory:
    """Factory for creating adapter instances"""
    
    def __init__(self, registry: AdapterRegistry = None):
        self.registry = registry or AdapterRegistry()
        self.active_adapters: Dict[str, ModelAdapterInterface] = {}
        self.json_util = JSONUtilities()
    
    def create_adapter(
        self,
        provider_name: str,
        model_name: str,
        config_overrides: Dict[str, Any] = None,
        **kwargs
    ) -> ModelAdapterInterface:
        """Create an adapter instance"""
        # Get adapter info
        adapter_info = self.registry.get_adapter_info(provider_name)
        if not adapter_info:
            raise AdapterConfigurationError(
                f"Adapter not found: {provider_name}",
                provider=provider_name
            )
        
        # Create configuration
        config_data = adapter_info.default_config.copy()
        config_data.update({
            'provider_name': provider_name,
            'model_name': model_name
        })
        
        if config_overrides:
            config_data.update(config_overrides)
        
        config_data.update(kwargs)
        
        # Create adapter config
        config = AdapterConfig(**config_data)
        
        # Validate configuration
        self.registry.validator.validate_adapter_config(config, adapter_info.adapter_class)
        
        # Create adapter instance
        adapter = adapter_info.adapter_class(config)
        
        logger.info(f"Created adapter: {provider_name}/{model_name}")
        return adapter
    
    async def create_and_initialize_adapter(
        self,
        provider_name: str,
        model_name: str,
        config_overrides: Dict[str, Any] = None,
        **kwargs
    ) -> ModelAdapterInterface:
        """Create and initialize an adapter"""
        adapter = self.create_adapter(provider_name, model_name, config_overrides, **kwargs)
        
        try:
            await adapter.initialize()
            return adapter
        except Exception as e:
            # Cleanup on failure
            try:
                await adapter.cleanup()
            except Exception:
                pass
            raise e
    
    def register_active_adapter(self, key: str, adapter: ModelAdapterInterface) -> None:
        """Register an active adapter for reuse"""
        self.active_adapters[key] = adapter
    
    def get_active_adapter(self, key: str) -> Optional[ModelAdapterInterface]:
        """Get an active adapter by key"""
        return self.active_adapters.get(key)
    
    def remove_active_adapter(self, key: str) -> bool:
        """Remove an active adapter"""
        if key in self.active_adapters:
            del self.active_adapters[key]
            return True
        return False
    
    async def cleanup_all_adapters(self) -> None:
        """Cleanup all active adapters"""
        cleanup_tasks = []
        
        for key, adapter in list(self.active_adapters.items()):
            cleanup_tasks.append(adapter.cleanup())
        
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        self.active_adapters.clear()
        logger.info("All adapters cleaned up")
    
    def get_adapter_statistics(self) -> Dict[str, Any]:
        """Get statistics about adapter usage"""
        stats = {
            'total_registered': len(self.registry.adapters),
            'total_active': len(self.active_adapters),
            'registered_adapters': self.registry.list_adapters(),
            'active_adapters': list(self.active_adapters.keys()),
            'capabilities_summary': {}
        }
        
        # Summarize capabilities
        for capability in ['streaming', 'embeddings', 'vision', 'function_calling']:
            adapters_with_capability = self.registry.list_adapters_with_capability(capability)
            stats['capabilities_summary'][capability] = {
                'count': len(adapters_with_capability),
                'adapters': adapters_with_capability
            }
        
        return stats


# Global registry and factory instances
_global_registry = None
_global_factory = None


def get_global_registry() -> AdapterRegistry:
    """Get the global adapter registry"""
    global _global_registry
    if _global_registry is None:
        _global_registry = AdapterRegistry()
    return _global_registry


def get_global_factory() -> AdapterFactory:
    """Get the global adapter factory"""
    global _global_factory
    if _global_factory is None:
        _global_factory = AdapterFactory(get_global_registry())
    return _global_factory


# Convenience functions
def register_adapter(adapter_class: AdapterClass, **kwargs) -> None:
    """Register an adapter with the global registry"""
    get_global_registry().register_adapter(adapter_class, **kwargs)


def create_adapter(provider_name: str, model_name: str, **kwargs) -> ModelAdapterInterface:
    """Create an adapter using the global factory"""
    return get_global_factory().create_adapter(provider_name, model_name, **kwargs)


async def create_and_initialize_adapter(
    provider_name: str, 
    model_name: str, 
    **kwargs
) -> ModelAdapterInterface:
    """Create and initialize an adapter using the global factory"""
    return await get_global_factory().create_and_initialize_adapter(
        provider_name, model_name, **kwargs
    )


# Export all public classes and functions
__all__ = [
    # Core classes
    'AdapterRegistry',
    'AdapterFactory',
    'AdapterLoader',
    'AdapterValidator',
    'AdapterInfo',
    
    # Global instances
    'get_global_registry',
    'get_global_factory',
    
    # Convenience functions
    'register_adapter',
    'create_adapter',
    'create_and_initialize_adapter'
]
