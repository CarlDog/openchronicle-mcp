"""
Model registry package.

Consolidated registry management following OpenChronicle organizational standards.
This package provides centralized configuration management for the entire
model adapter system.

Key Components:
- registry_manager.py: Core registry loading and configuration access
- content_router.py: Intelligent content routing and model selection
- health_monitor.py: Provider health checking and performance monitoring

Features:
- Centralized configuration from model_registry.json
- Provider-specific settings and validation rules
- Content routing and fallback chains
- Performance monitoring and rate limiting
- Clean separation of concerns
"""

from .content_router import ComplexityLevel
from .content_router import ContentRouter
from .content_router import ContentType
from .health_monitor import HealthCheckResult
from .health_monitor import HealthMonitor
from .health_monitor import HealthStatus
from .registry_manager import RegistryManager


__all__ = [
    "ComplexityLevel",
    "ContentRouter",
    "ContentType",
    "HealthCheckResult",
    "HealthMonitor",
    "HealthStatus",
    "RegistryManager",
]

# Version info
__version__ = "2.0.0"
__author__ = "OpenChronicle Development Team"
