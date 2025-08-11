#!/usr/bin/env python3
"""
OpenChronicle Bottleneck Analyzer

Focused component for identifying and analyzing performance bottlenecks.
Analyzes metrics data to detect slow operations and resource constraints.
"""

import statistics
from collections import Counter
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from typing import Any

from src.openchronicle.shared.logging_system import get_logger
from src.openchronicle.shared.logging_system import log_system_event

from ..interfaces.performance_interfaces import BottleneckReport
from ..interfaces.performance_interfaces import IBottleneckAnalyzer
from ..interfaces.performance_interfaces import PerformanceMetrics


@dataclass
class BottleneckPattern:
    """Represents a detected bottleneck pattern."""

    pattern_type: str  # 'duration', 'cpu', 'memory', 'error_rate'
    severity: str  # 'low', 'medium', 'high', 'critical'
    affected_adapters: list[str]
    affected_operations: list[str]
    frequency: int
    avg_impact: float
    description: str
    recommendations: list[str]


class BottleneckAnalyzer(IBottleneckAnalyzer):
    """Analyzes performance metrics to identify bottlenecks and performance issues."""

    def __init__(self):
        """Initialize the bottleneck analyzer."""
        self.logger = get_logger()
        self._severity_thresholds = {
            "duration": {"high": 10.0, "critical": 30.0},  # seconds
            "cpu_delta": {"high": 50.0, "critical": 80.0},  # percentage points
            "memory_delta": {"high": 500.0, "critical": 1000.0},  # MB
            "error_rate": {"high": 0.1, "critical": 0.25},  # 10% and 25%
        }

    async def analyze_bottlenecks(
        self,
        metrics: list[PerformanceMetrics],
        time_window: timedelta = timedelta(hours=1),
    ) -> BottleneckReport:
        """Analyze metrics to identify bottlenecks."""
        try:
            if not metrics:
                return self._create_empty_report()

            # Group metrics by adapter and operation type
            adapter_metrics = self._group_by_adapter(metrics)
            operation_metrics = self._group_by_operation(metrics)

            # Detect different types of bottlenecks
            duration_bottlenecks = await self._analyze_duration_bottlenecks(
                adapter_metrics
            )
            resource_bottlenecks = await self._analyze_resource_bottlenecks(
                adapter_metrics
            )
            error_bottlenecks = await self._analyze_error_bottlenecks(adapter_metrics)
            frequency_bottlenecks = await self._analyze_frequency_bottlenecks(
                operation_metrics, time_window
            )

            # Combine all bottleneck patterns
            all_patterns = (
                duration_bottlenecks
                + resource_bottlenecks
                + error_bottlenecks
                + frequency_bottlenecks
            )

            # Calculate overall metrics
            total_operations = len(metrics)
            failed_operations = sum(1 for m in metrics if not m.success)
            avg_duration = (
                statistics.mean(m.duration for m in metrics) if metrics else 0.0
            )

            # Identify top bottleneck adapters
            adapter_impact_scores = self._calculate_adapter_impact_scores(
                adapter_metrics
            )
            top_bottleneck_adapters = sorted(
                adapter_impact_scores.items(), key=lambda x: x[1], reverse=True
            )[:5]

            report = BottleneckReport(
                analysis_time=datetime.now(),
                time_period=(
                    datetime.fromtimestamp(min(m.start_time for m in metrics)),
                    datetime.fromtimestamp(max(m.end_time for m in metrics)),
                ),
                total_operations=total_operations,
                failed_operations=failed_operations,
                avg_duration=avg_duration,
                bottleneck_patterns=all_patterns,
                top_bottleneck_adapters=[
                    adapter for adapter, _ in top_bottleneck_adapters
                ],
                recommendations=self._generate_recommendations(all_patterns),
            )

            log_system_event(
                "bottleneck_analyzer",
                "Analysis completed",
                {
                    "total_operations": total_operations,
                    "patterns_found": len(all_patterns),
                    "critical_patterns": len(
                        [p for p in all_patterns if p.severity == "critical"]
                    ),
                    "top_bottleneck": (
                        top_bottleneck_adapters[0][0]
                        if top_bottleneck_adapters
                        else None
                    ),
                },
            )

            return report

        except Exception as e:
            self.logger.error(f"Failed to analyze bottlenecks: {e}")
            return self._create_empty_report()

    async def identify_slow_operations(
        self, metrics: list[PerformanceMetrics], threshold_percentile: float = 95.0
    ) -> list[PerformanceMetrics]:
        """Identify operations that are significantly slower than average."""
        try:
            if not metrics:
                return []

            # Calculate duration threshold based on percentile
            durations = [m.duration for m in metrics]
            durations.sort()
            threshold_index = int((threshold_percentile / 100.0) * len(durations))
            threshold_duration = (
                durations[threshold_index]
                if threshold_index < len(durations)
                else durations[-1]
            )

            # Find operations above threshold
            slow_operations = [m for m in metrics if m.duration >= threshold_duration]

            log_system_event(
                "bottleneck_analyzer",
                "Slow operations identified",
                {
                    "total_operations": len(metrics),
                    "slow_operations": len(slow_operations),
                    "threshold_duration": threshold_duration,
                    "threshold_percentile": threshold_percentile,
                },
            )

            return slow_operations

        except Exception as e:
            self.logger.error(f"Failed to identify slow operations: {e}")
            return []

    async def analyze_resource_usage_patterns(
        self, metrics: list[PerformanceMetrics]
    ) -> dict[str, Any]:
        """Analyze resource usage patterns and trends."""
        try:
            if not metrics:
                return {}

            # Calculate resource deltas
            cpu_deltas = [m.cpu_usage_after - m.cpu_usage_before for m in metrics]
            memory_deltas = [
                m.memory_usage_after - m.memory_usage_before for m in metrics
            ]

            # Analyze patterns by adapter
            adapter_patterns = {}
            for adapter_name, adapter_metrics in self._group_by_adapter(
                metrics
            ).items():
                adapter_cpu_deltas = [
                    m.cpu_usage_after - m.cpu_usage_before for m in adapter_metrics
                ]
                adapter_memory_deltas = [
                    m.memory_usage_after - m.memory_usage_before
                    for m in adapter_metrics
                ]

                adapter_patterns[adapter_name] = {
                    "avg_cpu_delta": (
                        statistics.mean(adapter_cpu_deltas)
                        if adapter_cpu_deltas
                        else 0.0
                    ),
                    "max_cpu_delta": (
                        max(adapter_cpu_deltas) if adapter_cpu_deltas else 0.0
                    ),
                    "avg_memory_delta": (
                        statistics.mean(adapter_memory_deltas)
                        if adapter_memory_deltas
                        else 0.0
                    ),
                    "max_memory_delta": (
                        max(adapter_memory_deltas) if adapter_memory_deltas else 0.0
                    ),
                    "operation_count": len(adapter_metrics),
                }

            # Overall patterns
            patterns = {
                "overall": {
                    "avg_cpu_delta": statistics.mean(cpu_deltas) if cpu_deltas else 0.0,
                    "max_cpu_delta": max(cpu_deltas) if cpu_deltas else 0.0,
                    "avg_memory_delta": (
                        statistics.mean(memory_deltas) if memory_deltas else 0.0
                    ),
                    "max_memory_delta": max(memory_deltas) if memory_deltas else 0.0,
                    "total_operations": len(metrics),
                },
                "by_adapter": adapter_patterns,
                "resource_intensive_adapters": self._identify_resource_intensive_adapters(
                    adapter_patterns
                ),
            }

            return patterns

        except Exception as e:
            self.logger.error(f"Failed to analyze resource usage patterns: {e}")
            return {}

    def _group_by_adapter(
        self, metrics: list[PerformanceMetrics]
    ) -> dict[str, list[PerformanceMetrics]]:
        """Group metrics by adapter name."""
        grouped = defaultdict(list)
        for metric in metrics:
            grouped[metric.adapter_name].append(metric)
        return dict(grouped)

    def _group_by_operation(
        self, metrics: list[PerformanceMetrics]
    ) -> dict[str, list[PerformanceMetrics]]:
        """Group metrics by operation type."""
        grouped = defaultdict(list)
        for metric in metrics:
            grouped[metric.operation_type].append(metric)
        return dict(grouped)

    async def _analyze_duration_bottlenecks(
        self, adapter_metrics: dict[str, list[PerformanceMetrics]]
    ) -> list[BottleneckPattern]:
        """Analyze duration-based bottlenecks."""
        patterns = []

        for adapter_name, metrics in adapter_metrics.items():
            durations = [m.duration for m in metrics]
            avg_duration = statistics.mean(durations) if durations else 0.0

            if avg_duration > self._severity_thresholds["duration"]["critical"]:
                severity = "critical"
            elif avg_duration > self._severity_thresholds["duration"]["high"]:
                severity = "high"
            else:
                continue  # Not a bottleneck

            # Get operation types for this adapter
            operation_types = list(set(m.operation_type for m in metrics))

            pattern = BottleneckPattern(
                pattern_type="duration",
                severity=severity,
                affected_adapters=[adapter_name],
                affected_operations=operation_types,
                frequency=len(metrics),
                avg_impact=avg_duration,
                description=f"Adapter {adapter_name} has high average duration: {avg_duration:.2f}s",
                recommendations=[
                    f"Investigate {adapter_name} adapter performance",
                    "Consider caching or optimization for slow operations",
                    "Check network connectivity if remote adapter",
                ],
            )
            patterns.append(pattern)

        return patterns

    async def _analyze_resource_bottlenecks(
        self, adapter_metrics: dict[str, list[PerformanceMetrics]]
    ) -> list[BottleneckPattern]:
        """Analyze resource usage bottlenecks."""
        patterns = []

        for adapter_name, metrics in adapter_metrics.items():
            cpu_deltas = [m.cpu_usage_after - m.cpu_usage_before for m in metrics]
            memory_deltas = [
                m.memory_usage_after - m.memory_usage_before for m in metrics
            ]

            avg_cpu_delta = statistics.mean(cpu_deltas) if cpu_deltas else 0.0
            avg_memory_delta = statistics.mean(memory_deltas) if memory_deltas else 0.0

            # Check CPU bottleneck
            if avg_cpu_delta > self._severity_thresholds["cpu_delta"]["critical"]:
                pattern = BottleneckPattern(
                    pattern_type="cpu",
                    severity="critical",
                    affected_adapters=[adapter_name],
                    affected_operations=list(set(m.operation_type for m in metrics)),
                    frequency=len(metrics),
                    avg_impact=avg_cpu_delta,
                    description=f"Adapter {adapter_name} causes high CPU usage: {avg_cpu_delta:.1f}% delta",
                    recommendations=[
                        f"Optimize {adapter_name} adapter CPU usage",
                        "Consider reducing batch sizes or parallel operations",
                        "Monitor CPU-intensive operations",
                    ],
                )
                patterns.append(pattern)

            # Check memory bottleneck
            if avg_memory_delta > self._severity_thresholds["memory_delta"]["critical"]:
                pattern = BottleneckPattern(
                    pattern_type="memory",
                    severity="critical",
                    affected_adapters=[adapter_name],
                    affected_operations=list(set(m.operation_type for m in metrics)),
                    frequency=len(metrics),
                    avg_impact=avg_memory_delta,
                    description=f"Adapter {adapter_name} causes high memory usage: {avg_memory_delta:.1f}MB delta",
                    recommendations=[
                        f"Optimize {adapter_name} adapter memory usage",
                        "Implement proper resource cleanup",
                        "Consider memory-efficient data structures",
                    ],
                )
                patterns.append(pattern)

        return patterns

    async def _analyze_error_bottlenecks(
        self, adapter_metrics: dict[str, list[PerformanceMetrics]]
    ) -> list[BottleneckPattern]:
        """Analyze error rate bottlenecks."""
        patterns = []

        for adapter_name, metrics in adapter_metrics.items():
            if not metrics:
                continue

            failed_count = sum(1 for m in metrics if not m.success)
            error_rate = failed_count / len(metrics)

            if error_rate > self._severity_thresholds["error_rate"]["critical"]:
                severity = "critical"
            elif error_rate > self._severity_thresholds["error_rate"]["high"]:
                severity = "high"
            else:
                continue  # Not a bottleneck

            # Collect common error messages
            error_messages = [m.error_message for m in metrics if m.error_message]
            common_errors = Counter(error_messages).most_common(3)

            pattern = BottleneckPattern(
                pattern_type="error_rate",
                severity=severity,
                affected_adapters=[adapter_name],
                affected_operations=list(set(m.operation_type for m in metrics)),
                frequency=failed_count,
                avg_impact=error_rate,
                description=f"Adapter {adapter_name} has high error rate: {error_rate:.1%}",
                recommendations=[
                    f"Investigate {adapter_name} adapter errors",
                    "Check adapter configuration and connectivity",
                    "Review common error patterns",
                    f"Most common errors: {', '.join([err[0][:50] for err in common_errors if err[0]])}",
                ],
            )
            patterns.append(pattern)

        return patterns

    async def _analyze_frequency_bottlenecks(
        self,
        operation_metrics: dict[str, list[PerformanceMetrics]],
        time_window: timedelta,
    ) -> list[BottleneckPattern]:
        """Analyze operation frequency bottlenecks."""
        patterns = []

        # Calculate operations per hour for each operation type
        window_hours = time_window.total_seconds() / 3600

        for operation_type, metrics in operation_metrics.items():
            if not metrics:
                continue

            operations_per_hour = len(metrics) / window_hours
            avg_duration = statistics.mean(m.duration for m in metrics)

            # High frequency + high duration = bottleneck
            if (
                operations_per_hour > 100 and avg_duration > 2.0
            ):  # Configurable thresholds
                affected_adapters = list(set(m.adapter_name for m in metrics))

                pattern = BottleneckPattern(
                    pattern_type="frequency",
                    severity="medium",
                    affected_adapters=affected_adapters,
                    affected_operations=[operation_type],
                    frequency=len(metrics),
                    avg_impact=operations_per_hour * avg_duration,
                    description=f"Operation {operation_type} has high frequency and duration: {operations_per_hour:.1f}/hr, {avg_duration:.2f}s avg",
                    recommendations=[
                        f"Consider caching for {operation_type} operations",
                        "Implement rate limiting if appropriate",
                        "Optimize high-frequency operation paths",
                    ],
                )
                patterns.append(pattern)

        return patterns

    def _calculate_adapter_impact_scores(
        self, adapter_metrics: dict[str, list[PerformanceMetrics]]
    ) -> dict[str, float]:
        """Calculate impact scores for each adapter."""
        scores = {}

        for adapter_name, metrics in adapter_metrics.items():
            if not metrics:
                scores[adapter_name] = 0.0
                continue

            # Calculate various impact factors
            avg_duration = statistics.mean(m.duration for m in metrics)
            error_rate = sum(1 for m in metrics if not m.success) / len(metrics)
            operation_count = len(metrics)

            # Calculate resource impact
            cpu_deltas = [m.cpu_usage_after - m.cpu_usage_before for m in metrics]
            memory_deltas = [
                m.memory_usage_after - m.memory_usage_before for m in metrics
            ]
            avg_cpu_delta = statistics.mean(cpu_deltas) if cpu_deltas else 0.0
            avg_memory_delta = statistics.mean(memory_deltas) if memory_deltas else 0.0

            # Combined impact score (higher = more problematic)
            impact_score = (
                avg_duration * 10  # Duration weight
                + error_rate * 100  # Error rate weight
                + (avg_cpu_delta / 10)  # CPU impact weight
                + (avg_memory_delta / 100)  # Memory impact weight
                + (operation_count / 100)  # Frequency weight
            )

            scores[adapter_name] = impact_score

        return scores

    def _identify_resource_intensive_adapters(
        self, adapter_patterns: dict[str, dict[str, Any]]
    ) -> list[str]:
        """Identify adapters that are resource intensive."""
        intensive_adapters = []

        for adapter_name, patterns in adapter_patterns.items():
            if (
                patterns["avg_cpu_delta"] > 20.0  # 20% CPU delta
                or patterns["avg_memory_delta"] > 200.0
            ):  # 200MB memory delta
                intensive_adapters.append(adapter_name)

        return intensive_adapters

    def _generate_recommendations(self, patterns: list[BottleneckPattern]) -> list[str]:
        """Generate overall recommendations based on patterns."""
        recommendations = []

        # Critical patterns get priority
        critical_patterns = [p for p in patterns if p.severity == "critical"]
        if critical_patterns:
            recommendations.append(
                "🔴 Critical bottlenecks detected - immediate attention required"
            )
            for pattern in critical_patterns[:3]:  # Top 3 critical
                recommendations.extend(
                    pattern.recommendations[:2]
                )  # Top 2 recommendations per pattern

        # High patterns
        high_patterns = [p for p in patterns if p.severity == "high"]
        if high_patterns:
            recommendations.append("🟡 High-impact bottlenecks require optimization")

        # General recommendations
        if patterns:
            recommendations.extend(
                [
                    "Monitor adapter performance regularly",
                    "Consider implementing caching for slow operations",
                    "Review adapter configurations and network connectivity",
                ]
            )
        else:
            recommendations.append(
                "✅ No significant bottlenecks detected - system performing well"
            )

        return recommendations

    def _create_empty_report(self) -> BottleneckReport:
        """Create an empty bottleneck report."""
        return BottleneckReport(
            analysis_time=datetime.now(),
            time_period=(datetime.now(), datetime.now()),
            total_operations=0,
            failed_operations=0,
            avg_duration=0.0,
            bottleneck_patterns=[],
            top_bottleneck_adapters=[],
            recommendations=["No metrics available for analysis"],
        )
