"""
Prometheus Metrics Exporter

Export cache metrics in Prometheus format for monitoring.
Extracted from production_monitoring.py for better modularity.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...cache_orchestrator import DistributedMultiTierCache


class PrometheusExporter:
    """Export cache metrics in Prometheus format."""

    def __init__(self, cache: "DistributedMultiTierCache"):
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
