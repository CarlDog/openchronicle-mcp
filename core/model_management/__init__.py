"""
Model Management Package for OpenChronicle.

This package contains the decomposed components of the original ModelManager
monolith, implementing Phase 3.0 of the core refactoring initiative.

Components:
- response_generator.py: Core response generation logic with fallback support
- lifecycle_manager.py: Adapter initialization and state management (Phase 3 Day 2)
- performance_monitor.py: Performance tracking and analytics (Phase 3 Day 3)
- orchestrator.py: Clean replacement for ModelManager (Phase 3 Day 4-5)

Architecture:
- Single Responsibility: Each component has one clear purpose
- Clean Interfaces: Well-defined APIs between components
- Testability: Each component can be independently tested
- Maintainability: Focused, readable code with clear boundaries
"""

from .response_generator import ResponseGenerator
from .lifecycle_manager import LifecycleManager

__all__ = [
    "ResponseGenerator",
    "LifecycleManager",
    # Future components will be added as they're implemented:
    # "PerformanceMonitor", 
    # "ModelOrchestrator"
]

# Package metadata
__version__ = "3.0.0"
__status__ = "Phase 3.0 - System Decomposition"
