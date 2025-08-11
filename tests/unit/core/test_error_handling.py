"""
Unit tests for the standardized error handling framework.

Tests all components of the error handling system including:
- Exception hierarchy
- Error recovery strategies
- Error handling decorators
- Error monitoring and reporting

Phase 2 Week 7-8: Error Handling Standardization
"""

import asyncio
import time

import pytest
from openchronicle.shared.error_handling import DatabaseError
from openchronicle.shared.error_handling import ErrorCategory
from openchronicle.shared.error_handling import ErrorContext
from openchronicle.shared.error_handling import ErrorMonitor  # Monitoring
from openchronicle.shared.error_handling import ErrorRecoveryManager
from openchronicle.shared.error_handling import ErrorSeverity
from openchronicle.shared.error_handling import FallbackValueStrategy
from openchronicle.shared.error_handling import MemoryError
from openchronicle.shared.error_handling import ModelError
from openchronicle.shared.error_handling import OpenChronicleError
from openchronicle.shared.error_handling import RetryStrategy
from openchronicle.shared.error_handling import SecurityError
from openchronicle.shared.error_handling import add_recovery_strategy
from openchronicle.shared.error_handling import critical_operation
from openchronicle.shared.error_handling import error_monitor
from openchronicle.shared.error_handling import get_error_monitor
from openchronicle.shared.error_handling import get_error_recovery_manager
from openchronicle.shared.error_handling import with_error_handling  # Decorators


class TestErrorHierarchy:
    """Test the OpenChronicle error exception hierarchy."""

    def test_base_error_creation(self):
        """Test OpenChronicleError base class."""
        context = ErrorContext(component="test", operation="test_op")
        error = OpenChronicleError(
            "Test error",
            category=ErrorCategory.DATABASE,
            severity=ErrorSeverity.HIGH,
            context=context,
        )

        assert error.message == "Test error"
        assert error.category == ErrorCategory.DATABASE
        assert error.severity == ErrorSeverity.HIGH
        assert error.context == context
        assert error.recoverable == True
        assert isinstance(error.timestamp, float)

        error_info = error.get_error_info()
        assert error_info["message"] == "Test error"
        assert error_info["category"] == "database"
        assert error_info["severity"] == "high"

    def test_specialized_errors(self):
        """Test specialized error classes."""
        # DatabaseError
        db_error = DatabaseError(
            "DB connection failed", database_path="/test/db.sqlite"
        )
        assert db_error.category == ErrorCategory.DATABASE
        assert db_error.database_path == "/test/db.sqlite"

        # ModelError
        model_error = ModelError("Model timeout", model_name="gpt-4")
        assert model_error.category == ErrorCategory.MODEL
        assert model_error.model_name == "gpt-4"

        # SecurityError
        sec_error = SecurityError(
            "Unauthorized access", security_violation="invalid_token"
        )
        assert sec_error.category == ErrorCategory.SECURITY
        assert sec_error.severity == ErrorSeverity.HIGH
        assert sec_error.recoverable == False
        assert sec_error.security_violation == "invalid_token"

    def test_error_context(self):
        """Test ErrorContext functionality."""
        context = ErrorContext(
            component="memory_orchestrator",
            operation="get_character_memory",
            story_id="test_story",
            scene_id="scene_001",
            model_name="gpt-4",
            metadata={"character_id": "hero_001"},
        )

        tags = context.to_log_tags()
        expected_tags = {
            "component": "memory_orchestrator",
            "operation": "get_character_memory",
            "story": "test_story",
            "scene": "scene_001",
            "model": "gpt-4",
        }
        assert tags == expected_tags


class TestRecoveryStrategies:
    """Test error recovery strategy implementations."""

    def test_fallback_value_strategy(self):
        """Test FallbackValueStrategy recovery."""
        strategy = FallbackValueStrategy(
            fallback_value="default_response",
            applicable_categories=[ErrorCategory.MODEL],
        )

        # Should recover from model errors
        model_error = ModelError("Model failed", recoverable=True)
        assert asyncio.run(strategy.can_recover(model_error)) == True

        # Should not recover from database errors (not in applicable categories)
        db_error = DatabaseError("DB failed", recoverable=True)
        assert asyncio.run(strategy.can_recover(db_error)) == False

        # Should not recover from unrecoverable errors
        critical_error = ModelError("Critical model failure", recoverable=False)
        assert asyncio.run(strategy.can_recover(critical_error)) == False

        # Test recovery execution
        result = asyncio.run(strategy.recover(model_error, (), {}))
        assert result == "default_response"

    @pytest.mark.asyncio
    async def test_retry_strategy(self):
        """Test RetryStrategy with mock function."""
        strategy = RetryStrategy(max_retries=3, base_delay=0.01, max_delay=0.1)

        # Should recover from database/model/performance errors
        db_error = DatabaseError("Temporary DB issue", recoverable=True)
        assert await strategy.can_recover(db_error) == True

        memory_error = MemoryError("Memory issue", recoverable=True)
        assert await strategy.can_recover(memory_error) == False

        # Mock function that fails twice then succeeds
        call_count = 0

        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise DatabaseError("Temporary failure")
            return "success"

        # Test successful retry
        kwargs = {"_original_func": mock_func}
        result = await strategy.recover(db_error, (), kwargs)
        assert result == "success"
        assert call_count == 3

    def test_error_recovery_manager(self):
        """Test ErrorRecoveryManager functionality."""
        manager = ErrorRecoveryManager()

        # Add custom strategy
        custom_strategy = FallbackValueStrategy("custom_fallback")
        manager.add_strategy(custom_strategy)

        # Should have custom strategy plus default strategies
        assert len(manager.strategies) >= 2
        assert (
            manager.strategies[0] == custom_strategy
        )  # Should be first (highest priority)


class TestErrorDecorators:
    """Test error handling decorators."""

    @pytest.mark.asyncio
    async def test_with_error_handling_async(self):
        """Test with_error_handling decorator on async functions."""

        @with_error_handling(
            context=ErrorContext(component="test", operation="test_func"),
            fallback_result="fallback",
            error_category=ErrorCategory.DATABASE,
            enable_recovery=False,  # Disable recovery for predictable testing
        )
        async def test_async_func(should_fail=False):
            if should_fail:
                raise ValueError("Test error")
            return "success"

        # Test successful execution
        result = await test_async_func(False)
        assert result == "success"

        # Test error with fallback (no recovery)
        result = await test_async_func(True)
        assert result == "fallback"

    def test_with_error_handling_sync(self):
        """Test with_error_handling decorator on sync functions."""

        @with_error_handling(
            context=ErrorContext(component="test", operation="sync_test"),
            fallback_result="sync_fallback",
        )
        def test_sync_func(should_fail=False):
            if should_fail:
                raise ValueError("Sync test error")
            return "sync_success"

        # Test successful execution
        result = test_sync_func(False)
        assert result == "sync_success"

        # Test error with fallback
        result = test_sync_func(True)
        assert result == "sync_fallback"

    @pytest.mark.asyncio
    async def test_specialized_decorators(self):
        """Test specialized error handling decorators."""

        @with_error_handling(
            fallback_result="db_fallback",
            error_category=ErrorCategory.DATABASE,
            enable_recovery=False,  # Disable recovery for predictable testing
        )
        async def db_operation(should_fail=False):
            if should_fail:
                raise DatabaseError("DB connection failed")
            return "db_success"

        @with_error_handling(
            fallback_result="model_fallback",
            error_category=ErrorCategory.MODEL,
            enable_recovery=False,  # Disable recovery for predictable testing
        )
        async def model_operation(should_fail=False):
            if should_fail:
                raise ModelError("Model timeout")
            return "model_success"

        # Test successful operations
        assert await db_operation(False) == "db_success"
        assert await model_operation(False) == "model_success"

        # Test error handling
        assert await db_operation(True) == "db_fallback"
        assert await model_operation(True) == "model_fallback"

    @pytest.mark.asyncio
    async def test_critical_operation_decorator(self):
        """Test critical_operation decorator (no fallbacks allowed)."""

        @critical_operation
        async def critical_func(should_fail=False):
            if should_fail:
                raise ValueError("Critical failure")
            return "critical_success"

        # Test successful execution
        result = await critical_func(False)
        assert result == "critical_success"

        # Test that errors are not caught (re-raised as OpenChronicleError)
        with pytest.raises(OpenChronicleError):
            await critical_func(True)


class TestErrorMonitoring:
    """Test error monitoring and reporting functionality."""

    def test_error_monitor_recording(self):
        """Test error recording and tracking."""
        monitor = ErrorMonitor()

        # Record some errors
        error1 = DatabaseError("DB error 1", severity=ErrorSeverity.HIGH)
        error2 = ModelError("Model error 1", severity=ErrorSeverity.MEDIUM)
        error3 = DatabaseError("DB error 2", severity=ErrorSeverity.HIGH)

        monitor.record_error(error1)
        monitor.record_error(error2)
        monitor.record_error(error3)

        # Check error counts
        summary = monitor.get_error_summary()
        assert summary["total_errors"] == 3
        assert summary["error_breakdown"]["database:high"] == 2
        assert summary["error_breakdown"]["model:medium"] == 1

        # Check trends
        assert len(monitor.error_trends) == 3
        assert monitor.error_trends[0]["category"] == "database"
        assert monitor.error_trends[1]["category"] == "model"

    def test_error_monitor_health_status(self):
        """Test health status calculation."""
        monitor = ErrorMonitor()

        # No recent errors - should be healthy
        summary = monitor.get_error_summary()
        assert summary["health_status"] == "healthy"

        # Add many recent errors
        current_time = time.time()
        for i in range(15):
            error = DatabaseError(f"Error {i}")
            error.timestamp = current_time  # Make them recent
            monitor.record_error(error)

        summary = monitor.get_error_summary()
        assert summary["health_status"] == "degraded"

        # Add more errors for critical status
        for i in range(40):
            error = ModelError(f"Error {i}")
            error.timestamp = current_time
            monitor.record_error(error)

        summary = monitor.get_error_summary()
        assert summary["health_status"] == "critical"


class TestIntegration:
    """Integration tests for the complete error handling system."""

    @pytest.mark.asyncio
    async def test_end_to_end_error_handling(self):
        """Test complete error handling workflow."""

        # Create a function that uses the full error handling system
        @with_error_handling(
            context=ErrorContext(
                component="integration_test",
                operation="end_to_end_test",
                story_id="test_story",
            ),
            fallback_result="integration_fallback",
            error_category=ErrorCategory.INTEGRATION,
        )
        async def integration_test_func(scenario: str):
            if scenario == "success":
                return "integration_success"
            if scenario == "recoverable_error":
                raise DatabaseError(
                    "Recoverable database error",
                    severity=ErrorSeverity.MEDIUM,
                    recoverable=True,
                )
            if scenario == "unrecoverable_error":
                raise SecurityError(
                    "Security violation",
                    severity=ErrorSeverity.CRITICAL,
                    recoverable=False,
                )
            raise ValueError("Unknown scenario")

        # Test successful execution
        result = await integration_test_func("success")
        assert result == "integration_success"

        # Test recoverable error (should use fallback after recovery attempts fail)
        result = await integration_test_func("recoverable_error")
        # The retry strategy will try 3 times, fail, then fall back to the default fallback
        assert result == "integration_fallback"

        # Test unrecoverable error (should use fallback)
        result = await integration_test_func("unrecoverable_error")
        assert result == "integration_fallback"

        # Test unexpected error (should be converted to OpenChronicleError and use fallback)
        result = await integration_test_func("unknown")
        assert result == "integration_fallback"

    def test_utility_functions(self):
        """Test utility functions for accessing global instances."""

        # Test error recovery manager access
        recovery_manager = get_error_recovery_manager()
        assert isinstance(recovery_manager, ErrorRecoveryManager)

        # Test adding custom strategy
        custom_strategy = FallbackValueStrategy("test_fallback")
        add_recovery_strategy(custom_strategy)
        assert custom_strategy in recovery_manager.strategies

        # Test error monitor access
        monitor = get_error_monitor()
        assert isinstance(monitor, ErrorMonitor)
        assert monitor == error_monitor  # Should be same global instance


# === Test Runner ===

if __name__ == "__main__":
    print("Running Error Handling Framework Tests...")

    # Run basic tests
    test_hierarchy = TestErrorHierarchy()
    test_hierarchy.test_base_error_creation()
    test_hierarchy.test_specialized_errors()
    test_hierarchy.test_error_context()
    print("✅ Error hierarchy tests passed")

    test_recovery = TestRecoveryStrategies()
    test_recovery.test_fallback_value_strategy()
    asyncio.run(test_recovery.test_retry_strategy())
    test_recovery.test_error_recovery_manager()
    print("✅ Recovery strategy tests passed")

    test_decorators = TestErrorDecorators()
    asyncio.run(test_decorators.test_with_error_handling_async())
    test_decorators.test_with_error_handling_sync()
    asyncio.run(test_decorators.test_specialized_decorators())
    asyncio.run(test_decorators.test_critical_operation_decorator())
    print("✅ Error decorator tests passed")

    test_monitoring = TestErrorMonitoring()
    test_monitoring.test_error_monitor_recording()
    test_monitoring.test_error_monitor_health_status()
    print("✅ Error monitoring tests passed")

    test_integration = TestIntegration()
    asyncio.run(test_integration.test_end_to_end_error_handling())
    test_integration.test_utility_functions()
    print("✅ Integration tests passed")

    print("\n🎉 All Error Handling Framework Tests Passed!")
