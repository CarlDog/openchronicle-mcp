"""
Production Monitoring Integration

Comprehensive production monitoring for distributed caching.
Now fully modularized for better maintainability.

Provides integrations with:
- Prometheus metrics export
- Health check endpoints
- Structured logging
- Performance benchmarking for production deployment
"""

import asyncio
import logging
import os
import time
from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from .health_checker import HealthChecker
from .health_checker import HealthCheckResult
from .prometheus_exporter import PrometheusExporter
from .structured_logger import StructuredLogger


if TYPE_CHECKING:
    from ...cache_orchestrator import DistributedMultiTierCache
    from .analytics.performance_analytics import CacheAnalyticsDashboard


class ProductionMonitoring:
    """
    Production monitoring integration for distributed caching.

    Provides comprehensive monitoring capabilities for production deployment.
    """

    def __init__(
        self,
        cache: "DistributedMultiTierCache",
        dashboard: "CacheAnalyticsDashboard | None" = None,
    ):
        self.cache = cache
        self.dashboard = dashboard
        self.prometheus_exporter = PrometheusExporter(cache)
        self.health_checker = HealthChecker(cache)
        self.structured_logger = StructuredLogger(cache)
        self.logger = logging.getLogger("openchronicle.cache.production")

        # Monitoring state
        self._monitoring_active = False
        self._monitoring_tasks = []

    async def start_production_monitoring(self, metrics_interval: int = 60, health_check_interval: int = 30):
        """Start production monitoring with specified intervals."""
        if self._monitoring_active:
            return

        self._monitoring_active = True

        # Start metrics collection
        metrics_task = asyncio.create_task(self._metrics_monitoring_loop(metrics_interval))
        self._monitoring_tasks.append(metrics_task)

        # Start health checks
        health_task = asyncio.create_task(self._health_monitoring_loop(health_check_interval))
        self._monitoring_tasks.append(health_task)

        self.logger.info(
            f"Production monitoring started - metrics: {metrics_interval}s, health: {health_check_interval}s"
        )

    async def stop_production_monitoring(self):
        """Stop all production monitoring."""
        self._monitoring_active = False

        for task in self._monitoring_tasks:
            task.cancel()

        await asyncio.gather(*self._monitoring_tasks, return_exceptions=True)
        self._monitoring_tasks.clear()

        self.logger.info("Production monitoring stopped")

    async def _metrics_monitoring_loop(self, interval: int):
        """Background metrics collection and logging."""
        while self._monitoring_active:
            try:
                metrics = await self.cache.get_distributed_metrics()
                self.structured_logger.log_performance_metrics(metrics)

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception("Metrics monitoring error")
                await asyncio.sleep(interval)

    async def _health_monitoring_loop(self, interval: int):
        """Background health check monitoring."""
        while self._monitoring_active:
            try:
                health_result = await self.health_checker.comprehensive_health_check()

                # Log health status changes
                if health_result["overall_status"] != "healthy":
                    self.structured_logger.log_alert(
                        "health_check",
                        health_result["overall_status"],
                        f"System health check status: {health_result['overall_status']}",
                        health_result,
                    )

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception("Health monitoring error")
                await asyncio.sleep(interval)

    async def get_prometheus_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        return await self.prometheus_exporter.export_metrics()

    async def get_health_status(self) -> dict[str, Any]:
        """Get current health status."""
        return await self.health_checker.comprehensive_health_check()

    async def benchmark_production_performance(self, duration_seconds: int = 300) -> dict[str, Any]:
        """Run production performance benchmark."""
        self.logger.info(f"Starting production benchmark for {duration_seconds} seconds")

        start_time = time.time()
        end_time = start_time + duration_seconds

        # Collect initial metrics
        initial_metrics = await self.cache.get_distributed_metrics()

        # Run test operations
        operations_completed = 0
        errors = 0

        while time.time() < end_time:
            try:
                # Simulate typical cache operations
                test_key = f"benchmark_{int(time.time() * 1000000)}"
                test_data = {
                    "character": "BenchmarkChar",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "data": "x" * 100,  # 100 character payload
                }

                # Set, get cycle (removed delete since it's not implemented)
                await self.cache.set(test_key, test_data, ttl=60)
                retrieved = await self.cache.get(test_key)

                operations_completed += 2

                # Small delay to avoid overwhelming
                await asyncio.sleep(0.01)

            except Exception as e:
                errors += 1
                self.logger.warning(f"Benchmark operation error: {e}")

        # Collect final metrics
        final_metrics = await self.cache.get_distributed_metrics()

        actual_duration = time.time() - start_time

        benchmark_results = {
            "duration_seconds": actual_duration,
            "operations_completed": operations_completed,
            "operations_per_second": operations_completed / actual_duration,
            "errors": errors,
            "error_rate": (errors / operations_completed if operations_completed > 0 else 0),
            "initial_metrics": initial_metrics,
            "final_metrics": final_metrics,
            "performance_improvement": {
                "hit_rate_delta": final_metrics.get("overall_hit_rate", 0) - initial_metrics.get("overall_hit_rate", 0),
                "response_time_delta": final_metrics.get("avg_redis_response_ms", 0)
                - initial_metrics.get("avg_redis_response_ms", 0),
            },
        }

        self.structured_logger.log_cache_event("production_benchmark", benchmark_results)
        self.logger.info(
            f"Benchmark completed: {operations_completed} ops in {actual_duration:.1f}s ({operations_completed/actual_duration:.1f} ops/sec)"
        )

        return benchmark_results

    def setup_environment_monitoring(self) -> dict[str, str]:
        """Setup environment-specific monitoring configuration."""
        env = os.getenv("ENVIRONMENT", "development")

        configs = {
            "development": {
                "metrics_interval": "60",
                "health_check_interval": "30",
                "log_level": "DEBUG",
            },
            "staging": {
                "metrics_interval": "30",
                "health_check_interval": "15",
                "log_level": "INFO",
            },
            "production": {
                "metrics_interval": "15",
                "health_check_interval": "10",
                "log_level": "WARNING",
            },
        }

        config = configs.get(env, configs["development"])

        # Apply configuration
        logging.getLogger("openchronicle.cache").setLevel(getattr(logging, config["log_level"]))

        self.logger.info(f"Monitoring configured for {env} environment")

        return config


# Convenience function for production setup
async def setup_production_monitoring(
    cache: "DistributedMultiTierCache",
) -> ProductionMonitoring:
    """Setup production monitoring with recommended settings."""
    monitoring = ProductionMonitoring(cache)

    # Configure for environment
    config = monitoring.setup_environment_monitoring()

    # Start monitoring
    await monitoring.start_production_monitoring(
        metrics_interval=int(config["metrics_interval"]),
        health_check_interval=int(config["health_check_interval"]),
    )

    return monitoring
