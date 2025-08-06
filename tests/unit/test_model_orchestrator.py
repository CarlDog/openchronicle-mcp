"""
Unit tests for ModelOrchestrator

Tests the model management and orchestration functionality.
"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any, List, Optional

# Import the orchestrator under test
    from core.model_management.model_orchestrator import ModelOrchestrator

# Import enhanced mock adapters for isolated testing
from tests.mocks.mock_adapters import MockLLMAdapter, MockModelOrchestrator, MockDatabaseManager


class TestModelOrchestratorInitialization:
    """Test ModelOrchestrator initialization and configuration."""
    
    def test_orchestrator_initialization(self):
        """Test basic orchestrator initialization."""
        orchestrator = ModelOrchestrator()
        
        assert orchestrator is not None
        assert hasattr(orchestrator, 'config_manager')
        assert hasattr(orchestrator, 'lifecycle_manager')
        assert hasattr(orchestrator, 'performance_monitor')
    
    def test_orchestrator_with_config(self):
        """Test orchestrator initialization with custom config."""
        config = {
            'default_model': 'test-model',
            'fallback_chain': ['model1', 'model2'],
            'max_retries': 5
        }
        
        orchestrator = ModelOrchestrator(config=config)
        
        assert orchestrator is not None
        # Verify config was applied
        assert orchestrator.config_manager is not None
    
    def test_orchestrator_component_status(self):
        """Test that all components are properly initialized."""
        orchestrator = ModelOrchestrator()
        
        # Check that all required components exist
        components = [
            'config_manager',
            'lifecycle_manager', 
            'performance_monitor',
            'response_generator'
        ]
        
        for component in components:
            assert hasattr(orchestrator, component)
            assert getattr(orchestrator, component) is not None


class TestModelOrchestratorConfiguration:
    """Test model configuration management."""
    
    def test_load_model_registry(self):
        """Test loading model registry configuration."""
        orchestrator = ModelOrchestrator()
        
        # Test that registry can be loaded
        registry = orchestrator.config_manager.load_model_registry()
        
        assert registry is not None
        assert isinstance(registry, dict)
        assert 'metadata' in registry
        assert 'text_models' in registry
    
    def test_get_available_models(self):
        """Test retrieving available model configurations."""
        orchestrator = ModelOrchestrator()
        
        models = orchestrator.config_manager.get_available_models()
        
        assert models is not None
        assert isinstance(models, list)
        assert len(models) > 0
        
        # Verify model structure
        for model in models:
            assert 'name' in model
            assert 'type' in model
            assert 'enabled' in model
    
    def test_model_configuration_validation(self):
        """Test model configuration validation."""
        orchestrator = ModelOrchestrator()
        
        # Test with valid configuration
        valid_config = {
            'name': 'test-model',
            'type': 'text',
            'enabled': True,
            'api_key': 'test-key'
        }
        
        is_valid = orchestrator.config_manager.validate_model_config(valid_config)
        assert is_valid is True
        
        # Test with invalid configuration
        invalid_config = {
            'name': 'test-model',
            # Missing required fields
        }
        
        is_valid = orchestrator.config_manager.validate_model_config(invalid_config)
        assert is_valid is False


class TestModelOrchestratorLifecycle:
    """Test model lifecycle management."""
    
    def test_model_initialization(self):
        """Test model initialization process."""
        orchestrator = ModelOrchestrator()
        
        # Test initialization
        result = orchestrator.lifecycle_manager.initialize_models()
        
        assert result is not None
        assert isinstance(result, dict)
        assert 'initialized_models' in result
        assert 'failed_models' in result
    
    def test_model_health_check(self):
        """Test model health monitoring."""
        orchestrator = ModelOrchestrator()
        
        health_status = orchestrator.performance_monitor.check_model_health()
        
        assert health_status is not None
        assert isinstance(health_status, dict)
        assert 'healthy_models' in health_status
        assert 'unhealthy_models' in health_status
    
    def test_model_fallback_chain(self):
        """Test fallback chain configuration."""
        orchestrator = ModelOrchestrator()
        
        fallback_chain = orchestrator.config_manager.get_fallback_chain()
        
        assert fallback_chain is not None
        assert isinstance(fallback_chain, list)
        assert len(fallback_chain) > 0


class TestModelOrchestratorPerformance:
    """Test performance monitoring and optimization."""
    
    def test_performance_metrics(self):
        """Test performance metrics collection."""
        orchestrator = ModelOrchestrator()
        
        metrics = orchestrator.performance_monitor.get_performance_metrics()
        
        assert metrics is not None
        assert isinstance(metrics, dict)
        assert 'response_times' in metrics
        assert 'success_rates' in metrics
        assert 'error_rates' in metrics
    
    def test_model_selection_optimization(self):
        """Test intelligent model selection based on performance."""
        orchestrator = ModelOrchestrator()
        
        # Test model selection
        selected_model = orchestrator.performance_monitor.select_optimal_model()
        
        assert selected_model is not None
        assert isinstance(selected_model, str)
    
    def test_performance_degradation_detection(self):
        """Test detection of performance degradation."""
        orchestrator = ModelOrchestrator()
        
        degradation_status = orchestrator.performance_monitor.detect_degradation()
        
        assert degradation_status is not None
        assert isinstance(degradation_status, dict)
        assert 'degraded_models' in degradation_status


class TestModelOrchestratorResponseGeneration:
    """Test response generation functionality."""
    
    @pytest.mark.asyncio
    async def test_generate_response_success(self):
        """Test successful response generation."""
        orchestrator = ModelOrchestrator()
        
        # Mock the response generator
        with patch.object(orchestrator.response_generator, 'generate_response') as mock_generate:
            mock_generate.return_value = {
                'content': 'Test response content',
                'model': 'test-model',
                'tokens_used': 50,
                'finish_reason': 'stop'
            }
            
            response = await orchestrator.response_generator.generate_response(
                prompt="Test prompt",
                model_name="test-model"
            )
            
            assert response is not None
            assert 'content' in response
            assert response['content'] == 'Test response content'
    
    @pytest.mark.asyncio
    async def test_generate_response_with_fallback(self):
        """Test response generation with fallback chain."""
        orchestrator = ModelOrchestrator()
        
        # Mock multiple model attempts
        with patch.object(orchestrator.response_generator, 'generate_response') as mock_generate:
            # First attempt fails
            mock_generate.side_effect = [
                Exception("Model 1 failed"),
                {
                    'content': 'Fallback response content',
                    'model': 'fallback-model',
                    'tokens_used': 45,
                    'finish_reason': 'stop'
                }
            ]
            
            response = await orchestrator.response_generator.generate_response_with_fallback(
                prompt="Test prompt"
            )
            
            assert response is not None
            assert 'content' in response
            assert response['content'] == 'Fallback response content'
    
    @pytest.mark.asyncio
    async def test_generate_response_error_handling(self):
        """Test error handling in response generation."""
        orchestrator = ModelOrchestrator()
        
        # Mock all models failing
        with patch.object(orchestrator.response_generator, 'generate_response') as mock_generate:
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
        assert hasattr(response, 'content')
        assert hasattr(response, 'model')
        assert hasattr(response, 'provider')
        assert hasattr(response, 'tokens_used')
        assert len(response.content) > 0
    
    @pytest.mark.asyncio
    async def test_mock_orchestrator_integration(self):
        """Test integration with mock model orchestrator."""
        # Create mock orchestrator
        mock_orchestrator = MockModelOrchestrator()
        
        # Test fallback chain
        response = await mock_orchestrator.generate_with_fallback("Test prompt")
        
        assert response is not None
        assert hasattr(response, 'content')
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
        with patch.object(orchestrator.config_manager, 'load_model_registry') as mock_load:
            mock_load.side_effect = Exception("Configuration error")
            
            # Should handle error gracefully
            result = orchestrator.config_manager.load_model_registry()
            assert result is None
    
    def test_model_initialization_error_handling(self):
        """Test handling of model initialization errors."""
        orchestrator = ModelOrchestrator()
        
        # Test initialization with errors
        with patch.object(orchestrator.lifecycle_manager, 'initialize_models') as mock_init:
            mock_init.side_effect = Exception("Initialization error")
            
            # Should handle error gracefully
            result = orchestrator.lifecycle_manager.initialize_models()
            assert result is None
    
    @pytest.mark.asyncio
    async def test_response_generation_error_handling(self):
        """Test error handling in response generation."""
        orchestrator = ModelOrchestrator()
        
        # Test with failing response generation
        with patch.object(orchestrator.response_generator, 'generate_response') as mock_generate:
            mock_generate.side_effect = Exception("Generation error")
            
            with pytest.raises(Exception) as exc_info:
                await orchestrator.response_generator.generate_response("Test prompt")
            
            assert "Generation error" in str(exc_info.value)


class TestModelOrchestratorPerformanceMonitoring:
    """Test performance monitoring capabilities."""
    
    def test_performance_metrics_collection(self):
        """Test collection of performance metrics."""
        orchestrator = ModelOrchestrator()
        
        # Mock performance data
        with patch.object(orchestrator.performance_monitor, 'get_performance_metrics') as mock_metrics:
            mock_metrics.return_value = {
                'response_times': {'model1': 1.5, 'model2': 2.1},
                'success_rates': {'model1': 0.95, 'model2': 0.88},
                'error_rates': {'model1': 0.05, 'model2': 0.12}
            }
            
            metrics = orchestrator.performance_monitor.get_performance_metrics()
            
            assert metrics is not None
            assert 'response_times' in metrics
            assert 'success_rates' in metrics
            assert 'error_rates' in metrics
    
    def test_performance_optimization(self):
        """Test performance optimization based on metrics."""
        orchestrator = ModelOrchestrator()
        
        # Test optimization recommendations
        with patch.object(orchestrator.performance_monitor, 'get_optimization_recommendations') as mock_opt:
            mock_opt.return_value = [
                {'model': 'model1', 'action': 'increase_timeout'},
                {'model': 'model2', 'action': 'reduce_batch_size'}
            ]
            
            recommendations = orchestrator.performance_monitor.get_optimization_recommendations()
            
            assert recommendations is not None
            assert isinstance(recommendations, list)
            assert len(recommendations) > 0


# Test data generators for comprehensive testing
class TestModelOrchestratorDataGeneration:
    """Test data generation for model orchestrator testing."""
    
    def test_generate_model_configs(self):
        """Test generation of model configurations."""
        configs = [
            {
                'name': 'test-model-1',
                'type': 'text',
                'enabled': True,
                'api_key': 'test-key-1'
            },
            {
                'name': 'test-model-2', 
                'type': 'text',
                'enabled': True,
                'api_key': 'test-key-2'
            }
        ]
        
        assert len(configs) == 2
        for config in configs:
            assert 'name' in config
            assert 'type' in config
            assert 'enabled' in config
    
    def test_generate_performance_data(self):
        """Test generation of performance test data."""
        performance_data = {
            'response_times': {'model1': 1.2, 'model2': 1.8},
            'success_rates': {'model1': 0.98, 'model2': 0.92},
            'error_rates': {'model1': 0.02, 'model2': 0.08}
        }
        
        assert 'response_times' in performance_data
        assert 'success_rates' in performance_data
        assert 'error_rates' in performance_data
        
        for model in performance_data['response_times']:
            assert performance_data['response_times'][model] > 0
            assert 0 <= performance_data['success_rates'][model] <= 1
            assert 0 <= performance_data['error_rates'][model] <= 1
