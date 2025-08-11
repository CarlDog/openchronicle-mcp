"""
OpenChronicle Performance Monitoring Interfaces Package

Interface definitions for the modular performance monitoring system.
"""

from .performance_interfaces import BottleneckAnalysis
from .performance_interfaces import BottleneckReport
from .performance_interfaces import IAlertManager
from .performance_interfaces import IBottleneckAnalyzer
from .performance_interfaces import IMetricsCollector  # Interfaces
from .performance_interfaces import IMetricsStorage
from .performance_interfaces import IPerformanceOrchestrator
from .performance_interfaces import IReportGenerator
from .performance_interfaces import ITrendAnalyzer
from .performance_interfaces import MetricsQuery
from .performance_interfaces import MonitoringContext
from .performance_interfaces import OperationContext
from .performance_interfaces import PerformanceMetrics  # Data classes
from .performance_interfaces import PerformanceReport
from .performance_interfaces import TrendAnalysis


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
