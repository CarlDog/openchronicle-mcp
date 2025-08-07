#!/usr/bin/env python3
"""
OpenChronicle Performance Monitoring Interfaces

Interface definitions for the modular performance monitoring system.
Follows SOLID principles with focused, segregated interfaces.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics for a single operation."""
    operation_id: str
    adapter_name: str
    operation_type: str  # "initialize", "generate", "analyze", etc.
    start_time: float
    end_time: float
    duration: float
    cpu_usage_before: float
    cpu_usage_after: float
    memory_usage_before: float  # MB
    memory_usage_after: float  # MB
    success: bool
    error_message: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


@dataclass
class BottleneckAnalysis:
    """Analysis of performance bottlenecks."""
    bottleneck_type: str  # "cpu", "memory", "network", "model"
    severity: str  # "low", "medium", "high", "critical"
    affected_operations: List[str]
    impact_description: str
    root_cause: str
    recommendation: str
    confidence: float  # 0.0 to 1.0


@dataclass
class BottleneckReport:
    """Comprehensive bottleneck analysis report."""
    analysis_time: datetime
    time_period: Tuple[datetime, datetime]
    total_operations: int
    failed_operations: int
    avg_duration: float
    bottleneck_patterns: List[Any]  # Will be BottleneckPattern instances
    top_bottleneck_adapters: List[str]
    recommendations: List[str]


@dataclass
class TrendAnalysis:
    """Trend analysis for performance metrics."""
    time_period: Tuple[datetime, datetime]
    trend_direction: str  # "improving", "stable", "degrading"
    confidence: float
    key_metrics: Dict[str, float]
    recommendations: List[str]


@dataclass
class MetricsQuery:
    """Query parameters for retrieving metrics."""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    adapter_names: Optional[List[str]] = None
    operation_types: Optional[List[str]] = None
    success_only: Optional[bool] = None
    limit: Optional[int] = None


@dataclass
class PerformanceReport:
    """Comprehensive performance analysis report."""
    report_id: str
    generated_at: datetime
    time_period: Tuple[datetime, datetime]
    
    # Overall metrics
    total_operations: int
    success_rate: float
    average_duration: float
    median_duration: float
    p95_duration: float
    
    # Resource usage
    average_cpu_usage: float
    peak_cpu_usage: float
    average_memory_usage: float
    peak_memory_usage: float
    
    # Model performance
    model_rankings: Dict[str, float]  # adapter_name -> performance_score
    slowest_operations: List[str]
    fastest_operations: List[str]
    
    # Analysis results
    bottlenecks: List[BottleneckAnalysis]
    optimization_recommendations: List[str]
    performance_trend: str  # "improving", "stable", "degrading"
    trend_confidence: float


@dataclass
class MonitoringContext:
    """Context for performance monitoring operations."""
    session_id: str
    monitoring_enabled: bool
    storage_path: Path
    retention_days: int = 30
    alert_thresholds: Optional[Dict[str, float]] = None


@dataclass
class OperationContext:
    """Context for individual operation tracking."""
    operation_id: str
    adapter_name: str
    operation_type: str
    metadata: Dict[str, Any]


class IMetricsCollector(ABC):
    """Interface for collecting performance metrics."""
    
    @abstractmethod
    async def start_operation_tracking(self, context: OperationContext) -> str:
        """Start tracking a new operation."""
        pass
    
    @abstractmethod
    async def finish_operation_tracking(self, operation_id: str, 
                                      success: bool, error_message: Optional[str] = None) -> PerformanceMetrics:
        """Finish tracking an operation and return metrics."""
        pass
    
    @abstractmethod
    def collect_system_metrics(self) -> Dict[str, float]:
        """Collect current system resource metrics."""
        pass
    
    @abstractmethod
    async def get_metrics_history(self, time_period: Tuple[datetime, datetime],
                                adapter_filter: Optional[str] = None) -> List[PerformanceMetrics]:
        """Retrieve historical metrics for analysis."""
        pass
    
    def enable_collection(self):
        """Enable metrics collection."""
        return
    
    def disable_collection(self):
        """Disable metrics collection."""
        return
    
    def get_collection_status(self) -> Dict[str, Any]:
        """Get current collection status and statistics."""
        return {}
    
    async def cleanup_stale_operations(self, max_age_hours: int = 24) -> int:
        """Clean up operations that have been running too long."""
        return 0


class IMetricsStorage(ABC):
    """Interface for storing and retrieving performance metrics."""
    
    async def initialize(self):
        """Initialize the storage backend."""
        return
    
    @abstractmethod
    async def store_metrics(self, metrics: PerformanceMetrics):
        """Store performance metrics."""
        pass
    
    @abstractmethod
    async def retrieve_metrics(self, query: 'MetricsQuery') -> List[PerformanceMetrics]:
        """Retrieve metrics based on query parameters."""
        pass
    
    @abstractmethod
    async def get_metrics_summary(self, time_period: Tuple[datetime, datetime],
                                adapter_filter: Optional[str] = None) -> Dict[str, Any]:
        """Get summary statistics for metrics in a time period."""
        pass
    
    @abstractmethod
    async def cleanup_old_metrics(self, retention_days: int = 30) -> int:
        """Clean up old metrics and return count of removed records."""
        pass
    
    @abstractmethod
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics and health information."""
        pass


class IBottleneckAnalyzer(ABC):
    """Interface for analyzing performance bottlenecks."""
    
    @abstractmethod
    async def analyze_bottlenecks(self, metrics: List[PerformanceMetrics],
                                time_window: Optional[Any] = None) -> 'BottleneckReport':
        """Analyze metrics to identify bottlenecks."""
        pass
    
    @abstractmethod
    async def identify_slow_operations(self, metrics: List[PerformanceMetrics],
                                     threshold_percentile: float = 95.0) -> List[PerformanceMetrics]:
        """Identify operations that are significantly slower than average."""
        pass
    
    @abstractmethod
    async def analyze_resource_usage_patterns(self, metrics: List[PerformanceMetrics]) -> Dict[str, Any]:
        """Analyze resource usage patterns and trends."""
        pass


class ITrendAnalyzer(ABC):
    """Interface for analyzing performance trends."""
    
    @abstractmethod
    async def analyze_performance_trends(self, metrics: List[PerformanceMetrics]) -> Dict[str, Any]:
        """Analyze performance trends over time."""
        pass
    
    async def analyze_trends(self, metrics: List[PerformanceMetrics], time_period: Tuple[datetime, datetime]) -> TrendAnalysis:
        """Analyze trends for a specific time period."""
        trends = await self.analyze_performance_trends(metrics)
        return TrendAnalysis(
            time_period=time_period,
            trend_direction=trends.get('direction', 'stable'),
            confidence=trends.get('confidence', 0.5),
            key_metrics=trends.get('metrics', {}),
            recommendations=trends.get('recommendations', [])
        )
    
    @abstractmethod
    async def predict_future_performance(self, metrics: List[PerformanceMetrics],
                                       prediction_days: int = 7) -> Dict[str, Any]:
        """Predict future performance based on trends."""
        pass
    
    @abstractmethod
    async def detect_performance_degradation(self, metrics: List[PerformanceMetrics]) -> List[Dict[str, Any]]:
        """Detect performance degradation patterns."""
        pass


class IReportGenerator(ABC):
    """Interface for generating performance reports."""
    
    @abstractmethod
    async def generate_performance_report(self, 
                                        time_period: Tuple[datetime, datetime],
                                        include_recommendations: bool = True) -> PerformanceReport:
        """Generate comprehensive performance report."""
        pass
    
    async def generate_report(self, analysis: Dict[str, Any], report_format: str = 'json') -> Dict[str, Any]:
        """Generate formatted report from analysis data."""
        return {
            'report_type': 'performance_analysis',
            'format': report_format,
            'generated_at': datetime.now().isoformat(),
            'data': analysis
        }
    
    @abstractmethod
    async def generate_summary_report(self, metrics: List[PerformanceMetrics]) -> Dict[str, Any]:
        """Generate summary performance report."""
        pass
    
    @abstractmethod
    async def export_report(self, report: PerformanceReport, 
                          output_path: Path, format_type: str = 'json') -> bool:
        """Export report to file in specified format."""
        pass
    
    @abstractmethod
    async def generate_dashboard_data(self, time_period: Tuple[datetime, datetime]) -> Dict[str, Any]:
        """Generate data for performance dashboard display."""
        pass


class IAlertManager(ABC):
    """Interface for performance alert management."""
    
    @abstractmethod
    async def check_alert_conditions(self, metrics: PerformanceMetrics) -> List[Dict[str, Any]]:
        """Check if metrics trigger any alert conditions."""
        pass
    
    async def check_metrics_for_alerts(self, metrics: PerformanceMetrics):
        """Check if metrics trigger any alerts."""
        return await self.check_alert_conditions(metrics)
    
    @abstractmethod
    async def configure_alert_thresholds(self, thresholds: Dict[str, float]) -> bool:
        """Configure performance alert thresholds."""
        pass
    
    @abstractmethod
    async def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get currently active performance alerts."""
        pass
    
    @abstractmethod
    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge and dismiss an alert."""
        pass


class IPerformanceOrchestrator(ABC):
    """Interface for the main performance monitoring orchestrator."""
    
    @abstractmethod
    async def initialize(self):
        """Initialize the performance monitoring system."""
        pass
    
    @abstractmethod
    async def start_operation_monitoring(self, context: OperationContext) -> str:
        """Start monitoring a new operation."""
        pass
    
    @abstractmethod
    async def finish_operation_monitoring(self, operation_id: str,
                                        success: bool, error_message: Optional[str] = None) -> PerformanceMetrics:
        """Finish monitoring an operation."""
        pass
    
    @abstractmethod
    async def analyze_performance(self, time_period: Optional[Tuple[datetime, datetime]] = None,
                                adapter_filter: Optional[str] = None) -> Dict[str, Any]:
        """Perform comprehensive performance analysis."""
        pass
    
    @abstractmethod
    async def get_real_time_metrics(self) -> Dict[str, Any]:
        """Get current real-time performance metrics."""
        pass
    
    @abstractmethod
    async def cleanup_old_data(self, retention_days: int = 30) -> Dict[str, int]:
        """Clean up old performance data and return cleanup statistics."""
        pass
