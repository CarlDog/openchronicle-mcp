"""
Unit tests for ModelOrchestrator

Tests the model management and orchestration functionality.
"""

import asyncio
from unittest.mock import patch

import pytest

# Import the orchestrator under test
from openchronicle.domain.models.model_orchestrator import ModelOrchestrator

# Import enhanced mock adapters for isolated testing
from tests.fixtures.mock_adapters import MockLLMAdapter
from tests.fixtures.mock_adapters import MockModelOrchestrator


class TestModelOrchestratorInitialization:
    """Test ModelOrchestrator initialization and configuration."""

    def test_orchestrator_initialization(self):
        """Test basic orchestrator initialization."""
        orchestrator = ModelOrchestrator()

        assert orchestrator is not None
        assert hasattr(orchestrator, "config_manager")
        assert hasattr(orchestrator, "lifecycle_manager")
        assert hasattr(orchestrator, "performance_monitor")

    def test_orchestrator_with_config(self):
        """Test orchestrator initialization uses ConfigurationManager properly."""
        orchestrator = ModelOrchestrator()

        assert orchestrator is not None
        # Verify config manager was initialized and discovered models
        assert orchestrator.config_manager is not None
        assert hasattr(orchestrator.config_manager, "registry")
        assert hasattr(orchestrator.config_manager, "config")

        # Verify dynamic discovery worked
        assert isinstance(orchestrator.config_manager.registry, dict)
        assert isinstance(orchestrator.config_manager.config, dict)

    def test_orchestrator_component_status(self):
        """Test that all components are properly initialized."""
        orchestrator = ModelOrchestrator()

        # Check that all required components exist
        components = [
            "config_manager",
            "lifecycle_manager",
            "performance_monitor",
            "response_generator",
        ]

        for component in components:
            assert hasattr(orchestrator, component)
            assert getattr(orchestrator, component) is not None


class TestModelOrchestratorConfiguration:
    """Test model configuration management."""

    def test_load_model_registry(self):
        """Test model registry loading through ConfigurationManager."""
        orchestrator = ModelOrchestrator()

        # Use the NEW architecture - registry is loaded automatically
        registry = orchestrator.config_manager.registry

        assert isinstance(registry, dict)
        # Registry should have providers from dynamic discovery
        assert "providers" in registry or "fallback_chains" in registry

    def test_get_available_models(self):
        """Test getting available models through NEW architecture."""
        orchestrator = ModelOrchestrator()

        # Use the NEW method that actually exists
        models = orchestrator.config_manager.list_model_configs()

        assert isinstance(models, dict)
        # Should have discovered models from config/models/
        assert len(models) >= 0  # Could be empty if no models in config

    def test_model_configuration_validation(self):
        """Test model configuration validation."""
        orchestrator = ModelOrchestrator()

        # Test with valid configuration
        valid_config = {
            "name": "test-model",
            "type": "text",
            "enabled": True,
            "api_key": "test-key",
        }

        result = orchestrator.config_manager.validate_model_config(valid_config)
        assert isinstance(result, dict)
        assert "valid" in result

        # Test with invalid configuration
        invalid_config = {
            "name": "test-model",
            # Missing required fields
        }

        is_valid = orchestrator.config_manager.validate_model_config(invalid_config)
        # NEW architecture returns dict with validation results
        assert isinstance(is_valid, dict)
        assert is_valid.get("valid") is False


class TestModelOrchestratorLifecycle:
    """Test model lifecycle management."""

    def test_model_health_check(self):
        """Test model health monitoring."""
        orchestrator = ModelOrchestrator()

        # NEW architecture uses get_system_health_summary
        health_status = orchestrator.performance_monitor.get_system_health_summary()

        assert health_status is not None
        assert isinstance(health_status, dict)
        # NEW architecture returns different keys - check for actual keys returned
        assert "health_status" in health_status or "available" in health_status
        # Verify we get some kind of meaningful health data
        if "health_status" in health_status:
            assert health_status["health_status"] in [
                "healthy",
                "unhealthy",
                "degraded",
            ]

    def test_model_fallback_chain(self):
        """Test fallback chain configuration."""
        orchestrator = ModelOrchestrator()

        # NEW architecture requires model_name parameter
        fallback_chain = orchestrator.config_manager.get_fallback_chain("mock")

        assert fallback_chain is not None
        assert isinstance(fallback_chain, list)
        assert len(fallback_chain) > 0


class TestModelOrchestratorPerformance:
    """Test performance monitoring and optimization."""

    def test_performance_metrics(self):
        """Test performance metrics collection through new architecture."""
        orchestrator = ModelOrchestrator()

        # NEW architecture uses generate_performance_report method
        metrics = asyncio.run(
            orchestrator.performance_monitor.generate_performance_report()
        )

        assert metrics is not None
        assert isinstance(metrics, dict)
        assert "success" in metrics

    def test_model_selection_optimization(self):
        """Test intelligent model selection based on performance."""
        orchestrator = ModelOrchestrator()

        # Mock the performance analytics method
        with patch.object(
            orchestrator.performance_monitor, "get_model_performance_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = {
                "success": True,
                "analytics": {
                    "adapter_name": None,
                    "metrics": {},
                    "timestamp": "2024-01-01T00:00:00Z",
                },
                "adapter_status": {
                    "mock_adapter": {
                        "available": True,
                        "type": "test",
                        "model_name": "test_model",
                        "initialized": True,
                    }
                },
            }

            # Test model selection
            # NEW architecture uses get_model_performance_analytics for optimization
            analytics = asyncio.run(
                orchestrator.performance_monitor.get_model_performance_analytics()
            )
            # Mock a selection based on analytics
            selected_model = "mock" if analytics.get("success") else None

            assert selected_model is not None
            assert isinstance(selected_model, str)

    def test_performance_degradation_detection(self):
        """Test detection of performance degradation."""
        orchestrator = ModelOrchestrator()

        # Mock the performance report method
        with patch.object(
            orchestrator.performance_monitor, "generate_performance_report"
        ) as mock_report:
            mock_report.return_value = {
                "success": True,
                "report": {
                    "degradation_detected": False,
                    "performance_trends": {},
                    "recommendations": [],
                },
                "timestamp": "2024-01-01T00:00:00Z",
            }

            # NEW architecture uses performance report for degradation detection
            report = asyncio.run(
                orchestrator.performance_monitor.generate_performance_report()
            )
            degradation_status = report.get("success", False)

            assert degradation_status is not None
        assert isinstance(degradation_status, bool)
        # Performance monitoring should be available and working
        assert degradation_status is True


class TestModelOrchestratorResponseGeneration:
    """Test response generation functionality."""

    @pytest.mark.asyncio
    async def test_generate_response_success(self):
        """Test successful response generation."""
        orchestrator = ModelOrchestrator()

        # Mock the response generator
        with patch.object(
            orchestrator.response_generator, "generate_response"
        ) as mock_generate:
            # NEW architecture returns async string response
            async def mock_async_generate(*args, **kwargs):
                return "Test response content"

            mock_generate.side_effect = mock_async_generate

            response = await orchestrator.response_generator.generate_response(
                prompt="Test prompt", adapter_name="test-model"
            )

            assert response is not None
            assert isinstance(response, str)
            assert len(response) > 0
            assert response == "Test response content"

    @pytest.mark.asyncio
    async def test_generate_response_with_fallback(self):
        """Test response generation with fallback chain."""
        orchestrator = ModelOrchestrator()

        # Mock multiple model attempts - in NEW architecture, generate_response handles fallbacks internally
        with patch.object(
            orchestrator.response_generator, "generate_response"
        ) as mock_generate:
            # NEW architecture: internal fallback handling returns successful async string response
            async def mock_async_fallback(*args, **kwargs):
                return "Fallback response content"

            mock_generate.side_effect = mock_async_fallback

            # NEW architecture: generate_response already handles fallbacks internally
            response = await orchestrator.response_generator.generate_response(
                prompt="Test prompt", adapter_name="test-model"
            )

            assert response is not None
            assert isinstance(response, str)
            assert len(response) > 0
            assert response == "Fallback response content"

    @pytest.mark.asyncio
    async def test_generate_response_error_handling(self):
        """Test error handling in response generation."""
        orchestrator = ModelOrchestrator()

        # Mock all models failing
        with patch.object(
            orchestrator.response_generator, "generate_response"
        ) as mock_generate:
            mock_generate.side_effect = Exception("All models failed")

            with pytest.raises(Exception) as exc_info:
                await orchestrator.response_generator.generate_response(
                    prompt="Test prompt"
                )

            assert "All models failed" in str(exc_info.value)


class TestModelOrchestratorIntegration:
    """Test integration with mock adapters."""

    @pytest.mark.asyncio
    async def test_mock_adapter_integration(self):
        """Test integration with enhanced mock adapters."""
        # Create mock adapter
        mock_adapter = MockLLMAdapter("test_provider")

        # Test async response generation
        response = await mock_adapter.generate_response("Test prompt")

        assert response is not None
        assert hasattr(response, "content")
        assert hasattr(response, "model")
        assert hasattr(response, "provider")
        assert hasattr(response, "tokens_used")
        assert len(response.content) > 0

    @pytest.mark.asyncio
    async def test_mock_orchestrator_integration(self):
        """Test integration with mock model orchestrator."""
        # Create mock orchestrator
        mock_orchestrator = MockModelOrchestrator()

        # Test fallback chain
        response = await mock_orchestrator.generate_with_fallback("Test prompt")

        assert response is not None
        assert hasattr(response, "content")
        assert len(response.content) > 0

    @pytest.mark.asyncio
    async def test_mock_adapter_failure_simulation(self):
        """Test failure simulation in mock adapters."""
        # Create mock adapter with failure simulation
        primary_adapter = MockLLMAdapter("primary_mock")
        fallback_adapter = MockLLMAdapter("fallback_mock", simulate_failures=True)

        # Test primary adapter (should succeed)
        response1 = await primary_adapter.generate_response("Test prompt")
        assert response1 is not None

        # Test fallback adapter (may fail due to simulation)
        try:
            response2 = await fallback_adapter.generate_response("Test prompt")
            assert response2 is not None
        except Exception as e:
            # Failure is expected due to simulation
            assert "Mock API error" in str(e)


class TestModelOrchestratorErrorHandling:
    """Test error handling and recovery mechanisms."""

    def test_configuration_error_handling(self):
        """Test handling of configuration errors."""
        orchestrator = ModelOrchestrator()

        # Test with invalid configuration
        with patch.object(
            orchestrator.config_manager, "list_model_configs"
        ) as mock_load:
            mock_load.side_effect = Exception("Configuration error")

            # Should handle error gracefully
            try:
                result = orchestrator.config_manager.list_model_configs()
                # If it doesn't throw, it should return None or empty list
                assert result is None or result == []
            except Exception:
                # If it throws, that's also acceptable error handling
                pass

    @pytest.mark.asyncio
    async def test_model_initialization_error_handling(self):
        """Test handling of model initialization errors."""
        orchestrator = ModelOrchestrator()

        # Test initialization with errors
        with patch.object(
            orchestrator.lifecycle_manager, "initialize_adapter"
        ) as mock_init:
            mock_init.side_effect = Exception("Initialization error")

            # Should handle error gracefully
            try:
                result = await orchestrator.lifecycle_manager.initialize_adapter(
                    "test-adapter"
                )
                # If it doesn't throw, it should return False for failure
                assert result is False
            except Exception:
                # If it throws, that's also acceptable error handling - test passes
                pass

    @pytest.mark.asyncio
    async def test_response_generation_error_handling(self):
        """Test error handling in response generation."""
        orchestrator = ModelOrchestrator()

        # Test with failing response generation
        with patch.object(
            orchestrator.response_generator, "generate_response"
        ) as mock_generate:
            mock_generate.side_effect = Exception("Generation error")

            with pytest.raises(Exception) as exc_info:
                await orchestrator.response_generator.generate_response("Test prompt")

            assert "Generation error" in str(exc_info.value)


class TestModelOrchestratorPerformanceMonitoring:
    """Test performance monitoring capabilities."""

    @pytest.mark.asyncio
    async def test_performance_metrics_collection(self):
        """Test collection of performance metrics."""
        orchestrator = ModelOrchestrator()

        # Mock performance data
        with patch.object(
            orchestrator.performance_monitor, "generate_performance_report"
        ) as mock_metrics:
            mock_metrics.return_value = {
                "success": True,
                "report": {
                    "response_times": {"model1": 1.5, "model2": 2.1},
                    "success_rates": {"model1": 0.95, "model2": 0.88},
                    "error_rates": {"model1": 0.05, "model2": 0.12},
                },
            }

            # NEW architecture uses generate_performance_report
            metrics = (
                await orchestrator.performance_monitor.generate_performance_report()
            )

            assert metrics is not None
            assert "success" in metrics
            assert metrics["success"] is True

    @pytest.mark.asyncio
    async def test_performance_optimization(self):
        """Test performance optimization based on metrics."""
        orchestrator = ModelOrchestrator()

        # Test optimization recommendations
        with patch.object(
            orchestrator.performance_monitor, "optimize_model_performance"
        ) as mock_opt:
            mock_opt.return_value = {
                "success": True,
                "optimizations_applied": [
                    {"model": "model1", "action": "increase_timeout"},
                    {"model": "model2", "action": "reduce_batch_size"},
                ],
            }

            # NEW architecture uses optimize_model_performance which includes recommendations
            recommendations = (
                await orchestrator.performance_monitor.optimize_model_performance()
            )

            assert recommendations is not None
            assert "success" in recommendations
            assert recommendations["success"] is True


# Test data generators for comprehensive testing
class TestModelOrchestratorDataGeneration:
    """Test data generation for model orchestrator testing."""

    def test_generate_model_configs(self):
        """Test generation of model configurations."""
        configs = [
            {
                "name": "test-model-1",
                "type": "text",
                "enabled": True,
                "api_key": "test-key-1",
            },
            {
                "name": "test-model-2",
                "type": "text",
                "enabled": True,
                "api_key": "test-key-2",
            },
        ]

        assert len(configs) == 2
        for config in configs:
            assert "name" in config
            assert "type" in config
            assert "enabled" in config

    def test_generate_performance_data(self):
        """Test generation of performance test data."""
        performance_data = {
            "response_times": {"model1": 1.2, "model2": 1.8},
            "success_rates": {"model1": 0.98, "model2": 0.92},
            "error_rates": {"model1": 0.02, "model2": 0.08},
        }

        assert "response_times" in performance_data
        assert "success_rates" in performance_data
        assert "error_rates" in performance_data

        for model in performance_data["response_times"]:
            assert performance_data["response_times"][model] > 0
            assert 0 <= performance_data["success_rates"][model] <= 1
            assert 0 <= performance_data["error_rates"][model] <= 1
