"""
Tests for Model Management Framework - Base Adapter Infrastructure

Tests cover:
- Adapter interfaces and configuration validation
- Base adapter template method pattern
- Adapter registry and factory functionality
- Configuration management and validation
- Real-world adapter creation patterns
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List
from datetime import datetime
import os
import tempfile

# Test imports
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.model_management.adapter_interfaces import (
    AdapterConfig, AdapterResponse, AdapterError,
    AdapterConnectionError, AdapterAuthenticationError,
    ModelAdapterInterface
)
from core.model_management.base_adapter import (
    BaseAdapter, BaseAPIAdapter, BaseLocalAdapter
)
from core.model_management.adapter_registry import (
    AdapterRegistry, AdapterFactory, AdapterInfo,
    AdapterValidator, AdapterLoader
)
from core.model_management.adapter_config import (
    ConfigValidator, ConfigManager, ConfigTemplate
)


class TestAdapterConfig:
    """Test adapter configuration and validation"""
    
    def test_adapter_config_creation(self):
        """Test basic adapter configuration creation"""
        config = AdapterConfig(
            provider_name="test_provider",
            model_name="test_model",
            api_key="test_key",
            max_tokens=500,
            temperature=0.8
        )
        
        assert config.provider_name == "test_provider"
        assert config.model_name == "test_model"
        assert config.api_key == "test_key"
        assert config.max_tokens == 500
        assert config.temperature == 0.8
        assert config.top_p == 0.9  # Default value
    
    def test_adapter_config_validation_success(self):
        """Test successful configuration validation"""
        config = AdapterConfig(
            provider_name="openai",
            model_name="gpt-3.5-turbo",
            max_tokens=1000,
            temperature=0.7
        )
        
        assert config.validate() == True
    
    def test_adapter_config_validation_failures(self):
        """Test configuration validation failures"""
        # Missing provider name
        with pytest.raises(ValueError, match="provider_name is required"):
            config = AdapterConfig(provider_name="", model_name="test")
            config.validate()
        
        # Missing model name
        with pytest.raises(ValueError, match="model_name is required"):
            config = AdapterConfig(provider_name="test", model_name="")
            config.validate()
        
        # Invalid max_tokens
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            config = AdapterConfig(provider_name="test", model_name="test", max_tokens=0)
            config.validate()
        
        # Invalid temperature
        with pytest.raises(ValueError, match="temperature must be between"):
            config = AdapterConfig(provider_name="test", model_name="test", temperature=3.0)
            config.validate()
        
        # Invalid top_p
        with pytest.raises(ValueError, match="top_p must be between"):
            config = AdapterConfig(provider_name="test", model_name="test", top_p=1.5)
            config.validate()
    
    def test_adapter_response_creation(self):
        """Test adapter response creation"""
        response = AdapterResponse(
            content="Test response",
            model_name="test_model",
            provider_name="test_provider",
            tokens_used=50,
            response_time=1.5
        )
        
        assert response.content == "Test response"
        assert response.model_name == "test_model"
        assert response.provider_name == "test_provider"
        assert response.tokens_used == 50
        assert response.response_time == 1.5
        assert isinstance(response.timestamp, datetime)


class MockAdapter(BaseAdapter):
    """Mock adapter for testing base adapter functionality"""
    
    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self.mock_client = Mock()
        self.mock_response = "Mock response content"
        # Ensure fresh metrics for each instance
        self._reset_test_metrics()
    
    def _reset_test_metrics(self):
        """Reset metrics for clean testing"""
        self.metrics = {
            'requests_made': 0,
            'requests_failed': 0,
            'total_tokens': 0,
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_response_time': 0.0,
            'average_response_time': 0.0,
            'last_request_time': None
        }
    
    def get_provider_name(self) -> str:
        return "mock_provider"
    
    def get_supported_models(self) -> List[str]:
        return ["mock_model", "mock_model_1", "mock_model_2"]
    
    async def _create_client(self) -> Any:
        return self.mock_client
    
    async def _generate_response_impl(self, prompt: str, params: Dict[str, Any]) -> Any:
        # Simulate API response with slight delay
        import time
        time.sleep(0.001)  # Small delay to ensure response_time > 0
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = self.mock_response
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 100
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 50
        return mock_response
    
    def _extract_content(self, raw_response: Any) -> str:
        return raw_response.choices[0].message.content


class TestBaseAdapter:
    """Test base adapter template method pattern"""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration"""
        return AdapterConfig(
            provider_name="mock_provider",
            model_name="mock_model",
            max_tokens=1000,
            temperature=0.7
        )
    
    @pytest.fixture
    def mock_adapter(self, mock_config):
        """Create mock adapter instance"""
        return MockAdapter(mock_config)
    
    def test_adapter_initialization(self, mock_adapter):
        """Test adapter initialization"""
        assert mock_adapter.provider_name == "mock_provider"
        assert mock_adapter.model_name == "mock_model"
        assert not mock_adapter.is_initialized
        assert mock_adapter.client is None
    
    @pytest.mark.asyncio
    async def test_adapter_initialize_template_method(self, mock_adapter):
        """Test adapter initialization template method"""
        await mock_adapter.initialize()
        
        assert mock_adapter.is_initialized
        assert mock_adapter.client == mock_adapter.mock_client
    
    @pytest.mark.asyncio
    async def test_adapter_generate_response_template_method(self, mock_adapter):
        """Test response generation template method"""
        await mock_adapter.initialize()
        
        response = await mock_adapter.generate_response("Test prompt")
        
        assert isinstance(response, AdapterResponse)
        assert response.content == "Mock response content"
        assert response.model_name == "mock_model"
        assert response.provider_name == "mock_provider"
        assert response.tokens_used == 100
        assert response.input_tokens == 50
        assert response.output_tokens == 50
        assert response.response_time > 0
    
    @pytest.mark.asyncio
    async def test_adapter_cleanup_template_method(self, mock_adapter):
        """Test adapter cleanup template method"""
        await mock_adapter.initialize()
        assert mock_adapter.is_initialized
        
        await mock_adapter.cleanup()
        assert not mock_adapter.is_initialized
        assert mock_adapter.client is None
    
    @pytest.mark.asyncio
    async def test_adapter_health_check(self, mock_adapter):
        """Test adapter health check"""
        await mock_adapter.initialize()
        
        health = await mock_adapter.health_check()
        assert health == True
    
    def test_adapter_metrics_tracking(self, mock_adapter):
        """Test metrics tracking functionality"""
        initial_stats = mock_adapter.get_usage_stats()
        
        assert initial_stats['requests_made'] == 0
        assert initial_stats['requests_failed'] == 0
        assert initial_stats['total_tokens'] == 0
    
    @pytest.mark.asyncio
    async def test_adapter_error_handling(self, mock_adapter):
        """Test adapter error handling"""
        # Test empty prompt
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            await mock_adapter.generate_response("")
        
        # Test uninitialized adapter auto-initialization
        response = await mock_adapter.generate_response("Test prompt")
        assert mock_adapter.is_initialized
        assert isinstance(response, AdapterResponse)


class MockAPIAdapter(BaseAPIAdapter):
    """Mock API adapter for testing API adapter functionality"""
    
    def get_provider_name(self) -> str:
        return "mock_api"
    
    def get_supported_models(self) -> List[str]:
        return ["api_model_1", "api_model_2"]
    
    def get_api_key_env_var(self) -> str:
        return "MOCK_API_KEY"
    
    async def _create_client(self) -> Any:
        return Mock()
    
    async def _generate_response_impl(self, prompt: str, params: Dict[str, Any]) -> Any:
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "API response"
        return mock_response
    
    def _extract_content(self, raw_response: Any) -> str:
        return raw_response.choices[0].message.content


class TestBaseAPIAdapter:
    """Test API adapter base class"""
    
    def test_api_adapter_with_api_key(self):
        """Test API adapter with provided API key"""
        config = AdapterConfig(
            provider_name="mock_api",
            model_name="test_model",
            api_key="test_key_123"
        )
        
        adapter = MockAPIAdapter(config)
        assert adapter.api_key == "test_key_123"
    
    @patch.dict(os.environ, {'MOCK_API_KEY': 'env_key_456'})
    def test_api_adapter_with_env_api_key(self):
        """Test API adapter loading API key from environment"""
        config = AdapterConfig(
            provider_name="mock_api",
            model_name="test_model"
        )
        
        adapter = MockAPIAdapter(config)
        assert adapter.api_key == "env_key_456"
    
    def test_api_adapter_missing_api_key(self):
        """Test API adapter with missing API key"""
        config = AdapterConfig(
            provider_name="mock_api",
            model_name="test_model"
        )
        
        # Should raise configuration error for missing API key
        with pytest.raises(Exception):  # AdapterConfigurationError
            MockAPIAdapter(config)


class TestAdapterRegistry:
    """Test adapter registry functionality"""
    
    @pytest.fixture
    def registry(self):
        """Create fresh adapter registry"""
        return AdapterRegistry()
    
    def test_register_adapter(self, registry):
        """Test adapter registration"""
        registry.register_adapter(MockAdapter, name="test_adapter")
        
        assert "test_adapter" in registry.list_adapters()
        
        adapter_info = registry.get_adapter_info("test_adapter")
        assert adapter_info is not None
        assert adapter_info.name == "test_adapter"
        assert adapter_info.adapter_class == MockAdapter
    
    def test_unregister_adapter(self, registry):
        """Test adapter unregistration"""
        registry.register_adapter(MockAdapter, name="test_adapter")
        assert "test_adapter" in registry.list_adapters()
        
        success = registry.unregister_adapter("test_adapter")
        assert success == True
        assert "test_adapter" not in registry.list_adapters()
        
        # Try to unregister non-existent adapter
        success = registry.unregister_adapter("non_existent")
        assert success == False
    
    def test_list_adapters_with_capability(self, registry):
        """Test listing adapters by capability"""
        # Register adapter with streaming capability
        registry.register_adapter(MockAdapter, name="streaming_adapter")
        
        # Mock the adapter to have streaming capability
        adapter_info = registry.get_adapter_info("streaming_adapter")
        adapter_info.capabilities['streaming'] = True
        
        streaming_adapters = registry.list_adapters_with_capability('streaming')
        assert "streaming_adapter" in streaming_adapters
    
    def test_find_adapters_for_model(self, registry):
        """Test finding adapters for specific model"""
        registry.register_adapter(MockAdapter, name="test_adapter")
        
        # Should find adapter that supports mock_model_1
        adapters = registry.find_adapters_for_model("mock_model_1")
        assert "test_adapter" in adapters
        
        # Should not find adapter for unsupported model
        adapters = registry.find_adapters_for_model("unsupported_model")
        assert "test_adapter" not in adapters


class TestAdapterFactory:
    """Test adapter factory functionality"""
    
    @pytest.fixture
    def factory_with_registry(self):
        """Create factory with pre-populated registry"""
        registry = AdapterRegistry()
        registry.register_adapter(MockAdapter, name="mock_provider")
        return AdapterFactory(registry)
    
    def test_create_adapter(self, factory_with_registry):
        """Test adapter creation"""
        adapter = factory_with_registry.create_adapter("mock_provider", "mock_model")
        
        assert isinstance(adapter, MockAdapter)
        assert adapter.provider_name == "mock_provider"
        assert adapter.model_name == "mock_model"
    
    @pytest.mark.asyncio
    async def test_create_and_initialize_adapter(self, factory_with_registry):
        """Test adapter creation and initialization"""
        adapter = await factory_with_registry.create_and_initialize_adapter(
            "mock_provider", "mock_model"
        )
        
        assert isinstance(adapter, MockAdapter)
        assert adapter.is_initialized
    
    def test_create_adapter_not_found(self, factory_with_registry):
        """Test creating adapter that doesn't exist"""
        with pytest.raises(Exception):  # AdapterConfigurationError
            factory_with_registry.create_adapter("non_existent", "model")
    
    def test_register_and_get_active_adapter(self, factory_with_registry):
        """Test active adapter management"""
        adapter = factory_with_registry.create_adapter("mock_provider", "mock_model")
        
        # Register as active
        factory_with_registry.register_active_adapter("test_key", adapter)
        
        # Retrieve active adapter
        retrieved_adapter = factory_with_registry.get_active_adapter("test_key")
        assert retrieved_adapter == adapter
        
        # Remove active adapter
        success = factory_with_registry.remove_active_adapter("test_key")
        assert success == True
        
        # Should no longer be found
        retrieved_adapter = factory_with_registry.get_active_adapter("test_key")
        assert retrieved_adapter is None
    
    @pytest.mark.asyncio
    async def test_cleanup_all_adapters(self, factory_with_registry):
        """Test cleanup of all active adapters"""
        # Create and register multiple adapters
        adapter1 = factory_with_registry.create_adapter("mock_provider", "model1")
        adapter2 = factory_with_registry.create_adapter("mock_provider", "model2")
        
        factory_with_registry.register_active_adapter("key1", adapter1)
        factory_with_registry.register_active_adapter("key2", adapter2)
        
        # Cleanup all
        await factory_with_registry.cleanup_all_adapters()
        
        # Should have no active adapters
        assert len(factory_with_registry.active_adapters) == 0
    
    def test_get_adapter_statistics(self, factory_with_registry):
        """Test adapter statistics"""
        stats = factory_with_registry.get_adapter_statistics()
        
        assert 'total_registered' in stats
        assert 'total_active' in stats
        assert 'registered_adapters' in stats
        assert 'active_adapters' in stats
        assert 'capabilities_summary' in stats
        
        assert stats['total_registered'] >= 1  # MockAdapter is registered


class TestConfigManager:
    """Test configuration management"""
    
    @pytest.fixture
    def config_manager(self):
        """Create configuration manager"""
        return ConfigManager()
    
    def test_create_config_with_defaults(self, config_manager):
        """Test creating config with template defaults"""
        config = config_manager.create_config(
            "openai", 
            "gpt-3.5-turbo",
            config_overrides={'api_key': 'test_key_for_defaults'}
        )
        
        assert config.provider_name == "openai"
        assert config.model_name == "gpt-3.5-turbo"
        assert config.max_tokens == 1000  # Default from template
        assert config.api_key == 'test_key_for_defaults'
    
    def test_create_config_with_overrides(self, config_manager):
        """Test creating config with overrides"""
        config = config_manager.create_config(
            "openai",
            "gpt-4",
            config_overrides={
                'max_tokens': 2000,
                'temperature': 0.9,
                'api_key': 'test_key_for_overrides'
            }
        )
        
        assert config.model_name == "gpt-4"
        assert config.max_tokens == 2000
        assert config.temperature == 0.9
        assert config.api_key == 'test_key_for_overrides'
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test_env_key'})
    def test_create_config_from_env(self, config_manager):
        """Test creating config with environment variables"""
        config = config_manager.create_config("openai", "gpt-3.5-turbo")
        
        assert config.api_key == "test_env_key"
    
    def test_config_file_operations(self, config_manager):
        """Test saving and loading config files"""
        config = config_manager.create_config(
            "openai", 
            "gpt-3.5-turbo",
            config_overrides={'api_key': 'test_key_for_file_ops'}
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Save config
            config_manager.save_config_to_file(config, temp_path)
            
            # Load config
            loaded_config = config_manager.load_config_from_file(temp_path)
            
            assert loaded_config.provider_name == config.provider_name
            assert loaded_config.model_name == config.model_name
            assert loaded_config.max_tokens == config.max_tokens
            
        finally:
            os.unlink(temp_path)
    
    def test_create_config_template_file(self, config_manager):
        """Test creating configuration template files"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            config_manager.create_config_template_file("openai", temp_path)
            
            # Verify template was created
            template_data = config_manager.json_util.load_file(temp_path)
            
            assert template_data['provider_name'] == "openai"
            assert template_data['model_name'] == "gpt-3.5-turbo"
            assert '_template_info' in template_data
            
        finally:
            os.unlink(temp_path)
    
    def test_get_config_summary(self, config_manager):
        """Test configuration summary"""
        config = config_manager.create_config(
            "openai", 
            "gpt-3.5-turbo",
            config_overrides={'api_key': 'test_key'}
        )
        
        summary = config_manager.get_config_summary(config)
        
        assert summary['provider'] == "openai"
        assert summary['model'] == "gpt-3.5-turbo"
        assert summary['has_api_key'] == True
        assert 'features' in summary
        assert 'streaming' in summary['features']


class TestIntegrationPatterns:
    """Test real-world integration patterns"""
    
    @pytest.mark.asyncio
    async def test_full_adapter_lifecycle(self):
        """Test complete adapter lifecycle"""
        # Create registry and factory
        registry = AdapterRegistry()
        factory = AdapterFactory(registry)
        
        # Register adapter
        registry.register_adapter(MockAdapter, name="test_provider")
        
        # Create and initialize adapter
        adapter = await factory.create_and_initialize_adapter(
            "test_provider", 
            "mock_model",  # Use supported model name
            max_tokens=500,
            temperature=0.8
        )
        
        # Generate response
        response = await adapter.generate_response("Test prompt for integration")
        
        assert isinstance(response, AdapterResponse)
        assert response.content == "Mock response content"
        assert response.provider_name == "test_provider"
        
        # Check metrics - test that metrics increase from baseline
        stats_before = adapter.get_usage_stats()
        initial_requests = stats_before.get('requests_made', 0)
        
        # Generate another response
        response2 = await adapter.generate_response("Second test prompt")
        
        stats_after = adapter.get_usage_stats()
        final_requests = stats_after.get('requests_made', 0)
        
        # Verify that requests increased by 1
        assert final_requests == initial_requests + 1
        assert isinstance(response2, AdapterResponse)
        
        # Cleanup
        await adapter.cleanup()
        assert not adapter.is_initialized
    
    def test_configuration_validation_workflow(self):
        """Test configuration validation workflow"""
        config_manager = ConfigManager()
        
        # Create valid configuration
        config = config_manager.create_config(
            "openai",
            "gpt-3.5-turbo",
            config_overrides={'api_key': 'valid_key'}
        )
        
        # Should validate successfully
        assert config_manager.validator.validate_config(config) == True
        
        # Test invalid configuration - Create a config with API key first, then modify temperature
        invalid_config = config_manager.create_config(
            "openai",
            "gpt-3.5-turbo",
            config_overrides={'api_key': 'test_key'}
        )
        invalid_config.temperature = 5.0  # Invalid temperature
        
        with pytest.raises(ValueError):
            config_manager.validator.validate_config(invalid_config)
    
    @pytest.mark.asyncio
    async def test_error_handling_patterns(self):
        """Test error handling patterns"""
        # Test adapter initialization error
        class FailingAdapter(MockAdapter):
            async def _create_client(self):
                raise ConnectionError("Cannot connect to provider")
        
        config = AdapterConfig(provider_name="failing", model_name="test")
        adapter = FailingAdapter(config)
        
        with pytest.raises(Exception):  # AdapterConnectionError
            await adapter.initialize()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
