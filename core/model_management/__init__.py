"""
Model Management Package - Base Infrastructure for Model Adapters

This package provides the foundational framework for OpenChronicle's model adapter system,
implementing the Template Method pattern to eliminate 90% of code duplication across 15+ adapters.

Key Components:
- BaseAdapter: Template method pattern with common functionality
- AdapterRegistry: Factory pattern for adapter creation and management
- AdapterInterfaces: Common interfaces and type definitions
- AdapterConfig: Configuration management and validation

Design Goals:
- Reduce adapter implementation from 100+ lines to 20-30 lines
- Eliminate code duplication across provider adapters
- Provide consistent error handling and logging
- Support dynamic adapter loading and hot-swapping
- Maintain backward compatibility during migration
"""

from .base_adapter import BaseAdapter, BaseAPIAdapter, BaseLocalAdapter
from .adapter_registry import AdapterRegistry, AdapterFactory
from .adapter_interfaces import ModelAdapterInterface, AdapterConfig
from .adapter_config import ConfigValidator, ConfigManager

__all__ = [
    # Base classes
    'BaseAdapter',
    'BaseAPIAdapter', 
    'BaseLocalAdapter',
    
    # Registry and factory
    'AdapterRegistry',
    'AdapterFactory',
    
    # Interfaces and configuration
    'ModelAdapterInterface',
    'AdapterConfig',
    'ConfigValidator',
    'ConfigManager'
]

# Version information
__version__ = '1.0.0'
__author__ = 'OpenChronicle Core Team'
