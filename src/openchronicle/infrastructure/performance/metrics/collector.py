#!/usr/bin/env python3
"""
OpenChronicle Metrics Collector

Focused component for collecting performance metrics from operations.
Handles system resource monitoring and operation timing.
"""

import time
from datetime import datetime
from typing import Any

import psutil
from openchronicle.shared.logging_system import get_logger
from openchronicle.shared.logging_system import log_system_event

from openchronicle.domain.ports.performance_interface_port import IPerformanceInterfacePort
from ..interfaces.performance_interfaces import IMetricsCollector
from ..interfaces.performance_interfaces import PerformanceMetrics
from ..interfaces.performance_interfaces import OperationContext






class MetricsCollector(IMetricsCollector):
    """Collects performance metrics from operations and system resources."""

    def __init__(self):
        """Initialize the metrics collector."""
        self.logger = get_logger()
        self._active_operations: dict[str, dict[str, Any]] = {}
        self._collection_enabled = True

    async def start_operation_tracking(self, context: OperationContext) -> str:
        """Start tracking a new operation."""
        if not self._collection_enabled:
            return context.operation_id

        try:
            start_time = time.time()
            system_metrics = self.collect_system_metrics()

            operation_data = {
                "context": context,
                "start_time": start_time,
                "start_system_metrics": system_metrics,
                "created_at": datetime.now(),
            }

            self._active_operations[context.operation_id] = operation_data

            log_system_event(
                "metrics_collector",
                "Operation tracking started",
                {
                    "operation_id": context.operation_id,
                    "adapter_name": context.adapter_name,
                    "operation_type": context.operation_type,
                },
            )

            return context.operation_id

        except Exception as e:
            self.logger.error(f"Failed to start operation tracking: {e}")
            return context.operation_id

    async def finish_operation_tracking(
        self, operation_id: str, success: bool, error_message: str | None = None
    ) -> PerformanceMetrics:
        """Finish tracking an operation and return metrics."""
        if not self._collection_enabled or operation_id not in self._active_operations:
            # Return a basic metrics object if tracking wasn't started or is disabled
            return self._create_fallback_metrics(operation_id, success, error_message)

        try:
            operation_data = self._active_operations.pop(operation_id)
            end_time = time.time()
            end_system_metrics = self.collect_system_metrics()

            context = operation_data["context"]
            start_time = operation_data["start_time"]
            start_metrics = operation_data["start_system_metrics"]

            # Calculate duration
            duration = end_time - start_time

            # Create performance metrics
            metrics = PerformanceMetrics(
                operation_id=operation_id,
                adapter_name=context.adapter_name,
                operation_type=context.operation_type,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                cpu_usage_before=start_metrics.get("cpu_percent", 0.0),
                cpu_usage_after=end_system_metrics.get("cpu_percent", 0.0),
                memory_usage_before=start_metrics.get("memory_mb", 0.0),
                memory_usage_after=end_system_metrics.get("memory_mb", 0.0),
                success=success,
                error_message=error_message,
                context=context.metadata,
            )

            log_system_event(
                "metrics_collector",
                "Operation tracking completed",
                {
                    "operation_id": operation_id,
                    "duration": duration,
                    "success": success,
                    "cpu_delta": metrics.cpu_usage_after - metrics.cpu_usage_before,
                    "memory_delta": metrics.memory_usage_after
                    - metrics.memory_usage_before,
                },
            )

            return metrics

        except Exception as e:
            self.logger.error(
                f"Failed to finish operation tracking for {operation_id}: {e}"
            )
            return self._create_fallback_metrics(operation_id, success, error_message)

    def collect_system_metrics(self) -> dict[str, float]:
        """Collect current system resource metrics."""
        try:
            # Get CPU usage (average over short interval)
            cpu_percent = psutil.cpu_percent(interval=0.1)

            # Get memory information
            memory = psutil.virtual_memory()
            memory_mb = memory.used / (1024 * 1024)  # Convert to MB
            memory_percent = memory.percent

            # Get disk I/O if available
            disk_io = psutil.disk_io_counters()
            disk_read_mb = disk_io.read_bytes / (1024 * 1024) if disk_io else 0.0
            disk_write_mb = disk_io.write_bytes / (1024 * 1024) if disk_io else 0.0

            # Get network I/O if available
            net_io = psutil.net_io_counters()
            net_sent_mb = net_io.bytes_sent / (1024 * 1024) if net_io else 0.0
            net_recv_mb = net_io.bytes_recv / (1024 * 1024) if net_io else 0.0

            return {
                "cpu_percent": cpu_percent,
                "memory_mb": memory_mb,
                "memory_percent": memory_percent,
                "disk_read_mb": disk_read_mb,
                "disk_write_mb": disk_write_mb,
                "network_sent_mb": net_sent_mb,
                "network_recv_mb": net_recv_mb,
                "timestamp": time.time(),
            }

        except Exception as e:
            self.logger.error(f"Failed to collect system metrics: {e}")
            return {
                "cpu_percent": 0.0,
                "memory_mb": 0.0,
                "memory_percent": 0.0,
                "disk_read_mb": 0.0,
                "disk_write_mb": 0.0,
                "network_sent_mb": 0.0,
                "network_recv_mb": 0.0,
                "timestamp": time.time(),
            }

    async def get_metrics_history(
        self,
        time_period: tuple[datetime, datetime],
        adapter_filter: str | None = None,
    ) -> list[PerformanceMetrics]:
        """Retrieve historical metrics for analysis."""
        # This method would typically interface with storage
        # For now, return empty list as this collector focuses on real-time collection
        self.logger.info(f"Historical metrics requested for period {time_period}")
        return []

    def enable_collection(self):
        """Enable metrics collection."""
        self._collection_enabled = True
        log_system_event("metrics_collector", "Collection enabled", {})

    def disable_collection(self):
        """Disable metrics collection."""
        self._collection_enabled = False
        log_system_event("metrics_collector", "Collection disabled", {})

    def get_active_operations_count(self) -> int:
        """Get the number of currently active operations."""
        return len(self._active_operations)

    def get_collection_status(self) -> dict[str, Any]:
        """Get current collection status and statistics."""
        return {
            "collection_enabled": self._collection_enabled,
            "active_operations": len(self._active_operations),
            "active_operation_ids": list(self._active_operations.keys()),
            "system_metrics": self.collect_system_metrics(),
        }

    def _create_fallback_metrics(
        self, operation_id: str, success: bool, error_message: str | None
    ) -> PerformanceMetrics:
        """Create fallback metrics when tracking fails or is disabled."""
        current_time = time.time()
        system_metrics = self.collect_system_metrics()

        return PerformanceMetrics(
            operation_id=operation_id,
            adapter_name="unknown",
            operation_type="unknown",
            start_time=current_time,
            end_time=current_time,
            duration=0.0,
            cpu_usage_before=system_metrics.get("cpu_percent", 0.0),
            cpu_usage_after=system_metrics.get("cpu_percent", 0.0),
            memory_usage_before=system_metrics.get("memory_mb", 0.0),
            memory_usage_after=system_metrics.get("memory_mb", 0.0),
            success=success,
            error_message=error_message,
            context={"fallback": True},
        )

    async def cleanup_stale_operations(self, max_age_hours: int = 24):
        """Clean up operations that have been running too long (likely orphaned)."""
        current_time = datetime.now()
        stale_operations = []

        for op_id, op_data in list(self._active_operations.items()):
            created_at = op_data.get("created_at", current_time)
            age_hours = (current_time - created_at).total_seconds() / 3600

            if age_hours > max_age_hours:
                stale_operations.append(op_id)
                del self._active_operations[op_id]

        if stale_operations:
            log_system_event(
                "metrics_collector",
                "Cleaned up stale operations",
                {"count": len(stale_operations), "operation_ids": stale_operations},
            )

        return len(stale_operations)
