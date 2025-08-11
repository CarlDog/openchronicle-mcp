#!/usr/bin/env python3
"""
Phase 3.0 Day 3: PerformanceMonitor Component

Extracted from ModelManager to handle performance tracking, metrics collection,
and analytics. Provides clean separation of concerns for monitoring functionality
with comprehensive performance analysis and optimization recommendations.

File: core/model_management/performance_monitor.py
"""

import json
import os
from contextlib import asynccontextmanager
from datetime import UTC
from datetime import datetime
from typing import Any

from openchronicle.shared.logging_system import log_error

# Import system components
from openchronicle.shared.logging_system import log_info
from openchronicle.shared.logging_system import log_system_event
from openchronicle.shared.logging_system import log_warning


UTC = UTC

try:
    # utilities.performance_monitor module doesn't exist - using fallback behavior
    UtilityPerformanceMonitor = None
    PERFORMANCE_MONITOR_AVAILABLE = False
except ImportError:
    PERFORMANCE_MONITOR_AVAILABLE = False


class PerformanceMonitor:
    """
    Manages performance tracking, metrics collection, and analytics.

    Extracted from ModelManager to provide focused responsibility for performance
    monitoring with clean interfaces and comprehensive analytics capabilities.
    """

    def __init__(self, adapters: dict[str, Any], config: dict[str, Any]):
        """
        Initialize the PerformanceMonitor.

        Args:
            adapters: Reference to the main adapters dictionary
            config: Configuration dictionary
        """
        self.adapters = adapters
        self.config = config

        # Performance monitoring state
        self.performance_monitor = None
        self.monitoring_enabled = False

        # Performance tracking data for test compatibility
        self.performance_history = []
        self.adapter_performance = {}

        # Initialize performance monitoring
        self._initialize_performance_monitoring()

        log_system_event(
            "performance_monitor_initialized", "Performance monitoring system ready"
        )

    def _initialize_performance_monitoring(self):
        """Initialize performance monitoring system."""
        try:
            if PERFORMANCE_MONITOR_AVAILABLE:
                self.performance_monitor = UtilityPerformanceMonitor()
                self.performance_monitor.start_monitoring()
                self.monitoring_enabled = True
                log_system_event(
                    "performance_monitoring_init",
                    "Performance monitoring system initialized",
                )
            else:
                log_system_event(
                    "performance_monitoring_disabled",
                    "Performance monitoring disabled - utilities not available",
                )
                self.monitoring_enabled = False
        except Exception as e:
            log_error(f"Failed to initialize performance monitoring: {e}")
            self.performance_monitor = None
            self.monitoring_enabled = False

    async def generate_performance_report(
        self, time_window_hours: int = 24
    ) -> dict[str, Any]:
        """
        Generate comprehensive performance diagnostic report.

        Args:
            time_window_hours: Hours to include in analysis

        Returns:
            Dictionary containing performance report and optimization recommendations
        """
        if not self.monitoring_enabled or not self.performance_monitor:
            return {
                "success": False,
                "error": "Performance monitoring not available",
                "recommendations": [
                    "Install psutil package to enable performance monitoring"
                ],
            }

        try:
            # Generate comprehensive report
            report = self.performance_monitor.generate_performance_report(
                time_window_hours
            )

            # Save report to file
            report_file = self.performance_monitor.save_report_to_file(report)

            # Get current system health
            health_summary = self.performance_monitor.get_system_health_summary()

            # Generate model registry updates
            registry_updates = self._generate_registry_performance_updates(report)

            # Apply automatic optimizations if enabled
            optimizations_applied = await self._apply_automatic_optimizations(report)

            log_system_event(
                "performance_report_generated",
                f"Performance report generated: {report.total_operations} operations analyzed, "
                f"{len(report.bottlenecks)} bottlenecks found, {len(report.optimization_recommendations)} recommendations",
            )

            return {
                "success": True,
                "report": report,
                "report_file": report_file,
                "health_summary": health_summary,
                "registry_updates": registry_updates,
                "optimizations_applied": optimizations_applied,
                "summary": {
                    "time_period": report.time_period,
                    "total_operations": report.total_operations,
                    "success_rate": report.successful_operations
                    / max(report.total_operations, 1),
                    "avg_duration": report.avg_duration,
                    "efficiency_score": report.avg_efficiency_score,
                    "bottlenecks_found": len(report.bottlenecks),
                    "recommendations_count": len(report.optimization_recommendations),
                    "performance_trend": report.performance_trend,
                    "trend_confidence": report.trend_confidence,
                    "fastest_models": report.fastest_models[:3],
                    "most_efficient_models": report.most_efficient_models[:3],
                    "critical_issues": [
                        b.description
                        for b in report.bottlenecks
                        if b.severity in ["critical", "high"]
                    ],
                },
            }

        except Exception as e:
            log_error(f"Failed to generate performance report: {e}")
            return {
                "success": False,
                "error": str(e),
                "recommendations": [
                    "Check performance monitoring system configuration"
                ],
            }

    async def get_model_performance_analytics(
        self, adapter_name: str | None = None
    ) -> dict[str, Any]:
        """
        Get detailed performance analytics for specific adapter or all adapters.

        Args:
            adapter_name: Specific adapter to analyze, or None for all adapters

        Returns:
            Dictionary containing performance analytics and rankings
        """
        if not self.monitoring_enabled or not self.performance_monitor:
            return {"success": False, "error": "Performance monitoring not available"}

        try:
            # Use fallback analytics for test compatibility
            analytics = {
                "adapter_name": adapter_name,
                "metrics": self.adapter_performance.get(adapter_name, {}),
                "timestamp": datetime.now(UTC).isoformat(),
            }

            # Add current adapter status
            if adapter_name:
                adapters_to_analyze = (
                    [adapter_name] if adapter_name in self.adapters else []
                )
            else:
                adapters_to_analyze = list(self.adapters.keys())

            adapter_status = {}
            for name in adapters_to_analyze:
                adapter = self.adapters.get(name)
                if adapter:
                    adapter_status[name] = {
                        "available": True,
                        "type": getattr(adapter, "provider_name", "unknown"),
                        "model_name": getattr(adapter, "model_name", name),
                        "initialized": getattr(adapter, "initialized", False),
                    }
                else:
                    adapter_status[name] = {
                        "available": False,
                        "reason": "Adapter not loaded",
                    }

            return {
                "success": True,
                "analytics": analytics,
                "adapter_status": adapter_status,
                "timestamp": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            log_error(f"Failed to get performance analytics: {e}")
            return {"success": False, "error": str(e)}

    def track_model_operation(self, adapter_name: str, operation_type: str, **kwargs):
        """
        Context manager for tracking model operation performance.

        Usage:
            async with performance_monitor.track_model_operation("gpt4", "generate") as tracker:
                result = await adapter.generate_response(prompt)
                tracker.set_tokens_processed(len(result.split()))
        """
        if self.monitoring_enabled and self.performance_monitor:
            return self.performance_monitor.track_operation(
                adapter_name, operation_type, **kwargs
            )

        # Return a no-op context manager if monitoring is disabled
        @asynccontextmanager
        async def dummy_tracker():
            class DummyTracker:
                def set_tokens_processed(self, count):
                    pass

                def set_response_size(self, size):
                    pass

                def set_network_latency(self, latency):
                    pass

                def set_processing_time(self, time):
                    pass

                def set_quality_score(self, score):
                    pass

            yield DummyTracker()

        return dummy_tracker()

    def get_performance_config(self) -> dict[str, Any]:
        """Get performance tuning configuration from the registry."""
        try:
            # Look for performance config in registry
            registry_file = os.path.join("config", "model_registry.json")
            if os.path.exists(registry_file):
                with open(registry_file, encoding="utf-8") as f:
                    registry = json.load(f)
                return registry.get("performance_tuning", {})
            return {}
        except Exception as e:
            log_error(f"Error getting performance config: {e}")
            return {}

    def is_monitoring_enabled(self) -> bool:
        """Check if performance monitoring is enabled and available."""
        return self.monitoring_enabled and self.performance_monitor is not None

    def get_system_health_summary(self) -> dict[str, Any]:
        """Get current system health summary."""
        if not self.monitoring_enabled or not self.performance_monitor:
            return {
                "available": False,
                "reason": "Performance monitoring not available",
            }

        try:
            return self.performance_monitor.get_system_health_summary()
        except Exception as e:
            log_error(f"Failed to get system health summary: {e}")
            return {"available": False, "error": str(e)}

    async def optimize_model_performance(
        self, adapter_name: str | None = None
    ) -> dict[str, Any]:
        """
        Apply performance optimizations for specific adapter or all adapters.

        Args:
            adapter_name: Specific adapter to optimize, or None for all adapters

        Returns:
            Dictionary containing optimization results
        """
        if not self.monitoring_enabled or not self.performance_monitor:
            return {"success": False, "error": "Performance monitoring not available"}

        try:
            # Generate performance report first
            report_result = await self.generate_performance_report(24)
            if not report_result["success"]:
                return report_result

            report = report_result["report"]
            optimizations = []

            # Apply optimizations based on report recommendations
            for recommendation in report.optimization_recommendations:
                if adapter_name and recommendation.adapter_name != adapter_name:
                    continue

                optimization_result = await self._apply_optimization(recommendation)
                optimizations.append(optimization_result)

            return {
                "success": True,
                "optimizations_applied": optimizations,
                "total_optimizations": len(optimizations),
                "timestamp": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            log_error(f"Failed to optimize model performance: {e}")
            return {"success": False, "error": str(e)}

    def _generate_registry_performance_updates(self, report) -> dict[str, Any]:
        """Generate performance-based updates for model registry."""
        try:
            updates = {}

            # Update performance ratings for each model
            for adapter_name, rating in report.model_rankings.items():
                updates[adapter_name] = {
                    "performance_rating": rating,
                    "last_benchmark": datetime.now(UTC).isoformat(),
                    "operations_count": report.total_operations,
                }

            # Add speed rankings
            for i, (adapter_name, speed_score) in enumerate(report.fastest_models):
                if adapter_name in updates:
                    updates[adapter_name]["speed_rank"] = i + 1
                    updates[adapter_name]["speed_score"] = speed_score

            # Add efficiency rankings
            for i, (adapter_name, efficiency_score) in enumerate(
                report.most_efficient_models
            ):
                if adapter_name in updates:
                    updates[adapter_name]["efficiency_rank"] = i + 1
                    updates[adapter_name]["efficiency_score"] = efficiency_score

            # Add reliability rankings
            for i, (adapter_name, reliability_score) in enumerate(
                report.most_reliable_models
            ):
                if adapter_name in updates:
                    updates[adapter_name]["reliability_rank"] = i + 1
                    updates[adapter_name]["reliability_score"] = reliability_score

            return {
                "success": True,
                "updates": updates,
                "timestamp": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            log_error(f"Failed to generate registry performance updates: {e}")
            return {"success": False, "error": str(e)}

    async def _apply_automatic_optimizations(self, report) -> list[dict[str, Any]]:
        """Apply automatic optimizations based on performance report."""
        optimizations = []

        try:
            # Apply low-risk optimizations automatically
            for recommendation in report.optimization_recommendations:
                if recommendation.risk_level == "low" and recommendation.auto_apply:
                    optimization_result = await self._apply_optimization(recommendation)
                    optimizations.append(optimization_result)

            return optimizations

        except Exception as e:
            log_error(f"Failed to apply automatic optimizations: {e}")
            return []

    async def _apply_optimization(self, recommendation) -> dict[str, Any]:
        """Apply a specific optimization recommendation."""
        try:
            # This would implement specific optimization logic
            # For now, return a mock result
            return {
                "recommendation_id": getattr(recommendation, "id", "unknown"),
                "adapter_name": getattr(recommendation, "adapter_name", "unknown"),
                "optimization_type": getattr(recommendation, "type", "unknown"),
                "applied": False,
                "reason": "Optimization logic not yet implemented",
                "timestamp": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            log_error(f"Failed to apply optimization: {e}")
            return {
                "applied": False,
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat(),
            }

    # Recording methods for integration compatibility
    def record_response_time(self, adapter_name: str, response_time: float):
        """Record response time for adapter."""
        if adapter_name not in self.adapter_performance:
            self.adapter_performance[adapter_name] = {
                "response_times": [],
                "success_count": 0,
                "failure_count": 0,
            }

        self.adapter_performance[adapter_name]["response_times"].append(response_time)
        log_info(f"Recorded response time for {adapter_name}: {response_time:.3f}s")

    def record_success(self, adapter_name: str, input_tokens: int, output_tokens: int):
        """Record successful operation for adapter."""
        if adapter_name not in self.adapter_performance:
            self.adapter_performance[adapter_name] = {
                "response_times": [],
                "success_count": 0,
                "failure_count": 0,
            }

        self.adapter_performance[adapter_name]["success_count"] += 1
        log_info(
            f"Recorded success for {adapter_name}: {input_tokens} in, {output_tokens} out"
        )

    def record_failure(self, adapter_name: str, error_type: str, error_message: str):
        """Record failed operation for adapter."""
        if adapter_name not in self.adapter_performance:
            self.adapter_performance[adapter_name] = {
                "response_times": [],
                "success_count": 0,
                "failure_count": 0,
            }

        self.adapter_performance[adapter_name]["failure_count"] += 1
        log_warning(
            f"Recorded failure for {adapter_name}: {error_type} - {error_message}"
        )

    def get_performance_summary(self, adapter_name: str = None) -> dict[str, Any]:
        """Get performance summary for adapter or all adapters."""
        if adapter_name:
            return self.adapter_performance.get(adapter_name, {})
        return self.adapter_performance
