#!/usr/bin/env python3
"""
OpenChronicle Performance Orchestrator

Central orchestrator for the modular performance monitoring system.
Coordinates metrics collection, storage, analysis, and reporting.
"""

from dataclasses import asdict
from datetime import datetime
from datetime import timedelta
from typing import Any

from openchronicle.shared.logging_system import get_logger
from openchronicle.shared.logging_system import log_system_event

from .analysis.bottleneck_analyzer import BottleneckAnalyzer
from .interfaces.performance_interfaces import IAlertManager
from .interfaces.performance_interfaces import IBottleneckAnalyzer
from .interfaces.performance_interfaces import IMetricsCollector
from .interfaces.performance_interfaces import IMetricsStorage
from .interfaces.performance_interfaces import IPerformanceOrchestrator
from .interfaces.performance_interfaces import IReportGenerator
from .interfaces.performance_interfaces import ITrendAnalyzer
from .interfaces.performance_interfaces import OperationContext
from .interfaces.performance_interfaces import PerformanceMetrics
from .metrics.collector import MetricsCollector
from .metrics.storage import MetricsStorage


class PerformanceOrchestrator(IPerformanceOrchestrator):
    """Orchestrates all performance monitoring components with dependency injection."""

    def __init__(
        self,
        metrics_collector: IMetricsCollector | None = None,
        metrics_storage: IMetricsStorage | None = None,
        bottleneck_analyzer: IBottleneckAnalyzer | None = None,
        trend_analyzer: ITrendAnalyzer | None = None,
        report_generator: IReportGenerator | None = None,
        alert_manager: IAlertManager | None = None,
    ):
        """Initialize orchestrator with dependency injection."""
        self.logger = get_logger()

        # Inject dependencies or use defaults
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.metrics_storage = metrics_storage or MetricsStorage()
        self.bottleneck_analyzer = bottleneck_analyzer or BottleneckAnalyzer()
        # TODO: Implement these components
        self.trend_analyzer = trend_analyzer  # Will be None until implemented
        self.report_generator = report_generator  # Will be None until implemented
        self.alert_manager = alert_manager  # Will be None until implemented

        self._initialized = False
        self._monitoring_enabled = True

    async def initialize(self):
        """Initialize all components."""
        if self._initialized:
            return

        try:
            # Initialize storage component
            if hasattr(self.metrics_storage, "initialize"):
                await self.metrics_storage.initialize()

            # Initialize other components as needed
            # (Most components don't require initialization)

            self._initialized = True

            log_system_event(
                "performance_orchestrator",
                "Orchestrator initialized",
                {
                    "components": {
                        "metrics_collector": type(self.metrics_collector).__name__,
                        "metrics_storage": type(self.metrics_storage).__name__,
                        "bottleneck_analyzer": type(self.bottleneck_analyzer).__name__,
                        "trend_analyzer": (
                            type(self.trend_analyzer).__name__
                            if self.trend_analyzer
                            else None
                        ),
                        "report_generator": (
                            type(self.report_generator).__name__
                            if self.report_generator
                            else None
                        ),
                        "alert_manager": (
                            type(self.alert_manager).__name__
                            if self.alert_manager
                            else None
                        ),
                    }
                },
            )

        except Exception as e:
            self.logger.error(f"Failed to initialize performance orchestrator: {e}")
            raise

    async def start_operation_monitoring(self, context: OperationContext) -> str:
        """Start monitoring a model operation."""
        if not self._monitoring_enabled:
            return context.operation_id

        if not self._initialized:
            await self.initialize()

        try:
            # Start metrics collection
            operation_id = await self.metrics_collector.start_operation_tracking(
                context
            )

            log_system_event(
                "performance_orchestrator",
                "Operation monitoring started",
                {
                    "operation_id": operation_id,
                    "adapter_name": context.adapter_name,
                    "operation_type": context.operation_type,
                },
            )

            return operation_id

        except Exception as e:
            self.logger.error(f"Failed to start operation monitoring: {e}")
            return context.operation_id

    async def finish_operation_monitoring(
        self, operation_id: str, success: bool, error_message: str | None = None
    ) -> PerformanceMetrics:
        """Finish monitoring an operation and store metrics."""
        if not self._monitoring_enabled:
            # Return a basic metrics object if monitoring is disabled
            return self._create_fallback_metrics(operation_id, success, error_message)

        if not self._initialized:
            await self.initialize()

        try:
            # Finish metrics collection
            metrics = await self.metrics_collector.finish_operation_tracking(
                operation_id, success, error_message
            )

            # Store metrics
            await self.metrics_storage.store_metrics(metrics)

            # Check for alerts if alert manager is available
            if self.alert_manager:
                await self._check_alerts(metrics)

            log_system_event(
                "performance_orchestrator",
                "Operation monitoring completed",
                {
                    "operation_id": operation_id,
                    "duration": metrics.duration,
                    "success": success,
                    "adapter_name": metrics.adapter_name,
                },
            )

            return metrics

        except Exception as e:
            self.logger.error(
                f"Failed to finish operation monitoring for {operation_id}: {e}"
            )
            return self._create_fallback_metrics(operation_id, success, error_message)

    async def analyze_performance(
        self,
        time_period: tuple[datetime, datetime] | None = None,
        adapter_filter: str | None = None,
    ) -> dict[str, Any]:
        """Perform comprehensive performance analysis."""
        if not self._initialized:
            await self.initialize()

        try:
            # Default to last 24 hours if no time period specified
            if not time_period:
                end_time = datetime.now()
                start_time = end_time - timedelta(hours=24)
                time_period = (start_time, end_time)

            # Build metrics query
            from .interfaces import MetricsQuery

            query = MetricsQuery(
                start_time=time_period[0],
                end_time=time_period[1],
                adapter_names=[adapter_filter] if adapter_filter else None,
                limit=10000,  # Reasonable limit for analysis
            )

            # Retrieve metrics
            metrics = await self.metrics_storage.retrieve_metrics(query)

            # Get storage summary
            storage_summary = await self.metrics_storage.get_metrics_summary(
                time_period, adapter_filter
            )

            # Perform bottleneck analysis
            bottleneck_report = await self.bottleneck_analyzer.analyze_bottlenecks(
                metrics
            )

            # Identify slow operations
            slow_operations = await self.bottleneck_analyzer.identify_slow_operations(
                metrics
            )

            # Analyze resource usage patterns
            resource_patterns = (
                await self.bottleneck_analyzer.analyze_resource_usage_patterns(metrics)
            )

            # Compile comprehensive analysis
            analysis = {
                "analysis_time": datetime.now().isoformat(),
                "time_period": {
                    "start": time_period[0].isoformat(),
                    "end": time_period[1].isoformat(),
                },
                "adapter_filter": adapter_filter,
                "metrics_summary": storage_summary,
                "bottleneck_analysis": asdict(bottleneck_report),
                "slow_operations": {
                    "count": len(slow_operations),
                    "operations": [asdict(op) for op in slow_operations[:10]],  # Top 10
                },
                "resource_patterns": resource_patterns,
                "recommendations": bottleneck_report.recommendations,
            }

            # Add trend analysis if available
            if self.trend_analyzer:
                trend_analysis = await self.trend_analyzer.analyze_trends(
                    metrics, time_period
                )
                analysis["trend_analysis"] = asdict(trend_analysis)

            log_system_event(
                "performance_orchestrator",
                "Performance analysis completed",
                {
                    "metrics_analyzed": len(metrics),
                    "bottlenecks_found": len(bottleneck_report.bottleneck_patterns),
                    "slow_operations": len(slow_operations),
                    "time_period_hours": (
                        time_period[1] - time_period[0]
                    ).total_seconds()
                    / 3600,
                },
            )

            return analysis

        except Exception as e:
            self.logger.error(f"Failed to analyze performance: {e}")
            return {
                "analysis_time": datetime.now().isoformat(),
                "error": str(e),
                "recommendations": ["Analysis failed - check system logs"],
            }

    async def get_real_time_metrics(self) -> dict[str, Any]:
        """Get current real-time performance metrics."""
        if not self._initialized:
            await self.initialize()

        try:
            # Get system metrics from collector
            system_metrics = self.metrics_collector.collect_system_metrics()

            # Get collector status
            collector_status = self.metrics_collector.get_collection_status()

            # Get storage stats
            storage_stats = await self.metrics_storage.get_storage_stats()

            # Compile real-time metrics
            real_time_metrics = {
                "timestamp": datetime.now().isoformat(),
                "system_metrics": system_metrics,
                "collector_status": collector_status,
                "storage_stats": storage_stats,
                "monitoring_enabled": self._monitoring_enabled,
                "initialized": self._initialized,
            }

            return real_time_metrics

        except Exception as e:
            self.logger.error(f"Failed to get real-time metrics: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "monitoring_enabled": self._monitoring_enabled,
                "initialized": self._initialized,
            }

    async def cleanup_old_data(self, retention_days: int = 30) -> dict[str, int]:
        """Clean up old performance data."""
        if not self._initialized:
            await self.initialize()

        try:
            # Clean up storage
            deleted_metrics = await self.metrics_storage.cleanup_old_metrics(
                retention_days
            )

            # Clean up stale operations in collector
            cleaned_operations = await self.metrics_collector.cleanup_stale_operations(
                24
            )  # 24 hours

            cleanup_stats = {
                "deleted_metrics": deleted_metrics,
                "cleaned_operations": cleaned_operations,
                "retention_days": retention_days,
            }

            log_system_event(
                "performance_orchestrator", "Data cleanup completed", cleanup_stats
            )

            return cleanup_stats

        except Exception as e:
            self.logger.error(f"Failed to cleanup old data: {e}")
            return {
                "deleted_metrics": 0,
                "cleaned_operations": 0,
                "retention_days": retention_days,
            }

    async def generate_performance_report(
        self, time_period: tuple[datetime, datetime], report_format: str = "json"
    ) -> dict[str, Any]:
        """Generate a comprehensive performance report."""
        if not self._initialized:
            await self.initialize()

        try:
            # Perform full analysis
            analysis = await self.analyze_performance(time_period)

            # Use report generator if available
            if self.report_generator:
                formatted_report = await self.report_generator.generate_report(
                    analysis, report_format
                )
                return formatted_report
            # Return analysis as basic report
            return {
                "report_type": "performance_analysis",
                "format": report_format,
                "generated_at": datetime.now().isoformat(),
                "data": analysis,
            }

        except Exception as e:
            self.logger.error(f"Failed to generate performance report: {e}")
            return {
                "report_type": "performance_analysis",
                "format": report_format,
                "generated_at": datetime.now().isoformat(),
                "error": str(e),
            }

    def enable_monitoring(self):
        """Enable performance monitoring."""
        self._monitoring_enabled = True
        if hasattr(self.metrics_collector, "enable_collection"):
            self.metrics_collector.enable_collection()

        log_system_event("performance_orchestrator", "Monitoring enabled", {})

    def disable_monitoring(self):
        """Disable performance monitoring."""
        self._monitoring_enabled = False
        if hasattr(self.metrics_collector, "disable_collection"):
            self.metrics_collector.disable_collection()

        log_system_event("performance_orchestrator", "Monitoring disabled", {})

    async def initialize_monitoring(self, story_id: str) -> bool:
        """Initialize monitoring for a specific story."""
        try:
            # Initialize the orchestrator if not already done
            if not self._initialized:
                await self.initialize()
            
            # Enable monitoring
            self.enable_monitoring()
            
            # Log initialization
            log_system_event(
                "performance_orchestrator", 
                f"Monitoring initialized for story: {story_id}",
                {"story_id": story_id}
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing monitoring for story {story_id}: {e}")
            return False

    def get_monitoring_status(self) -> dict[str, Any]:
        """Get current monitoring status."""
        return {
            "monitoring_enabled": self._monitoring_enabled,
            "initialized": self._initialized,
            "components": {
                "metrics_collector": type(self.metrics_collector).__name__,
                "metrics_storage": type(self.metrics_storage).__name__,
                "bottleneck_analyzer": type(self.bottleneck_analyzer).__name__,
                "trend_analyzer": (
                    type(self.trend_analyzer).__name__ if self.trend_analyzer else None
                ),
                "report_generator": (
                    type(self.report_generator).__name__
                    if self.report_generator
                    else None
                ),
                "alert_manager": (
                    type(self.alert_manager).__name__ if self.alert_manager else None
                ),
            },
        }

    async def _check_alerts(self, metrics: PerformanceMetrics):
        """Check if metrics trigger any alerts."""
        try:
            if self.alert_manager:
                await self.alert_manager.check_metrics_for_alerts(metrics)
        except Exception as e:
            self.logger.error(f"Failed to check alerts for {metrics.operation_id}: {e}")

    def _create_fallback_metrics(
        self, operation_id: str, success: bool, error_message: str | None
    ) -> PerformanceMetrics:
        """Create fallback metrics when monitoring is disabled or fails."""
        current_time = datetime.now().timestamp()

        return PerformanceMetrics(
            operation_id=operation_id,
            adapter_name="unknown",
            operation_type="unknown",
            start_time=current_time,
            end_time=current_time,
            duration=0.0,
            cpu_usage_before=0.0,
            cpu_usage_after=0.0,
            memory_usage_before=0.0,
            memory_usage_after=0.0,
            success=success,
            error_message=error_message,
            context={"monitoring_disabled": True},
        )
