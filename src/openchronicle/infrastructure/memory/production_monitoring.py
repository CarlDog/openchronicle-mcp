"""
Production Monitoring Integration - Week 17
Integration with observability tools and production monitoring systems

Provides integrations with:
- Prometheus metrics export
- Health check endpoints
- Structured logging
- Performance benchmarking for production deployment
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import asdict
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

from .distributed_cache import DistributedMultiTierCache
from .performance_analytics import CacheAnalyticsDashboard


@dataclass
class HealthCheckResult:
    """Health check result for monitoring systems."""

    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    response_time_ms: float
    details: dict[str, Any]
    timestamp: datetime


class PrometheusExporter:
    """Export cache metrics in Prometheus format."""

    def __init__(self, cache: DistributedMultiTierCache):
        self.cache = cache
        self.logger = logging.getLogger("openchronicle.cache.prometheus")

    async def export_metrics(self) -> str:
        """Export metrics in Prometheus format."""
        metrics = await self.cache.get_distributed_metrics()
        prometheus_lines = []

        # Basic cache metrics
        prometheus_lines.extend(
            [
                "# HELP openchronicle_cache_hit_rate Overall cache hit rate",
                "# TYPE openchronicle_cache_hit_rate gauge",
                f"openchronicle_cache_hit_rate {metrics.get('overall_hit_rate', 0):.6f}",
                "",
                "# HELP openchronicle_cache_operations_total Total cache operations",
                "# TYPE openchronicle_cache_operations_total counter",
                f"openchronicle_cache_operations_total {metrics.get('total_operations', 0)}",
                "",
                "# HELP openchronicle_redis_response_time_ms Average Redis response time in milliseconds",
                "# TYPE openchronicle_redis_response_time_ms gauge",
                f"openchronicle_redis_response_time_ms {metrics.get('avg_redis_response_ms', 0):.3f}",
                "",
            ]
        )

        # Redis-specific metrics
        prometheus_lines.extend(
            [
                "# HELP openchronicle_redis_hit_rate Redis cache hit rate",
                "# TYPE openchronicle_redis_hit_rate gauge",
                f"openchronicle_redis_hit_rate {metrics.get('redis_hit_rate', 0):.6f}",
                "",
                "# HELP openchronicle_local_hit_rate Local cache hit rate",
                "# TYPE openchronicle_local_hit_rate gauge",
                f"openchronicle_local_hit_rate {metrics.get('local_hit_rate', 0):.6f}",
                "",
            ]
        )

        # Cluster node metrics
        cluster_nodes = metrics.get("cluster_nodes", {})
        if cluster_nodes:
            prometheus_lines.extend(
                [
                    "# HELP openchronicle_cluster_node_operations Operations per cluster node",
                    "# TYPE openchronicle_cluster_node_operations gauge",
                ]
            )

            for node_id, node_metrics in cluster_nodes.items():
                operations = node_metrics.get("operations", 0)
                success_rate = node_metrics.get("success_rate", 0)
                response_time = node_metrics.get("avg_response_ms", 0)

                prometheus_lines.extend(
                    [
                        f'openchronicle_cluster_node_operations{{node="{node_id}"}} {operations}',
                        f'openchronicle_cluster_node_success_rate{{node="{node_id}"}} {success_rate:.6f}',
                        f'openchronicle_cluster_node_response_time_ms{{node="{node_id}"}} {response_time:.3f}',
                    ]
                )

            prometheus_lines.append("")

        # Partition metrics
        partitions = metrics.get("partitions", {})
        if partitions:
            prometheus_lines.extend(
                [
                    "# HELP openchronicle_partition_operations Operations per partition",
                    "# TYPE openchronicle_partition_operations gauge",
                ]
            )

            for partition_id, partition_metrics in partitions.items():
                operations = partition_metrics.get("operations", 0)
                unique_keys = partition_metrics.get("unique_keys", 0)

                prometheus_lines.extend(
                    [
                        f'openchronicle_partition_operations{{partition="{partition_id}"}} {operations}',
                        f'openchronicle_partition_unique_keys{{partition="{partition_id}"}} {unique_keys}',
                    ]
                )

            prometheus_lines.append("")

        # Cache warming metrics
        warming_metrics = metrics.get("cache_warming", {})
        if warming_metrics:
            prometheus_lines.extend(
                [
                    "# HELP openchronicle_cache_warming_operations Cache warming operations count",
                    "# TYPE openchronicle_cache_warming_operations counter",
                    f"openchronicle_cache_warming_operations {warming_metrics.get('operations', 0)}",
                    "",
                    "# HELP openchronicle_cache_warming_success_rate Cache warming success rate",
                    "# TYPE openchronicle_cache_warming_success_rate gauge",
                    f"openchronicle_cache_warming_success_rate {warming_metrics.get('success_rate', 0):.6f}",
                    "",
                    "# HELP openchronicle_cache_warming_time_ms Average cache warming time",
                    "# TYPE openchronicle_cache_warming_time_ms gauge",
                    f"openchronicle_cache_warming_time_ms {warming_metrics.get('avg_time_ms', 0):.3f}",
                    "",
                ]
            )

        # Uptime metric
        prometheus_lines.extend(
            [
                "# HELP openchronicle_cache_uptime_seconds Cache system uptime in seconds",
                "# TYPE openchronicle_cache_uptime_seconds counter",
                f"openchronicle_cache_uptime_seconds {metrics.get('uptime_seconds', 0):.1f}",
                "",
            ]
        )

        return "\n".join(prometheus_lines)


class HealthChecker:
    """Performs health checks for production monitoring."""

    def __init__(self, cache: DistributedMultiTierCache):
        self.cache = cache
        self.logger = logging.getLogger("openchronicle.cache.health")

    async def check_redis_connectivity(self) -> HealthCheckResult:
        """Check Redis connectivity and basic operations."""
        start_time = time.time()

        try:
            # Test basic connectivity
            clients = await self.cache.cluster_manager.get_all_clients()

            if not clients:
                return HealthCheckResult(
                    name="redis_connectivity",
                    status="unhealthy",
                    response_time_ms=(time.time() - start_time) * 1000,
                    details={"error": "No Redis clients available"},
                    timestamp=datetime.now(UTC),
                )

            # Test each client
            failed_nodes = []
            total_response_time = 0

            for client, node_index in clients:
                try:
                    node_start = time.time()
                    await client.ping()
                    node_time = time.time() - node_start
                    total_response_time += node_time
                except Exception as e:
                    failed_nodes.append(f"node_{node_index}: {e!s}")

            avg_response_time = total_response_time / len(clients) if clients else 0
            response_time_ms = (time.time() - start_time) * 1000

            if failed_nodes:
                status = "degraded" if len(failed_nodes) < len(clients) else "unhealthy"
                details = {
                    "total_nodes": len(clients),
                    "failed_nodes": len(failed_nodes),
                    "failures": failed_nodes,
                    "avg_node_response_ms": avg_response_time * 1000,
                }
            else:
                status = "healthy"
                details = {
                    "total_nodes": len(clients),
                    "avg_node_response_ms": avg_response_time * 1000,
                }

            return HealthCheckResult(
                name="redis_connectivity",
                status=status,
                response_time_ms=response_time_ms,
                details=details,
                timestamp=datetime.now(UTC),
            )

        except Exception as e:
            return HealthCheckResult(
                name="redis_connectivity",
                status="unhealthy",
                response_time_ms=(time.time() - start_time) * 1000,
                details={"error": str(e)},
                timestamp=datetime.now(UTC),
            )

    async def check_cache_operations(self) -> HealthCheckResult:
        """Check cache operations (set/get/delete)."""
        start_time = time.time()

        try:
            test_key = f"health_check_{int(time.time())}"
            test_value = {
                "health_check": True,
                "timestamp": datetime.now(UTC).isoformat(),
            }

            # Test set operation
            set_success = await self.cache.set(test_key, test_value, ttl=60)

            if not set_success:
                return HealthCheckResult(
                    name="cache_operations",
                    status="unhealthy",
                    response_time_ms=(time.time() - start_time) * 1000,
                    details={"error": "Failed to set test value"},
                    timestamp=datetime.now(UTC),
                )

            # Test get operation
            retrieved_value = await self.cache.get(test_key)

            if retrieved_value != test_value:
                return HealthCheckResult(
                    name="cache_operations",
                    status="degraded",
                    response_time_ms=(time.time() - start_time) * 1000,
                    details={"error": "Retrieved value doesn't match set value"},
                    timestamp=datetime.now(UTC),
                )

            # Test delete operation
            delete_success = await self.cache.delete(test_key)

            response_time_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                name="cache_operations",
                status="healthy",
                response_time_ms=response_time_ms,
                details={
                    "operations_tested": ["set", "get", "delete"],
                    "all_successful": delete_success,
                },
                timestamp=datetime.now(UTC),
            )

        except Exception as e:
            return HealthCheckResult(
                name="cache_operations",
                status="unhealthy",
                response_time_ms=(time.time() - start_time) * 1000,
                details={"error": str(e)},
                timestamp=datetime.now(UTC),
            )

    async def check_performance_thresholds(self) -> HealthCheckResult:
        """Check if performance meets acceptable thresholds."""
        start_time = time.time()

        try:
            metrics = await self.cache.get_distributed_metrics()

            # Define performance thresholds
            thresholds = {
                "min_hit_rate": 0.7,
                "max_response_time_ms": 100,
                "min_operations_per_second": 10,
            }

            issues = []
            hit_rate = metrics.get("overall_hit_rate", 0)
            response_time = metrics.get("avg_redis_response_ms", 0)
            ops_per_second = metrics.get("operations_per_second", 0)

            if hit_rate < thresholds["min_hit_rate"]:
                issues.append(
                    f"Hit rate {hit_rate:.1%} below threshold {thresholds['min_hit_rate']:.1%}"
                )

            if response_time > thresholds["max_response_time_ms"]:
                issues.append(
                    f"Response time {response_time:.1f}ms above threshold {thresholds['max_response_time_ms']}ms"
                )

            if ops_per_second < thresholds["min_operations_per_second"]:
                issues.append(
                    f"Operations per second {ops_per_second:.1f} below threshold {thresholds['min_operations_per_second']}"
                )

            status = "healthy" if not issues else "degraded"

            return HealthCheckResult(
                name="performance_thresholds",
                status=status,
                response_time_ms=(time.time() - start_time) * 1000,
                details={
                    "hit_rate": hit_rate,
                    "response_time_ms": response_time,
                    "operations_per_second": ops_per_second,
                    "thresholds": thresholds,
                    "issues": issues,
                },
                timestamp=datetime.now(UTC),
            )

        except Exception as e:
            return HealthCheckResult(
                name="performance_thresholds",
                status="unhealthy",
                response_time_ms=(time.time() - start_time) * 1000,
                details={"error": str(e)},
                timestamp=datetime.now(UTC),
            )

    async def comprehensive_health_check(self) -> dict[str, Any]:
        """Perform comprehensive health check."""
        checks = [
            self.check_redis_connectivity(),
            self.check_cache_operations(),
            self.check_performance_thresholds(),
        ]

        results = await asyncio.gather(*checks, return_exceptions=True)

        health_checks = {}
        overall_status = "healthy"

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                check_name = f"check_{i}"
                health_checks[check_name] = {
                    "status": "unhealthy",
                    "error": str(result),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                overall_status = "unhealthy"
            else:
                health_checks[result.name] = asdict(result)
                if result.status == "unhealthy":
                    overall_status = "unhealthy"
                elif result.status == "degraded" and overall_status == "healthy":
                    overall_status = "degraded"

        return {
            "overall_status": overall_status,
            "timestamp": datetime.now(UTC).isoformat(),
            "checks": health_checks,
        }


class StructuredLogger:
    """Structured logging for production monitoring."""

    def __init__(self, cache: DistributedMultiTierCache):
        self.cache = cache
        self.logger = logging.getLogger("openchronicle.cache.structured")

        # Setup structured logging format
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Create file handler for cache events
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        file_handler = logging.FileHandler(log_dir / "cache_events.jsonl")
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        self.logger.setLevel(logging.INFO)

    def log_cache_event(self, event_type: str, details: dict[str, Any]):
        """Log structured cache event."""
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": event_type,
            "details": details,
            "source": "openchronicle_cache",
        }

        self.logger.info(json.dumps(event))

    def log_performance_metrics(self, metrics: dict[str, Any]):
        """Log performance metrics as structured event."""
        self.log_cache_event(
            "performance_metrics",
            {
                "hit_rate": metrics.get("overall_hit_rate", 0),
                "response_time_ms": metrics.get("avg_redis_response_ms", 0),
                "operations": metrics.get("total_operations", 0),
                "uptime_seconds": metrics.get("uptime_seconds", 0),
                "cluster_nodes": len(metrics.get("cluster_nodes", {})),
                "partitions": len(metrics.get("partitions", {})),
            },
        )

    def log_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        details: dict[str, Any] = None,
    ):
        """Log performance alert."""
        self.log_cache_event(
            "performance_alert",
            {
                "alert_type": alert_type,
                "severity": severity,
                "message": message,
                "details": details or {},
            },
        )

    def log_cache_warming(self, story_ids: list[str], results: dict[str, Any]):
        """Log cache warming operation."""
        self.log_cache_event(
            "cache_warming",
            {"story_count": len(story_ids), "story_ids": story_ids, "results": results},
        )


class ProductionMonitoring:
    """
    Production monitoring integration for distributed caching.

    Provides comprehensive monitoring capabilities for production deployment.
    """

    def __init__(
        self,
        cache: DistributedMultiTierCache,
        dashboard: CacheAnalyticsDashboard | None = None,
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

    async def start_production_monitoring(
        self, metrics_interval: int = 60, health_check_interval: int = 30
    ):
        """Start production monitoring with specified intervals."""
        if self._monitoring_active:
            return

        self._monitoring_active = True

        # Start metrics collection
        metrics_task = asyncio.create_task(
            self._metrics_monitoring_loop(metrics_interval)
        )
        self._monitoring_tasks.append(metrics_task)

        # Start health checks
        health_task = asyncio.create_task(
            self._health_monitoring_loop(health_check_interval)
        )
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
                self.logger.error(f"Metrics monitoring error: {e}")
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
                self.logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(interval)

    async def get_prometheus_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        return await self.prometheus_exporter.export_metrics()

    async def get_health_status(self) -> dict[str, Any]:
        """Get current health status."""
        return await self.health_checker.comprehensive_health_check()

    async def benchmark_production_performance(
        self, duration_seconds: int = 300
    ) -> dict[str, Any]:
        """Run production performance benchmark."""
        self.logger.info(
            f"Starting production benchmark for {duration_seconds} seconds"
        )

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

                # Set, get, delete cycle
                await self.cache.set(test_key, test_data, ttl=60)
                retrieved = await self.cache.get(test_key)
                await self.cache.delete(test_key)

                operations_completed += 3

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
            "error_rate": (
                errors / operations_completed if operations_completed > 0 else 0
            ),
            "initial_metrics": initial_metrics,
            "final_metrics": final_metrics,
            "performance_improvement": {
                "hit_rate_delta": final_metrics.get("overall_hit_rate", 0)
                - initial_metrics.get("overall_hit_rate", 0),
                "response_time_delta": final_metrics.get("avg_redis_response_ms", 0)
                - initial_metrics.get("avg_redis_response_ms", 0),
            },
        }

        self.structured_logger.log_cache_event(
            "production_benchmark", benchmark_results
        )
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
        logging.getLogger("openchronicle.cache").setLevel(
            getattr(logging, config["log_level"])
        )

        self.logger.info(f"Monitoring configured for {env} environment")

        return config


# Convenience function for production setup
async def setup_production_monitoring(
    cache: DistributedMultiTierCache,
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
