#!/usr/bin/env python3
"""
Test suite for Phase 3.0 Day 4: ConfigurationManager Component

Tests extracted configuration management functionality with comprehensive coverage
of config loading, validation, and dynamic management capabilities.

File: tests/test_configuration_manager.py
"""

import pytest
import json
import tempfile
import shutil
from unittest.mock import Mock, patch, mock_open
from datetime import datetime, timezone
from pathlib import Path

# Mock utilities before importing component
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock logging system
mock_log_info = Mock()
mock_log_error = Mock()  
mock_log_warning = Mock()
mock_log_system_event = Mock()

sys.modules['utilities.logging_system'] = Mock()
sys.modules['utilities.logging_system'].log_info = mock_log_info
sys.modules['utilities.logging_system'].log_error = mock_log_error
sys.modules['utilities.logging_system'].log_warning = mock_log_warning
sys.modules['utilities.logging_system'].log_system_event = mock_log_system_event

# Now import the component
from core.model_management.configuration_manager import ConfigurationManager


class TestConfigurationManager:
    """Test suite for ConfigurationManager component."""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary configuration directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def mock_registry_data(self):
        """Create mock registry data."""
        return {
            "metadata": {
                "name": "Test Registry",
                "description": "Test configuration"
            },
            "defaults": {
                "text_model": "gpt4",
                "image_model": "dalle3",
                "timeout": 30.0
            },
            "global_settings": {
                "enable_logging": True,
                "enable_fallbacks": True,
                "intelligent_routing": {"enabled": True}
            },
            "environment_config": {
                "providers": {
                    "openai": {
                        "base_url_env": "OPENAI_BASE_URL",
                        "default_base_url": "https://api.openai.com/v1",
                        "timeout": 30.0,
                        "validation": {
                            "requires_api_key": True,
                            "api_key_env": "OPENAI_API_KEY"
                        }
                    },
                    "ollama": {
                        "base_url_env": "OLLAMA_BASE_URL",
                        "default_base_url": "http://localhost:11434",
                        "timeout": 60.0
                    }
                }
            },
            "text_models": {
                "high_priority": [
                    {
                        "name": "gpt4",
                        "type": "openai",
                        "enabled": True,
                        "model_name": "gpt-4",
                        "provider": "openai"
                    }
                ],
                "testing": [
                    {
                        "name": "ollama",
                        "type": "ollama",
                        "enabled": True,
                        "model_name": "llama3",
                        "provider": "ollama"
                    }
                ]
            },
            "image_models": {
                "primary": [
                    {
                        "name": "dalle3",
                        "type": "openai",
                        "enabled": True,
                        "model_name": "dall-e-3",
                        "provider": "openai"
                    }
                ]
            },
            "content_routing": {
                "safe_content": {
                    "allowed_models": ["gpt4", "ollama"],
                    "default_model": "gpt4"
                }
            },
            "performance_tuning": {
                "max_concurrent_requests": 10,
                "timeout": 30.0
            },
            "fallback_chains": {
                "gpt4": ["gpt4", "ollama"],
                "ollama": ["ollama"]
            }
        }
    
    @pytest.fixture
    def configuration_manager(self, temp_config_dir, mock_registry_data):
        """Create ConfigurationManager instance with mocked file system."""
        registry_file = Path(temp_config_dir) / "model_registry.json"
        
        # Write mock registry data to file
        with open(registry_file, "w") as f:
            json.dump(mock_registry_data, f, indent=2)
        
        return ConfigurationManager(temp_config_dir)
    
    def test_initialization(self, configuration_manager):
        """Test ConfigurationManager initialization."""
        assert configuration_manager is not None
        assert configuration_manager.config_path is not None
        assert configuration_manager.global_config is not None
        assert configuration_manager.registry is not None
        assert configuration_manager.config is not None
        
        # Verify initialization logging
        mock_log_system_event.assert_called()
        calls = [call.args for call in mock_log_system_event.call_args_list]
        assert any("configuration_manager_initialized" in call for call in calls)
    
    def test_initialization_without_registry(self, temp_config_dir):
        """Test initialization when registry file doesn't exist."""
        # Remove the registry file
        registry_file = Path(temp_config_dir) / "model_registry.json"
        if registry_file.exists():
            registry_file.unlink()
        
        with pytest.raises(FileNotFoundError):
            ConfigurationManager(temp_config_dir)
    
    def test_load_global_config(self, configuration_manager):
        """Test global configuration loading."""
        global_config = configuration_manager.global_config
        
        assert "discovery" in global_config
        assert "defaults" in global_config
        assert "intelligent_routing" in global_config
        assert "content_routing" in global_config
        assert "performance_tuning" in global_config
        assert "fallback_chains" in global_config
        
        # Check defaults
        defaults = global_config["defaults"]
        assert defaults["text_model"] == "gpt4"
        assert defaults["image_model"] == "dalle3"
        assert defaults["timeout"] == 30.0
    
    def test_load_full_registry(self, configuration_manager):
        """Test full registry loading."""
        registry = configuration_manager.registry
        
        assert "metadata" in registry
        assert "text_models" in registry
        assert "image_models" in registry
        assert "content_routing" in registry
        assert registry["metadata"]["name"] == "Test Registry"
    
    def test_load_config(self, configuration_manager):
        """Test model configuration loading."""
        config = configuration_manager.config
        
        assert "adapters" in config
        adapters = config["adapters"]
        
        # Should have loaded gpt4, ollama, and dalle3
        assert "gpt4" in adapters
        assert "ollama" in adapters
        assert "dalle3" in adapters
        
        # Check adapter properties
        gpt4_config = adapters["gpt4"]
        assert gpt4_config["type"] == "openai"
        assert gpt4_config["enabled"] is True
        assert gpt4_config["provider"] == "openai"
    
    def test_get_global_default(self, configuration_manager):
        """Test getting global default values."""
        assert configuration_manager.get_global_default("text_model") == "gpt4"
        assert configuration_manager.get_global_default("image_model") == "dalle3"
        assert configuration_manager.get_global_default("timeout") == 30.0
        assert configuration_manager.get_global_default("nonexistent", "fallback") == "fallback"
    
    def test_get_intelligent_routing_config(self, configuration_manager):
        """Test intelligent routing configuration retrieval."""
        routing_config = configuration_manager.get_intelligent_routing_config()
        
        assert "enabled" in routing_config
        assert routing_config["enabled"] is True
    
    def test_get_content_routing_config(self, configuration_manager):
        """Test content routing configuration retrieval."""
        content_config = configuration_manager.get_content_routing_config()
        
        assert "safe_content" in content_config
        assert content_config["safe_content"]["default_model"] == "gpt4"
    
    def test_get_performance_config(self, configuration_manager):
        """Test performance configuration retrieval."""
        perf_config = configuration_manager.get_performance_config()
        
        assert "max_concurrent_requests" in perf_config
        assert perf_config["max_concurrent_requests"] == 10
        assert perf_config["timeout"] == 30.0
    
    def test_get_enabled_models_by_type_text(self, configuration_manager):
        """Test getting enabled text models."""
        text_models = configuration_manager.get_enabled_models_by_type("text")
        
        assert len(text_models) == 2  # gpt4 and ollama
        model_names = [model["name"] for model in text_models]
        assert "gpt4" in model_names
        assert "ollama" in model_names
    
    def test_get_enabled_models_by_type_image(self, configuration_manager):
        """Test getting enabled image models."""
        image_models = configuration_manager.get_enabled_models_by_type("image")
        
        assert len(image_models) == 1  # dalle3
        assert image_models[0]["name"] == "dalle3"
    
    def test_add_model_config_text(self, configuration_manager):
        """Test adding a new text model configuration."""
        new_config = {
            "type": "anthropic",
            "provider": "anthropic",
            "model_name": "claude-3",
            "api_key_env": "ANTHROPIC_API_KEY"
        }
        
        result = configuration_manager.add_model_config("claude3", new_config, enabled=True)
        
        assert result is True
        
        # Verify the model was added
        models = configuration_manager.get_enabled_models_by_type("text")
        model_names = [model["name"] for model in models]
        assert "claude3" in model_names
    
    def test_add_model_config_image(self, configuration_manager):
        """Test adding a new image model configuration."""
        new_config = {
            "type": "image",
            "provider": "stability",
            "model_name": "stable-diffusion-xl"
        }
        
        result = configuration_manager.add_model_config("stability_xl", new_config, enabled=True)
        
        assert result is True
        
        # Verify the model was added
        models = configuration_manager.get_enabled_models_by_type("image")
        model_names = [model["name"] for model in models]
        assert "stability_xl" in model_names
    
    def test_remove_model_config(self, configuration_manager):
        """Test removing a model configuration."""
        # First verify the model exists
        models_before = configuration_manager.get_enabled_models_by_type("text")
        model_names_before = [model["name"] for model in models_before]
        assert "ollama" in model_names_before
        
        # Remove the model
        result = configuration_manager.remove_model_config("ollama")
        assert result is True
        
        # Verify the model was removed
        models_after = configuration_manager.get_enabled_models_by_type("text")
        model_names_after = [model["name"] for model in models_after]
        assert "ollama" not in model_names_after
    
    def test_enable_disable_model(self, configuration_manager):
        """Test enabling and disabling models."""
        # Disable a model
        result = configuration_manager.disable_model("gpt4")
        assert result is True
        
        # Verify it's disabled (won't appear in enabled models)
        enabled_models = configuration_manager.get_enabled_models_by_type("text")
        model_names = [model["name"] for model in enabled_models]
        assert "gpt4" not in model_names
        
        # Re-enable the model
        result = configuration_manager.enable_model("gpt4")
        assert result is True
        
        # Verify it's enabled again
        enabled_models = configuration_manager.get_enabled_models_by_type("text")
        model_names = [model["name"] for model in enabled_models]
        assert "gpt4" in model_names
    
    def test_list_model_configs(self, configuration_manager):
        """Test listing all model configurations."""
        models_info = configuration_manager.list_model_configs()
        
        assert isinstance(models_info, dict)
        assert "gpt4" in models_info
        assert "ollama" in models_info
        assert "dalle3" in models_info
        
        # Check model info structure
        gpt4_info = models_info["gpt4"]
        assert "type" in gpt4_info
        assert "enabled" in gpt4_info
        assert "category" in gpt4_info
        assert "provider" in gpt4_info
        assert gpt4_info["enabled"] is True
        assert gpt4_info["provider"] == "openai"
    
    def test_validate_model_config_valid(self, configuration_manager):
        """Test model configuration validation with valid config."""
        valid_config = {
            "type": "openai",
            "provider": "openai",
            "model_name": "gpt-4",
            "timeout": 30,
            "max_tokens": 2048
        }
        
        result = configuration_manager.validate_model_config("test_model", valid_config)
        
        assert result["valid"] is True
        assert len(result["errors"]) == 0
    
    def test_validate_model_config_invalid(self, configuration_manager):
        """Test model configuration validation with invalid config."""
        invalid_config = {
            # Missing required 'type' field
            "provider": "openai",
            "timeout": "invalid_number",  # Should be numeric
            "max_tokens": -1  # Should be positive
        }
        
        result = configuration_manager.validate_model_config("test_model", invalid_config)
        
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert "Missing required field: type" in result["errors"]
    
    def test_get_base_url_for_provider(self, configuration_manager):
        """Test getting base URL for providers."""
        openai_url = configuration_manager.get_base_url_for_provider("openai")
        assert openai_url == "https://api.openai.com/v1"
        
        ollama_url = configuration_manager.get_base_url_for_provider("ollama")
        assert ollama_url == "http://localhost:11434"
        
        # Non-existent provider
        invalid_url = configuration_manager.get_base_url_for_provider("nonexistent")
        assert invalid_url is None
    
    def test_get_fallback_chain(self, configuration_manager):
        """Test getting fallback chains for models."""
        gpt4_chain = configuration_manager.get_fallback_chain("gpt4")
        assert gpt4_chain == ["gpt4", "ollama"]
        
        ollama_chain = configuration_manager.get_fallback_chain("ollama")
        assert ollama_chain == ["ollama"]
        
        # Non-existent model should return itself
        unknown_chain = configuration_manager.get_fallback_chain("unknown")
        assert unknown_chain == ["unknown"]
    
    def test_reload_configuration(self, configuration_manager, temp_config_dir, mock_registry_data):
        """Test configuration reloading."""
        # Modify the registry file
        modified_data = mock_registry_data.copy()
        modified_data["defaults"]["text_model"] = "modified_model"
        
        registry_file = Path(temp_config_dir) / "model_registry.json"
        with open(registry_file, "w") as f:
            json.dump(modified_data, f, indent=2)
        
        # Reload configuration
        result = configuration_manager.reload_configuration()
        assert result is True
        
        # Verify the change was loaded
        assert configuration_manager.get_global_default("text_model") == "modified_model"
    
    def test_export_configuration(self, configuration_manager, temp_config_dir):
        """Test configuration export."""
        export_path = configuration_manager.export_configuration()
        
        assert Path(export_path).exists()
        
        # Verify export content
        with open(export_path, "r") as f:
            export_data = json.load(f)
        
        assert "timestamp" in export_data
        assert "global_config" in export_data
        assert "registry" in export_data
        assert "config" in export_data
        
        # Clean up
        Path(export_path).unlink()
    
    def test_get_configuration_summary(self, configuration_manager):
        """Test configuration summary generation."""
        summary = configuration_manager.get_configuration_summary()
        
        assert "total_models" in summary
        assert "enabled_models" in summary
        assert "text_models" in summary
        assert "image_models" in summary
        assert "providers" in summary
        assert "has_fallback_chains" in summary
        assert "content_routing_enabled" in summary
        assert "configuration_files" in summary
        
        # Check values
        assert summary["total_models"] == 3  # gpt4, ollama, dalle3
        assert summary["enabled_models"] == 3
        assert summary["text_models"] == 2
        assert summary["image_models"] == 1
        assert "openai" in summary["providers"]
        assert "ollama" in summary["providers"]
        assert summary["has_fallback_chains"] is True
        assert summary["content_routing_enabled"] is True
    
    def test_fallback_configuration_creation(self, temp_config_dir):
        """Test fallback configuration when files are corrupted."""
        # Create corrupted registry file
        registry_file = Path(temp_config_dir) / "model_registry.json"
        with open(registry_file, "w") as f:
            f.write("invalid json content")
        
        # Should create fallback configuration instead of crashing
        config_manager = ConfigurationManager(temp_config_dir)
        
        assert config_manager is not None
        assert config_manager.get_global_default("text_model") == "mock"
        
        # Should have logged warning about fallback
        mock_log_warning.assert_called()


class TestConfigurationManagerIntegration:
    """Integration tests for ConfigurationManager component."""
    
    @pytest.fixture
    def integration_registry(self):
        """Create realistic registry for integration testing."""
        return {
            "metadata": {"name": "Integration Test Registry"},
            "defaults": {"text_model": "gpt4", "image_model": "dalle3"},
            "global_settings": {
                "enable_logging": True,
                "enable_fallbacks": True,
                "intelligent_routing": {"enabled": True, "threshold": 0.8}
            },
            "environment_config": {
                "providers": {
                    "openai": {
                        "base_url_env": "OPENAI_BASE_URL",
                        "default_base_url": "https://api.openai.com/v1",
                        "validation": {"requires_api_key": True, "api_key_env": "OPENAI_API_KEY"}
                    }
                }
            },
            "text_models": {
                "high_priority": [
                    {"name": "gpt4", "type": "openai", "enabled": True, "provider": "openai"}
                ]
            },
            "content_routing": {
                "safe_content": {"allowed_models": ["gpt4"], "default_model": "gpt4"}
            },
            "fallback_chains": {"gpt4": ["gpt4"]},
            "performance_tuning": {"max_concurrent_requests": 5}
        }
    
    @pytest.fixture
    def integration_config_manager(self, integration_registry):
        """Create ConfigurationManager for integration testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_file = Path(temp_dir) / "model_registry.json"
            with open(registry_file, "w") as f:
                json.dump(integration_registry, f, indent=2)
            
            yield ConfigurationManager(temp_dir)
    
    def test_full_configuration_workflow(self, integration_config_manager):
        """Test complete configuration management workflow."""
        config_manager = integration_config_manager
        
        # 1. Verify initial state
        summary = config_manager.get_configuration_summary()
        assert summary["total_models"] == 1
        assert summary["enabled_models"] == 1
        
        # 2. Add new model
        new_model_config = {
            "type": "anthropic",
            "provider": "anthropic",
            "model_name": "claude-3",
            "timeout": 45
        }
        result = config_manager.add_model_config("claude3", new_model_config)
        assert result is True
        
        # 3. Verify model was added
        summary = config_manager.get_configuration_summary()
        assert summary["total_models"] == 2
        
        # 4. Validate new model config
        validation = config_manager.validate_model_config("claude3", new_model_config)
        assert validation["valid"] is True
        
        # 5. Test configuration listing
        models = config_manager.list_model_configs()
        assert "claude3" in models
        assert models["claude3"]["provider"] == "anthropic"
        
        # 6. Test enable/disable
        config_manager.disable_model("claude3")
        enabled_models = config_manager.get_enabled_models_by_type("text")
        model_names = [model["name"] for model in enabled_models]
        assert "claude3" not in model_names
        
        # 7. Export configuration
        export_path = config_manager.export_configuration()
        assert Path(export_path).exists()
        
        # Cleanup
        Path(export_path).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
