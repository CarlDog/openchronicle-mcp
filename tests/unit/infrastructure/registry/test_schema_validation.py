"""
Tests for Registry Schema Validation

Comprehensive test suite for the pydantic-based schema validation system
for OpenChronicle model registry configurations.
"""

import json
import tempfile
from pathlib import Path

import pytest
from openchronicle.infrastructure.registry.schema_validation import (
    ContentRoutingConfig,
)
from openchronicle.infrastructure.registry.schema_validation import ContentType
from openchronicle.infrastructure.registry.schema_validation import (
    FallbackBehaviorConfig,
)
from openchronicle.infrastructure.registry.schema_validation import ModelConfig
from openchronicle.infrastructure.registry.schema_validation import (
    ModelRegistrySchema,
)
from openchronicle.infrastructure.registry.schema_validation import (
    PerformanceConfig,
)
from openchronicle.infrastructure.registry.schema_validation import ProviderConfig
from openchronicle.infrastructure.registry.schema_validation import ProviderType
from openchronicle.infrastructure.registry.schema_validation import (
    RegistryValidator,
)
from openchronicle.infrastructure.registry.schema_validation import (
    SchemaValidationError,
)
from openchronicle.infrastructure.registry.schema_validation import (
    validate_provider_config,
)
from openchronicle.infrastructure.registry.schema_validation import (
    validate_registry_config,
)


class TestSchemaValidation:
    """Test pydantic schema validation for registry configurations."""

    def test_valid_model_config(self):
        """Test valid model configuration validation."""
        config_data = {
            "name": "test_model",
            "priority": 1,
            "fallbacks": ["backup_model"],
            "enabled": True,
            "content_types": ["safe"],
            "max_tokens": 4096,
            "temperature": 0.7,
            "metadata": {"description": "Test model"},
        }

        model = ModelConfig(**config_data)
        assert model.name == "test_model"
        assert model.priority == 1
        assert model.enabled is True
        assert ContentType.SAFE in model.content_types

    def test_invalid_model_config_priority(self):
        """Test model config with invalid priority."""
        config_data = {
            "name": "test_model",
            "priority": 0,  # Invalid: must be >= 1
            "enabled": True,
        }

        with pytest.raises(ValueError):
            ModelConfig(**config_data)

    def test_invalid_model_config_name(self):
        """Test model config with invalid name."""
        config_data = {
            "name": "test model!",  # Invalid: contains special characters
            "priority": 1,
            "enabled": True,
        }

        with pytest.raises(ValueError):
            ModelConfig(**config_data)

    def test_duplicate_fallbacks(self):
        """Test model config with duplicate fallbacks."""
        config_data = {
            "name": "test_model",
            "priority": 1,
            "fallbacks": ["model1", "model1"],  # Duplicate
            "enabled": True,
        }

        with pytest.raises(ValueError):
            ModelConfig(**config_data)

    def test_valid_provider_config(self):
        """Test valid provider configuration validation."""
        config_data = {
            "provider": "openai",
            "display_name": "OpenAI GPT",
            "enabled": True,
            "api_config": {"api_key": "test"},
            "model_list": ["gpt-4", "gpt-3.5-turbo"],
            "content_filter": True,
            "rate_limits": {"requests_per_minute": 60},
            "metadata": {"version": "1.0"},
        }

        provider = ProviderConfig(**config_data)
        assert provider.provider == ProviderType.OPENAI
        assert provider.display_name == "OpenAI GPT"
        assert provider.enabled is True
        assert "gpt-4" in provider.model_list

    def test_invalid_provider_type(self):
        """Test provider config with invalid provider type."""
        config_data = {
            "provider": "invalid_provider",
            "display_name": "Invalid Provider",
            "enabled": True,
        }

        with pytest.raises(ValueError):
            ProviderConfig(**config_data)

    def test_content_routing_config(self):
        """Test content routing configuration."""
        config_data = {
            "nsfw_models": ["ollama"],
            "safe_models": ["openai", "anthropic"],
            "default_nsfw_model": "ollama",
            "default_safe_model": "openai",
            "content_filter_enabled": True,
        }

        routing = ContentRoutingConfig(**config_data)
        assert routing.default_nsfw_model == "ollama"
        assert routing.default_safe_model == "openai"
        assert routing.content_filter_enabled is True

    def test_performance_config(self):
        """Test performance configuration."""
        config_data = {
            "max_concurrent_requests": 5,
            "timeout_seconds": 30,
            "retry_attempts": 3,
            "rate_limit_per_minute": 60,
            "cache_enabled": True,
            "cache_ttl_seconds": 300,
        }

        performance = PerformanceConfig(**config_data)
        assert performance.max_concurrent_requests == 5
        assert performance.timeout_seconds == 30
        assert performance.cache_enabled is True

    def test_invalid_performance_config(self):
        """Test performance config with invalid values."""
        config_data = {
            "max_concurrent_requests": 0,  # Invalid: must be >= 1
            "timeout_seconds": 30,
        }

        with pytest.raises(ValueError):
            PerformanceConfig(**config_data)

    def test_fallback_behavior_config(self):
        """Test fallback behavior configuration."""
        config_data = {
            "max_fallback_attempts": 3,
            "fallback_delay_seconds": 1.5,
            "log_fallback_usage": True,
            "fail_on_all_fallbacks": True,
            "circuit_breaker_enabled": True,
            "circuit_breaker_threshold": 5,
        }

        fallback = FallbackBehaviorConfig(**config_data)
        assert fallback.max_fallback_attempts == 3
        assert fallback.fallback_delay_seconds == 1.5
        assert fallback.circuit_breaker_enabled is True

    def test_complete_registry_schema(self):
        """Test complete registry schema validation."""
        config_data = {
            "metadata": {"schema_version": "3.1.0", "description": "Test Registry"},
            "models": [
                {
                    "name": "openai",
                    "priority": 1,
                    "fallbacks": ["anthropic"],
                    "enabled": True,
                },
                {
                    "name": "anthropic",
                    "priority": 2,
                    "fallbacks": ["mock"],
                    "enabled": True,
                },
                {"name": "mock", "priority": 99, "fallbacks": [], "enabled": True},
            ],
            "content_routing": {
                "nsfw_models": ["mock"],
                "safe_models": ["openai", "anthropic"],
                "default_nsfw_model": "mock",
                "default_safe_model": "openai",
            },
            "performance": {
                "max_concurrent_requests": 3,
                "timeout_seconds": 30,
                "retry_attempts": 2,
                "rate_limit_per_minute": 60,
            },
            "fallback_behavior": {
                "max_fallback_attempts": 3,
                "fallback_delay_seconds": 1.0,
                "log_fallback_usage": True,
                "fail_on_all_fallbacks": True,
            },
        }

        registry = ModelRegistrySchema(**config_data)
        assert len(registry.models) == 3
        assert registry.content_routing.default_safe_model == "openai"
        assert registry.performance.max_concurrent_requests == 3

    def test_duplicate_model_names(self):
        """Test registry with duplicate model names."""
        config_data = {
            "models": [
                {"name": "openai", "priority": 1, "enabled": True},
                {"name": "openai", "priority": 2, "enabled": True},  # Duplicate name
            ],
            "content_routing": {
                "default_nsfw_model": "openai",
                "default_safe_model": "openai",
            },
        }

        with pytest.raises(ValueError, match="Model names must be unique"):
            ModelRegistrySchema(**config_data)

    def test_duplicate_priorities(self):
        """Test registry with duplicate priorities."""
        config_data = {
            "models": [
                {"name": "openai", "priority": 1, "enabled": True},
                {
                    "name": "anthropic",
                    "priority": 1,  # Duplicate priority
                    "enabled": True,
                },
            ],
            "content_routing": {
                "default_nsfw_model": "openai",
                "default_safe_model": "anthropic",
            },
        }

        with pytest.raises(ValueError, match="Model priorities must be unique"):
            ModelRegistrySchema(**config_data)

    def test_invalid_fallback_reference(self):
        """Test registry with invalid fallback reference."""
        config_data = {
            "models": [
                {
                    "name": "openai",
                    "priority": 1,
                    "fallbacks": ["nonexistent_model"],  # Invalid reference
                    "enabled": True,
                }
            ],
            "content_routing": {
                "default_nsfw_model": "openai",
                "default_safe_model": "openai",
            },
        }

        registry = ModelRegistrySchema(**config_data)
        with pytest.raises(ValueError, match="references unknown fallback"):
            registry.validate_fallback_references()

    def test_self_referencing_fallback(self):
        """Test registry with self-referencing fallback."""
        config_data = {
            "models": [
                {
                    "name": "openai",
                    "priority": 1,
                    "fallbacks": ["openai"],  # Self-reference
                    "enabled": True,
                }
            ],
            "content_routing": {
                "default_nsfw_model": "openai",
                "default_safe_model": "openai",
            },
        }

        registry = ModelRegistrySchema(**config_data)
        with pytest.raises(ValueError, match="cannot fallback to itself"):
            registry.validate_fallback_references()

    def test_invalid_content_routing_reference(self):
        """Test registry with invalid content routing reference."""
        config_data = {
            "models": [{"name": "openai", "priority": 1, "enabled": True}],
            "content_routing": {
                "default_nsfw_model": "nonexistent_model",  # Invalid reference
                "default_safe_model": "openai",
            },
        }

        registry = ModelRegistrySchema(**config_data)
        with pytest.raises(ValueError, match="Default NSFW model .* not found"):
            registry.validate_content_routing_references()


class TestRegistryValidator:
    """Test the RegistryValidator class."""

    def setup_method(self):
        """Setup for each test method."""
        self.validator = RegistryValidator()
        self.temp_dir = Path(tempfile.mkdtemp())

    def test_validate_registry_success(self):
        """Test successful registry validation."""
        config_data = {
            "models": [{"name": "mock", "priority": 1, "enabled": True}],
            "content_routing": {
                "default_nsfw_model": "mock",
                "default_safe_model": "mock",
            },
        }

        result = self.validator.validate_registry(config_data)
        assert isinstance(result, ModelRegistrySchema)
        assert len(result.models) == 1

    def test_validate_registry_failure(self):
        """Test registry validation failure."""
        config_data = {
            "models": [],  # Invalid: must have at least one model
            "content_routing": {
                "default_nsfw_model": "mock",
                "default_safe_model": "mock",
            },
        }

        with pytest.raises(SchemaValidationError):
            self.validator.validate_registry(config_data)

    def test_validate_provider_success(self):
        """Test successful provider validation."""
        config_data = {
            "provider": "mock",
            "display_name": "Mock Provider",
            "enabled": True,
        }

        result = self.validator.validate_provider(config_data)
        assert isinstance(result, ProviderConfig)
        assert result.provider == ProviderType.MOCK

    def test_validate_provider_failure(self):
        """Test provider validation failure."""
        config_data = {
            "provider": "invalid_provider",
            "display_name": "Invalid Provider",
            "enabled": True,
        }

        with pytest.raises(SchemaValidationError):
            self.validator.validate_provider(config_data)

    def test_validate_registry_file(self):
        """Test registry file validation."""
        config_data = {
            "models": [{"name": "mock", "priority": 1, "enabled": True}],
            "content_routing": {
                "default_nsfw_model": "mock",
                "default_safe_model": "mock",
            },
        }

        # Create temporary registry file
        registry_file = self.temp_dir / "test_registry.json"
        with open(registry_file, "w") as f:
            json.dump(config_data, f)

        result = self.validator.validate_registry_file(registry_file)
        assert isinstance(result, ModelRegistrySchema)

    def test_validate_nonexistent_file(self):
        """Test validation of nonexistent file."""
        nonexistent_file = self.temp_dir / "nonexistent.json"

        with pytest.raises(SchemaValidationError, match="Registry file not found"):
            self.validator.validate_registry_file(nonexistent_file)

    def test_validate_invalid_json_file(self):
        """Test validation of file with invalid JSON."""
        invalid_file = self.temp_dir / "invalid.json"
        with open(invalid_file, "w") as f:
            f.write("{ invalid json")

        with pytest.raises(SchemaValidationError, match="Invalid JSON"):
            self.validator.validate_registry_file(invalid_file)

    def test_create_backup(self):
        """Test backup creation."""
        # Create a test file
        test_file = self.temp_dir / "test.json"
        test_content = {"test": "data"}
        with open(test_file, "w") as f:
            json.dump(test_content, f)

        # Create backup
        backup_path = self.validator.create_backup(test_file)

        assert backup_path.exists()
        assert backup_path.suffix.startswith(".bak_")

        # Verify backup content
        with open(backup_path) as f:
            backup_content = json.load(f)
        assert backup_content == test_content

    def test_safe_save_registry(self):
        """Test safe registry saving with backup."""
        config_data = {
            "models": [{"name": "mock", "priority": 1, "enabled": True}],
            "content_routing": {
                "default_nsfw_model": "mock",
                "default_safe_model": "mock",
            },
        }

        registry = ModelRegistrySchema(**config_data)
        save_file = self.temp_dir / "registry.json"

        # Save registry
        self.validator.safe_save_registry(registry, save_file)

        # Verify file was created
        assert save_file.exists()

        # Verify content
        with open(save_file) as f:
            saved_content = json.load(f)
        assert len(saved_content["models"]) == 1
        assert "metadata" in saved_content
        assert "last_modified" in saved_content["metadata"]

    def test_safe_save_provider(self):
        """Test safe provider saving with backup."""
        config_data = {
            "provider": "mock",
            "display_name": "Mock Provider",
            "enabled": True,
        }

        provider = ProviderConfig(**config_data)
        save_file = self.temp_dir / "provider.json"

        # Save provider
        self.validator.safe_save_provider(provider, save_file)

        # Verify file was created
        assert save_file.exists()

        # Verify content
        with open(save_file) as f:
            saved_content = json.load(f)
        assert saved_content["provider"] == "mock"
        assert saved_content["display_name"] == "Mock Provider"


class TestConvenienceFunctions:
    """Test convenience functions for validation."""

    def test_validate_registry_config_function(self):
        """Test convenience function for registry validation."""
        config_data = {
            "models": [{"name": "mock", "priority": 1, "enabled": True}],
            "content_routing": {
                "default_nsfw_model": "mock",
                "default_safe_model": "mock",
            },
        }

        result = validate_registry_config(config_data)
        assert isinstance(result, ModelRegistrySchema)

    def test_validate_provider_config_function(self):
        """Test convenience function for provider validation."""
        config_data = {
            "provider": "mock",
            "display_name": "Mock Provider",
            "enabled": True,
        }

        result = validate_provider_config(config_data)
        assert isinstance(result, ProviderConfig)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_registry(self):
        """Test empty registry configuration."""
        config_data = {}

        with pytest.raises(ValueError):
            ModelRegistrySchema(**config_data)

    def test_missing_required_fields(self):
        """Test configuration with missing required fields."""
        config_data = {
            "models": [
                {
                    # Missing required 'name' field
                    "priority": 1,
                    "enabled": True,
                }
            ]
        }

        with pytest.raises(ValueError):
            ModelRegistrySchema(**config_data)

    def test_extra_fields_forbidden(self):
        """Test that extra fields are forbidden."""
        config_data = {
            "name": "test_model",
            "priority": 1,
            "enabled": True,
            "invalid_extra_field": "not allowed",  # Extra field
        }

        with pytest.raises(ValueError):
            ModelConfig(**config_data)

    def test_type_coercion(self):
        """Test automatic type coercion."""
        # Test valid coercion
        config_data = {
            "name": "test_model",
            "priority": "1",  # String that should be coerced to int
            "enabled": True,
        }

        # Priority should be coerced to int
        model = ModelConfig(**config_data)
        assert model.priority == 1
        assert isinstance(model.priority, int)

        # Test invalid type that can't be coerced
        invalid_config = {
            "name": "test_model",
            "priority": "invalid_priority",  # String that can't be coerced to int
            "enabled": True,
        }

        with pytest.raises(ValueError):
            ModelConfig(**invalid_config)

    def test_whitespace_stripping(self):
        """Test automatic whitespace stripping."""
        config_data = {
            "name": "  test_model  ",  # Should be stripped
            "priority": 1,
            "enabled": True,
        }

        model = ModelConfig(**config_data)
        assert model.name == "test_model"  # Whitespace stripped


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
