"""
Model Management Package for OpenChronicle.

This package contains the modular components implementing comprehensive
model management with orchestrator pattern.

Components:
- model_orchestrator.py: Main orchestrator for model operations
- response_generator.py: Core response generation logic with fallback support
- lifecycle_manager.py: Adapter initialization and state management
- performance_monitor.py: Performance tracking and analytics
- configuration_manager.py: Configuration and registry management

Architecture:
- Orchestrator Pattern: ModelOrchestrator coordinates all operations
- Single Responsibility: Each component has one clear purpose
- Clean Interfaces: Well-defined APIs between components
- Testability: Each component can be independently tested
- Maintainability: Focused, readable code with clear boundaries
"""

from .model_orchestrator import ModelOrchestrator
from .response_generator import ResponseGenerator
from .lifecycle_manager import LifecycleManager
from .performance_monitor import PerformanceMonitor
from .configuration_manager import ConfigurationManager

__all__ = [
    "ModelOrchestrator",
    "ResponseGenerator", 
    "LifecycleManager",
    "PerformanceMonitor",
    "ConfigurationManager"
]

# Package metadata
__version__ = "2.0.0"
__status__ = "Modular Architecture Complete"
