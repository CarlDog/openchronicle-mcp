"""
Model Management Package - Modular replacement for the monolithic ModelManager.

This package provides clean separation of concerns that were all embedded
in the original 4,473-line model_adapter.py file:

Components:
- RegistryManager: Configuration and provider management
- AdapterFactory: Registry-aware adapter creation  
- ModelOrchestrator: Main coordination and adapter management (~200 lines)
- ContentRouter: Intelligent content-based routing
- HealthMonitor: Comprehensive health checking and performance tracking

Total lines across all components: ~1,200 vs original 4,473 lines
Code reduction: ~73% while adding significant new functionality

Usage:
    from core.model_management import ModelOrchestrator, RegistryManager
    
    # Initialize the modular system
    registry = RegistryManager()
    from core.adapters.factory import AdapterFactory
    factory = AdapterFactory(registry)
    orchestrator = ModelOrchestrator(registry, factory)
    
    # Use like the original ModelManager but with better separation
    response = await orchestrator.generate_response(prompt, content_type="narrative")
"""

from .registry import RegistryManager
from .orchestrator import ModelOrchestrator
from .content_router import ContentRouter, ContentType, ComplexityLevel
from .health_monitor import HealthMonitor, HealthStatus, HealthCheckResult, PerformanceMetrics

# Import the main orchestrator as ModelManager for backward compatibility
ModelManager = ModelOrchestrator

__all__ = [
    'ModelManager',      # Backward compatibility
    'RegistryManager',
    'ModelOrchestrator', 
    'ContentRouter',
    'ContentType',
    'ComplexityLevel',
    'HealthMonitor',
    'HealthStatus',
    'HealthCheckResult',
    'PerformanceMetrics'
]

# Version info for the modular system
__version__ = "2.0.0"
__description__ = "Modular model management system replacing monolithic ModelManager"
