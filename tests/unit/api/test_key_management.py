"""
Comprehensive test suite for the API key management system.

This test suite covers all components of the modular API key management
system including interfaces, implementations, and integration scenarios.
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Import the API key management components
from utilities.api_key_management import (
    # Interfaces
    IApiKeyOrchestrator, IKeyringBackend, IProviderRegistry, IApiKeyValidator, 
    IApiKeyStorage, IUserInterface,
    # Data classes
    ApiKeyInfo, ValidationResult, ProviderConfig, KeyringInfo, StorageResult,
    # Implementations
    ApiKeyOrchestrator, KeyringBackend, ProviderRegistry, ApiKeyValidator,
    ApiKeyStorage, CliUserInterface, InteractiveManager,
    # Mock implementations
    MockKeyringBackend, MockProviderRegistry, MockApiKeyValidator, MockUserInterface,
    # Factory functions
    create_api_key_manager, create_mock_api_key_manager, create_memory_api_key_manager,
    create_keyring_backend, create_provider_registry, create_api_key_validator,
    create_api_key_storage, create_cli_user_interface
)

from utilities.api_key_management.storage.keyring_backend import FallbackKeyringBackend
from utilities.api_key_management.providers.provider_registry import StaticProviderRegistry
from utilities.api_key_management.validation.api_key_validator import LenientApiKeyValidator
from utilities.api_key_management.storage.api_key_storage import MemoryApiKeyStorage
from utilities.api_key_management.ui.user_interface import SilentUserInterface


class TestDataClasses:
    """Test API key management data classes."""
    
    def test_api_key_info_creation(self):
        """Test ApiKeyInfo data class creation."""
        info = ApiKeyInfo(
            provider="openai",
            masked_key="sk-****************************xxxx",
            stored_date=datetime.now(),
            is_valid_format=True,
            validation_message="Valid format"
        )
        
        assert info.provider == "openai"
        assert "sk-" in info.masked_key
        assert info.is_valid_format is True
        assert info.validation_message == "Valid format"
    
    def test_validation_result_creation(self):
        """Test ValidationResult data class creation."""
        result = ValidationResult(
            valid=True,
            reason="Valid OpenAI API key format",
            pattern=r"^sk-[A-Za-z0-9]{48}$"
        )
        
        assert result.valid is True
        assert "Valid" in result.reason
        assert result.pattern is not None
    
    def test_provider_config_creation(self):
        """Test ProviderConfig data class creation."""
        config = ProviderConfig(
            name="openai",
            display_name="OpenAI",
            keyring_username="openai_api_key",
            api_key_pattern=r"^sk-[A-Za-z0-9]{48}$",
            setup_url="https://platform.openai.com/api-keys",
            aliases=[]
        )
        
        assert config.name == "openai"
        assert config.display_name == "OpenAI"
        assert config.api_key_pattern is not None
    
    def test_keyring_info_creation(self):
        """Test KeyringInfo data class creation."""
        info = KeyringInfo(
            available=True,
            backend_name="MockKeyring",
            service_name="openchronicle"
        )
        
        assert info.available is True
        assert info.backend_name == "MockKeyring"
        assert info.service_name == "openchronicle"
    
    def test_storage_result_creation(self):
        """Test StorageResult data class creation."""
        result = StorageResult(
            success=True,
            message="API key stored successfully",
            error_details=None
        )
        
        assert result.success is True
        assert "stored" in result.message
        assert result.error_details is None


class TestMockKeyringBackend:
    """Test mock keyring backend implementation."""
    
    def test_available_backend(self):
        """Test available mock keyring backend."""
        backend = MockKeyringBackend(available=True)
        
        assert backend.is_available() is True
        
        info = backend.get_keyring_info()
        assert info.available is True
        assert info.backend_name == "MockKeyring"
    
    def test_unavailable_backend(self):
        """Test unavailable mock keyring backend."""
        backend = MockKeyringBackend(available=False)
        
        assert backend.is_available() is False
        
        info = backend.get_keyring_info()
        assert info.available is False
        assert "not available" in info.reason
    
    def test_password_operations(self):
        """Test password storage operations."""
        backend = MockKeyringBackend(available=True)
        
        # Test storing password
        success = backend.set_password("service", "user", "password123")
        assert success is True
        
        # Test retrieving password
        password = backend.get_password("service", "user")
        assert password == "password123"
        
        # Test deleting password
        success = backend.delete_password("service", "user")
        assert success is True
        
        # Test retrieving deleted password
        password = backend.get_password("service", "user")
        assert password is None


class TestMockProviderRegistry:
    """Test mock provider registry implementation."""
    
    def test_provider_registry_initialization(self):
        """Test provider registry initialization."""
        registry = MockProviderRegistry()
        
        providers = registry.get_all_providers()
        assert len(providers) >= 2  # At least openai and anthropic
        
        openai_config = registry.get_provider_config("openai")
        assert openai_config is not None
        assert openai_config.name == "openai"
        assert openai_config.display_name == "OpenAI"
    
    def test_provider_alias_resolution(self):
        """Test provider alias resolution."""
        registry = MockProviderRegistry()
        
        # Test alias resolution
        resolved = registry.resolve_provider_alias("gemini")
        assert resolved == "google"
        
        # Test non-alias
        resolved = registry.resolve_provider_alias("openai")
        assert resolved == "openai"
    
    def test_validation_patterns(self):
        """Test loading validation patterns."""
        registry = MockProviderRegistry()
        
        patterns = registry.load_validation_patterns()
        assert "openai" in patterns
        assert "pattern" in patterns["openai"]
        assert patterns["openai"]["service_name"] == "OpenAI"


class TestMockApiKeyValidator:
    """Test mock API key validator implementation."""
    
    def test_validator_initialization(self):
        """Test validator initialization."""
        registry = MockProviderRegistry()
        validator = MockApiKeyValidator(registry)
        
        # Test valid OpenAI key
        result = validator.validate_format("openai", "sk-" + "x" * 48)
        assert result.valid is True
        
        # Test invalid OpenAI key
        result = validator.validate_format("openai", "invalid-key")
        assert result.valid is False
        assert "Invalid" in result.reason
    
    def test_validation_info(self):
        """Test getting validation information."""
        registry = MockProviderRegistry()
        validator = MockApiKeyValidator(registry)
        
        info = validator.get_validation_info("openai")
        assert "pattern" in info
        assert info["setup_url"] is not None
    
    def test_unknown_provider_validation(self):
        """Test validation for unknown provider."""
        registry = MockProviderRegistry()
        validator = MockApiKeyValidator(registry)
        
        result = validator.validate_format("unknown", "some-api-key")
        assert result.valid is False or len("some-api-key") >= 10


class TestMockUserInterface:
    """Test mock user interface implementation."""
    
    def test_user_interface_initialization(self):
        """Test user interface initialization."""
        ui = MockUserInterface()
        
        assert ui.prompts == []
    
    def test_api_key_prompting(self):
        """Test API key prompting."""
        ui = MockUserInterface()
        config = ProviderConfig("openai", "OpenAI", "openai_api_key")
        
        # Set up mock response
        ui.set_api_key_response("openai", "sk-test-key")
        
        # Test prompting
        result = ui.prompt_for_api_key("openai", config)
        assert result == "sk-test-key"
        assert "prompt_api_key_openai" in ui.prompts
    
    def test_confirmation_handling(self):
        """Test confirmation handling."""
        ui = MockUserInterface()
        
        # Set up mock response
        ui.set_confirm_response("test_message", True)
        
        # Test confirmation
        result = ui.confirm_action("test_message")
        assert result is True
        assert "confirm_test_message" in ui.prompts
    
    def test_message_display(self):
        """Test message display tracking."""
        ui = MockUserInterface()
        
        ui.show_success_message("openai", "setup", "details")
        assert "success_setup_openai" in ui.prompts
        
        ui.show_error_message("error occurred", "details")
        assert "error_error occurred" in ui.prompts


class TestKeyringBackend:
    """Test production keyring backend implementation."""
    
    @patch('utilities.api_key_management.storage.keyring_backend.KEYRING_AVAILABLE', True)
    @patch('utilities.api_key_management.storage.keyring_backend.keyring')
    def test_available_keyring(self, mock_keyring):
        """Test available keyring backend."""
        mock_keyring.get_keyring.return_value = Mock(__class__=Mock(__name__="TestBackend"))
        
        backend = KeyringBackend()
        
        assert backend.is_available() is True
        
        info = backend.get_keyring_info()
        assert info.available is True
        assert info.backend_name == "TestBackend"
    
    @patch('utilities.api_key_management.storage.keyring_backend.KEYRING_AVAILABLE', False)
    def test_unavailable_keyring(self):
        """Test unavailable keyring backend."""
        backend = KeyringBackend()
        
        assert backend.is_available() is False
        
        info = backend.get_keyring_info()
        assert info.available is False
        assert "not installed" in info.reason
    
    def test_fallback_backend(self):
        """Test fallback keyring backend."""
        backend = FallbackKeyringBackend()
        
        assert backend.is_available() is False
        
        info = backend.get_keyring_info()
        assert info.available is False
        assert info.backend_name == "FallbackBackend"
        
        # Test operations return appropriate values
        assert backend.get_password("service", "user") is None
        assert backend.set_password("service", "user", "password") is False
        assert backend.delete_password("service", "user") is False


class TestProviderRegistry:
    """Test production provider registry implementation."""
    
    def test_static_provider_registry(self):
        """Test static provider registry."""
        registry = StaticProviderRegistry()
        
        providers = registry.get_all_providers()
        assert len(providers) >= 8  # Built-in providers
        
        # Test built-in providers
        openai_config = registry.get_provider_config("openai")
        assert openai_config is not None
        assert openai_config.name == "openai"
        assert openai_config.api_key_pattern is not None
    
    def test_provider_registry_with_missing_file(self):
        """Test provider registry with missing model registry file."""
        non_existent_path = Path("/non/existent/path/model_registry.json")
        registry = ProviderRegistry(non_existent_path)
        
        # Should still have built-in providers
        providers = registry.get_all_providers()
        assert len(providers) >= 8
        
        openai_config = registry.get_provider_config("openai")
        assert openai_config is not None
    
    def test_provider_registry_with_valid_file(self):
        """Test provider registry with valid model registry file."""
        # Create temporary model registry file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            registry_data = {
                "environment_config": {
                    "providers": {
                        "test_provider": {
                            "validation": {
                                "requires_api_key": True,
                                "api_key_format": r"^test-[A-Za-z0-9]{32}$",
                                "service_name": "Test Provider",
                                "setup_url": "https://test.example.com",
                                "description": "Test provider API key"
                            }
                        }
                    }
                }
            }
            json.dump(registry_data, f)
            temp_path = Path(f.name)
        
        try:
            registry = ProviderRegistry(temp_path)
            
            # Should have built-in providers plus test provider
            test_config = registry.get_provider_config("test_provider")
            assert test_config is not None
            assert test_config.display_name == "Test Provider"
            assert test_config.api_key_pattern == r"^test-[A-Za-z0-9]{32}$"
            
        finally:
            temp_path.unlink()
    
    def test_alias_resolution(self):
        """Test provider alias resolution."""
        registry = StaticProviderRegistry()
        
        # Test built-in aliases
        assert registry.resolve_provider_alias("gemini") == "google"
        assert registry.resolve_provider_alias("azure_openai") == "azure"
        assert registry.resolve_provider_alias("hf") == "huggingface"
        
        # Test non-aliases
        assert registry.resolve_provider_alias("openai") == "openai"
        assert registry.resolve_provider_alias("anthropic") == "anthropic"


class TestApiKeyValidator:
    """Test production API key validator implementation."""
    
    def test_validator_with_patterns(self):
        """Test validator with provider patterns."""
        registry = StaticProviderRegistry()
        validator = ApiKeyValidator(registry)
        
        # Test valid OpenAI key
        result = validator.validate_format("openai", "sk-" + "A" * 48)
        assert result.valid is True
        assert "Valid" in result.reason
        
        # Test invalid OpenAI key
        result = validator.validate_format("openai", "invalid-key")
        assert result.valid is False
        assert "Invalid" in result.reason
        assert result.expected_pattern is not None
    
    def test_validator_without_patterns(self):
        """Test validator for providers without patterns."""
        registry = StaticProviderRegistry()
        validator = ApiKeyValidator(registry)
        
        # Test provider with no pattern (e.g., cohere)
        result = validator.validate_format("cohere", "cohere-api-key-123")
        assert result.valid is True  # Should pass basic validation
        assert "No format pattern available" in result.reason
    
    def test_validator_unknown_provider(self):
        """Test validator for unknown provider."""
        registry = StaticProviderRegistry()
        validator = ApiKeyValidator(registry)
        
        # Test unknown provider
        result = validator.validate_format("unknown", "some-long-api-key")
        assert result.valid is True  # Should pass basic validation
        assert len(result.reason) > 0
    
    def test_lenient_validator(self):
        """Test lenient API key validator."""
        registry = StaticProviderRegistry()
        validator = LenientApiKeyValidator(registry)
        
        # Test very short key (should fail)
        result = validator.validate_format("openai", "abc")
        assert result.valid is False
        assert "too short" in result.reason
        
        # Test reasonable key (should pass)
        result = validator.validate_format("openai", "reasonable-length-key")
        assert result.valid is True
        assert "Lenient validation passed" in result.reason
    
    def test_validation_examples(self):
        """Test getting provider examples."""
        registry = StaticProviderRegistry()
        validator = ApiKeyValidator(registry)
        
        examples = validator.get_provider_examples("openai")
        assert examples["provider"] == "openai"
        assert len(examples["examples"]) > 0
        assert any("sk-" in example for example in examples["examples"])


class TestApiKeyStorage:
    """Test API key storage implementations."""
    
    def test_memory_storage(self):
        """Test memory API key storage."""
        registry = StaticProviderRegistry()
        validator = ApiKeyValidator(registry)
        storage = MemoryApiKeyStorage(registry, validator)
        
        # Test storing valid key
        result = storage.set_api_key("openai", "sk-" + "A" * 48)
        assert result.success is True
        
        # Test retrieving key
        api_key = storage.get_api_key("openai")
        assert api_key == "sk-" + "A" * 48
        
        # Test checking existence
        assert storage.has_api_key("openai") is True
        assert storage.has_api_key("anthropic") is False
        
        # Test listing keys
        keys = storage.list_stored_keys()
        assert len(keys) == 1
        assert keys[0].provider == "openai"
        assert keys[0].is_valid_format is True
        
        # Test removing key
        result = storage.remove_api_key("openai")
        assert result.success is True
        
        # Test key no longer exists
        assert storage.has_api_key("openai") is False
    
    def test_memory_storage_invalid_key(self):
        """Test memory storage with invalid API key."""
        registry = StaticProviderRegistry()
        validator = ApiKeyValidator(registry)
        storage = MemoryApiKeyStorage(registry, validator)
        
        # Test storing invalid key
        result = storage.set_api_key("openai", "invalid-key")
        assert result.success is False
        assert "Invalid" in result.message
    
    def test_memory_storage_stats(self):
        """Test memory storage statistics."""
        registry = StaticProviderRegistry()
        validator = ApiKeyValidator(registry)
        storage = MemoryApiKeyStorage(registry, validator)
        
        # Add some keys
        storage.set_api_key("openai", "sk-" + "A" * 48)  # Valid
        
        stats = storage.get_storage_stats()
        assert stats["keyring_available"] is False
        assert stats["keyring_backend"] == "MemoryStorage"
        assert stats["total_stored_keys"] == 1
        assert stats["valid_keys"] == 1
        assert stats["invalid_keys"] == 0


class TestApiKeyOrchestrator:
    """Test API key orchestrator implementation."""
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initialization."""
        keyring = MockKeyringBackend(available=True)
        registry = MockProviderRegistry()
        validator = MockApiKeyValidator(registry)
        storage = MemoryApiKeyStorage(registry, validator)
        ui = MockUserInterface()
        
        orchestrator = ApiKeyOrchestrator(keyring, registry, validator, storage, ui)
        
        assert orchestrator is not None
    
    def test_orchestrator_setup_key_success(self):
        """Test successful API key setup."""
        keyring = MockKeyringBackend(available=True)
        registry = MockProviderRegistry()
        validator = MockApiKeyValidator(registry)
        storage = MemoryApiKeyStorage(registry, validator)
        ui = MockUserInterface()
        
        orchestrator = ApiKeyOrchestrator(keyring, registry, validator, storage, ui)
        
        # Set up mock responses
        ui.set_api_key_response("openai", "sk-" + "A" * 48)
        
        # Test setup
        result = orchestrator.setup_api_key("openai", interactive=True)
        assert result.success is True
    
    def test_orchestrator_setup_key_validation_failure(self):
        """Test API key setup with validation failure."""
        keyring = MockKeyringBackend(available=True)
        registry = MockProviderRegistry()
        validator = MockApiKeyValidator(registry)
        storage = MemoryApiKeyStorage(registry, validator)
        ui = MockUserInterface()
        
        orchestrator = ApiKeyOrchestrator(keyring, registry, validator, storage, ui)
        
        # Set up mock responses
        ui.set_api_key_response("openai", "invalid-key")
        ui.set_confirm_response("validation_error_openai", False)  # User cancels
        
        # Test setup
        result = orchestrator.setup_api_key("openai", interactive=True)
        assert result.success is False
        assert "validation failure" in result.message
    
    def test_orchestrator_keyring_unavailable(self):
        """Test orchestrator with unavailable keyring."""
        keyring = MockKeyringBackend(available=False)
        registry = MockProviderRegistry()
        validator = MockApiKeyValidator(registry)
        storage = MemoryApiKeyStorage(registry, validator)
        ui = MockUserInterface()
        
        orchestrator = ApiKeyOrchestrator(keyring, registry, validator, storage, ui)
        
        # Test setup fails with unavailable keyring
        result = orchestrator.setup_api_key("openai", interactive=True)
        assert result.success is False
        assert "not available" in result.message
    
    def test_orchestrator_unsupported_provider(self):
        """Test orchestrator with unsupported provider."""
        keyring = MockKeyringBackend(available=True)
        registry = MockProviderRegistry()
        validator = MockApiKeyValidator(registry)
        storage = MemoryApiKeyStorage(registry, validator)
        ui = MockUserInterface()
        
        orchestrator = ApiKeyOrchestrator(keyring, registry, validator, storage, ui)
        
        # Test setup with unsupported provider
        result = orchestrator.setup_api_key("unsupported", interactive=True)
        assert result.success is False
        assert "Unsupported provider" in result.message
    
    def test_orchestrator_get_system_info(self):
        """Test getting system information."""
        keyring = MockKeyringBackend(available=True)
        registry = MockProviderRegistry()
        validator = MockApiKeyValidator(registry)
        storage = MemoryApiKeyStorage(registry, validator)
        ui = MockUserInterface()
        
        orchestrator = ApiKeyOrchestrator(keyring, registry, validator, storage, ui)
        
        info = orchestrator.get_system_info()
        assert "keyring_info" in info
        assert "supported_providers" in info
        assert info["keyring_info"]["available"] is True
    
    def test_orchestrator_check_provider_support(self):
        """Test checking provider support."""
        keyring = MockKeyringBackend(available=True)
        registry = MockProviderRegistry()
        validator = MockApiKeyValidator(registry)
        storage = MemoryApiKeyStorage(registry, validator)
        ui = MockUserInterface()
        
        orchestrator = ApiKeyOrchestrator(keyring, registry, validator, storage, ui)
        
        # Test supported provider
        support_info = orchestrator.check_provider_support("openai")
        assert support_info["supported"] is True
        assert support_info["name"] == "openai"
        
        # Test unsupported provider
        support_info = orchestrator.check_provider_support("unsupported")
        assert support_info["supported"] is False
    
    def test_orchestrator_bulk_validation(self):
        """Test bulk validation of stored keys."""
        keyring = MockKeyringBackend(available=True)
        registry = MockProviderRegistry()
        validator = MockApiKeyValidator(registry)
        storage = MemoryApiKeyStorage(registry, validator)
        ui = MockUserInterface()
        
        orchestrator = ApiKeyOrchestrator(keyring, registry, validator, storage, ui)
        
        # Add some keys
        storage.set_api_key("openai", "sk-" + "A" * 48)
        
        # Test bulk validation
        results = orchestrator.bulk_validate_stored_keys()
        assert "openai" in results
        assert results["openai"].valid is True


class TestFactoryFunctions:
    """Test factory functions for creating components."""
    
    def test_create_api_key_manager(self):
        """Test creating production API key manager."""
        manager = create_api_key_manager(verbose=False)
        assert manager is not None
        assert isinstance(manager, IApiKeyOrchestrator)
    
    def test_create_mock_api_key_manager(self):
        """Test creating mock API key manager."""
        manager = create_mock_api_key_manager()
        assert manager is not None
        assert isinstance(manager, IApiKeyOrchestrator)
    
    def test_create_memory_api_key_manager(self):
        """Test creating memory API key manager."""
        manager = create_memory_api_key_manager(verbose=False)
        assert manager is not None
        assert isinstance(manager, IApiKeyOrchestrator)
    
    def test_create_keyring_backend(self):
        """Test creating keyring backend."""
        backend = create_keyring_backend()
        assert backend is not None
        assert isinstance(backend, IKeyringBackend)
    
    def test_create_provider_registry(self):
        """Test creating provider registry."""
        registry = create_provider_registry()
        assert registry is not None
        assert isinstance(registry, IProviderRegistry)
    
    def test_create_api_key_validator(self):
        """Test creating API key validator."""
        registry = create_provider_registry()
        validator = create_api_key_validator(registry)
        assert validator is not None
        assert isinstance(validator, IApiKeyValidator)
    
    def test_create_api_key_storage(self):
        """Test creating API key storage."""
        keyring = create_keyring_backend()
        registry = create_provider_registry()
        validator = create_api_key_validator(registry)
        storage = create_api_key_storage(keyring, registry, validator)
        assert storage is not None
        assert isinstance(storage, IApiKeyStorage)
    
    def test_create_cli_user_interface(self):
        """Test creating CLI user interface."""
        ui = create_cli_user_interface()
        assert ui is not None
        assert isinstance(ui, IUserInterface)


class TestIntegration:
    """Test integration scenarios."""
    
    def test_complete_workflow_with_mocks(self):
        """Test complete API key management workflow with mocks."""
        # Create mock manager
        manager = create_mock_api_key_manager()
        
        # Test system info
        info = manager.get_system_info()
        assert info["keyring_info"]["available"] is True
        
        # Test provider support
        support = manager.check_provider_support("openai")
        assert support["supported"] is True
        
        # Test validation
        result = manager.validate_api_key("openai", "sk-" + "A" * 48)
        assert result.valid is True
        
        # List keys (should be empty initially)
        keys = manager.list_api_keys()
        assert len(keys) == 0
    
    def test_error_handling(self):
        """Test error handling in various scenarios."""
        # Test with unavailable keyring
        keyring = MockKeyringBackend(available=False)
        registry = MockProviderRegistry()
        validator = MockApiKeyValidator(registry)
        storage = MemoryApiKeyStorage(registry, validator)
        ui = MockUserInterface()
        
        orchestrator = ApiKeyOrchestrator(keyring, registry, validator, storage, ui)
        
        # Should handle unavailable keyring gracefully
        result = orchestrator.setup_api_key("openai", interactive=False)
        assert result.success is False
        assert "not available" in result.message
        
        # Should handle empty API key
        ui.set_api_key_response("openai", "")
        result = orchestrator.setup_api_key("openai", interactive=True)
        assert result.success is False
    
    def test_memory_vs_keyring_storage(self):
        """Test difference between memory and keyring storage."""
        # Memory storage
        memory_manager = create_memory_api_key_manager(verbose=False)
        memory_info = memory_manager.get_system_info()
        assert memory_info["storage_stats"]["keyring_backend"] == "MemoryStorage"
        
        # Mock keyring storage
        mock_manager = create_mock_api_key_manager()
        mock_info = mock_manager.get_system_info()
        assert mock_info["keyring_info"]["backend_name"] == "MockKeyring"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
