#!/usr/bin/env python3
"""
OpenChronicle Performance Monitoring Interfaces

Interface definitions for the modular performance monitoring system.
Follows SOLID principles with focused, segregated interfaces.
"""

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


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
    error_message: str | None = None
    context: dict[str, Any] | None = None


@dataclass
class BottleneckAnalysis:
    """Analysis of performance bottlenecks."""

    bottleneck_type: str  # "cpu", "memory", "network", "model"
    severity: str  # "low", "medium", "high", "critical"
    affected_operations: list[str]
    impact_description: str
    root_cause: str
    recommendation: str
    confidence: float  # 0.0 to 1.0


@dataclass
class BottleneckReport:
    """Comprehensive bottleneck analysis report."""

    analysis_time: datetime
    time_period: tuple[datetime, datetime]
    total_operations: int
    failed_operations: int
    avg_duration: float
    bottleneck_patterns: list[Any]  # Will be BottleneckPattern instances
    top_bottleneck_adapters: list[str]
    recommendations: list[str]


@dataclass
class TrendAnalysis:
    """Trend analysis for performance metrics."""

    time_period: tuple[datetime, datetime]
    trend_direction: str  # "improving", "stable", "degrading"
    confidence: float
    key_metrics: dict[str, float]
    recommendations: list[str]


@dataclass
class MetricsQuery:
    """Query parameters for retrieving metrics."""

    start_time: datetime | None = None
    end_time: datetime | None = None
    adapter_names: list[str] | None = None
    operation_types: list[str] | None = None
    success_only: bool | None = None
    limit: int | None = None


@dataclass
class PerformanceReport:
    """Comprehensive performance analysis report."""

    report_id: str
    generated_at: datetime
    time_period: tuple[datetime, datetime]

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
    model_rankings: dict[str, float]  # adapter_name -> performance_score
    slowest_operations: list[str]
    fastest_operations: list[str]

    # Analysis results
    bottlenecks: list[BottleneckAnalysis]
    optimization_recommendations: list[str]
    performance_trend: str  # "improving", "stable", "degrading"
    trend_confidence: float


@dataclass
class MonitoringContext:
    """Context for performance monitoring operations."""

    session_id: str
    monitoring_enabled: bool
    storage_path: Path
    retention_days: int = 30
    alert_thresholds: dict[str, float] | None = None


@dataclass
class OperationContext:
    """Context for individual operation tracking."""

    operation_id: str
    adapter_name: str
    operation_type: str
    metadata: dict[str, Any]


class IMetricsCollector(ABC):
    """Interface for collecting performance metrics."""

    @abstractmethod
    async def start_operation_tracking(self, context: OperationContext) -> str:
        """Start tracking a new operation."""

    @abstractmethod
    async def finish_operation_tracking(
        self, operation_id: str, success: bool, error_message: str | None = None
    ) -> PerformanceMetrics:
        """Finish tracking an operation and return metrics."""

    @abstractmethod
    def collect_system_metrics(self) -> dict[str, float]:
        """Collect current system resource metrics."""

    @abstractmethod
    async def get_metrics_history(
        self,
        time_period: tuple[datetime, datetime],
        adapter_filter: str | None = None,
    ) -> list[PerformanceMetrics]:
        """Retrieve historical metrics for analysis."""

    def enable_collection(self):
        """Enable metrics collection."""
        return

    def disable_collection(self):
        """Disable metrics collection."""
        return

    def get_collection_status(self) -> dict[str, Any]:
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

    @abstractmethod
    async def retrieve_metrics(self, query: "MetricsQuery") -> list[PerformanceMetrics]:
        """Retrieve metrics based on query parameters."""

    @abstractmethod
    async def get_metrics_summary(
        self,
        time_period: tuple[datetime, datetime],
        adapter_filter: str | None = None,
    ) -> dict[str, Any]:
        """Get summary statistics for metrics in a time period."""

    @abstractmethod
    async def cleanup_old_metrics(self, retention_days: int = 30) -> int:
        """Clean up old metrics and return count of removed records."""

    @abstractmethod
    async def get_storage_stats(self) -> dict[str, Any]:
        """Get storage statistics and health information."""


class IBottleneckAnalyzer(ABC):
    """Interface for analyzing performance bottlenecks."""

    @abstractmethod
    async def analyze_bottlenecks(
        self, metrics: list[PerformanceMetrics], time_window: Any | None = None
    ) -> "BottleneckReport":
        """Analyze metrics to identify bottlenecks."""

    @abstractmethod
    async def identify_slow_operations(
        self, metrics: list[PerformanceMetrics], threshold_percentile: float = 95.0
    ) -> list[PerformanceMetrics]:
        """Identify operations that are significantly slower than average."""

    @abstractmethod
    async def analyze_resource_usage_patterns(self, metrics: list[PerformanceMetrics]) -> dict[str, Any]:
        """Analyze resource usage patterns and trends."""


class ITrendAnalyzer(ABC):
    """Interface for analyzing performance trends."""

    @abstractmethod
    async def analyze_performance_trends(self, metrics: list[PerformanceMetrics]) -> dict[str, Any]:
        """Analyze performance trends over time."""

    async def analyze_trends(
        self, metrics: list[PerformanceMetrics], time_period: tuple[datetime, datetime]
    ) -> TrendAnalysis:
        """Analyze trends for a specific time period."""
        trends = await self.analyze_performance_trends(metrics)
        return TrendAnalysis(
            time_period=time_period,
            trend_direction=trends.get("direction", "stable"),
            confidence=trends.get("confidence", 0.5),
            key_metrics=trends.get("metrics", {}),
            recommendations=trends.get("recommendations", []),
        )

    @abstractmethod
    async def predict_future_performance(
        self, metrics: list[PerformanceMetrics], prediction_days: int = 7
    ) -> dict[str, Any]:
        """Predict future performance based on trends."""

    @abstractmethod
    async def detect_performance_degradation(self, metrics: list[PerformanceMetrics]) -> list[dict[str, Any]]:
        """Detect performance degradation patterns."""


class IReportGenerator(ABC):
    """Interface for generating performance reports."""

    @abstractmethod
    async def generate_performance_report(
        self,
        time_period: tuple[datetime, datetime],
        include_recommendations: bool = True,
    ) -> PerformanceReport:
        """Generate comprehensive performance report."""

    async def generate_report(self, analysis: dict[str, Any], report_format: str = "json") -> dict[str, Any]:
        """Generate formatted report from analysis data."""
        return {
            "report_type": "performance_analysis",
            "format": report_format,
            "generated_at": datetime.now().isoformat(),
            "data": analysis,
        }

    @abstractmethod
    async def generate_summary_report(self, metrics: list[PerformanceMetrics]) -> dict[str, Any]:
        """Generate summary performance report."""

    @abstractmethod
    async def export_report(self, report: PerformanceReport, output_path: Path, format_type: str = "json") -> bool:
        """Export report to file in specified format."""

    @abstractmethod
    async def generate_dashboard_data(self, time_period: tuple[datetime, datetime]) -> dict[str, Any]:
        """Generate data for performance dashboard display."""


class IAlertManager(ABC):
    """Interface for performance alert management."""

    @abstractmethod
    async def check_alert_conditions(self, metrics: PerformanceMetrics) -> list[dict[str, Any]]:
        """Check if metrics trigger any alert conditions."""

    async def check_metrics_for_alerts(self, metrics: PerformanceMetrics):
        """Check if metrics trigger any alerts."""
        return await self.check_alert_conditions(metrics)

    @abstractmethod
    async def configure_alert_thresholds(self, thresholds: dict[str, float]) -> bool:
        """Configure performance alert thresholds."""

    @abstractmethod
    async def get_active_alerts(self) -> list[dict[str, Any]]:
        """Get currently active performance alerts."""

    @abstractmethod
    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge and dismiss an alert."""


class IPerformanceOrchestrator(ABC):
    """Interface for the main performance monitoring orchestrator."""

    @abstractmethod
    async def initialize(self):
        """Initialize the performance monitoring system."""

    @abstractmethod
    async def start_operation_monitoring(self, context: OperationContext) -> str:
        """Start monitoring a new operation."""

    @abstractmethod
    async def finish_operation_monitoring(
        self, operation_id: str, success: bool, error_message: str | None = None
    ) -> PerformanceMetrics:
        """Finish monitoring an operation."""

    @abstractmethod
    async def analyze_performance(
        self,
        time_period: tuple[datetime, datetime] | None = None,
        adapter_filter: str | None = None,
    ) -> dict[str, Any]:
        """Perform comprehensive performance analysis."""

    @abstractmethod
    async def get_real_time_metrics(self) -> dict[str, Any]:
        """Get current real-time performance metrics."""

    @abstractmethod
    async def cleanup_old_data(self, retention_days: int = 30) -> dict[str, int]:
        """Clean up old performance data and return cleanup statistics."""
