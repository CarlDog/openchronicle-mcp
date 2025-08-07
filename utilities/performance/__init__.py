#!/usr/bin/env python3
"""
OpenChronicle Performance Package

Modular performance monitoring system for the OpenChronicle narrative AI engine.
Provides comprehensive metrics collection, analysis, and reporting capabilities.

Core Components:
- MetricsCollector: Collects performance metrics from operations
- MetricsStorage: Stores and retrieves metrics data
- BottleneckAnalyzer: Identifies performance bottlenecks
- PerformanceOrchestrator: Coordinates all components
- CLI: Command-line interface

Example Usage:
    # Direct orchestrator usage
    from utilities.performance import PerformanceOrchestrator, OperationContext
    
    orchestrator = PerformanceOrchestrator()
    await orchestrator.initialize()
    
    # Monitor an operation
    context = OperationContext(
        operation_id="op_123",
        adapter_name="openai_gpt4",
        operation_type="text_generation",
        metadata={"tokens": 150}
    )
    
    operation_id = await orchestrator.start_operation_monitoring(context)
    # ... perform operation ...
    metrics = await orchestrator.finish_operation_monitoring(operation_id, True)
    
    # Analyze performance
    analysis = await orchestrator.analyze_performance()
    
    # CLI usage
    from utilities.performance.cli import run_performance_command
    
    status = await run_performance_command('status')
    analysis = await run_performance_command('analyze', hours=24, adapter='openai_gpt4')
"""

from .orchestrator import PerformanceOrchestrator
from .interfaces.performance_interfaces import (
    IPerformanceOrchestrator, IMetricsCollector, IMetricsStorage,
    IBottleneckAnalyzer, ITrendAnalyzer, IReportGenerator, IAlertManager,
    PerformanceMetrics, OperationContext, BottleneckReport, TrendAnalysis,
    MetricsQuery
)
from .metrics.collector import MetricsCollector
from .metrics.storage import MetricsStorage
from .analysis.bottleneck_analyzer import BottleneckAnalyzer
from .cli import PerformanceCLI, run_performance_command

# Package version
__version__ = "1.0.0"

# Main exports
__all__ = [
    # Core orchestrator
    'PerformanceOrchestrator',
    
    # Interfaces
    'IPerformanceOrchestrator',
    'IMetricsCollector', 
    'IMetricsStorage',
    'IBottleneckAnalyzer',
    'ITrendAnalyzer',
    'IReportGenerator',
    'IAlertManager',
    
    # Data classes
    'PerformanceMetrics',
    'OperationContext',
    'BottleneckReport',
    'TrendAnalysis',
    'MetricsQuery',
    
    # Concrete implementations
    'MetricsCollector',
    'MetricsStorage', 
    'BottleneckAnalyzer',
    
    # CLI
    'PerformanceCLI',
    'run_performance_command'
]

# Package metadata
__author__ = "OpenChronicle Development Team"
__description__ = "Modular performance monitoring system for OpenChronicle"
__license__ = "MIT"


def create_default_orchestrator() -> PerformanceOrchestrator:
    """Create a default performance orchestrator with standard components."""
    return PerformanceOrchestrator(
        metrics_collector=MetricsCollector(),
        metrics_storage=MetricsStorage(),
        bottleneck_analyzer=BottleneckAnalyzer()
        # TODO: Add trend_analyzer, report_generator, alert_manager when implemented
    )


def get_package_info() -> dict:
    """Get package information and component status."""
    return {
        'name': 'utilities.performance',
        'version': __version__,
        'description': __description__,
        'author': __author__,
        'license': __license__,
        'components': {
            'metrics_collector': 'MetricsCollector - Implemented',
            'metrics_storage': 'MetricsStorage - Implemented', 
            'bottleneck_analyzer': 'BottleneckAnalyzer - Implemented',
            'orchestrator': 'PerformanceOrchestrator - Implemented',
            'cli': 'PerformanceCLI - Implemented',
            'trend_analyzer': 'ITrendAnalyzer - TODO',
            'report_generator': 'IReportGenerator - TODO',
            'alert_manager': 'IAlertManager - TODO'
        },
        'interfaces': len([name for name in __all__ if name.startswith('I')]),
        'implementations': len([name for name in __all__ if not name.startswith('I') and 'CLI' not in name])
    }
