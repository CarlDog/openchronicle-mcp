"""
Test suite for DynamicRegistryManager

This test suite validates the Phase 2.0 dynamic configuration system,
ensuring that content-driven provider discovery works correctly and
maintains backward compatibility.
"""

import unittest
import tempfile
import json
import shutil
from pathlib import Path
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.model_registry.registry_manager import (
    RegistryManager as DynamicRegistryManager, 
    # ConfigurationError, 
    # ProviderNotFoundError
)


class TestDynamicRegistryManager(unittest.TestCase):
    """Test cases for DynamicRegistryManager functionality."""
    
    def setUp(self):
        """Set up test environment with temporary directories."""
        self.test_dir = tempfile.mkdtemp()
        self.models_dir = Path(self.test_dir) / "models"
        self.settings_file = Path(self.test_dir) / "registry_settings.json"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test configurations
        self._create_test_configs()
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def _create_test_configs(self):
        """Create test model configurations."""
        # OpenAI configuration
        openai_config = {
            "provider": "openai",
            "display_name": "Test OpenAI GPT-4",
            "enabled": True,
            "adapter_class": "OpenAIAdapter",
            "api_config": {
                "endpoint": "https://api.openai.com/v1/chat/completions",
                "model": "gpt-4",
                "api_key_env": "OPENAI_API_KEY",
                "timeout": 30
            },
            "capabilities": {
                "text_generation": True,
                "streaming": True
            },
            "fallback_chain": ["anthropic", "ollama"]
        }
        
        # Anthropic configuration  
        anthropic_config = {
            "provider": "anthropic",
            "display_name": "Test Claude 3.5 Sonnet",
            "enabled": True,
            "adapter_class": "AnthropicAdapter",
            "api_config": {
                "endpoint": "https://api.anthropic.com/v1/messages",
                "model": "claude-3-5-sonnet-20241022",
                "api_key_env": "ANTHROPIC_API_KEY",
                "timeout": 30
            },
            "capabilities": {
                "text_generation": True,
                "streaming": True
            },
            "fallback_chain": ["openai"]
        }
        
        # Disabled configuration (for testing filtering)
        disabled_config = {
            "provider": "test_provider",
            "display_name": "Disabled Test Model",
            "enabled": False,
            "adapter_class": "TestAdapter",
            "api_config": {
                "endpoint": "https://api.test.com/v1",
                "model": "test-model",
                "timeout": 30
            },
            "capabilities": {
                "text_generation": True
            }
        }
        
        # Save configurations
        with open(self.models_dir / "test_openai_gpt4.json", 'w') as f:
            json.dump(openai_config, f, indent=2)
        
        with open(self.models_dir / "test_anthropic_claude.json", 'w') as f:
            json.dump(anthropic_config, f, indent=2)
        
        with open(self.models_dir / "disabled_test_model.json", 'w') as f:
            json.dump(disabled_config, f, indent=2)
    
    def test_initialization(self):
        """Test DynamicRegistryManager initialization."""
        registry = DynamicRegistryManager(str(self.models_dir), str(self.settings_file))
        
        # Verify initialization
        self.assertIsInstance(registry, DynamicRegistryManager)
        self.assertEqual(str(registry.models_dir), str(self.models_dir))
        self.assertEqual(str(registry.settings_file), str(self.settings_file))
        
        # Verify global settings were created
        self.assertTrue(self.settings_file.exists())
        self.assertIsInstance(registry.global_settings, dict)
    
    def test_provider_discovery(self):
        """Test content-driven provider discovery."""
        registry = DynamicRegistryManager(str(self.models_dir), str(self.settings_file))
        
        providers = registry.discover_providers()
        
        # Verify providers were discovered
        self.assertIn("openai", providers)
        self.assertIn("anthropic", providers)
        self.assertIn("test_provider", providers)
        
        # Verify model counts
        self.assertEqual(len(providers["openai"]), 1)
        self.assertEqual(len(providers["anthropic"]), 1)
        self.assertEqual(len(providers["test_provider"]), 1)
    
    def test_get_provider_models(self):
        """Test getting models for specific provider."""
        registry = DynamicRegistryManager(str(self.models_dir), str(self.settings_file))
        
        # Test valid provider
        openai_models = registry.get_provider_models("openai")
        self.assertEqual(len(openai_models), 1)
        self.assertEqual(openai_models[0]["display_name"], "Test OpenAI GPT-4")
        
        # Test invalid provider
        with self.assertRaises(ValueError):  # Provider not found
            registry.get_provider_models("nonexistent_provider")
    
    def test_get_model_config(self):
        """Test getting specific model configuration."""
        registry = DynamicRegistryManager(str(self.models_dir), str(self.settings_file))
        
        # Test valid config
        config = registry.get_model_config("test_openai_gpt4")
        self.assertEqual(config["provider"], "openai")
        self.assertEqual(config["display_name"], "Test OpenAI GPT-4")
        
        # Test invalid config
        with self.assertRaises(ValueError):  # Provider not found
            registry.get_model_config("nonexistent_config")
    
    def test_enabled_providers(self):
        """Test filtering of enabled providers."""
        registry = DynamicRegistryManager(str(self.models_dir), str(self.settings_file))
        
        enabled_providers = registry.get_enabled_providers()
        
        # Should include providers with enabled models
        self.assertIn("openai", enabled_providers)
        self.assertIn("anthropic", enabled_providers)
        
        # Should not include providers with only disabled models
        self.assertNotIn("test_provider", enabled_providers)
    
    def test_fallback_chains(self):
        """Test fallback chain generation."""
        registry = DynamicRegistryManager(str(self.models_dir), str(self.settings_file))
        
        # Test OpenAI fallback chain
        openai_chain = registry.get_fallback_chain("openai")
        self.assertEqual(openai_chain[0], "openai")  # Primary provider first
        self.assertIn("anthropic", openai_chain)     # Should include specified fallback
        
        # Test Anthropic fallback chain
        anthropic_chain = registry.get_fallback_chain("anthropic")
        self.assertEqual(anthropic_chain[0], "anthropic")
        self.assertIn("openai", anthropic_chain)
    
    def test_add_model_config(self):
        """Test runtime addition of model configurations."""
        registry = DynamicRegistryManager(str(self.models_dir), str(self.settings_file))
        
        # Add new configuration
        new_config = {
            "provider": "test_runtime",
            "display_name": "Runtime Test Model",
            "enabled": True,
            "adapter_class": "RuntimeTestAdapter",
            "api_config": {
                "endpoint": "https://api.runtime.com/v1",
                "model": "runtime-model",
                "timeout": 30
            },
            "capabilities": {
                "text_generation": True
            }
        }
        
        success = registry.add_model_config("runtime_test", new_config)
        self.assertTrue(success)
        
        # Verify configuration was added
        providers = registry.get_all_providers()
        self.assertIn("test_runtime", providers)
        
        runtime_models = registry.get_provider_models("test_runtime")
        self.assertEqual(len(runtime_models), 1)
        self.assertEqual(runtime_models[0]["display_name"], "Runtime Test Model")
        
        # Verify file was created
        config_file = self.models_dir / "runtime_test.json"
        self.assertTrue(config_file.exists())
    
    def test_remove_model_config(self):
        """Test runtime removal of model configurations."""
        registry = DynamicRegistryManager(str(self.models_dir), str(self.settings_file))
        
        # Verify config exists initially
        self.assertIn("openai", registry.get_all_providers())
        
        # Remove configuration
        success = registry.remove_model_config("test_openai_gpt4")
        self.assertTrue(success)
        
        # Verify configuration was removed from registry
        providers = registry.get_all_providers()
        self.assertNotIn("openai", providers)  # No more OpenAI models
        
        # Verify file was deleted
        config_file = self.models_dir / "test_openai_gpt4.json"
        self.assertFalse(config_file.exists())
    
    def test_registry_summary(self):
        """Test registry summary generation."""
        registry = DynamicRegistryManager(str(self.models_dir), str(self.settings_file))
        
        summary = registry.get_registry_summary()
        
        # Verify summary structure
        self.assertIn("schema_version", summary)
        self.assertIn("total_providers", summary)
        self.assertIn("enabled_providers", summary)
        self.assertIn("total_models", summary)
        self.assertIn("enabled_models", summary)
        self.assertIn("providers", summary)
        
        # Verify counts
        self.assertEqual(summary["total_providers"], 3)  # openai, anthropic, test_provider
        self.assertEqual(summary["enabled_providers"], 2)  # openai, anthropic (test_provider disabled)
        self.assertEqual(summary["total_models"], 3)
        self.assertEqual(summary["enabled_models"], 2)
    
    def test_legacy_compatibility(self):
        """Test legacy registry format generation."""
        registry = DynamicRegistryManager(str(self.models_dir), str(self.settings_file))
        
        legacy_format = registry.get_legacy_registry_format()
        
        # Verify legacy structure
        self.assertIn("adapters", legacy_format)
        self.assertIn("fallback_chains", legacy_format)
        self.assertIn("global_settings", legacy_format)
        
        # Verify adapters section
        adapters = legacy_format["adapters"]
        self.assertIsInstance(adapters, dict)
        
        # Should only include enabled adapters
        enabled_adapter_count = sum(1 for adapter in adapters.values() if adapter.get("enabled", False))
        self.assertEqual(enabled_adapter_count, 2)  # Only enabled models
        
        # Verify fallback chains
        fallback_chains = legacy_format["fallback_chains"]
        self.assertIn("openai", fallback_chains)
        self.assertIn("anthropic", fallback_chains)
    
    def test_validation(self):
        """Test configuration validation."""
        registry = DynamicRegistryManager(str(self.models_dir), str(self.settings_file))
        
        # Test invalid configuration (missing required field)
        invalid_config = {
            "display_name": "Invalid Model",
            "enabled": True,
            "adapter_class": "InvalidAdapter"
            # Missing "provider" field
        }
        
        success = registry.add_model_config("invalid_test", invalid_config)
        self.assertFalse(success)
        
        # Verify invalid config was not added
        providers = registry.get_all_providers()
        # Should not create any new provider for invalid config
        self.assertEqual(len(providers), 3)  # Still original 3 providers
    
    def test_refresh_providers(self):
        """Test provider refresh functionality."""
        registry = DynamicRegistryManager(str(self.models_dir), str(self.settings_file))
        
        initial_count = len(registry.get_all_providers())
        
        # Manually add a configuration file
        new_config = {
            "provider": "manual_test",
            "display_name": "Manually Added Model",
            "enabled": True,
            "adapter_class": "ManualTestAdapter",
            "api_config": {
                "endpoint": "https://api.manual.com/v1",
                "model": "manual-model",
                "timeout": 30
            },
            "capabilities": {
                "text_generation": True
            }
        }
        
        with open(self.models_dir / "manual_test.json", 'w') as f:
            json.dump(new_config, f, indent=2)
        
        # Refresh providers to detect manually added file
        updated_providers = registry.refresh_providers()
        
        # Verify new provider was discovered
        self.assertEqual(len(updated_providers), initial_count + 1)
        self.assertIn("manual_test", updated_providers)


class TestDynamicRegistryIntegration(unittest.TestCase):
    """Integration tests using real configuration files."""
    
    def test_real_config_discovery(self):
        """Test discovery using actual configuration files."""
        # Use real config directory if it exists
        models_dir = "config/models"
        if not Path(models_dir).exists():
            self.skipTest("Real config directory not found")
        
        registry = DynamicRegistryManager(models_dir)
        
        providers = registry.get_all_providers()
        self.assertGreater(len(providers), 0, "Should discover at least one provider")
        
        # Verify each provider has valid models
        for provider in providers:
            models = registry.get_provider_models(provider)
            self.assertGreater(len(models), 0, f"Provider {provider} should have models")
            
            for model in models:
                # Verify required fields
                self.assertIn("provider", model)
                self.assertIn("display_name", model)
                self.assertIn("enabled", model)
                self.assertIn("adapter_class", model)


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
