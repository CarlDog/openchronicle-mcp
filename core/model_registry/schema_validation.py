"""
Registry Schema Validation for OpenChronicle Model Configuration

This module implements comprehensive pydantic schema validation for the model registry
configuration files, ensuring data integrity and preventing configuration corruption.

Key Features:
- Pydantic v2 schema validation for all registry configurations
- Type safety for model configurations
- Automatic validation on load/save operations
- Detailed error reporting for configuration issues
- Schema versioning support
- Provider-specific validation rules
"""

import json
import logging
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Literal
from datetime import datetime, timezone
from pydantic import BaseModel, Field, validator, ConfigDict, field_validator

# UTC for consistent timezone handling
UTC = timezone.utc

# Setup logging
logger = logging.getLogger('openchronicle.registry_validation')


class SchemaValidationError(Exception):
    """Raised when schema validation fails."""
    pass


class ContentType(str, Enum):
    """Enumeration of supported content types."""
    SAFE = "safe"
    NSFW = "nsfw"
    ALL = "all"


class ProviderType(str, Enum):
    """Enumeration of supported provider types."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    GROQ = "groq"
    COHERE = "cohere"
    MISTRAL = "mistralai"
    GOOGLE = "google"
    GEMINI = "gemini"  # Added for Gemini provider support
    AZURE_OPENAI = "azure_openai"
    HUGGINGFACE = "huggingface"
    TRANSFORMERS = "transformers"  # Added for Transformers provider support
    MOCK = "mock"


class ModelConfig(BaseModel):
    """Schema for individual model configuration."""
    model_config = ConfigDict(
        extra='forbid',  # Prevent extra fields
        str_strip_whitespace=True,  # Strip whitespace from strings
        validate_assignment=True,  # Validate on assignment
        frozen=False  # Allow modifications
    )
    
    name: str = Field(..., min_length=1, max_length=100, description="Model name")
    priority: int = Field(..., ge=1, le=100, description="Model priority (1-100)")
    fallbacks: List[str] = Field(default_factory=list, description="Fallback model names")
    enabled: bool = Field(default=True, description="Whether model is enabled")
    content_types: List[ContentType] = Field(
        default=[ContentType.SAFE], 
        description="Supported content types"
    )
    max_tokens: Optional[int] = Field(default=None, ge=1, description="Maximum tokens")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0, description="Temperature setting")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @field_validator('fallbacks')
    @classmethod
    def validate_fallbacks(cls, v: List[str]) -> List[str]:
        """Validate fallback list doesn't contain duplicates."""
        if len(v) != len(set(v)):
            raise ValueError("Fallback list contains duplicates")
        return v
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate model name is safe for filenames."""
        if not v.replace('_', '').replace('-', '').replace('.', '').isalnum():
            raise ValueError("Model name must contain only alphanumeric characters, hyphens, underscores, and dots")
        return v


class ContentRoutingConfig(BaseModel):
    """Schema for content routing configuration."""
    model_config = ConfigDict(extra='forbid')
    
    nsfw_models: List[str] = Field(default_factory=list, description="Models that support NSFW content")
    safe_models: List[str] = Field(default_factory=list, description="Models for safe content")
    default_nsfw_model: str = Field(..., min_length=1, description="Default NSFW model")
    default_safe_model: str = Field(..., min_length=1, description="Default safe model")
    content_filter_enabled: bool = Field(default=True, description="Whether content filtering is enabled")
    
    @field_validator('nsfw_models', 'safe_models')
    @classmethod
    def validate_model_lists(cls, v: List[str]) -> List[str]:
        """Validate model lists don't contain duplicates."""
        if len(v) != len(set(v)):
            raise ValueError("Model list contains duplicates")
        return v


class PerformanceConfig(BaseModel):
    """Schema for performance configuration."""
    model_config = ConfigDict(extra='forbid')
    
    max_concurrent_requests: int = Field(default=3, ge=1, le=100, description="Maximum concurrent requests")
    timeout_seconds: int = Field(default=30, ge=1, le=300, description="Request timeout in seconds")
    retry_attempts: int = Field(default=2, ge=0, le=10, description="Number of retry attempts")
    rate_limit_per_minute: int = Field(default=60, ge=1, le=1000, description="Rate limit per minute")
    cache_enabled: bool = Field(default=True, description="Whether caching is enabled")
    cache_ttl_seconds: int = Field(default=300, ge=1, le=3600, description="Cache TTL in seconds")


class FallbackBehaviorConfig(BaseModel):
    """Schema for fallback behavior configuration."""
    model_config = ConfigDict(extra='forbid')
    
    max_fallback_attempts: int = Field(default=3, ge=1, le=10, description="Maximum fallback attempts")
    fallback_delay_seconds: float = Field(default=1.0, ge=0.1, le=10.0, description="Delay between fallbacks")
    log_fallback_usage: bool = Field(default=True, description="Whether to log fallback usage")
    fail_on_all_fallbacks: bool = Field(default=True, description="Whether to fail when all fallbacks exhausted")
    circuit_breaker_enabled: bool = Field(default=False, description="Whether circuit breaker is enabled")
    circuit_breaker_threshold: int = Field(default=5, ge=1, le=100, description="Circuit breaker failure threshold")


class MetadataConfig(BaseModel):
    """Schema for registry metadata."""
    model_config = ConfigDict(extra='forbid')
    
    schema_version: str = Field(default="3.1.0", description="Schema version")
    last_modified: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Last modification time")
    created_by: str = Field(default="OpenChronicle", description="Created by")
    description: str = Field(default="OpenChronicle Model Registry", description="Registry description")
    config_format_version: int = Field(default=1, ge=1, description="Configuration format version")


class ModelRegistrySchema(BaseModel):
    """Complete schema for model registry configuration."""
    model_config = ConfigDict(
        extra='forbid',
        validate_assignment=True,
        str_strip_whitespace=True
    )
    
    metadata: MetadataConfig = Field(default_factory=MetadataConfig, description="Registry metadata")
    models: List[ModelConfig] = Field(..., min_length=1, description="List of model configurations")
    content_routing: ContentRoutingConfig = Field(default_factory=lambda: ContentRoutingConfig(), description="Content routing configuration")
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig, description="Performance configuration")
    fallback_behavior: FallbackBehaviorConfig = Field(default_factory=FallbackBehaviorConfig, description="Fallback behavior configuration")
    
    @field_validator('models')
    @classmethod
    def validate_unique_model_names(cls, v: List[ModelConfig]) -> List[ModelConfig]:
        """Ensure model names are unique."""
        names = [model.name for model in v]
        if len(names) != len(set(names)):
            raise ValueError("Model names must be unique")
        return v
    
    @field_validator('models')
    @classmethod
    def validate_priority_uniqueness(cls, v: List[ModelConfig]) -> List[ModelConfig]:
        """Ensure priorities are unique."""
        priorities = [model.priority for model in v]
        if len(priorities) != len(set(priorities)):
            raise ValueError("Model priorities must be unique")
        return v
    
    def validate_fallback_references(self) -> None:
        """Validate that all fallback references point to existing models."""
        model_names = {model.name for model in self.models}
        
        for model in self.models:
            for fallback in model.fallbacks:
                if fallback not in model_names:
                    raise ValueError(f"Model '{model.name}' references unknown fallback '{fallback}'")
                if fallback == model.name:
                    raise ValueError(f"Model '{model.name}' cannot fallback to itself")
    
    def validate_content_routing_references(self) -> None:
        """Validate that content routing references point to existing models."""
        model_names = {model.name for model in self.models}
        
        if self.content_routing.default_nsfw_model not in model_names:
            raise ValueError(f"Default NSFW model '{self.content_routing.default_nsfw_model}' not found")
        
        if self.content_routing.default_safe_model not in model_names:
            raise ValueError(f"Default safe model '{self.content_routing.default_safe_model}' not found")
        
        for model_name in self.content_routing.nsfw_models:
            if model_name not in model_names:
                raise ValueError(f"NSFW model '{model_name}' not found")
        
        for model_name in self.content_routing.safe_models:
            if model_name not in model_names:
                raise ValueError(f"Safe model '{model_name}' not found")
    
    def validate_complete(self) -> None:
        """Run complete validation including cross-references."""
        self.validate_fallback_references()
        self.validate_content_routing_references()


class ProviderConfig(BaseModel):
    """Schema for individual provider configuration files."""
    model_config = ConfigDict(
        extra='allow',  # Allow additional fields for rich configurations
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    provider: ProviderType = Field(..., description="Provider type")
    display_name: str = Field(..., min_length=1, max_length=100, description="Human-readable provider name")
    enabled: bool = Field(default=True, description="Whether provider is enabled")
    api_config: Dict[str, Any] = Field(default_factory=dict, description="API configuration")
    model_list: List[str] = Field(default_factory=list, description="Available models")
    content_filter: bool = Field(default=True, description="Whether content filtering is enabled")
    rate_limits: Dict[str, int] = Field(default_factory=dict, description="Rate limit configuration")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    # Additional fields commonly found in model configs (all optional)
    name: Optional[str] = Field(None, description="Model configuration name")
    description: Optional[str] = Field(None, description="Model description")
    adapter_class: Optional[str] = Field(None, description="Adapter class name")
    capabilities: Optional[Dict[str, Any]] = Field(None, description="Model capabilities")
    limits: Optional[Dict[str, Any]] = Field(None, description="Model limits and constraints")
    health_check: Optional[Dict[str, Any]] = Field(None, description="Health check configuration")
    validation: Optional[Dict[str, Any]] = Field(None, description="Validation requirements")
    cost_tracking: Optional[Dict[str, Any]] = Field(None, description="Cost tracking configuration")
    fallback_chain: Optional[List[str]] = Field(None, description="Fallback model chain")
    performance: Optional[Dict[str, Any]] = Field(None, description="Performance characteristics")
    local_config: Optional[Dict[str, Any]] = Field(None, description="Local deployment configuration")
    
    @field_validator('model_list')
    @classmethod
    def validate_model_list(cls, v: List[str]) -> List[str]:
        """Validate model list doesn't contain duplicates."""
        if len(v) != len(set(v)):
            raise ValueError("Model list contains duplicates")
        return v


class RegistryValidator:
    """Main validator class for registry configurations."""
    
    def __init__(self):
        """Initialize the registry validator."""
        self.logger = logging.getLogger('openchronicle.registry_validator')
    
    def validate_registry(self, config_data: Dict[str, Any]) -> ModelRegistrySchema:
        """
        Validate complete registry configuration.
        
        Args:
            config_data: Raw configuration dictionary
            
        Returns:
            Validated ModelRegistrySchema instance
            
        Raises:
            SchemaValidationError: If validation fails
        """
        try:
            registry = ModelRegistrySchema(**config_data)
            registry.validate_complete()
            self.logger.info("Registry validation successful")
            return registry
        except Exception as e:
            error_msg = f"Registry validation failed: {e}"
            self.logger.error(error_msg)
            raise SchemaValidationError(error_msg) from e
    
    def validate_provider(self, config_data: Dict[str, Any]) -> ProviderConfig:
        """
        Validate provider configuration.
        
        Args:
            config_data: Raw configuration dictionary
            
        Returns:
            Validated ProviderConfig instance
            
        Raises:
            SchemaValidationError: If validation fails
        """
        try:
            provider = ProviderConfig(**config_data)
            self.logger.info(f"Provider '{provider.provider}' validation successful")
            return provider
        except Exception as e:
            error_msg = f"Provider validation failed: {e}"
            self.logger.error(error_msg)
            raise SchemaValidationError(error_msg) from e
    
    def validate_registry_file(self, file_path: Union[str, Path]) -> ModelRegistrySchema:
        """
        Validate registry configuration from file.
        
        Args:
            file_path: Path to registry file
            
        Returns:
            Validated ModelRegistrySchema instance
            
        Raises:
            SchemaValidationError: If validation fails
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            return self.validate_registry(config_data)
        except FileNotFoundError:
            raise SchemaValidationError(f"Registry file not found: {file_path}")
        except json.JSONDecodeError as e:
            raise SchemaValidationError(f"Invalid JSON in registry file: {e}")
    
    def validate_provider_file(self, file_path: Union[str, Path]) -> ProviderConfig:
        """
        Validate provider configuration from file.
        
        Args:
            file_path: Path to provider file
            
        Returns:
            Validated ProviderConfig instance
            
        Raises:
            SchemaValidationError: If validation fails
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            return self.validate_provider(config_data)
        except FileNotFoundError:
            raise SchemaValidationError(f"Provider file not found: {file_path}")
        except json.JSONDecodeError as e:
            raise SchemaValidationError(f"Invalid JSON in provider file: {e}")
    
    def create_backup(self, file_path: Union[str, Path]) -> Path:
        """
        Create backup of configuration file before modification.
        
        Args:
            file_path: Path to file to backup
            
        Returns:
            Path to backup file
        """
        file_path = Path(file_path)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        backup_path = file_path.with_suffix(f'.bak_{timestamp}')
        
        if file_path.exists():
            backup_path.write_text(file_path.read_text(encoding='utf-8'), encoding='utf-8')
            self.logger.info(f"Created backup: {backup_path}")
        
        return backup_path
    
    def safe_save_registry(self, registry: ModelRegistrySchema, file_path: Union[str, Path]) -> None:
        """
        Safely save registry configuration with backup.
        
        Args:
            registry: Validated registry configuration
            file_path: Path to save file
        """
        file_path = Path(file_path)
        
        # Create backup before saving
        if file_path.exists():
            self.create_backup(file_path)
        
        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict and save
        config_dict = registry.model_dump(mode='json', exclude_none=False)
        
        # Update metadata
        config_dict['metadata']['last_modified'] = datetime.now(UTC).isoformat()
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Registry saved to: {file_path}")
    
    def safe_save_provider(self, provider: ProviderConfig, file_path: Union[str, Path]) -> None:
        """
        Safely save provider configuration with backup.
        
        Args:
            provider: Validated provider configuration
            file_path: Path to save file
        """
        file_path = Path(file_path)
        
        # Create backup before saving
        if file_path.exists():
            self.create_backup(file_path)
        
        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict and save
        config_dict = provider.model_dump(mode='json', exclude_none=False)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Provider saved to: {file_path}")


# Convenience functions for common operations
def validate_registry_config(config_data: Dict[str, Any]) -> ModelRegistrySchema:
    """Convenience function to validate registry configuration."""
    validator = RegistryValidator()
    return validator.validate_registry(config_data)


def validate_provider_config(config_data: Dict[str, Any]) -> ProviderConfig:
    """Convenience function to validate provider configuration."""
    validator = RegistryValidator()
    return validator.validate_provider(config_data)


def validate_registry_file(file_path: Union[str, Path]) -> ModelRegistrySchema:
    """Convenience function to validate registry file."""
    validator = RegistryValidator()
    return validator.validate_registry_file(file_path)


def validate_provider_file(file_path: Union[str, Path]) -> ProviderConfig:
    """Convenience function to validate provider file."""
    validator = RegistryValidator()
    return validator.validate_provider_file(file_path)
