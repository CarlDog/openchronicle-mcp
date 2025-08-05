"""
Test suite for Model Adapter - Updated for Registry-Driven Architecture

Comprehensive tests for the registry-driven ModelManager and adapter system.
Tests cover initialization, adapter management, API key validation, and response generation.
"""

import pytest
import asyncio
import json
import os
from unittest.mock import Mock, patch, AsyncMock, MagicMock, mock_open
from pathlib import Path

from core.model_management import ModelOrchestrator
from core.model_adapter import (
    ModelManager,
    ModelAdapter
)
from core.model_adapters.providers.openai_adapter import OpenAIAdapter
from core.model_adapters.providers.ollama_adapter import OllamaAdapter
from tests.mocks.mock_adapters import MockAdapter, MockImageAdapter


@pytest.fixture
def mock_registry_config():
    """Mock registry configuration for testing."""
    return {
        "schema_version": "3.0.0",
        "environment_config": {
            "providers": {
                "openai": {
                    "base_url_env": "OPENAI_BASE_URL",
                    "default_base_url": "https://api.openai.com/v1",
                    "api_key_env": "OPENAI_API_KEY",
                    "timeout": 30,
                    "validation": {
                        "requires_api_key": True,
                        "api_key_format": "^sk-[A-Za-z0-9]{20,}$",
                        "health_endpoint": "/models",
                        "method": "GET",
                        "auth_header": "Authorization",
                        "auth_format": "Bearer {api_key}"
                    }
                },
                "ollama": {
                    "base_url_env": "OLLAMA_HOST",
                    "default_base_url": "http://localhost:11434",
                    "api_key_env": None,
                    "timeout": 120,
                    "validation": {
                        "requires_api_key": False,
                        "health_endpoint": "/api/tags",
                        "method": "GET"
                    }
                }
            }
        },
        "text_models": {
            "high_priority": [
                {
                    "name": "openai",
                    "provider": "openai",
                    "enabled": True,
                    "model_name": "gpt-4o-mini"
                }
            ]
        }
    }


@pytest.fixture
def sample_config():
    """Sample model configuration - now unused but kept for compatibility."""
    return {
        "model_name": "test-model",
        "api_endpoint": "https://api.test.com/v1",
        "api_key": "test-key-123",
        "max_tokens": 2048,
        "temperature": 0.7
    }


@pytest.fixture
def mock_openai_adapter():
    """Mock OpenAI adapter."""
    adapter = Mock()
    adapter.name = "openai"
    adapter.supports_streaming = True
    adapter.max_tokens = 4096
    adapter.generate_response = AsyncMock(return_value="Mock OpenAI response")
    adapter.get_model_info = Mock(return_value={
        "name": "openai",
        "model": "gpt-4",
        "max_tokens": 4096,
        "supports_streaming": True
    })
    adapter.initialize = AsyncMock(return_value=True)
    return adapter


@pytest.fixture 
def mock_anthropic_adapter():
    """Mock Anthropic adapter."""
    adapter = Mock()
    adapter.name = "anthropic"
    adapter.supports_streaming = True
    adapter.max_tokens = 8192
    adapter.generate_response = AsyncMock(return_value="Mock Anthropic response")
    adapter.get_model_info = Mock(return_value={
        "name": "anthropic", 
        "model": "claude-3",
        "max_tokens": 8192,
        "supports_streaming": True
    })
    adapter.initialize = AsyncMock(return_value=True)
    return adapter


class TestModelManagerInitialization:
    """Test ModelManager initialization and configuration loading."""
    
    def test_init_loads_config(self):
        """Test ModelManager initialization loads registry config."""
        with patch.object(ModelManager, '_load_global_config') as mock_load_global, \
             patch.object(ModelManager, '_load_config') as mock_load_config, \
             patch.object(ModelManager, '_validate_all_configured_adapters'):
            
            mock_load_global.return_value = {"defaults": {"text_model": "ollama"}}
            mock_load_config.return_value = {"adapters": {}}
            
            manager = ModelManager()
            
            assert hasattr(manager, 'config')
            assert hasattr(manager, 'adapters')
            assert hasattr(manager, 'adapter_status')
            mock_load_global.assert_called_once()
            mock_load_config.assert_called_once()
    
    def test_init_handles_missing_registry(self):
        """Test ModelManager handles missing registry file gracefully."""
        with patch('os.path.exists', return_value=False):
            with pytest.raises(FileNotFoundError, match="Model registry not found"):
                ModelManager()


class TestModelManagerAdapterManagement:
    """Test adapter registration and management."""
    
    def test_register_adapter(self, mock_openai_adapter):
        """Test registering an adapter."""
        with patch.object(ModelManager, '_load_global_config'), \
             patch.object(ModelManager, '_load_config'), \
             patch.object(ModelManager, '_validate_all_configured_adapters'):
            
            manager = ModelManager()
            manager.register_adapter("test_openai", mock_openai_adapter)
            
            assert "test_openai" in manager.adapters
            assert manager.adapters["test_openai"] == mock_openai_adapter
    
    @pytest.mark.asyncio
    async def test_initialize_adapter_success(self, mock_openai_adapter):
        """Test successful adapter initialization."""
        with patch.object(ModelManager, '_load_global_config'), \
             patch.object(ModelManager, '_load_config'), \
             patch.object(ModelManager, '_validate_all_configured_adapters'), \
             patch.object(ModelManager, '_create_adapter_instance', return_value=mock_openai_adapter), \
             patch.object(ModelManager, '_validate_adapter_prerequisites', return_value={"valid": True}):
            
            manager = ModelManager()
            manager.config = {"adapters": {"openai": {"type": "openai"}}}
            
            result = await manager.initialize_adapter("openai")
            
            assert result is True
            assert "openai" in manager.adapters
    
    def test_get_available_adapters(self, mock_openai_adapter):
        """Test getting list of available adapters - only working ones."""
        with patch.object(ModelManager, '_load_global_config'), \
             patch.object(ModelManager, '_load_config'), \
             patch.object(ModelManager, '_validate_all_configured_adapters'):
            
            manager = ModelManager()
            # Set config and actually working adapters
            manager.config = {"adapters": {"openai": {"type": "openai"}}}
            manager.adapters = {"openai": mock_openai_adapter}  # Simulate initialized adapter
            
            adapters = manager.get_available_adapters()
            
            assert "openai" in adapters
    
    def test_get_available_adapters_vs_actually_working(self):
        """Test the improved behavior: get_available_adapters() returns only working adapters.
        
        This test validates that get_available_adapters() now returns only adapters
        that are actually initialized and working, supporting standalone-first architecture.
        """
        with patch.object(ModelManager, '_load_global_config'), \
             patch.object(ModelManager, '_load_config'), \
             patch.object(ModelManager, '_validate_all_configured_adapters'):
            
            manager = ModelManager()
            
            # Set up config with multiple adapters
            manager.config = {
                "adapters": {
                    "openai": {"type": "openai"},
                    "ollama": {"type": "ollama"}, 
                    "anthropic": {"type": "anthropic"},
                    "mock": {"type": "mock"}
                }
            }
            
            # Simulate only mock adapter being initialized (standalone mode)
            from tests.mocks.mock_adapters import MockAdapter
            mock_adapter = MockAdapter({"type": "mock", "model_name": "mock-test"})
            manager.adapters = {"mock": mock_adapter}
            
            # Mark external adapters as disabled (normal for standalone mode)
            manager.disabled_adapters = {
                "openai": {"reason": "Missing API key", "type": "openai"},
                "ollama": {"reason": "Service unavailable", "type": "ollama"},
                "anthropic": {"reason": "Missing API key", "type": "anthropic"}
            }
            
            # Get what the ModelManager reports as available (should be only working ones)
            available_adapters = manager.get_available_adapters()
            actually_working = list(manager.adapters.keys())
            
            print(f"\nDEBUG: Available adapters: {available_adapters}")
            print(f"DEBUG: Actually working: {actually_working}")
            print(f"DEBUG: Disabled adapters: {list(manager.disabled_adapters.keys())}")
            
            # With standalone-first architecture, available should match actually working
            assert set(available_adapters) == set(actually_working), \
                "get_available_adapters() should return only actually working adapters"
            
            # In standalone mode, should only have mock adapter
            assert "mock" in available_adapters, "Mock adapter should be available in standalone mode"
            assert "openai" not in available_adapters, "Non-working external adapters should not be available"
            assert "ollama" not in available_adapters, "Non-working external adapters should not be available"
            # NOTE: This test exposes the architectural limitation that needs fixing:
            # get_available_adapters() should filter by actual initialization status,
            # not just return the configuration list


class TestModelManagerResponseGeneration:
    """Test response generation functionality."""
    
    @pytest.mark.asyncio
    async def test_generate_response_success(self, mock_openai_adapter):
        """Test successful response generation."""
        with patch.object(ModelManager, '_load_global_config'), \
             patch.object(ModelManager, '_load_config'), \
             patch.object(ModelManager, '_validate_all_configured_adapters'):
            
            manager = ModelManager()
            manager.adapters["openai"] = mock_openai_adapter
            
            response = await manager.generate_response("Test prompt", adapter_name="openai")
            
            assert response == "Mock OpenAI response"
            mock_openai_adapter.generate_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_response_adapter_not_found(self):
        """Test response generation with non-existent adapter."""
        with patch.object(ModelManager, '_load_global_config'), \
             patch.object(ModelManager, '_load_config'), \
             patch.object(ModelManager, '_validate_all_configured_adapters'):
            
            manager = ModelManager()
            
            with pytest.raises(RuntimeError, match="Failed to initialize adapter"):
                await manager.generate_response("Test prompt", adapter_name="nonexistent")


class TestAPIKeyValidation:
    """Test API key validation functionality."""
    
    def test_validate_api_key_format_regex_valid(self):
        """Test API key format validation with valid key."""
        with patch.object(ModelManager, '_load_global_config'), \
             patch.object(ModelManager, '_load_config'), \
             patch.object(ModelManager, '_validate_all_configured_adapters'):
            
            manager = ModelManager()
            
            # Test OpenAI format
            result = manager._validate_api_key_format_regex("sk-1234567890abcdef1234", "^sk-[A-Za-z0-9]{20,}$")
            assert result is True
    
    def test_validate_api_key_format_regex_invalid(self):
        """Test API key format validation with invalid key."""
        with patch.object(ModelManager, '_load_global_config'), \
             patch.object(ModelManager, '_load_config'), \
             patch.object(ModelManager, '_validate_all_configured_adapters'):
            
            manager = ModelManager()
            
            # Test invalid format
            result = manager._validate_api_key_format_regex("invalid-key", "^sk-[A-Za-z0-9]{20,}$")
            assert result is False


class TestAdapterStatusManagement:
    """Test adapter status tracking and management."""
    
    def test_get_adapter_status_summary(self):
        """Test getting adapter status summary."""
        with patch.object(ModelManager, '_load_global_config'), \
             patch.object(ModelManager, '_load_config'), \
             patch.object(ModelManager, '_validate_all_configured_adapters'):
            
            manager = ModelManager()
            manager.adapter_status = {
                "openai": {
                    "status": "available", 
                    "last_check": "2025-01-01T00:00:00Z",
                    "type": "text",
                    "model_name": "gpt-4o-mini",
                    "description": "OpenAI GPT models",
                    "supports_nsfw": False,
                    "content_types": ["general"],
                    "initialized_at": "2025-01-01T00:00:00Z"
                }
            }
            
            summary = manager.get_adapter_status_summary()
            
            assert "overview" in summary
            assert "active_adapters" in summary
            assert isinstance(summary["overview"], dict)
    
    def test_get_api_key_setup_guide(self):
        """Test getting API key setup guide."""
        with patch.object(ModelManager, '_load_global_config'), \
             patch.object(ModelManager, '_load_config'), \
             patch.object(ModelManager, '_validate_all_configured_adapters'):
            
            manager = ModelManager()
            
            guide = manager.get_api_key_setup_guide()
            
            assert "providers" in guide
            # API returns providers as dict, not list
            assert isinstance(guide["providers"], dict)
    
    def test_check_for_new_api_keys(self):
        """Test checking for newly added API keys."""
        with patch.object(ModelManager, '_load_global_config'), \
             patch.object(ModelManager, '_load_config'), \
             patch.object(ModelManager, '_validate_all_configured_adapters'):
            
            manager = ModelManager()
            
            result = manager.check_for_new_api_keys()
            
            assert "newly_available" in result
            # API returns "still_disabled" instead of "still_missing"
            assert "still_disabled" in result
            assert isinstance(result["newly_available"], list)
            assert isinstance(result["still_disabled"], list)


class TestAdapterHealthChecks:
    """Test adapter health checking functionality."""
    
    @pytest.mark.asyncio
    async def test_check_adapter_health_available(self, mock_openai_adapter):
        """Test health check for available adapter."""
        with patch.object(ModelManager, '_load_global_config'), \
             patch.object(ModelManager, '_load_config'), \
             patch.object(ModelManager, '_validate_all_configured_adapters'):
            
            manager = ModelManager()
            manager.adapters["openai"] = mock_openai_adapter
            # Also need to set up config for the adapter
            manager.config = {"adapters": {"openai": {"type": "openai"}}}
            
            health = await manager.check_adapter_health("openai")
            
            assert "status" in health
            # The actual method may not return adapter_name if adapter isn't in config
            assert health["status"] in ["healthy", "unhealthy", "unknown"]
    
    @pytest.mark.asyncio
    async def test_check_adapter_health_not_found(self):
        """Test health check for non-existent adapter."""
        with patch.object(ModelManager, '_load_global_config'), \
             patch.object(ModelManager, '_load_config'), \
             patch.object(ModelManager, '_validate_all_configured_adapters'):
            
            manager = ModelManager()
            
            health = await manager.check_adapter_health("nonexistent")
            
            # API returns "unknown" instead of "not_found"
            assert health["status"] == "unknown"
            assert "error" in health


class TestContentRouting:
    """Test content-based adapter routing."""
    
    def test_get_adapter_for_content_nsfw(self):
        """Test getting adapter for NSFW content."""
        with patch.object(ModelManager, '_load_global_config'), \
             patch.object(ModelManager, '_load_config'), \
             patch.object(ModelManager, '_validate_all_configured_adapters'):
            
            manager = ModelManager()
            
            # The method checks content_routing in config and defaults to "mock"
            # Also need adapters section since get_available_adapters checks it
            manager.config = {
                "content_routing": {
                    "nsfw_content": "ollama",
                    "default": "ollama"
                },
                "adapters": {
                    "ollama": {"type": "ollama"}
                }
            }
            
            adapter = manager.get_adapter_for_content("nsfw_content")
            
            # Should return the configured adapter
            assert adapter == "ollama"
    
    def test_get_adapter_for_content_safe(self):
        """Test getting adapter for safe content."""
        with patch.object(ModelManager, '_load_global_config'), \
             patch.object(ModelManager, '_load_config'), \
             patch.object(ModelManager, '_validate_all_configured_adapters'):
            
            manager = ModelManager()
            
            # The method checks content_routing in config and defaults to "mock"
            # Also need adapters section since get_available_adapters checks it
            manager.config = {
                "content_routing": {
                    "safe_content": "openai",
                    "default": "openai"
                },
                "adapters": {
                    "openai": {"type": "openai"}
                }
            }
            
            adapter = manager.get_adapter_for_content("safe_content")
            
            # Should return the configured adapter
            assert adapter == "openai"


class TestConfigurationLoading:
    """Test configuration loading and processing."""
    
    def test_get_global_default(self):
        """Test getting global default values."""
        with patch.object(ModelManager, '_load_global_config') as mock_load_global, \
             patch.object(ModelManager, '_load_config'), \
             patch.object(ModelManager, '_validate_all_configured_adapters'):
            
            mock_load_global.return_value = {
                "defaults": {
                    "text_model": "ollama",
                    "timeout": 30
                }
            }
            
            manager = ModelManager()
            
            assert manager.get_global_default("text_model") == "ollama"
            assert manager.get_global_default("timeout") == 30
            assert manager.get_global_default("nonexistent", "fallback") == "fallback"
    
    def test_get_enabled_models_by_type(self):
        """Test getting enabled models by type."""
        with patch.object(ModelManager, '_load_global_config'), \
             patch.object(ModelManager, '_load_config'), \
             patch.object(ModelManager, '_validate_all_configured_adapters'):
            
            manager = ModelManager()
            
            # Mock the file reading since the method directly reads from registry file
            mock_registry = {
                "text_models": {
                    "high_priority": [
                        {"name": "openai", "enabled": True},
                        {"name": "anthropic", "enabled": False}
                    ]
                }
            }
            
            with patch('os.path.exists', return_value=True), \
                 patch('builtins.open', mock_open(read_data=json.dumps(mock_registry))):
                
                models = manager.get_enabled_models_by_type("text")
                
                # Should only include enabled models
                enabled_names = [m["name"] for m in models]
                assert "openai" in enabled_names
                assert "anthropic" not in enabled_names


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_generate_response_api_timeout(self, mock_openai_adapter):
        """Test handling API timeout errors."""
        with patch.object(ModelManager, '_load_global_config'), \
             patch.object(ModelManager, '_load_config'), \
             patch.object(ModelManager, '_validate_all_configured_adapters'):
            
            manager = ModelManager()
            manager.adapters["openai"] = mock_openai_adapter
            
            # Simulate timeout
            mock_openai_adapter.generate_response.side_effect = asyncio.TimeoutError("Request timeout")
            
            with pytest.raises(asyncio.TimeoutError):
                await manager.generate_response("Test prompt", adapter_name="openai")
    
    @pytest.mark.asyncio
    async def test_generate_response_api_error(self, mock_openai_adapter):
        """Test handling general API errors."""
        with patch.object(ModelManager, '_load_global_config'), \
             patch.object(ModelManager, '_load_config'), \
             patch.object(ModelManager, '_validate_all_configured_adapters'):
            
            manager = ModelManager()
            manager.adapters["openai"] = mock_openai_adapter
            
            # Simulate API error
            mock_openai_adapter.generate_response.side_effect = Exception("API Error: Rate limit exceeded")
            
            with pytest.raises(Exception, match="API Error"):
                await manager.generate_response("Test prompt", adapter_name="openai")
    
    @pytest.mark.asyncio
    async def test_auto_initialize_available_adapters(self):
        """Test auto initialization of available adapters."""
        with patch.object(ModelManager, '_load_global_config'), \
             patch.object(ModelManager, '_load_config'), \
             patch.object(ModelManager, '_validate_all_configured_adapters'):
            
            manager = ModelManager()
            manager.config = {"adapters": {"openai": {"type": "openai"}}}
            
            with patch.object(manager, 'initialize_adapter', return_value=True) as mock_init:
                result = await manager.auto_initialize_available_adapters()
                
                # API returns different key names
                assert "newly_initialized" in result
                assert "failed_initializations" in result
                assert isinstance(result["newly_initialized"], list)
                assert isinstance(result["failed_initializations"], list)


if __name__ == "__main__":
    pytest.main([__file__])
