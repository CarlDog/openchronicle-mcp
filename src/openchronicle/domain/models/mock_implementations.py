"""
Mock Implementations - Fallback implementations for domain interfaces

These mock implementations provide fallback behavior when infrastructure
adapters are not available, maintaining system stability.
"""

from typing import Any

from .model_interfaces import IModelPerformanceMonitor


class MockPerformanceMonitor(IModelPerformanceMonitor):
    """Mock implementation of performance monitoring."""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def record_response_time(self, adapter_name: str, response_time: float) -> None:
        """Record response time for performance tracking."""
        pass

    def record_success(
        self, adapter_name: str, prompt_length: int, response_length: int
    ) -> None:
        """Record successful operation metrics."""
        pass

    def record_failure(
        self, adapter_name: str, error_type: str, error_message: str
    ) -> None:
        """Record failure metrics for analysis."""
        pass

    def get_performance_stats(self) -> dict[str, Any]:
        """Get overall performance statistics."""
        return {"total_requests": 0, "avg_response_time": 0.1, "success_rate": 1.0}

    def get_adapter_metrics(self, adapter_name: str) -> dict[str, Any]:
        """Get performance metrics for specific adapter."""
        return {"requests": 0, "avg_response_time": 0.1, "success_rate": 1.0}

    def get_success_rate(self, adapter_name: str, window_hours: int = 24) -> float:
        """Get success rate for adapter in time window."""
        return 1.0

    def get_average_response_time(
        self, adapter_name: str, window_hours: int = 24
    ) -> float:
        """Get average response time for adapter in time window."""
        return 0.1

    def get_error_analysis(
        self, adapter_name: str, window_hours: int = 24
    ) -> dict[str, Any]:
        """Get error analysis for adapter in time window."""
        return {"errors": [], "error_rate": 0.0, "most_common_error": None}

    def start_monitoring(self) -> None:
        """Start background performance monitoring."""
        pass

    def stop_monitoring(self) -> None:
        """Stop background performance monitoring."""
        pass

    async def generate_performance_report(self, output_path: str | None = None) -> dict[str, Any]:
        """Generate comprehensive performance report (async)."""
        return {"report_generated": True, "path": output_path, "timestamp": "mock"}

    def get_system_health_summary(self) -> dict[str, Any]:
        """Return a simple system health summary for orchestrator tests."""
        return {"status": "healthy", "active_adapters": 0, "avg_response_time": 0.1}

    async def get_model_performance_analytics(self) -> dict[str, Any]:
        """Return basic analytics payload for optimization logic (async)."""
        return {"analytics": "mock", "recommendations": [], "metrics": {}}

    async def optimize_model_performance(self) -> dict[str, Any]:
        """Return placeholder optimization result (async)."""
        return {"optimized": True, "changes": [], "performance_gain": 0.0}
