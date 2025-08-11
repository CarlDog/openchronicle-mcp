"""
OpenChronicle Performance Monitoring Interfaces Package

Interface definitions for the modular performance monitoring system.
"""

from .performance_interfaces import (
    # Data classes
    PerformanceMetrics,
    BottleneckAnalysis,
    BottleneckReport,
    TrendAnalysis,
    MetricsQuery,
    PerformanceReport,
    MonitoringContext,
    OperationContext,
    # Interfaces
    IMetricsCollector,
    IMetricsStorage,
    IBottleneckAnalyzer,
    ITrendAnalyzer,
    IReportGenerator,
    IAlertManager,
    IPerformanceOrchestrator,
)

__all__ = [
    # Data classes
    "PerformanceMetrics",
    "BottleneckAnalysis",
    "BottleneckReport",
    "TrendAnalysis",
    "MetricsQuery",
    "PerformanceReport",
    "MonitoringContext",
    "OperationContext",
    # Interfaces
    "IMetricsCollector",
    "IMetricsStorage",
    "IBottleneckAnalyzer",
    "ITrendAnalyzer",
    "IReportGenerator",
    "IAlertManager",
    "IPerformanceOrchestrator",
]
