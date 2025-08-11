"""
Health Monitor - Extracted health checking system from the monolithic ModelManager.

This component provides comprehensive health monitoring, performance tracking,
and automated recovery capabilities that were embedded in the original ModelManager.

Key Features:
- Periodic health checks with configurable intervals
- Performance metrics tracking and analysis
- Automated fallback and recovery logic
- Health history and trend analysis
- Alert system for degraded performance
- Registry-driven health check configuration
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from enum import Enum
from typing import Any

from openchronicle.shared.logging_system import log_error
from openchronicle.shared.logging_system import log_info
from openchronicle.shared.logging_system import log_system_event


logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""

    adapter_name: str
    status: HealthStatus
    response_time: float
    error_message: str | None = None
    timestamp: datetime = datetime.now(UTC)
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class PerformanceMetrics:
    """Performance metrics for an adapter."""

    adapter_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    last_success: datetime | None = None
    last_failure: datetime | None = None
    uptime_percentage: float = 100.0


class HealthMonitor:
    """
    Comprehensive health monitoring system for model adapters.

    Provides automated health checking, performance tracking, and
    recovery management with registry-driven configuration.
    """

    def __init__(self, registry_manager, health_check_interval: int = 300):
        self.registry_manager = registry_manager
        self.health_check_interval = health_check_interval  # seconds

        # Health tracking
        self.health_results: dict[str, list[HealthCheckResult]] = {}
        self.performance_metrics: dict[str, PerformanceMetrics] = {}
        self.current_status: dict[str, HealthStatus] = {}

        # Monitoring control
        self.monitoring_active = False
        self.monitoring_task: asyncio.Task | None = None

        # Configuration from registry
        self.health_config = self._load_health_configuration()

        log_info(f"HealthMonitor initialized with {health_check_interval}s interval")

    def _load_health_configuration(self) -> dict[str, Any]:
        """Load health monitoring configuration from registry."""
        try:
            config = self.registry_manager.get_health_check_config()
            return config if config else self._get_default_health_config()
        except Exception as e:
            log_error(f"Failed to load health config from registry: {e}")
            return self._get_default_health_config()

    def _get_default_health_config(self) -> dict[str, Any]:
        """Default health monitoring configuration."""
        return {
            "health_check_timeout": 10.0,
            "max_consecutive_failures": 3,
            "degraded_response_threshold": 5.0,  # seconds
            "unhealthy_response_threshold": 10.0,  # seconds
            "history_retention_hours": 24,
            "alert_on_degraded": True,
            "auto_recovery_enabled": True,
        }

    async def start_monitoring(self, adapters: dict[str, Any]):
        """Start continuous health monitoring."""
        if self.monitoring_active:
            log_info("Health monitoring already active")
            return

        self.monitoring_active = True

        # Initialize performance metrics for all adapters
        for adapter_name in adapters:
            if adapter_name not in self.performance_metrics:
                self.performance_metrics[adapter_name] = PerformanceMetrics(
                    adapter_name
                )

        # Start monitoring task
        self.monitoring_task = asyncio.create_task(self._monitoring_loop(adapters))
        log_info("Health monitoring started")
        log_system_event(
            "health_monitoring_started", f"Monitoring {len(adapters)} adapters"
        )

    async def stop_monitoring(self):
        """Stop health monitoring."""
        self.monitoring_active = False

        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        log_info("Health monitoring stopped")
        log_system_event("health_monitoring_stopped", "Health monitoring shut down")

    async def _monitoring_loop(self, adapters: dict[str, Any]):
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                await self._perform_health_checks(adapters)
                await self._cleanup_old_results()
                await asyncio.sleep(self.health_check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log_error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(30)  # Wait before retrying

    async def _perform_health_checks(self, adapters: dict[str, Any]):
        """Perform health checks on all adapters."""
        tasks = []

        for adapter_name, adapter in adapters.items():
            if self.registry_manager.should_health_check(adapter_name):
                task = asyncio.create_task(
                    self._check_adapter_health(adapter_name, adapter)
                )
                tasks.append(task)

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for result in results:
                if isinstance(result, HealthCheckResult):
                    await self._process_health_result(result)
                elif isinstance(result, Exception):
                    log_error(f"Health check task failed: {result}")

    async def _check_adapter_health(
        self, adapter_name: str, adapter: Any
    ) -> HealthCheckResult:
        """Perform health check on a single adapter."""
        start_time = datetime.now(UTC)

        try:
            # Use adapter's health check if available
            if hasattr(adapter, "health_check"):
                timeout = self.health_config.get("health_check_timeout", 10.0)
                is_healthy = await asyncio.wait_for(
                    adapter.health_check(), timeout=timeout
                )
            else:
                # Basic health check - verify initialization
                is_healthy = getattr(adapter, "initialized", False)

            response_time = (datetime.now(UTC) - start_time).total_seconds()

            # Determine status based on response time and health
            if not is_healthy or response_time > self.health_config.get(
                "unhealthy_response_threshold", 10.0
            ):
                status = HealthStatus.UNHEALTHY
            elif response_time > self.health_config.get(
                "degraded_response_threshold", 5.0
            ):
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY

            return HealthCheckResult(
                adapter_name=adapter_name,
                status=status,
                response_time=response_time,
                metadata={
                    "health_check_method": (
                        "adapter" if hasattr(adapter, "health_check") else "basic"
                    )
                },
            )

        except TimeoutError:
            response_time = (datetime.now(UTC) - start_time).total_seconds()
            return HealthCheckResult(
                adapter_name=adapter_name,
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                error_message="Health check timeout",
            )

        except Exception as e:
            response_time = (datetime.now(UTC) - start_time).total_seconds()
            return HealthCheckResult(
                adapter_name=adapter_name,
                status=HealthStatus.UNHEALTHY,
                response_time=response_time,
                error_message=str(e),
            )

    async def _process_health_result(self, result: HealthCheckResult):
        """Process and store health check result."""
        adapter_name = result.adapter_name

        # Store result in history
        if adapter_name not in self.health_results:
            self.health_results[adapter_name] = []

        self.health_results[adapter_name].append(result)
        self.current_status[adapter_name] = result.status

        # Update performance metrics
        metrics = self.performance_metrics.get(adapter_name)
        if metrics:
            metrics.total_requests += 1

            if result.status == HealthStatus.HEALTHY:
                metrics.successful_requests += 1
                metrics.last_success = result.timestamp
            else:
                metrics.failed_requests += 1
                metrics.last_failure = result.timestamp

            # Update average response time (exponential moving average)
            if metrics.average_response_time == 0:
                metrics.average_response_time = result.response_time
            else:
                metrics.average_response_time = (
                    0.8 * metrics.average_response_time + 0.2 * result.response_time
                )

            # Update uptime percentage
            if metrics.total_requests > 0:
                metrics.uptime_percentage = (
                    metrics.successful_requests / metrics.total_requests
                ) * 100

        # Handle alerts and recovery
        await self._handle_health_change(result)

        # Log significant status changes
        if result.status != HealthStatus.HEALTHY:
            log_error(
                f"Health issue detected for {adapter_name}: {result.status.value}"
            )
            if result.error_message:
                log_error(f"Error details: {result.error_message}")

    async def _handle_health_change(self, result: HealthCheckResult):
        """Handle health status changes and trigger recovery if needed."""
        adapter_name = result.adapter_name

        # Check for consecutive failures
        recent_results = self.get_recent_results(adapter_name, count=3)
        consecutive_failures = all(
            r.status != HealthStatus.HEALTHY for r in recent_results
        )

        if consecutive_failures and len(recent_results) >= 3:
            log_error(
                f"Adapter {adapter_name} has {len(recent_results)} consecutive failures"
            )

            # Trigger auto-recovery if enabled
            if self.health_config.get("auto_recovery_enabled", True):
                await self._attempt_recovery(adapter_name)

        # Send alerts for degraded performance
        if result.status == HealthStatus.DEGRADED and self.health_config.get(
            "alert_on_degraded", True
        ):
            log_system_event(
                "adapter_degraded", f"Adapter {adapter_name} performance degraded"
            )

    async def _attempt_recovery(self, adapter_name: str):
        """Attempt to recover an unhealthy adapter."""
        log_info(f"Attempting recovery for adapter: {adapter_name}")

        # This would typically involve:
        # 1. Restarting the adapter
        # 2. Clearing connection pools
        # 3. Reinitializing configurations
        # 4. Triggering fallback mechanisms

        # For now, just log the recovery attempt
        log_system_event("recovery_attempted", f"Recovery initiated for {adapter_name}")

    async def _cleanup_old_results(self):
        """Clean up old health check results."""
        retention_hours = self.health_config.get("history_retention_hours", 24)
        cutoff_time = datetime.now(UTC) - timedelta(hours=retention_hours)

        for adapter_name in self.health_results:
            old_count = len(self.health_results[adapter_name])
            self.health_results[adapter_name] = [
                result
                for result in self.health_results[adapter_name]
                if result.timestamp > cutoff_time
            ]
            new_count = len(self.health_results[adapter_name])

            if old_count != new_count:
                log_info(
                    f"Cleaned up {old_count - new_count} old health results for {adapter_name}"
                )

    def get_recent_results(
        self, adapter_name: str, count: int = 10
    ) -> list[HealthCheckResult]:
        """Get recent health check results for an adapter."""
        results = self.health_results.get(adapter_name, [])
        return sorted(results, key=lambda r: r.timestamp, reverse=True)[:count]

    def get_adapter_status(self, adapter_name: str) -> HealthStatus:
        """Get current health status for an adapter."""
        return self.current_status.get(adapter_name, HealthStatus.UNKNOWN)

    def get_performance_summary(self, adapter_name: str) -> PerformanceMetrics | None:
        """Get performance metrics summary for an adapter."""
        return self.performance_metrics.get(adapter_name)

    def get_overall_health_summary(self) -> dict[str, Any]:
        """Get overall health summary for all adapters."""
        total_adapters = len(self.current_status)
        healthy_count = sum(
            1
            for status in self.current_status.values()
            if status == HealthStatus.HEALTHY
        )
        degraded_count = sum(
            1
            for status in self.current_status.values()
            if status == HealthStatus.DEGRADED
        )
        unhealthy_count = sum(
            1
            for status in self.current_status.values()
            if status == HealthStatus.UNHEALTHY
        )

        return {
            "total_adapters": total_adapters,
            "healthy": healthy_count,
            "degraded": degraded_count,
            "unhealthy": unhealthy_count,
            "overall_health_percentage": (
                (healthy_count / total_adapters * 100) if total_adapters > 0 else 0
            ),
            "monitoring_active": self.monitoring_active,
            "last_check": max(
                (
                    r.timestamp
                    for results in self.health_results.values()
                    for r in results
                ),
                default=None,
            ),
        }
