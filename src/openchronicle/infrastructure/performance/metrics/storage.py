#!/usr/bin/env python3
"""
OpenChronicle Metrics Storage

Focused component for storing and retrieving performance metrics.
Handles persistence and efficient querying of metrics data.
"""

import json
import sqlite3
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any

from src.openchronicle.shared.logging_system import get_logger
from src.openchronicle.shared.logging_system import log_system_event

from ..interfaces.performance_interfaces import IMetricsStorage
from ..interfaces.performance_interfaces import MetricsQuery
from ..interfaces.performance_interfaces import PerformanceMetrics


class MetricsStorage(IMetricsStorage):
    """Stores and retrieves performance metrics with SQLite backend."""

    def __init__(self, storage_path: str = "storage/performance_metrics.db"):
        """Initialize the metrics storage."""
        self.logger = get_logger()
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection_pool = {}
        self._initialized = False

    async def initialize(self):
        """Initialize the storage backend."""
        if self._initialized:
            return

        try:
            await self._setup_database()
            self._initialized = True
            log_system_event(
                "metrics_storage",
                "Storage initialized",
                {"storage_path": str(self.storage_path)},
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize storage: {e}")
            raise

    async def store_metrics(self, metrics: PerformanceMetrics):
        """Store performance metrics."""
        if not self._initialized:
            await self.initialize()

        try:
            conn = await self._get_connection()
            cursor = conn.cursor()

            # Insert metrics data
            cursor.execute(
                """
                INSERT INTO performance_metrics (
                    operation_id, adapter_name, operation_type, start_time, end_time,
                    duration, cpu_usage_before, cpu_usage_after, memory_usage_before,
                    memory_usage_after, success, error_message, context_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    metrics.operation_id,
                    metrics.adapter_name,
                    metrics.operation_type,
                    metrics.start_time,
                    metrics.end_time,
                    metrics.duration,
                    metrics.cpu_usage_before,
                    metrics.cpu_usage_after,
                    metrics.memory_usage_before,
                    metrics.memory_usage_after,
                    metrics.success,
                    metrics.error_message,
                    json.dumps(metrics.context) if metrics.context else None,
                ),
            )

            conn.commit()

            log_system_event(
                "metrics_storage",
                "Metrics stored",
                {
                    "operation_id": metrics.operation_id,
                    "adapter_name": metrics.adapter_name,
                    "duration": metrics.duration,
                },
            )

        except Exception as e:
            self.logger.error(f"Failed to store metrics: {e}")
            raise

    async def retrieve_metrics(self, query: MetricsQuery) -> list[PerformanceMetrics]:
        """Retrieve metrics based on query parameters."""
        if not self._initialized:
            await self.initialize()

        try:
            conn = await self._get_connection()
            cursor = conn.cursor()

            # Build query
            sql_query = "SELECT * FROM performance_metrics WHERE 1=1"
            params: list[Any] = []

            if query.start_time:
                sql_query += " AND start_time >= ?"
                params.append(query.start_time.timestamp())

            if query.end_time:
                sql_query += " AND end_time <= ?"
                params.append(query.end_time.timestamp())

            if query.adapter_names:
                placeholders = ",".join("?" * len(query.adapter_names))
                sql_query += f" AND adapter_name IN ({placeholders})"
                params.extend(query.adapter_names)

            if query.operation_types:
                placeholders = ",".join("?" * len(query.operation_types))
                sql_query += f" AND operation_type IN ({placeholders})"
                params.extend(query.operation_types)

            if query.success_only is not None:
                sql_query += " AND success = ?"
                params.append(query.success_only)

            # Add ordering and limits
            sql_query += " ORDER BY start_time DESC"

            if query.limit:
                sql_query += " LIMIT ?"
                params.append(query.limit)

            cursor.execute(sql_query, params)
            rows = cursor.fetchall()

            # Convert rows to PerformanceMetrics objects
            metrics_list = []
            for row in rows:
                context = json.loads(row[12]) if row[12] else {}

                metrics = PerformanceMetrics(
                    operation_id=row[1],
                    adapter_name=row[2],
                    operation_type=row[3],
                    start_time=row[4],
                    end_time=row[5],
                    duration=row[6],
                    cpu_usage_before=row[7],
                    cpu_usage_after=row[8],
                    memory_usage_before=row[9],
                    memory_usage_after=row[10],
                    success=bool(row[11]),
                    error_message=row[13],
                    context=context,
                )
                metrics_list.append(metrics)

            log_system_event(
                "metrics_storage",
                "Metrics retrieved",
                {
                    "count": len(metrics_list),
                    "start_time": (
                        query.start_time.isoformat() if query.start_time else None
                    ),
                    "end_time": query.end_time.isoformat() if query.end_time else None,
                    "adapter_names": query.adapter_names,
                    "operation_types": query.operation_types,
                    "success_only": query.success_only,
                    "limit": query.limit,
                },
            )

            return metrics_list

        except Exception as e:
            self.logger.error(f"Failed to retrieve metrics: {e}")
            return []

    async def get_metrics_summary(
        self,
        time_period: tuple[datetime, datetime],
        adapter_filter: str | None = None,
    ) -> dict[str, Any]:
        """Get summary statistics for metrics in a time period."""
        if not self._initialized:
            await self.initialize()

        try:
            conn = await self._get_connection()
            cursor = conn.cursor()

            # Build base query
            base_query = """
                SELECT 
                    COUNT(*) as total_operations,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_operations,
                    AVG(duration) as avg_duration,
                    MIN(duration) as min_duration,
                    MAX(duration) as max_duration,
                    AVG(cpu_usage_after - cpu_usage_before) as avg_cpu_delta,
                    AVG(memory_usage_after - memory_usage_before) as avg_memory_delta
                FROM performance_metrics 
                WHERE start_time >= ? AND end_time <= ?
            """

            params: list[Any] = [time_period[0].timestamp(), time_period[1].timestamp()]

            if adapter_filter:
                base_query += " AND adapter_name = ?"
                params.append(adapter_filter)

            cursor.execute(base_query, params)
            row = cursor.fetchone()

            summary = {
                "total_operations": row[0] or 0,
                "successful_operations": row[1] or 0,
                "failed_operations": (row[0] or 0) - (row[1] or 0),
                "success_rate": (row[1] / row[0] * 100) if row[0] else 0.0,
                "avg_duration": row[2] or 0.0,
                "min_duration": row[3] or 0.0,
                "max_duration": row[4] or 0.0,
                "avg_cpu_delta": row[5] or 0.0,
                "avg_memory_delta": row[6] or 0.0,
                "time_period": {
                    "start": time_period[0].isoformat(),
                    "end": time_period[1].isoformat(),
                },
                "adapter_filter": adapter_filter,
            }

            # Get adapter breakdown
            adapter_query = """
                SELECT adapter_name, COUNT(*), AVG(duration)
                FROM performance_metrics 
                WHERE start_time >= ? AND end_time <= ?
            """
            adapter_params: list[Any] = [
                time_period[0].timestamp(),
                time_period[1].timestamp(),
            ]

            if adapter_filter:
                adapter_query += " AND adapter_name = ?"
                adapter_params.append(adapter_filter)

            adapter_query += " GROUP BY adapter_name"

            cursor.execute(adapter_query, adapter_params)
            adapter_rows = cursor.fetchall()

            summary["adapter_breakdown"] = [
                {
                    "adapter_name": row[0],
                    "operation_count": row[1],
                    "avg_duration": row[2],
                }
                for row in adapter_rows
            ]

            return summary

        except Exception as e:
            self.logger.error(f"Failed to get metrics summary: {e}")
            return {
                "total_operations": 0,
                "successful_operations": 0,
                "failed_operations": 0,
                "success_rate": 0.0,
                "avg_duration": 0.0,
                "min_duration": 0.0,
                "max_duration": 0.0,
                "avg_cpu_delta": 0.0,
                "avg_memory_delta": 0.0,
                "adapter_breakdown": [],
            }

    async def cleanup_old_metrics(self, retention_days: int = 30) -> int:
        """Clean up old metrics beyond retention period."""
        if not self._initialized:
            await self.initialize()

        try:
            cutoff_time = datetime.now() - timedelta(days=retention_days)

            conn = await self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM performance_metrics WHERE start_time < ?",
                (cutoff_time.timestamp(),),
            )

            deleted_count = cursor.rowcount
            conn.commit()

            log_system_event(
                "metrics_storage",
                "Old metrics cleaned up",
                {
                    "deleted_count": deleted_count,
                    "retention_days": retention_days,
                    "cutoff_time": cutoff_time.isoformat(),
                },
            )

            return deleted_count

        except Exception as e:
            self.logger.error(f"Failed to cleanup old metrics: {e}")
            return 0

    async def get_storage_stats(self) -> dict[str, Any]:
        """Get storage statistics and health information."""
        if not self._initialized:
            await self.initialize()

        try:
            conn = await self._get_connection()
            cursor = conn.cursor()

            # Get row count
            cursor.execute("SELECT COUNT(*) FROM performance_metrics")
            total_records = cursor.fetchone()[0]

            # Get date range
            cursor.execute(
                """
                SELECT MIN(start_time), MAX(start_time) 
                FROM performance_metrics
            """
            )
            date_range = cursor.fetchone()

            # Get file size
            file_size_mb = self.storage_path.stat().st_size / (1024 * 1024)

            stats = {
                "total_records": total_records,
                "file_size_mb": round(file_size_mb, 2),
                "storage_path": str(self.storage_path),
                "date_range": {
                    "earliest": (
                        datetime.fromtimestamp(date_range[0]).isoformat()
                        if date_range[0]
                        else None
                    ),
                    "latest": (
                        datetime.fromtimestamp(date_range[1]).isoformat()
                        if date_range[1]
                        else None
                    ),
                },
                "initialized": self._initialized,
            }

            return stats

        except Exception as e:
            self.logger.error(f"Failed to get storage stats: {e}")
            return {
                "total_records": 0,
                "file_size_mb": 0.0,
                "storage_path": str(self.storage_path),
                "date_range": {"earliest": None, "latest": None},
                "initialized": self._initialized,
            }

    async def _setup_database(self):
        """Set up the SQLite database schema."""
        conn = await self._get_connection()
        cursor = conn.cursor()

        # Create metrics table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_id TEXT NOT NULL,
                adapter_name TEXT NOT NULL,
                operation_type TEXT NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                duration REAL NOT NULL,
                cpu_usage_before REAL,
                cpu_usage_after REAL,
                memory_usage_before REAL,
                memory_usage_after REAL,
                success BOOLEAN NOT NULL,
                error_message TEXT,
                context_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Create indexes for efficient querying
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_adapter_name 
            ON performance_metrics(adapter_name)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_start_time 
            ON performance_metrics(start_time)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_operation_type 
            ON performance_metrics(operation_type)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_success 
            ON performance_metrics(success)
        """
        )

        conn.commit()

    async def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection (thread-safe)."""
        # In a real implementation, you might use a connection pool
        # For now, create a new connection each time
        conn = sqlite3.connect(self.storage_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn
