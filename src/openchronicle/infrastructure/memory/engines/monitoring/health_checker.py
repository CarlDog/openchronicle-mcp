"""
Health Checker

Performs health checks for production monitoring.
Extracted from production_monitoring.py for better modularity.
"""

import asyncio
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, UTC
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ...cache_orchestrator import DistributedMultiTierCache


@dataclass
class HealthCheckResult:
    """Health check result for monitoring systems."""

    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    response_time_ms: float
    details: dict[str, Any]
    timestamp: datetime


class HealthChecker:
    """Performs health checks for production monitoring."""

    def __init__(self, cache: "DistributedMultiTierCache"):
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

            # Test delete operation - assuming cache has delete method
            # delete_success = await self.cache.delete(test_key)

            response_time_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                name="cache_operations",
                status="healthy",
                response_time_ms=response_time_ms,
                details={
                    "operations_tested": ["set", "get"],  # removed delete for now
                    "all_successful": True,
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
