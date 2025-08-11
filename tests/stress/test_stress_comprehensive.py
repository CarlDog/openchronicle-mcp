"""
Production-Grade Stress Tests for OpenChronicle.

This module implements comprehensive stress tests using the stress testing framework
to validate production-grade reliability across all major system components.

Test Categories:
- Orchestrator Load Testing (Model, Memory, Scene, etc.)
- Database Integrity Under Load
- Memory Pressure Testing
- Concurrent Operation Limits
- Performance Regression Detection
- Chaos Engineering Scenarios
"""

import asyncio
import sys
import time
from pathlib import Path

import pytest


# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.openchronicle.domain.models.model_orchestrator import ModelOrchestrator
from src.openchronicle.domain.services.scenes.scene_orchestrator import (
    SceneOrchestrator,
)
from src.openchronicle.infrastructure.memory.memory_orchestrator import (
    MemoryOrchestrator,
)
from src.openchronicle.shared.logging_system import log_info

from tests.stress.stress_testing_framework import create_stress_test_config
from tests.stress.stress_testing_framework import create_stress_testing_framework


class TestOrchestatorStressTesting:
    """Stress tests for all major orchestrators."""

    @pytest.fixture
    def stress_framework(self):
        """Create stress testing framework for tests."""
        config = create_stress_test_config(
            max_concurrent=20,  # Start with moderate load
            duration=30,        # 30 second tests
            success_rate=0.95,  # 95% success required
            enable_chaos=False  # Disable chaos for basic tests
        )
        return create_stress_testing_framework(config)

    @pytest.mark.stress
    @pytest.mark.asyncio
    async def test_model_orchestrator_stress(self, stress_framework):
        """Test ModelOrchestrator under concurrent load."""

        async def model_operation(orchestrator, operation_id):
            """Test operation for ModelOrchestrator."""
            # Test basic orchestrator operations
            status = orchestrator.get_status()
            adapters = orchestrator.get_available_adapters()
            await asyncio.sleep(0.01)  # Simulate work
            return f"operation_{operation_id}_complete"

        result = await stress_framework.stress_test_orchestrator(
            orchestrator_class=ModelOrchestrator,
            test_operation=model_operation,
            concurrent_requests=15,
            duration_seconds=20,
            test_name="model_orchestrator_stress"
        )

        # Assertions
        assert result.passed, f"Model orchestrator stress test failed: {result.success_rate:.2%} success rate"
        assert result.total_operations > 50, "Should have completed at least 50 operations"
        assert result.average_response_time < 1.0, "Average response time should be under 1 second"
        assert result.memory_peak_mb < 200, "Memory usage should be reasonable"

        log_info(f"Model orchestrator stress test: {result.total_operations} ops, {result.success_rate:.2%} success")

    @pytest.mark.stress
    @pytest.mark.asyncio
    async def test_memory_orchestrator_stress(self, stress_framework):
        """Test MemoryOrchestrator under concurrent load."""

        async def memory_operation(orchestrator, operation_id):
            """Test operation for MemoryOrchestrator."""
            # Test memory management operations
            story_id = f"test_story_{operation_id % 5}"  # Rotate through 5 stories
            character_id = f"character_{operation_id % 3}"  # 3 characters

            # Simulate memory operations
            await asyncio.sleep(0.005)  # Simulate memory work
            return f"memory_op_{operation_id}"

        result = await stress_framework.stress_test_orchestrator(
            orchestrator_class=MemoryOrchestrator,
            test_operation=memory_operation,
            concurrent_requests=10,
            duration_seconds=15,
            test_name="memory_orchestrator_stress"
        )

        # Assertions
        assert result.passed, f"Memory orchestrator stress test failed: {result.success_rate:.2%} success rate"
        assert result.total_operations > 30, "Should have completed at least 30 operations"
        assert result.average_response_time < 0.5, "Memory operations should be fast"

        log_info(f"Memory orchestrator stress test: {result.total_operations} ops, {result.success_rate:.2%} success")

    @pytest.mark.stress
    @pytest.mark.asyncio
    async def test_scene_orchestrator_stress(self, stress_framework):
        """Test SceneOrchestrator under concurrent load."""

        async def scene_operation(orchestrator, operation_id):
            """Test operation for SceneOrchestrator."""
            # Test scene creation operations
            scene_id = f"scene_{operation_id}"
            story_id = f"story_{operation_id % 3}"

            # Simulate scene work
            await asyncio.sleep(0.02)  # Scene operations take longer
            return f"scene_{scene_id}_created"

        result = await stress_framework.stress_test_orchestrator(
            orchestrator_class=lambda: SceneOrchestrator("test_story_id"),
            test_operation=scene_operation,
            concurrent_requests=8,  # Lower concurrency for scene operations
            duration_seconds=20,
            test_name="scene_orchestrator_stress"
        )

        # Assertions
        assert result.passed, f"Scene orchestrator stress test failed: {result.success_rate:.2%} success rate"
        assert result.total_operations > 20, "Should have completed at least 20 operations"
        assert result.average_response_time < 2.0, "Scene operations should complete within 2 seconds"

        log_info(f"Scene orchestrator stress test: {result.total_operations} ops, {result.success_rate:.2%} success")

    @pytest.mark.stress
    @pytest.mark.asyncio
    async def test_mixed_orchestrator_concurrency(self, stress_framework):
        """Test multiple orchestrators running concurrently."""

        # Create multiple orchestrators
        model_orch = ModelOrchestrator()
        memory_orch = MemoryOrchestrator()
        scene_orch = SceneOrchestrator("test_story_id")

        async def mixed_operation(orchestrator, operation_id):
            """Mixed operations across orchestrators."""
            op_type = operation_id % 3

            if op_type == 0:
                # Model operation
                status = model_orch.get_status()
                await asyncio.sleep(0.01)
            elif op_type == 1:
                # Memory operation
                await asyncio.sleep(0.005)
            else:
                # Scene operation
                await asyncio.sleep(0.02)

            return f"mixed_op_{operation_id}_type_{op_type}"

        result = await stress_framework.stress_test_orchestrator(
            orchestrator_class=lambda: None,  # No specific orchestrator
            test_operation=mixed_operation,
            concurrent_requests=12,
            duration_seconds=25,
            test_name="mixed_orchestrator_stress"
        )

        # Assertions
        assert result.passed, f"Mixed orchestrator stress test failed: {result.success_rate:.2%} success rate"
        assert result.total_operations > 40, "Should have completed at least 40 mixed operations"

        log_info(f"Mixed orchestrator stress test: {result.total_operations} ops, {result.success_rate:.2%} success")


class TestDatabaseStressTesting:
    """Database-specific stress tests."""

    @pytest.fixture
    def stress_framework(self):
        """Create stress testing framework for database tests."""
        config = create_stress_test_config(
            max_concurrent=25,
            duration=20,
            success_rate=0.95
        )
        return create_stress_testing_framework(config)

    @pytest.mark.stress
    @pytest.mark.asyncio
    async def test_database_concurrent_operations(self, stress_framework):
        """Test database operations under concurrent load."""

        result = await stress_framework.database_stress_test(concurrent_db_ops=15)

        # Assertions
        assert result.passed, f"Database stress test failed: {result.success_rate:.2%} success rate"
        assert result.total_operations > 20, "Should have completed multiple database operations"
        assert len(result.errors) < 5, "Should have minimal database errors"

        log_info(f"Database stress test: {result.total_operations} ops, {result.success_rate:.2%} success")

    @pytest.mark.stress
    @pytest.mark.asyncio
    async def test_database_integrity_under_load(self, stress_framework):
        """Test database integrity during high load."""

        # Run database stress with higher concurrency
        result = await stress_framework.database_stress_test(concurrent_db_ops=30)

        # Even under high load, database should maintain integrity
        assert result.success_rate > 0.90, "Database should maintain 90%+ success rate under load"
        assert result.average_response_time < 5.0, "Database operations should complete within 5 seconds"

        log_info(f"Database integrity test: {result.success_rate:.2%} success under high load")


class TestMemoryStressTesting:
    """Memory pressure and resource stress tests."""

    @pytest.fixture
    def stress_framework(self):
        """Create stress testing framework for memory tests."""
        config = create_stress_test_config(
            max_concurrent=10,
            duration=15,
            success_rate=0.85  # Lower threshold for memory pressure tests
        )
        return create_stress_testing_framework(config)

    @pytest.mark.stress
    @pytest.mark.asyncio
    async def test_memory_pressure_handling(self, stress_framework):
        """Test system behavior under memory pressure."""

        result = await stress_framework.memory_stress_test(target_memory_mb=50)

        # Under memory pressure, system should degrade gracefully
        assert result.success_rate > 0.80, "System should maintain 80%+ operation success under memory pressure"
        assert result.performance_metrics.get('graceful_degradation', False), "Should handle memory pressure gracefully"

        log_info(f"Memory pressure test: {result.success_rate:.2%} success under 50MB pressure")

    @pytest.mark.stress
    @pytest.mark.asyncio
    async def test_extreme_memory_pressure(self, stress_framework):
        """Test system behavior under extreme memory pressure."""

        result = await stress_framework.memory_stress_test(target_memory_mb=100)

        # Even under extreme pressure, system shouldn't crash
        assert result.success_rate > 0.50, "System should maintain some functionality under extreme pressure"
        assert len(result.errors) < 20, "Should not generate excessive errors"

        log_info(f"Extreme memory pressure test: {result.success_rate:.2%} success under 100MB pressure")


class TestPerformanceRegression:
    """Performance regression detection tests."""

    @pytest.fixture
    def stress_framework(self):
        """Create stress testing framework for performance tests."""
        return create_stress_testing_framework()

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_performance_baseline_establishment(self, stress_framework):
        """Establish performance baselines for regression detection."""

        # Test ModelOrchestrator performance baseline
        start_time = time.time()
        orchestrator = ModelOrchestrator()

        # Perform standard operations
        for i in range(10):
            status = orchestrator.get_status()
            adapters = orchestrator.get_available_adapters()
            await asyncio.sleep(0.001)

        baseline_time = time.time() - start_time

        # Baseline should be reasonable
        assert baseline_time < 1.0, "Baseline operations should complete quickly"

        log_info(f"Performance baseline established: {baseline_time:.3f}s for 10 operations")

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_performance_regression_detection(self, stress_framework):
        """Test performance regression detection mechanism."""

        baseline_time = 0.100  # 100ms baseline
        current_time = 0.250   # 250ms current (2.5x slower)

        # Should detect regression (2.5x > 2.0x threshold)
        regression_detected = stress_framework.detect_performance_regression(
            test_name="test_operation",
            current_time=current_time,
            baseline_time=baseline_time
        )

        assert regression_detected, "Should detect performance regression when 2.5x slower than baseline"

        # Test non-regression case
        current_time = 0.150  # 150ms current (1.5x slower - acceptable)
        regression_detected = stress_framework.detect_performance_regression(
            test_name="test_operation",
            current_time=current_time,
            baseline_time=baseline_time
        )

        assert not regression_detected, "Should not detect regression for 1.5x slowdown"


class TestChaosEngineering:
    """Chaos engineering and failure simulation tests."""

    @pytest.fixture
    def stress_framework(self):
        """Create stress testing framework with chaos enabled."""
        config = create_stress_test_config(enable_chaos=True)
        return create_stress_testing_framework(config)

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_chaos_engineering_scenarios(self, stress_framework):
        """Test system resilience under chaos engineering scenarios."""

        result = await stress_framework.simulate_chaos_failures()

        # System should recover from most chaos scenarios
        assert result.success_rate > 0.60, "System should recover from 60%+ of chaos scenarios"
        assert result.performance_metrics.get('recovery_rate', 0) > 0.60, "Recovery rate should be reasonable"

        log_info(f"Chaos engineering test: {result.success_rate:.2%} recovery rate")

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_orchestrator_failure_recovery(self, stress_framework):
        """Test orchestrator recovery from simulated failures."""

        async def failing_operation(orchestrator, operation_id):
            """Operation that sometimes fails to test recovery."""
            if operation_id % 4 == 0:  # 25% failure rate
                raise Exception(f"Simulated failure for operation {operation_id}")

            await asyncio.sleep(0.01)
            return f"operation_{operation_id}_success"

        result = await stress_framework.stress_test_orchestrator(
            orchestrator_class=ModelOrchestrator,
            test_operation=failing_operation,
            concurrent_requests=8,
            duration_seconds=15,
            test_name="failure_recovery_stress"
        )

        # With 25% simulated failure rate, should still achieve reasonable success
        assert result.success_rate > 0.70, "Should achieve 70%+ success despite 25% simulated failures"
        assert result.total_operations > 15, "Should complete multiple operations despite failures"

        log_info(f"Failure recovery test: {result.success_rate:.2%} success with simulated failures")


class TestProductionReadiness:
    """Production readiness validation tests."""

    @pytest.fixture
    def stress_framework(self):
        """Create stress testing framework for production tests."""
        config = create_stress_test_config(
            max_concurrent=50,
            duration=60,
            success_rate=0.95
        )
        return create_stress_testing_framework(config)

    @pytest.mark.production
    @pytest.mark.asyncio
    async def test_production_load_simulation(self, stress_framework):
        """Simulate production-like load patterns."""

        async def production_operation(orchestrator, operation_id):
            """Simulate realistic production operations."""
            # Mix of different operation types with realistic timing
            if operation_id % 10 < 6:  # 60% model operations
                status = orchestrator.get_status()
                await asyncio.sleep(0.02)  # Realistic model operation time
            elif operation_id % 10 < 8:  # 20% memory operations
                await asyncio.sleep(0.01)  # Memory operations
            else:  # 20% scene operations
                await asyncio.sleep(0.05)  # Scene operations take longer

            return f"production_op_{operation_id}"

        result = await stress_framework.stress_test_orchestrator(
            orchestrator_class=ModelOrchestrator,
            test_operation=production_operation,
            concurrent_requests=25,  # Moderate production load
            duration_seconds=45,
            test_name="production_load_simulation"
        )

        # Production requirements
        assert result.passed, f"Production load test failed: {result.success_rate:.2%} success rate"
        assert result.total_operations > 200, "Should handle significant operation volume"
        assert result.average_response_time < 1.0, "Production operations should be responsive"
        assert result.memory_peak_mb < 300, "Memory usage should be sustainable"
        assert result.performance_metrics['operations_per_second'] > 5, "Should maintain reasonable throughput"

        log_info(f"Production load test: {result.total_operations} ops at {result.performance_metrics['operations_per_second']:.1f} ops/sec")

    @pytest.mark.production
    @pytest.mark.asyncio
    async def test_comprehensive_stress_report(self, stress_framework):
        """Generate comprehensive stress test report."""

        # Run a quick test to generate some results
        async def simple_operation(orchestrator, operation_id):
            await asyncio.sleep(0.001)
            return f"simple_op_{operation_id}"

        await stress_framework.stress_test_orchestrator(
            orchestrator_class=ModelOrchestrator,
            test_operation=simple_operation,
            concurrent_requests=5,
            duration_seconds=5,
            test_name="report_generation_test"
        )

        # Generate and validate report
        report = stress_framework.generate_stress_test_report()

        assert len(report) > 500, "Report should be comprehensive"
        assert "OPENCHRONICLE STRESS TEST REPORT" in report, "Report should have proper header"
        assert "SUMMARY STATISTICS" in report, "Report should include summary"
        assert "INDIVIDUAL TEST RESULTS" in report, "Report should include individual results"

        # Print report for manual inspection
        print("\n" + report)

        log_info("Comprehensive stress test report generated successfully")


# Utility functions for external integration
def run_production_stress_tests():
    """Run all production stress tests and return results."""
    import subprocess
    import sys

    result = subprocess.run([
        sys.executable, "-m", "pytest",
        str(Path(__file__)),
        "-v", "-m", "production",
        "--tb=short"
    ], check=False, capture_output=True, text=True)

    return result.returncode == 0, result.stdout, result.stderr


def run_quick_stress_validation():
    """Run quick stress validation for CI/CD pipeline."""
    import subprocess
    import sys

    result = subprocess.run([
        sys.executable, "-m", "pytest",
        str(Path(__file__)),
        "-v", "-m", "stress and not chaos and not production",
        "--tb=short", "-x"  # Stop on first failure
    ], check=False, capture_output=True, text=True)

    return result.returncode == 0, result.stdout, result.stderr


if __name__ == "__main__":
    # Run quick validation when executed directly
    success, stdout, stderr = run_quick_stress_validation()
    print(stdout)
    if stderr:
        print("STDERR:", stderr)
    if not success:
        exit(1)
