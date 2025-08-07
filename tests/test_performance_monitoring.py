#!/usr/bin/env python3
"""
OpenChronicle Performance Monitoring Tests

Basic tests for the modular performance monitoring system.
"""

import asyncio
import unittest
from datetime import datetime, timedelta
import tempfile
import os

from utilities.performance import (
    PerformanceOrchestrator, MetricsCollector, MetricsStorage, BottleneckAnalyzer,
    OperationContext, PerformanceMetrics
)


class TestPerformanceMonitoring(unittest.TestCase):
    """Test the modular performance monitoring system."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "test_metrics.db")
        
        # Create components with dependency injection
        self.collector = MetricsCollector()
        self.storage = MetricsStorage(self.storage_path)
        self.analyzer = BottleneckAnalyzer()
        
        # Create orchestrator with injected dependencies
        self.orchestrator = PerformanceOrchestrator(
            metrics_collector=self.collector,
            metrics_storage=self.storage,
            bottleneck_analyzer=self.analyzer
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        try:
            if os.path.exists(self.storage_path):
                os.remove(self.storage_path)
            os.rmdir(self.temp_dir)
        except Exception:
            pass  # Best effort cleanup
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initialization."""
        async def run_test():
            await self.orchestrator.initialize()
            status = self.orchestrator.get_monitoring_status()
            
            self.assertTrue(status['initialized'])
            self.assertTrue(status['monitoring_enabled'])
            self.assertIn('metrics_collector', status['components'])
            self.assertIn('metrics_storage', status['components'])
            self.assertIn('bottleneck_analyzer', status['components'])
        
        asyncio.run(run_test())
    
    def test_operation_monitoring_cycle(self):
        """Test complete operation monitoring cycle."""
        async def run_test():
            await self.orchestrator.initialize()
            
            # Create operation context
            context = OperationContext(
                operation_id="test_op_001",
                adapter_name="test_adapter",
                operation_type="test_operation",
                metadata={"test": True, "tokens": 100}
            )
            
            # Start monitoring
            operation_id = await self.orchestrator.start_operation_monitoring(context)
            self.assertEqual(operation_id, "test_op_001")
            
            # Simulate some work
            await asyncio.sleep(0.1)  # 100ms operation
            
            # Finish monitoring
            metrics = await self.orchestrator.finish_operation_monitoring(
                operation_id, success=True
            )
            
            # Validate metrics
            self.assertEqual(metrics.operation_id, "test_op_001")
            self.assertEqual(metrics.adapter_name, "test_adapter")
            self.assertEqual(metrics.operation_type, "test_operation")
            self.assertTrue(metrics.success)
            self.assertGreater(metrics.duration, 0.05)  # At least 50ms
            self.assertIsNotNone(metrics.start_time)
            self.assertIsNotNone(metrics.end_time)
        
        asyncio.run(run_test())
    
    def test_metrics_storage_and_retrieval(self):
        """Test metrics storage and retrieval."""
        async def run_test():
            await self.storage.initialize()
            
            # Create test metrics
            test_time = datetime.now().timestamp()
            metrics = PerformanceMetrics(
                operation_id="test_store_001",
                adapter_name="test_adapter",
                operation_type="test_operation",
                start_time=test_time,
                end_time=test_time + 1.0,
                duration=1.0,
                cpu_usage_before=10.0,
                cpu_usage_after=15.0,
                memory_usage_before=100.0,
                memory_usage_after=120.0,
                success=True,
                context={"test": True}
            )
            
            # Store metrics
            await self.storage.store_metrics(metrics)
            
            # Retrieve metrics
            from utilities.performance.interfaces.performance_interfaces import MetricsQuery
            query = MetricsQuery(
                start_time=datetime.fromtimestamp(test_time - 10),
                end_time=datetime.fromtimestamp(test_time + 10),
                adapter_names=["test_adapter"]
            )
            
            retrieved_metrics = await self.storage.retrieve_metrics(query)
            
            # Validate retrieval
            self.assertEqual(len(retrieved_metrics), 1)
            retrieved = retrieved_metrics[0]
            self.assertEqual(retrieved.operation_id, "test_store_001")
            self.assertEqual(retrieved.adapter_name, "test_adapter")
            self.assertEqual(retrieved.duration, 1.0)
            self.assertTrue(retrieved.success)
        
        asyncio.run(run_test())
    
    def test_bottleneck_analysis(self):
        """Test bottleneck analysis."""
        async def run_test():
            # Create test metrics with different performance characteristics
            base_time = datetime.now().timestamp()
            test_metrics = []
            
            # Normal operations
            for i in range(5):
                metrics = PerformanceMetrics(
                    operation_id=f"normal_op_{i}",
                    adapter_name="normal_adapter",
                    operation_type="normal_operation",
                    start_time=base_time + i,
                    end_time=base_time + i + 1.0,
                    duration=1.0,
                    cpu_usage_before=10.0,
                    cpu_usage_after=15.0,
                    memory_usage_before=100.0,
                    memory_usage_after=110.0,
                    success=True
                )
                test_metrics.append(metrics)
            
            # Slow operations (bottleneck)
            for i in range(3):
                metrics = PerformanceMetrics(
                    operation_id=f"slow_op_{i}",
                    adapter_name="slow_adapter",
                    operation_type="slow_operation",
                    start_time=base_time + 10 + i,
                    end_time=base_time + 10 + i + 15.0,  # 15 second duration (critical)
                    duration=15.0,
                    cpu_usage_before=10.0,
                    cpu_usage_after=80.0,  # High CPU usage
                    memory_usage_before=100.0,
                    memory_usage_after=600.0,  # High memory usage
                    success=True
                )
                test_metrics.append(metrics)
            
            # Analyze bottlenecks
            report = await self.analyzer.analyze_bottlenecks(test_metrics)
            
            # Validate analysis
            self.assertIsNotNone(report)
            self.assertEqual(report.total_operations, 8)
            self.assertEqual(report.failed_operations, 0)
            self.assertGreater(len(report.bottleneck_patterns), 0)  # Should detect bottlenecks
            self.assertIn("slow_adapter", report.top_bottleneck_adapters)
            self.assertGreater(len(report.recommendations), 0)
            
            # Test slow operation identification
            slow_ops = await self.analyzer.identify_slow_operations(test_metrics, 90.0)
            self.assertGreater(len(slow_ops), 0)  # Should identify slow operations
            
            # Test resource usage analysis
            resource_patterns = await self.analyzer.analyze_resource_usage_patterns(test_metrics)
            self.assertIn('overall', resource_patterns)
            self.assertIn('by_adapter', resource_patterns)
            self.assertGreater(resource_patterns['overall']['avg_cpu_delta'], 0)
        
        asyncio.run(run_test())
    
    def test_real_time_metrics(self):
        """Test real-time metrics collection."""
        async def run_test():
            await self.orchestrator.initialize()
            
            # Get real-time metrics
            real_time = await self.orchestrator.get_real_time_metrics()
            
            # Validate real-time metrics
            self.assertIn('timestamp', real_time)
            self.assertIn('system_metrics', real_time)
            self.assertIn('collector_status', real_time)
            self.assertIn('storage_stats', real_time)
            self.assertTrue(real_time['monitoring_enabled'])
            self.assertTrue(real_time['initialized'])
            
            # Validate system metrics
            system_metrics = real_time['system_metrics']
            self.assertIn('cpu_percent', system_metrics)
            self.assertIn('memory_mb', system_metrics)
            self.assertIn('timestamp', system_metrics)
        
        asyncio.run(run_test())
    
    def test_monitoring_enable_disable(self):
        """Test enabling and disabling monitoring."""
        async def run_test():
            await self.orchestrator.initialize()
            
            # Test disabling
            self.orchestrator.disable_monitoring()
            status = self.orchestrator.get_monitoring_status()
            self.assertFalse(status['monitoring_enabled'])
            
            # Test enabling
            self.orchestrator.enable_monitoring()
            status = self.orchestrator.get_monitoring_status()
            self.assertTrue(status['monitoring_enabled'])
        
        asyncio.run(run_test())
    
    def test_performance_analysis(self):
        """Test comprehensive performance analysis."""
        async def run_test():
            await self.orchestrator.initialize()
            
            # Create and store some test data
            context = OperationContext(
                operation_id="analysis_test_001",
                adapter_name="analysis_adapter",
                operation_type="analysis_operation",
                metadata={"test": True}
            )
            
            operation_id = await self.orchestrator.start_operation_monitoring(context)
            await asyncio.sleep(0.05)  # 50ms operation
            await self.orchestrator.finish_operation_monitoring(operation_id, True)
            
            # Perform analysis
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=5)
            
            analysis = await self.orchestrator.analyze_performance((start_time, end_time))
            
            # Validate analysis
            self.assertIn('analysis_time', analysis)
            self.assertIn('time_period', analysis)
            self.assertIn('metrics_summary', analysis)
            self.assertIn('bottleneck_analysis', analysis)
            self.assertIn('recommendations', analysis)
        
        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()
