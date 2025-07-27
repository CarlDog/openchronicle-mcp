"""
Performance Diagnostic and Optimization System

This module provides comprehensive performance monitoring, bottleneck detection,
and optimization recommendations for the OpenChronicle AI narrative engine.

Features:
- Real-time performance monitoring for all model interactions
- Bottleneck detection in request pipelines
- Model speed benchmarking and ranking system
- Latency analysis (network, processing, memory access)
- Automatic performance ratings in model registry
- User-friendly diagnostic reports with improvement suggestions
- Optimal routing recommendations based on actual performance data

Author: OpenChronicle Development Team
Date: July 24, 2025
"""

import asyncio
import time
import psutil
import json
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import threading
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from utilities.logging_system import log_system_event


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics for a single operation."""
    operation_id: str
    adapter_name: str
    operation_type: str  # "initialize", "generate", "analyze", etc.
    start_time: float
    end_time: float
    duration: float
    cpu_usage_before: float
    cpu_usage_after: float
    memory_usage_before: float  # MB
    memory_usage_after: float  # MB
    success: bool
    error_message: Optional[str] = None
    
    # Operation-specific metrics
    tokens_processed: Optional[int] = None
    tokens_per_second: Optional[float] = None
    response_size_bytes: Optional[int] = None
    network_latency: Optional[float] = None
    processing_time: Optional[float] = None
    queue_time: Optional[float] = None
    
    # Quality metrics
    quality_score: Optional[float] = None
    user_satisfaction: Optional[float] = None
    
    @property
    def efficiency_score(self) -> float:
        """Calculate overall efficiency score (0.0 to 1.0)."""
        if not self.success:
            return 0.0
            
        # Base score from speed (inverse of duration, normalized)
        speed_score = max(0.0, 1.0 - min(self.duration / 30.0, 1.0))  # 30s = 0 score
        
        # Memory efficiency (lower usage = better)
        memory_delta = self.memory_usage_after - self.memory_usage_before
        memory_score = max(0.0, 1.0 - min(memory_delta / 1000.0, 1.0))  # 1GB = 0 score
        
        # CPU efficiency
        cpu_delta = self.cpu_usage_after - self.cpu_usage_before
        cpu_score = max(0.0, 1.0 - min(cpu_delta / 50.0, 1.0))  # 50% = 0 score
        
        # Tokens per second (if available)
        tokens_score = 1.0
        if self.tokens_per_second:
            tokens_score = min(self.tokens_per_second / 100.0, 1.0)  # 100 TPS = 1.0 score
        
        # Weighted combination
        return (speed_score * 0.4 + memory_score * 0.25 + cpu_score * 0.25 + tokens_score * 0.1)


@dataclass
class BottleneckAnalysis:
    """Analysis of performance bottlenecks."""
    bottleneck_type: str  # "network", "cpu", "memory", "model", "queue"
    severity: str  # "low", "medium", "high", "critical"
    impact_score: float  # 0.0 to 1.0
    description: str
    recommendation: str
    affected_operations: List[str]
    evidence: Dict[str, Any]


@dataclass
class PerformanceReport:
    """Comprehensive performance analysis report."""
    report_id: str
    generation_time: datetime
    time_period: str
    total_operations: int
    successful_operations: int
    failed_operations: int
    
    # Performance statistics
    avg_duration: float
    median_duration: float
    p95_duration: float
    avg_efficiency_score: float
    
    # Resource usage
    avg_cpu_usage: float
    peak_cpu_usage: float
    avg_memory_usage: float
    peak_memory_usage: float
    
    # Model rankings
    model_rankings: Dict[str, float]  # adapter_name -> efficiency_score
    fastest_models: List[Tuple[str, float]]
    most_efficient_models: List[Tuple[str, float]]
    most_reliable_models: List[Tuple[str, float]]
    
    # Bottlenecks and recommendations
    bottlenecks: List[BottleneckAnalysis]
    optimization_recommendations: List[str]
    
    # Trends
    performance_trend: str  # "improving", "stable", "degrading"
    trend_confidence: float  # 0.0 to 1.0


class PerformanceMonitor:
    """
    Comprehensive performance monitoring and diagnostic system.
    
    Tracks all model operations, analyzes performance patterns,
    and provides optimization recommendations.
    """
    
    def __init__(self, storage_path: str = "storage/data/performance"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # In-memory storage for recent metrics (last 1000 operations)
        self.recent_metrics: deque = deque(maxlen=1000)
        self.operation_counter = 0
        self._lock = threading.Lock()
        
        # Performance tracking by adapter
        self.adapter_metrics: Dict[str, List[PerformanceMetrics]] = defaultdict(list)
        self.adapter_statistics: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # Active operation tracking
        self.active_operations: Dict[str, Dict[str, Any]] = {}
        
        # Background monitoring
        self.monitoring_active = False
        self.monitor_thread = None
        
        # Configuration
        self.max_stored_metrics = 10000
        self.metrics_retention_days = 30
        self.auto_cleanup_enabled = True
        
        log_system_event("performance_monitor_init", "Performance monitoring system initialized")
    
    def start_monitoring(self):
        """Start background performance monitoring."""
        if self.monitoring_active:
            return
            
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._background_monitor, daemon=True)
        self.monitor_thread.start()
        
        log_system_event("performance_monitor_start", "Background performance monitoring started")
    
    def stop_monitoring(self):
        """Stop background performance monitoring."""
        if not self.monitoring_active:
            return
            
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        
        log_system_event("performance_monitor_stop", "Background performance monitoring stopped")
    
    def _background_monitor(self):
        """Background thread for continuous system monitoring."""
        while self.monitoring_active:
            try:
                # System resource monitoring
                cpu_percent = psutil.cpu_percent(interval=1.0)
                memory_info = psutil.virtual_memory()
                
                # Check for resource stress
                if cpu_percent > 80:
                    log_system_event("performance_alert", f"High CPU usage detected: {cpu_percent}%")
                
                if memory_info.percent > 85:
                    log_system_event("performance_alert", f"High memory usage detected: {memory_info.percent}%")
                
                # Cleanup old metrics if enabled
                if self.auto_cleanup_enabled:
                    self._cleanup_old_metrics()
                
                time.sleep(10)  # Monitor every 10 seconds
                
            except Exception as e:
                log_system_event("performance_monitor_error", f"Background monitoring error: {str(e)}")
                time.sleep(30)  # Wait longer on error
    
    @asynccontextmanager
    async def track_operation(self, adapter_name: str, operation_type: str, **kwargs):
        """
        Context manager for tracking operation performance.
        
        Usage:
            async with monitor.track_operation("gpt4", "generate") as tracker:
                result = await some_operation()
                tracker.set_tokens_processed(len(result))
        """
        operation_id = f"{adapter_name}_{operation_type}_{int(time.time() * 1000)}"
        
        # Start tracking
        start_metrics = self._capture_system_state()
        start_time = time.time()
        
        tracker = OperationTracker(operation_id)
        
        try:
            with self._lock:
                self.active_operations[operation_id] = {
                    "adapter_name": adapter_name,
                    "operation_type": operation_type,
                    "start_time": start_time,
                    "start_metrics": start_metrics,
                    **kwargs
                }
            
            yield tracker
            
            # Operation completed successfully
            end_time = time.time()
            end_metrics = self._capture_system_state()
            
            metrics = PerformanceMetrics(
                operation_id=operation_id,
                adapter_name=adapter_name,
                operation_type=operation_type,
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time,
                cpu_usage_before=start_metrics["cpu_percent"],
                cpu_usage_after=end_metrics["cpu_percent"],
                memory_usage_before=start_metrics["memory_mb"],
                memory_usage_after=end_metrics["memory_mb"],
                success=True,
                tokens_processed=tracker.tokens_processed,
                tokens_per_second=tracker.calculate_tokens_per_second(end_time - start_time),
                response_size_bytes=tracker.response_size_bytes,
                network_latency=tracker.network_latency,
                processing_time=tracker.processing_time,
                queue_time=tracker.queue_time,
                quality_score=tracker.quality_score
            )
            
            self._record_metrics(metrics)
            
        except Exception as e:
            # Operation failed
            end_time = time.time()
            end_metrics = self._capture_system_state()
            
            metrics = PerformanceMetrics(
                operation_id=operation_id,
                adapter_name=adapter_name,
                operation_type=operation_type,
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time,
                cpu_usage_before=start_metrics["cpu_percent"],
                cpu_usage_after=end_metrics["cpu_percent"],
                memory_usage_before=start_metrics["memory_mb"],
                memory_usage_after=end_metrics["memory_mb"],
                success=False,
                error_message=str(e)
            )
            
            self._record_metrics(metrics)
            raise
            
        finally:
            with self._lock:
                self.active_operations.pop(operation_id, None)
    
    def _capture_system_state(self) -> Dict[str, Any]:
        """Capture current system resource state."""
        try:
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            
            return {
                "cpu_percent": cpu_percent,
                "memory_mb": memory.used / (1024 * 1024),
                "memory_percent": memory.percent,
                "timestamp": time.time()
            }
        except Exception as e:
            log_system_event("performance_capture_error", f"Failed to capture system state: {str(e)}")
            return {
                "cpu_percent": 0.0,
                "memory_mb": 0.0,
                "memory_percent": 0.0,
                "timestamp": time.time()
            }
    
    def _record_metrics(self, metrics: PerformanceMetrics):
        """Record performance metrics."""
        with self._lock:
            self.recent_metrics.append(metrics)
            self.adapter_metrics[metrics.adapter_name].append(metrics)
            self.operation_counter += 1
            
            # Update adapter statistics
            self._update_adapter_statistics(metrics.adapter_name)
        
        # Persist to disk (async to avoid blocking)
        threading.Thread(
            target=self._persist_metrics_async,
            args=(metrics,),
            daemon=True
        ).start()
        
        log_system_event(
            "performance_metric_recorded",
            f"Recorded {metrics.operation_type} for {metrics.adapter_name}: "
            f"{metrics.duration:.2f}s, efficiency: {metrics.efficiency_score:.2f}"
        )
    
    def _update_adapter_statistics(self, adapter_name: str):
        """Update statistical summary for an adapter."""
        metrics_list = self.adapter_metrics[adapter_name]
        if not metrics_list:
            return
        
        successful_metrics = [m for m in metrics_list if m.success]
        if not successful_metrics:
            self.adapter_statistics[adapter_name] = {
                "success_rate": 0.0,
                "avg_duration": 0.0,
                "avg_efficiency": 0.0,
                "total_operations": len(metrics_list)
            }
            return
        
        durations = [m.duration for m in successful_metrics]
        efficiency_scores = [m.efficiency_score for m in successful_metrics]
        
        self.adapter_statistics[adapter_name] = {
            "success_rate": len(successful_metrics) / len(metrics_list),
            "avg_duration": statistics.mean(durations),
            "median_duration": statistics.median(durations),
            "p95_duration": self._percentile(durations, 95),
            "avg_efficiency": statistics.mean(efficiency_scores),
            "total_operations": len(metrics_list),
            "last_updated": time.time()
        }
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = (percentile / 100.0) * (len(sorted_data) - 1)
        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))
    
    def _persist_metrics_async(self, metrics: PerformanceMetrics):
        """Persist metrics to disk asynchronously."""
        try:
            # Save to daily metrics file
            date_str = datetime.fromtimestamp(metrics.start_time).strftime("%Y%m%d")
            metrics_file = self.storage_path / f"metrics_{date_str}.jsonl"
            
            with open(metrics_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(metrics)) + "\n")
                
        except Exception as e:
            log_system_event("performance_persist_error", f"Failed to persist metrics: {str(e)}")
    
    def _cleanup_old_metrics(self):
        """Clean up old metric files and in-memory data."""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.metrics_retention_days)
            
            # Clean up old files
            for metrics_file in self.storage_path.glob("metrics_*.jsonl"):
                try:
                    date_str = metrics_file.stem.split("_")[1]
                    file_date = datetime.strptime(date_str, "%Y%m%d")
                    
                    if file_date < cutoff_date:
                        metrics_file.unlink()
                        log_system_event("performance_cleanup", f"Removed old metrics file: {metrics_file.name}")
                        
                except (ValueError, IndexError):
                    continue  # Skip malformed filenames
            
            # Clean up in-memory data
            cutoff_timestamp = cutoff_date.timestamp()
            
            with self._lock:
                for adapter_name in list(self.adapter_metrics.keys()):
                    old_metrics = [
                        m for m in self.adapter_metrics[adapter_name]
                        if m.start_time < cutoff_timestamp
                    ]
                    
                    if old_metrics:
                        self.adapter_metrics[adapter_name] = [
                            m for m in self.adapter_metrics[adapter_name]
                            if m.start_time >= cutoff_timestamp
                        ]
                        
                        # Update statistics after cleanup
                        self._update_adapter_statistics(adapter_name)
            
        except Exception as e:
            log_system_event("performance_cleanup_error", f"Cleanup failed: {str(e)}")
    
    def get_adapter_statistics(self, adapter_name: str) -> Optional[Dict[str, Any]]:
        """Get performance statistics for a specific adapter."""
        return self.adapter_statistics.get(adapter_name)
    
    def get_all_adapter_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get performance statistics for all adapters."""
        return dict(self.adapter_statistics)
    
    def get_model_rankings(self, criteria: str = "efficiency") -> List[Tuple[str, float]]:
        """
        Get ranked list of models by performance criteria.
        
        Args:
            criteria: "efficiency", "speed", "reliability", or "overall"
        """
        rankings = []
        
        for adapter_name, stats in self.adapter_statistics.items():
            if stats["total_operations"] < 3:  # Need minimum operations for reliable ranking
                continue
            
            if criteria == "efficiency":
                score = stats.get("avg_efficiency", 0.0)
            elif criteria == "speed":
                # Lower duration = higher score
                avg_duration = stats.get("avg_duration", float("inf"))
                score = max(0.0, 1.0 - min(avg_duration / 30.0, 1.0))
            elif criteria == "reliability":
                score = stats.get("success_rate", 0.0)
            elif criteria == "overall":
                # Weighted combination
                efficiency = stats.get("avg_efficiency", 0.0)
                duration = stats.get("avg_duration", float("inf"))
                speed_score = max(0.0, 1.0 - min(duration / 30.0, 1.0))
                reliability = stats.get("success_rate", 0.0)
                score = (efficiency * 0.4 + speed_score * 0.3 + reliability * 0.3)
            else:
                raise ValueError(f"Unknown criteria: {criteria}")
            
            rankings.append((adapter_name, score))
        
        return sorted(rankings, key=lambda x: x[1], reverse=True)
    
    def analyze_bottlenecks(self, time_window_hours: int = 24) -> List[BottleneckAnalysis]:
        """
        Analyze performance bottlenecks in recent operations.
        
        Args:
            time_window_hours: Hours to look back for analysis
        """
        cutoff_time = time.time() - (time_window_hours * 3600)
        recent_metrics = [
            m for m in self.recent_metrics
            if m.start_time >= cutoff_time
        ]
        
        if not recent_metrics:
            return []
        
        bottlenecks = []
        
        # Analyze slow operations
        durations = [m.duration for m in recent_metrics if m.success]
        if durations:
            p95_duration = self._percentile(durations, 95)
            slow_operations = [m for m in recent_metrics if m.duration > p95_duration]
            
            if slow_operations and p95_duration > 10.0:  # More than 10 seconds
                bottlenecks.append(BottleneckAnalysis(
                    bottleneck_type="performance",
                    severity="high" if p95_duration > 30.0 else "medium",
                    impact_score=min(p95_duration / 60.0, 1.0),
                    description=f"Slow operations detected: 95th percentile duration is {p95_duration:.1f}s",
                    recommendation=f"Consider optimizing slow models or using faster alternatives for time-sensitive tasks",
                    affected_operations=[m.operation_id for m in slow_operations[-5:]],  # Last 5
                    evidence={
                        "p95_duration": p95_duration,
                        "slow_operation_count": len(slow_operations),
                        "total_operations": len(recent_metrics)
                    }
                ))
        
        # Analyze memory usage
        memory_increases = [
            m.memory_usage_after - m.memory_usage_before
            for m in recent_metrics if m.success
        ]
        if memory_increases:
            avg_memory_increase = statistics.mean(memory_increases)
            if avg_memory_increase > 500:  # More than 500MB average increase
                bottlenecks.append(BottleneckAnalysis(
                    bottleneck_type="memory",
                    severity="high" if avg_memory_increase > 1000 else "medium",
                    impact_score=min(avg_memory_increase / 2000.0, 1.0),
                    description=f"High memory usage detected: average increase of {avg_memory_increase:.1f}MB per operation",
                    recommendation="Consider using models with lower memory requirements or implementing memory cleanup",
                    affected_operations=[],
                    evidence={
                        "avg_memory_increase_mb": avg_memory_increase,
                        "max_memory_increase_mb": max(memory_increases),
                        "operations_analyzed": len(memory_increases)
                    }
                ))
        
        # Analyze failure rates
        failure_rate = len([m for m in recent_metrics if not m.success]) / len(recent_metrics)
        if failure_rate > 0.1:  # More than 10% failure rate
            bottlenecks.append(BottleneckAnalysis(
                bottleneck_type="reliability",
                severity="critical" if failure_rate > 0.3 else "high",
                impact_score=failure_rate,
                description=f"High failure rate detected: {failure_rate:.1%} of operations failing",
                recommendation="Check model configurations, API keys, and network connectivity",
                affected_operations=[m.operation_id for m in recent_metrics if not m.success][-10:],
                evidence={
                    "failure_rate": failure_rate,
                    "total_failures": len([m for m in recent_metrics if not m.success]),
                    "total_operations": len(recent_metrics)
                }
            ))
        
        return bottlenecks
    
    def generate_performance_report(self, time_window_hours: int = 24) -> PerformanceReport:
        """
        Generate comprehensive performance report.
        
        Args:
            time_window_hours: Hours to include in report
        """
        cutoff_time = time.time() - (time_window_hours * 3600)
        recent_metrics = [
            m for m in self.recent_metrics
            if m.start_time >= cutoff_time
        ]
        
        if not recent_metrics:
            return PerformanceReport(
                report_id=f"perf_report_{int(time.time())}",
                generation_time=datetime.now(),
                time_period=f"Last {time_window_hours} hours",
                total_operations=0,
                successful_operations=0,
                failed_operations=0,
                avg_duration=0.0,
                median_duration=0.0,
                p95_duration=0.0,
                avg_efficiency_score=0.0,
                avg_cpu_usage=0.0,
                peak_cpu_usage=0.0,
                avg_memory_usage=0.0,
                peak_memory_usage=0.0,
                model_rankings={},
                fastest_models=[],
                most_efficient_models=[],
                most_reliable_models=[],
                bottlenecks=[],
                optimization_recommendations=[],
                performance_trend="stable",
                trend_confidence=0.0
            )
        
        successful_metrics = [m for m in recent_metrics if m.success]
        failed_metrics = [m for m in recent_metrics if not m.success]
        
        # Calculate statistics
        durations = [m.duration for m in successful_metrics] if successful_metrics else [0.0]
        efficiency_scores = [m.efficiency_score for m in successful_metrics] if successful_metrics else [0.0]
        
        # Model rankings
        model_efficiency = defaultdict(list)
        for m in successful_metrics:
            model_efficiency[m.adapter_name].append(m.efficiency_score)
        
        model_rankings = {
            adapter: statistics.mean(scores)
            for adapter, scores in model_efficiency.items()
            if len(scores) >= 2  # Require at least 2 operations
        }
        
        # Get rankings by different criteria
        fastest_models = self.get_model_rankings("speed")[:5]
        most_efficient_models = self.get_model_rankings("efficiency")[:5]
        most_reliable_models = self.get_model_rankings("reliability")[:5]
        
        # Analyze bottlenecks
        bottlenecks = self.analyze_bottlenecks(time_window_hours)
        
        # Generate optimization recommendations
        recommendations = self._generate_optimization_recommendations(
            recent_metrics, bottlenecks, model_rankings
        )
        
        # Analyze performance trend
        trend, confidence = self._analyze_performance_trend(time_window_hours)
        
        return PerformanceReport(
            report_id=f"perf_report_{int(time.time())}",
            generation_time=datetime.now(),
            time_period=f"Last {time_window_hours} hours",
            total_operations=len(recent_metrics),
            successful_operations=len(successful_metrics),
            failed_operations=len(failed_metrics),
            avg_duration=statistics.mean(durations),
            median_duration=statistics.median(durations),
            p95_duration=self._percentile(durations, 95),
            avg_efficiency_score=statistics.mean(efficiency_scores),
            avg_cpu_usage=statistics.mean([m.cpu_usage_after for m in recent_metrics]),
            peak_cpu_usage=max([m.cpu_usage_after for m in recent_metrics]),
            avg_memory_usage=statistics.mean([m.memory_usage_after for m in recent_metrics]),
            peak_memory_usage=max([m.memory_usage_after for m in recent_metrics]),
            model_rankings=model_rankings,
            fastest_models=fastest_models,
            most_efficient_models=most_efficient_models,
            most_reliable_models=most_reliable_models,
            bottlenecks=bottlenecks,
            optimization_recommendations=recommendations,
            performance_trend=trend,
            trend_confidence=confidence
        )
    
    def _generate_optimization_recommendations(self, 
                                             metrics: List[PerformanceMetrics],
                                             bottlenecks: List[BottleneckAnalysis],
                                             model_rankings: Dict[str, float]) -> List[str]:
        """Generate specific optimization recommendations."""
        recommendations = []
        
        if not metrics:
            return recommendations
        
        # Analyze failure patterns
        failed_metrics = [m for m in metrics if not m.success]
        if failed_metrics:
            failure_rate = len(failed_metrics) / len(metrics)
            if failure_rate > 0.15:
                recommendations.append(
                    f"High failure rate ({failure_rate:.1%}) detected. "
                    "Check API keys and network connectivity."
                )
        
        # Analyze slow operations
        successful_metrics = [m for m in metrics if m.success]
        if successful_metrics:
            durations = [m.duration for m in successful_metrics]
            avg_duration = statistics.mean(durations)
            
            if avg_duration > 15.0:
                fastest_models = self.get_model_rankings("speed")[:3]
                if fastest_models:
                    fastest_names = [name for name, _ in fastest_models]
                    recommendations.append(
                        f"Average operation time is {avg_duration:.1f}s. "
                        f"Consider using faster models: {', '.join(fastest_names)}"
                    )
        
        # Memory optimization
        memory_increases = [
            m.memory_usage_after - m.memory_usage_before
            for m in successful_metrics
        ]
        if memory_increases:
            avg_memory_increase = statistics.mean(memory_increases)
            if avg_memory_increase > 300:
                recommendations.append(
                    f"High memory usage detected (avg: {avg_memory_increase:.0f}MB per operation). "
                    "Consider implementing memory cleanup or using lighter models."
                )
        
        # Model-specific recommendations
        if model_rankings:
            best_model = max(model_rankings, key=model_rankings.get)
            worst_models = [
                name for name, score in model_rankings.items()
                if score < 0.3
            ]
            
            if worst_models:
                recommendations.append(
                    f"Consider replacing underperforming models ({', '.join(worst_models)}) "
                    f"with {best_model} for better efficiency."
                )
        
        # Bottleneck-specific recommendations
        for bottleneck in bottlenecks:
            if bottleneck.recommendation not in recommendations:
                recommendations.append(bottleneck.recommendation)
        
        return recommendations
    
    def _analyze_performance_trend(self, time_window_hours: int) -> Tuple[str, float]:
        """
        Analyze performance trend over time.
        
        Returns:
            Tuple of (trend, confidence) where trend is "improving", "stable", or "degrading"
            and confidence is 0.0 to 1.0
        """
        try:
            # Get metrics for trend analysis (need more history)
            cutoff_time = time.time() - (time_window_hours * 2 * 3600)  # Double the window
            historical_metrics = [
                m for m in self.recent_metrics
                if m.start_time >= cutoff_time and m.success
            ]
            
            if len(historical_metrics) < 10:
                return "stable", 0.2  # Not enough data
            
            # Split into two halves for comparison
            mid_point = len(historical_metrics) // 2
            first_half = historical_metrics[:mid_point]
            second_half = historical_metrics[mid_point:]
            
            # Compare efficiency scores
            first_half_efficiency = statistics.mean([m.efficiency_score for m in first_half])
            second_half_efficiency = statistics.mean([m.efficiency_score for m in second_half])
            
            efficiency_change = second_half_efficiency - first_half_efficiency
            
            # Compare durations (lower is better)
            first_half_duration = statistics.mean([m.duration for m in first_half])
            second_half_duration = statistics.mean([m.duration for m in second_half])
            
            duration_improvement = first_half_duration - second_half_duration  # Positive = improvement
            
            # Determine trend
            if efficiency_change > 0.1 or duration_improvement > 2.0:
                trend = "improving"
                confidence = min(abs(efficiency_change) * 5 + abs(duration_improvement) / 10, 1.0)
            elif efficiency_change < -0.1 or duration_improvement < -2.0:
                trend = "degrading"
                confidence = min(abs(efficiency_change) * 5 + abs(duration_improvement) / 10, 1.0)
            else:
                trend = "stable"
                confidence = 0.7  # High confidence in stability
            
            return trend, min(confidence, 1.0)
            
        except Exception as e:
            log_system_event("performance_trend_error", f"Failed to analyze trend: {str(e)}")
            return "stable", 0.0
    
    def save_report_to_file(self, report: PerformanceReport, filename: Optional[str] = None) -> str:
        """Save performance report to file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_report_{timestamp}.json"
        
        report_path = self.storage_path / filename
        
        try:
            # Convert datetime objects to strings for JSON serialization
            report_dict = asdict(report)
            report_dict["generation_time"] = report.generation_time.isoformat()
            
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report_dict, f, indent=2, ensure_ascii=False)
            
            log_system_event("performance_report_saved", f"Performance report saved to {report_path}")
            return str(report_path)
            
        except Exception as e:
            log_system_event("performance_report_error", f"Failed to save report: {str(e)}")
            raise
    
    def get_active_operations(self) -> List[Dict[str, Any]]:
        """Get list of currently active operations."""
        with self._lock:
            return [
                {
                    "operation_id": op_id,
                    "duration": time.time() - op_data["start_time"],
                    **op_data
                }
                for op_id, op_data in self.active_operations.items()
            ]
    
    def get_system_health_summary(self) -> Dict[str, Any]:
        """Get current system health summary."""
        try:
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            
            recent_success_rate = 1.0
            if self.recent_metrics:
                recent_successful = len([m for m in self.recent_metrics if m.success])
                recent_success_rate = recent_successful / len(self.recent_metrics)
            
            return {
                "cpu_usage_percent": cpu_percent,
                "memory_usage_percent": memory.percent,
                "memory_available_gb": memory.available / (1024**3),
                "recent_success_rate": recent_success_rate,
                "active_operations": len(self.active_operations),
                "total_recorded_operations": self.operation_counter,
                "monitoring_active": self.monitoring_active,
                "adapters_tracked": len(self.adapter_statistics),
                "health_status": self._determine_health_status(cpu_percent, memory.percent, recent_success_rate)
            }
        except Exception as e:
            log_system_event("performance_health_error", f"Failed to get health summary: {str(e)}")
            return {
                "health_status": "unknown",
                "error": str(e)
            }
    
    def _determine_health_status(self, cpu_percent: float, memory_percent: float, success_rate: float) -> str:
        """Determine overall system health status."""
        if cpu_percent > 85 or memory_percent > 90 or success_rate < 0.8:
            return "critical"
        elif cpu_percent > 70 or memory_percent > 80 or success_rate < 0.9:
            return "warning"
        else:
            return "healthy"


class OperationTracker:
    """Helper class for tracking individual operation details."""
    
    def __init__(self, operation_id: str):
        self.operation_id = operation_id
        self.tokens_processed: Optional[int] = None
        self.response_size_bytes: Optional[int] = None
        self.network_latency: Optional[float] = None
        self.processing_time: Optional[float] = None
        self.queue_time: Optional[float] = None
        self.quality_score: Optional[float] = None
    
    def set_tokens_processed(self, count: int):
        """Set number of tokens processed."""
        self.tokens_processed = count
    
    def set_response_size(self, size_bytes: int):
        """Set response size in bytes."""
        self.response_size_bytes = size_bytes
    
    def set_network_latency(self, latency: float):
        """Set network latency in seconds."""
        self.network_latency = latency
    
    def set_processing_time(self, processing_time: float):
        """Set processing time in seconds."""
        self.processing_time = processing_time
    
    def set_queue_time(self, queue_time: float):
        """Set queue time in seconds."""
        self.queue_time = queue_time
    
    def set_quality_score(self, score: float):
        """Set quality score (0.0 to 1.0)."""
        self.quality_score = max(0.0, min(1.0, score))
    
    def calculate_tokens_per_second(self, total_time: float) -> Optional[float]:
        """Calculate tokens per second if data is available."""
        if self.tokens_processed and total_time > 0:
            return self.tokens_processed / total_time
        return None


# Convenience functions for global performance monitoring
_global_monitor: Optional[PerformanceMonitor] = None


def get_global_performance_monitor() -> PerformanceMonitor:
    """Get or create global performance monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
        _global_monitor.start_monitoring()
    return _global_monitor


def track_operation(adapter_name: str, operation_type: str, **kwargs):
    """Convenience function for tracking operations with global monitor."""
    monitor = get_global_performance_monitor()
    return monitor.track_operation(adapter_name, operation_type, **kwargs)


def get_quick_performance_summary() -> Dict[str, Any]:
    """Get quick performance summary from global monitor."""
    monitor = get_global_performance_monitor()
    return monitor.get_system_health_summary()


def generate_quick_report(hours: int = 24) -> PerformanceReport:
    """Generate quick performance report from global monitor."""
    monitor = get_global_performance_monitor()
    return monitor.generate_performance_report(hours)
