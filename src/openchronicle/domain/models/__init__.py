"""
Model Management Package for OpenChronicle.

This package contains the modular components implementing comprehensive
model management with orchestrator pattern.

Components:
- model_orchestrator.py: Main orchestrator for model operations
- response_generator.py: Core response generation logic with fallback support
- lifecycle_manager.py: Adapter initialization and state management
- performance_monitor.py: Performance tracking and analytics (via dependency injection)
- configuration_manager.py: Configuration and registry management (via dependency injection)

Architecture:
- Orchestrator Pattern: ModelOrchestrator coordinates all operations
- Single Responsibility: Each component has one clear purpose
- Clean Interfaces: Well-defined APIs between components
- Testability: Each component can be independently tested
- Maintainability: Focused, readable code with clear boundaries
- Hexagonal Architecture: Domain isolated from infrastructure via ports/adapters
"""

# VIOLATION FIXED: Use dependency injection instead of direct infrastructure imports
# from src.openchronicle.infrastructure.performance.model_monitor import PerformanceMonitor

from .configuration_manager import ConfigurationManager
from .lifecycle_manager import LifecycleManager
from .model_orchestrator import ModelOrchestrator
from .response_generator import ResponseGenerator


__all__ = [
    "ConfigurationManager",
    "LifecycleManager",
    "ModelOrchestrator",
    "PerformanceMonitor",
    "ResponseGenerator",
]

# Package metadata
__version__ = "2.0.0"
__status__ = "Modular Architecture Complete"
