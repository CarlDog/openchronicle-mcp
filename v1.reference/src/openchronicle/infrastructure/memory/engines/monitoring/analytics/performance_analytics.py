"""
Performance Analytics Dashboard - Week 17
Real-time monitoring and analytics for distributed caching

Provides comprehensive dashboard for monitoring:
- Cache performance across clusters
- Real-time metrics visualization
- Performance alerts and recommendations
- Cache optimization insights
"""

import asyncio
import json
import logging
from dataclasses import asdict
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

from ....cache_orchestrator import DistributedMultiTierCache


@dataclass
class AlertRule:
    """Performance alert rule configuration."""

    name: str
    metric_path: str  # e.g., "overall_hit_rate", "cluster_nodes.node_0.success_rate"
    threshold: float
    comparison: str  # "lt", "gt", "eq"
    severity: str  # "warning", "critical"
    enabled: bool = True


@dataclass
class PerformanceAlert:
    """Performance alert instance."""

    rule_name: str
    message: str
    severity: str
    timestamp: datetime
    metric_value: float
    threshold: float
    resolved: bool = False


class MetricsCollector:
    """Collects and aggregates cache metrics over time."""

    def __init__(self, max_history_hours: int = 24):
        self.max_history_hours = max_history_hours
        self.metrics_history: list[dict[str, Any]] = []
        self.logger = logging.getLogger("openchronicle.cache.collector")

    def add_metrics_snapshot(self, metrics: dict[str, Any]):
        """Add a metrics snapshot to history."""
        snapshot = {"timestamp": datetime.now(UTC).isoformat(), "metrics": metrics}

        self.metrics_history.append(snapshot)

        # Clean old history
        cutoff_time = datetime.now(UTC) - timedelta(hours=self.max_history_hours)
        self.metrics_history = [
            s
            for s in self.metrics_history
            if datetime.fromisoformat(s["timestamp"].replace("Z", "+00:00")) > cutoff_time
        ]

    def get_time_series(self, metric_path: str, hours: int = 1) -> list[tuple[datetime, float]]:
        """Get time series data for a specific metric."""
        cutoff_time = datetime.now(UTC) - timedelta(hours=hours)

        series = []
        for snapshot in self.metrics_history:
            timestamp = datetime.fromisoformat(snapshot["timestamp"].replace("Z", "+00:00"))
            if timestamp <= cutoff_time:
                continue

            # Navigate metric path (e.g., "cluster_nodes.node_0.success_rate")
            value = self._get_nested_value(snapshot["metrics"], metric_path)
            if value is not None:
                series.append((timestamp, float(value)))

        return sorted(series, key=lambda x: x[0])

    def _get_nested_value(self, data: dict[str, Any], path: str) -> float | None:
        """Get nested value from metrics using dot notation."""
        try:
            current = data
            for key in path.split("."):
                current = current[key]
            return float(current) if current is not None else None
        except (KeyError, TypeError, ValueError):
            return None

    def get_aggregated_metrics(self, hours: int = 1) -> dict[str, float]:
        """Get aggregated metrics over time period."""
        cutoff_time = datetime.now(UTC) - timedelta(hours=hours)

        relevant_snapshots = [
            s
            for s in self.metrics_history
            if datetime.fromisoformat(s["timestamp"].replace("Z", "+00:00")) > cutoff_time
        ]

        if not relevant_snapshots:
            return {}

        # Aggregate common metrics
        hit_rates = []
        response_times = []
        operations_counts = []

        for snapshot in relevant_snapshots:
            metrics = snapshot["metrics"]

            if "overall_hit_rate" in metrics:
                hit_rates.append(metrics["overall_hit_rate"])

            if "avg_redis_response_ms" in metrics:
                response_times.append(metrics["avg_redis_response_ms"])

            if "total_operations" in metrics:
                operations_counts.append(metrics["total_operations"])

        aggregated = {}

        if hit_rates:
            aggregated.update(
                {
                    "avg_hit_rate": sum(hit_rates) / len(hit_rates),
                    "min_hit_rate": min(hit_rates),
                    "max_hit_rate": max(hit_rates),
                }
            )

        if response_times:
            aggregated.update(
                {
                    "avg_response_time": sum(response_times) / len(response_times),
                    "min_response_time": min(response_times),
                    "max_response_time": max(response_times),
                }
            )

        if operations_counts:
            total_ops = sum(operations_counts)
            time_span = len(relevant_snapshots) * 60  # Assuming 1-minute intervals
            aggregated["avg_ops_per_minute"] = total_ops / (time_span / 60) if time_span > 0 else 0

        return aggregated


class AlertManager:
    """Manages performance alerts and notifications."""

    def __init__(self):
        self.alert_rules: list[AlertRule] = []
        self.active_alerts: list[PerformanceAlert] = []
        self.logger = logging.getLogger("openchronicle.cache.alerts")

        # Default alert rules
        self._setup_default_rules()

    def _setup_default_rules(self):
        """Setup default performance alert rules."""
        self.alert_rules = [
            AlertRule(
                name="Low Hit Rate",
                metric_path="overall_hit_rate",
                threshold=0.7,
                comparison="lt",
                severity="warning",
            ),
            AlertRule(
                name="Critical Hit Rate",
                metric_path="overall_hit_rate",
                threshold=0.5,
                comparison="lt",
                severity="critical",
            ),
            AlertRule(
                name="High Response Time",
                metric_path="avg_redis_response_ms",
                threshold=100.0,
                comparison="gt",
                severity="warning",
            ),
            AlertRule(
                name="Critical Response Time",
                metric_path="avg_redis_response_ms",
                threshold=500.0,
                comparison="gt",
                severity="critical",
            ),
            AlertRule(
                name="Node Failure",
                metric_path="cluster_nodes.*.success_rate",
                threshold=0.8,
                comparison="lt",
                severity="critical",
            ),
        ]

    def check_alerts(self, metrics: dict[str, Any]) -> list[PerformanceAlert]:
        """Check metrics against alert rules."""
        new_alerts = []

        for rule in self.alert_rules:
            if not rule.enabled:
                continue

            # Handle wildcard metric paths
            if "*" in rule.metric_path:
                alerts = self._check_wildcard_rule(rule, metrics)
                new_alerts.extend(alerts)
            else:
                alert = self._check_single_rule(rule, metrics)
                if alert:
                    new_alerts.append(alert)

        # Add to active alerts
        for alert in new_alerts:
            self.active_alerts.append(alert)
            self.logger.warning(f"Performance alert: {alert.message}")

        return new_alerts

    def _check_single_rule(self, rule: AlertRule, metrics: dict[str, Any]) -> PerformanceAlert | None:
        """Check a single alert rule."""
        value = self._get_metric_value(metrics, rule.metric_path)
        if value is None:
            return None

        triggered = False
        if (
            (rule.comparison == "lt" and value < rule.threshold)
            or (rule.comparison == "gt" and value > rule.threshold)
            or (rule.comparison == "eq" and abs(value - rule.threshold) < 0.001)
        ):
            triggered = True

        if triggered:
            return PerformanceAlert(
                rule_name=rule.name,
                message=f"{rule.name}: {rule.metric_path} = {value:.3f} (threshold: {rule.threshold})",
                severity=rule.severity,
                timestamp=datetime.now(UTC),
                metric_value=value,
                threshold=rule.threshold,
            )

        return None

    def _check_wildcard_rule(self, rule: AlertRule, metrics: dict[str, Any]) -> list[PerformanceAlert]:
        """Check rule with wildcard metric path."""
        alerts = []

        # Simple wildcard implementation for cluster_nodes.*
        if rule.metric_path.startswith("cluster_nodes.*."):
            suffix = rule.metric_path.split("cluster_nodes.*.")[-1]
            cluster_nodes = metrics.get("cluster_nodes", {})

            for node_id, node_metrics in cluster_nodes.items():
                value = node_metrics.get(suffix)
                if value is not None:
                    triggered = False
                    if (rule.comparison == "lt" and value < rule.threshold) or (
                        rule.comparison == "gt" and value > rule.threshold
                    ):
                        triggered = True

                    if triggered:
                        alert = PerformanceAlert(
                            rule_name=f"{rule.name} ({node_id})",
                            message=f"{rule.name} on {node_id}: {suffix} = {value:.3f} (threshold: {rule.threshold})",
                            severity=rule.severity,
                            timestamp=datetime.now(UTC),
                            metric_value=value,
                            threshold=rule.threshold,
                        )
                        alerts.append(alert)

        return alerts

    def _get_metric_value(self, metrics: dict[str, Any], path: str) -> float | None:
        """Get metric value using dot notation."""
        try:
            current = metrics
            for key in path.split("."):
                current = current[key]
            return float(current) if current is not None else None
        except (KeyError, TypeError, ValueError):
            return None

    def resolve_alert(self, alert_id: int):
        """Mark an alert as resolved."""
        if 0 <= alert_id < len(self.active_alerts):
            self.active_alerts[alert_id].resolved = True

    def get_active_alerts(self, severity: str | None = None) -> list[PerformanceAlert]:
        """Get active alerts, optionally filtered by severity."""
        alerts = [a for a in self.active_alerts if not a.resolved]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return sorted(alerts, key=lambda x: x.timestamp, reverse=True)

    def cleanup_old_alerts(self, hours: int = 24):
        """Remove old resolved alerts."""
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        self.active_alerts = [a for a in self.active_alerts if not a.resolved or a.timestamp > cutoff]


class PerformanceRecommendationEngine:
    """Generates performance recommendations based on metrics."""

    def __init__(self):
        self.logger = logging.getLogger("openchronicle.cache.recommendations")

    def analyze_performance(
        self, current_metrics: dict[str, Any], historical_data: MetricsCollector
    ) -> list[dict[str, str]]:
        """Analyze performance and generate recommendations."""
        recommendations = []

        # Analyze hit rate
        hit_rate = current_metrics.get("overall_hit_rate", 0)
        if hit_rate < 0.7:
            recommendations.append(
                {
                    "type": "hit_rate",
                    "severity": "warning" if hit_rate > 0.5 else "critical",
                    "title": "Low Cache Hit Rate",
                    "description": f"Hit rate is {hit_rate:.1%}, consider increasing cache TTL or warming strategies",
                    "action": "Increase character_ttl and memory_ttl in cache configuration",
                }
            )

        # Analyze response time
        response_time = current_metrics.get("avg_redis_response_ms", 0)
        if response_time > 50:
            recommendations.append(
                {
                    "type": "response_time",
                    "severity": "warning" if response_time < 200 else "critical",
                    "title": "High Redis Response Time",
                    "description": f"Average response time is {response_time:.1f}ms",
                    "action": "Consider adding more Redis nodes or checking network latency",
                }
            )

        # Analyze cluster balance
        cluster_nodes = current_metrics.get("cluster_nodes", {})
        if len(cluster_nodes) > 1:
            operations = [node.get("operations", 0) for node in cluster_nodes.values()]
            if operations and max(operations) > 2 * min(operations):
                recommendations.append(
                    {
                        "type": "cluster_balance",
                        "severity": "warning",
                        "title": "Unbalanced Cluster Load",
                        "description": "Some nodes are handling significantly more operations",
                        "action": "Review partitioning strategy or add cache warming",
                    }
                )

        # Analyze historical trends
        hit_rate_trend = historical_data.get_time_series("overall_hit_rate", hours=1)
        if len(hit_rate_trend) > 5:
            # Check if hit rate is declining
            recent_rates = [rate for _, rate in hit_rate_trend[-5:]]
            if all(recent_rates[i] > recent_rates[i + 1] for i in range(len(recent_rates) - 1)):
                recommendations.append(
                    {
                        "type": "trend",
                        "severity": "warning",
                        "title": "Declining Hit Rate Trend",
                        "description": "Cache hit rate has been consistently declining",
                        "action": "Investigate if cache invalidation is too aggressive or TTL too short",
                    }
                )

        return recommendations


class CacheAnalyticsDashboard:
    """
    Performance analytics dashboard for distributed caching.

    Provides real-time monitoring, alerting, and performance insights.
    """

    def __init__(self, cache: DistributedMultiTierCache):
        self.cache = cache
        self.metrics_collector = MetricsCollector()
        self.alert_manager = AlertManager()
        self.recommendation_engine = PerformanceRecommendationEngine()
        self.logger = logging.getLogger("openchronicle.cache.dashboard")

        # Dashboard state
        self._monitoring_active = False
        self._monitoring_task = None
        self._dashboard_data = {}

    async def start_monitoring(self, interval_seconds: int = 60):
        """Start continuous monitoring and data collection."""
        if self._monitoring_active:
            return

        self._monitoring_active = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop(interval_seconds))
        self.logger.info(f"Dashboard monitoring started (interval: {interval_seconds}s)")

    async def stop_monitoring(self):
        """Stop monitoring."""
        self._monitoring_active = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Dashboard monitoring stopped")

    async def _monitoring_loop(self, interval_seconds: int):
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                # Collect current metrics
                current_metrics = await self.cache.get_distributed_metrics()

                # Add to history
                self.metrics_collector.add_metrics_snapshot(current_metrics)

                # Check alerts
                new_alerts = self.alert_manager.check_alerts(current_metrics)

                # Generate recommendations
                recommendations = self.recommendation_engine.analyze_performance(
                    current_metrics, self.metrics_collector
                )

                # Update dashboard data
                self._dashboard_data = {
                    "current_metrics": current_metrics,
                    "active_alerts": self.alert_manager.get_active_alerts(),
                    "recommendations": recommendations,
                    "last_updated": datetime.now(UTC).isoformat(),
                }

                if new_alerts:
                    self.logger.warning(f"Generated {len(new_alerts)} new alerts")

                # Cleanup old data
                self.alert_manager.cleanup_old_alerts()

                await asyncio.sleep(interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception("Monitoring loop error")
                await asyncio.sleep(interval_seconds)

    def get_dashboard_data(self) -> dict[str, Any]:
        """Get current dashboard data."""
        return self._dashboard_data.copy()

    def get_time_series_data(self, metric: str, hours: int = 1) -> list[dict[str, Any]]:
        """Get time series data for charts."""
        series = self.metrics_collector.get_time_series(metric, hours)
        return [{"timestamp": ts.isoformat(), "value": value} for ts, value in series]

    def get_cluster_overview(self) -> dict[str, Any]:
        """Get cluster overview with health status."""
        current_metrics = self._dashboard_data.get("current_metrics", {})
        cluster_nodes = current_metrics.get("cluster_nodes", {})

        overview = {
            "total_nodes": len(cluster_nodes),
            "healthy_nodes": 0,
            "total_operations": 0,
            "avg_response_time": 0,
            "nodes": [],
        }

        response_times = []

        for node_id, node_metrics in cluster_nodes.items():
            success_rate = node_metrics.get("success_rate", 0)
            response_time = node_metrics.get("avg_response_ms", 0)
            operations = node_metrics.get("operations", 0)

            is_healthy = success_rate > 0.9 and response_time < 100
            if is_healthy:
                overview["healthy_nodes"] += 1

            overview["total_operations"] += operations
            response_times.append(response_time)

            overview["nodes"].append(
                {
                    "id": node_id,
                    "healthy": is_healthy,
                    "success_rate": success_rate,
                    "response_time": response_time,
                    "operations": operations,
                    "last_operation": node_metrics.get("last_operation"),
                }
            )

        if response_times:
            overview["avg_response_time"] = sum(response_times) / len(response_times)

        return overview

    def export_metrics(self, filepath: str, hours: int = 24):
        """Export metrics history to JSON file."""
        cutoff_time = datetime.now(UTC) - timedelta(hours=hours)

        export_data = {
            "export_timestamp": datetime.now(UTC).isoformat(),
            "time_range_hours": hours,
            "metrics_history": [
                s
                for s in self.metrics_collector.metrics_history
                if datetime.fromisoformat(s["timestamp"].replace("Z", "+00:00")) > cutoff_time
            ],
            "alerts": [asdict(alert) for alert in self.alert_manager.active_alerts],
            "aggregated_metrics": self.metrics_collector.get_aggregated_metrics(hours),
        }

        with open(filepath, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        self.logger.info(f"Metrics exported to {filepath}")

    async def generate_performance_report(self) -> dict[str, Any]:
        """Generate comprehensive performance report."""
        current_metrics = await self.cache.get_distributed_metrics()

        # Get aggregated data for different time periods
        hourly_metrics = self.metrics_collector.get_aggregated_metrics(1)
        daily_metrics = self.metrics_collector.get_aggregated_metrics(24)

        # Get recommendations
        recommendations = self.recommendation_engine.analyze_performance(current_metrics, self.metrics_collector)

        # Get cluster overview
        cluster_overview = self.get_cluster_overview()

        report = {
            "report_timestamp": datetime.now(UTC).isoformat(),
            "summary": {
                "overall_health": (
                    "healthy" if cluster_overview["healthy_nodes"] == cluster_overview["total_nodes"] else "degraded"
                ),
                "total_operations": current_metrics.get("total_operations", 0),
                "overall_hit_rate": current_metrics.get("overall_hit_rate", 0),
                "avg_response_time": current_metrics.get("avg_redis_response_ms", 0),
            },
            "current_metrics": current_metrics,
            "hourly_aggregates": hourly_metrics,
            "daily_aggregates": daily_metrics,
            "cluster_overview": cluster_overview,
            "active_alerts": [asdict(alert) for alert in self.alert_manager.get_active_alerts()],
            "recommendations": recommendations,
            "cache_warming": current_metrics.get("cache_warming", {}),
            "partitions": current_metrics.get("partitions", {}),
        }

        return report


# Convenience function for quick dashboard setup
async def create_cache_dashboard(cache: DistributedMultiTierCache, auto_start: bool = True) -> CacheAnalyticsDashboard:
    """Create and optionally start cache analytics dashboard."""
    dashboard = CacheAnalyticsDashboard(cache)

    if auto_start:
        await dashboard.start_monitoring()

    return dashboard
