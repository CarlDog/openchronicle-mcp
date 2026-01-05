"""
Distributed Cache Metrics

Enhanced metrics collection for distributed caching operations.
Extracted from distributed_cache.py for better modularity.
"""

from datetime import UTC
from datetime import datetime
from typing import Any

from .redis_cache import CacheMetrics


class DistributedCacheMetrics(CacheMetrics):
    """Enhanced metrics for distributed caching."""

    def __init__(self):
        super().__init__()
        self.cluster_metrics = {}
        self.partition_metrics = {}
        self.warming_metrics = {
            "operations": 0,
            "success_rate": 0.0,
            "avg_time_ms": 0.0,
        }

    def record_cluster_operation(self, node_id: str, operation: str, success: bool, response_time: float):
        """Record cluster-specific operation."""
        if node_id not in self.cluster_metrics:
            self.cluster_metrics[node_id] = {
                "operations": 0,
                "successes": 0,
                "failures": 0,
                "response_times": [],
                "last_operation": None,
            }

        metrics = self.cluster_metrics[node_id]
        metrics["operations"] += 1
        metrics["last_operation"] = datetime.now(UTC).isoformat()

        if success:
            metrics["successes"] += 1
        else:
            metrics["failures"] += 1

        metrics["response_times"].append(response_time)
        # Keep only last 100 measurements per node
        if len(metrics["response_times"]) > 100:
            metrics["response_times"] = metrics["response_times"][-100:]

    def record_partition_operation(self, partition_id: str, operation: str, key_hash: str):
        """Record partition-specific operation."""
        if partition_id not in self.partition_metrics:
            self.partition_metrics[partition_id] = {
                "operations": 0,
                "unique_keys": set(),
                "last_access": None,
            }

        metrics = self.partition_metrics[partition_id]
        metrics["operations"] += 1
        metrics["unique_keys"].add(key_hash)
        metrics["last_access"] = datetime.now(UTC).isoformat()

        # Limit set size to prevent memory issues
        if len(metrics["unique_keys"]) > 10000:
            # Keep random subset
            unique_list = list(metrics["unique_keys"])
            metrics["unique_keys"] = set(unique_list[-5000:])

    def get_distributed_summary(self) -> dict[str, Any]:
        """Get comprehensive distributed cache metrics."""
        base_summary = self.get_summary()

        # Cluster metrics summary
        cluster_summary = {}
        for node_id, metrics in self.cluster_metrics.items():
            total_ops = metrics["operations"]
            success_rate = metrics["successes"] / total_ops if total_ops > 0 else 0
            avg_response = (
                sum(metrics["response_times"]) / len(metrics["response_times"]) if metrics["response_times"] else 0
            )

            cluster_summary[node_id] = {
                "operations": total_ops,
                "success_rate": success_rate,
                "avg_response_ms": avg_response * 1000,
                "last_operation": metrics["last_operation"],
            }

        # Partition metrics summary
        partition_summary = {}
        for partition_id, metrics in self.partition_metrics.items():
            partition_summary[partition_id] = {
                "operations": metrics["operations"],
                "unique_keys": len(metrics["unique_keys"]),
                "last_access": metrics["last_access"],
            }

        return {
            **base_summary,
            "cluster_nodes": cluster_summary,
            "partitions": partition_summary,
            "cache_warming": self.warming_metrics,
        }
