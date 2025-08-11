"""
OpenChronicle Performance Module

Unified performance monitoring, metrics collection, analysis, and reporting.
Consolidates all performance-related functionality into a centralized system.

Components:
- PerformanceOrchestrator: Central coordination of all performance monitoring
- ModelPerformanceMonitor: Model-specific performance tracking (from core/models)
- MetricsCollector: Real-time metrics collection
- BottleneckAnalyzer: Performance bottleneck detection and analysis
- Interfaces: Clean abstractions for all performance components

Usage:
    from src.openchronicle.infrastructure.performance import PerformanceOrchestrator, ModelPerformanceMonitor
    from src.openchronicle.infrastructure.performance import MetricsCollector, BottleneckAnalyzer
"""

# Core performance orchestration
try:
    from .orchestrator import PerformanceOrchestrator

    ORCHESTRATOR_AVAILABLE = True
except ImportError:
    ORCHESTRATOR_AVAILABLE = False
    PerformanceOrchestrator = None

# Model-specific performance monitoring
try:
    from .model_monitor import PerformanceMonitor as ModelPerformanceMonitor

    MODEL_MONITOR_AVAILABLE = True
except ImportError:
    MODEL_MONITOR_AVAILABLE = False
    ModelPerformanceMonitor = None

# Metrics collection and storage
try:
    from .metrics.collector import MetricsCollector
    from .metrics.storage import MetricsStorage

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    MetricsCollector = None
    MetricsStorage = None

# Performance analysis
try:
    from .analysis.bottleneck_analyzer import BottleneckAnalyzer

    ANALYSIS_AVAILABLE = True
except ImportError:
    ANALYSIS_AVAILABLE = False
    BottleneckAnalyzer = None

# Performance interfaces
try:
    from .interfaces.performance_interfaces import (
        IPerformanceOrchestrator,
        IMetricsCollector,
        IMetricsStorage,
        IBottleneckAnalyzer,
        PerformanceMetrics,
        OperationContext,
    )

    INTERFACES_AVAILABLE = True
except ImportError:
    INTERFACES_AVAILABLE = False
    IPerformanceOrchestrator = None
    IMetricsCollector = None
    IMetricsStorage = None
    IBottleneckAnalyzer = None
    PerformanceMetrics = None
    OperationContext = None

# Backwards compatibility - maintain old import
PerformanceMonitor = ModelPerformanceMonitor


def get_performance_status():
    """Get availability status of performance components."""
    return {
        "PerformanceOrchestrator": ORCHESTRATOR_AVAILABLE,
        "ModelPerformanceMonitor": MODEL_MONITOR_AVAILABLE,
        "MetricsCollector": METRICS_AVAILABLE,
        "BottleneckAnalyzer": ANALYSIS_AVAILABLE,
        "Interfaces": INTERFACES_AVAILABLE,
    }


def create_performance_orchestrator(*args, **kwargs):
    """Factory function for PerformanceOrchestrator with error handling."""
    if not ORCHESTRATOR_AVAILABLE:
        raise ImportError("PerformanceOrchestrator not available")
    return PerformanceOrchestrator(*args, **kwargs)


def create_model_performance_monitor(*args, **kwargs):
    """Factory function for ModelPerformanceMonitor with error handling."""
    if not MODEL_MONITOR_AVAILABLE:
        raise ImportError("ModelPerformanceMonitor not available")
    return ModelPerformanceMonitor(*args, **kwargs)


# Public API
__all__ = [
    # Main Components
    "PerformanceOrchestrator",
    "ModelPerformanceMonitor",
    "MetricsCollector",
    "MetricsStorage",
    "BottleneckAnalyzer",
    # Interfaces
    "IPerformanceOrchestrator",
    "IMetricsCollector",
    "IMetricsStorage",
    "IBottleneckAnalyzer",
    "PerformanceMetrics",
    "OperationContext",
    # Utilities
    "get_performance_status",
    "create_performance_orchestrator",
    "create_model_performance_monitor",
    # Backwards Compatibility
    "PerformanceMonitor",  # Alias for ModelPerformanceMonitor
]
