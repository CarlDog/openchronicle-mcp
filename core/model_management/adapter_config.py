"""
Adapter Configuration Management - Validation and management of adapter configurations

This module provides utilities for managing adapter configurations, including
validation, defaults, environment variable loading, and configuration templates.

Key Components:
- ConfigValidator: Validates adapter configurations
- ConfigManager: Manages configuration loading and defaults
- ConfigTemplate: Templates for different adapter types
- EnvironmentLoader: Loads configuration from environment variables
"""

import os
import logging
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
from pathlib import Path

from .adapter_interfaces import AdapterConfig, AdapterConfigurationError
from ..shared.json_utilities import JSONUtilities

logger = logging.getLogger(__name__)


@dataclass
class ConfigTemplate:
    """Template for adapter configuration"""
    provider_name: str
    default_model: str
    base_url: Optional[str] = None
    api_key_env_var: Optional[str] = None
    default_max_tokens: int = 1000
    default_temperature: float = 0.7
    supported_features: Dict[str, bool] = None
    required_config: List[str] = None
    
    def __post_init__(self):
        if self.supported_features is None:
            self.supported_features = {
                'streaming': False,
                'embeddings': False,
                'vision': False,
                'function_calling': False
            }
        
        if self.required_config is None:
            self.required_config = []


class EnvironmentLoader:
    """Loads configuration from environment variables"""
    
    @staticmethod
    def load_api_key(provider_name: str, env_var_name: str = None) -> Optional[str]:
        """Load API key from environment"""
        if env_var_name:
            return os.getenv(env_var_name)
        
        # Try common patterns
        common_patterns = [
            f"{provider_name.upper()}_API_KEY",
            f"{provider_name.upper()}_KEY", 
            f"API_KEY_{provider_name.upper()}",
            f"{provider_name}_API_KEY"
        ]
        
        for pattern in common_patterns:
            value = os.getenv(pattern)
            if value:
                return value
        
        return None
    
    @staticmethod
    def load_base_url(provider_name: str) -> Optional[str]:
        """Load base URL from environment"""
        env_vars = [
            f"{provider_name.upper()}_BASE_URL",
            f"{provider_name.upper()}_URL",
            f"BASE_URL_{provider_name.upper()}"
        ]
        
        for env_var in env_vars:
            value = os.getenv(env_var)
            if value:
                return value
        
        return None
    
    @staticmethod
    def load_model_config(provider_name: str) -> Dict[str, Any]:
        """Load model configuration from environment"""
        config = {}
        
        # Load common configuration
        env_prefix = f"{provider_name.upper()}_"
        
        config_mappings = {
            'max_tokens': ('MAX_TOKENS', int),
            'temperature': ('TEMPERATURE', float),
            'top_p': ('TOP_P', float),
            'timeout': ('TIMEOUT', int),
            'max_retries': ('MAX_RETRIES', int)
        }
        
        for config_key, (env_suffix, type_converter) in config_mappings.items():
            env_var = env_prefix + env_suffix
            value = os.getenv(env_var)
            if value:
                try:
                    config[config_key] = type_converter(value)
                except ValueError as e:
                    logger.warning(f"Invalid value for {env_var}: {value} ({e})")
        
        return config


class ConfigValidator:
    """Validates adapter configurations"""
    
    def __init__(self):
        self.templates: Dict[str, ConfigTemplate] = {}
        self._load_default_templates()
    
    def _load_default_templates(self):
        """Load default configuration templates"""
        # OpenAI template
        self.templates['openai'] = ConfigTemplate(
            provider_name='openai',
            default_model='gpt-3.5-turbo',
            api_key_env_var='OPENAI_API_KEY',
            supported_features={
                'streaming': True,
                'embeddings': True,
                'vision': True,
                'function_calling': True
            },
            required_config=['api_key']
        )
        
        # Anthropic template
        self.templates['anthropic'] = ConfigTemplate(
            provider_name='anthropic',
            default_model='claude-3-sonnet-20240229',
            api_key_env_var='ANTHROPIC_API_KEY',
            supported_features={
                'streaming': True,
                'embeddings': False,
                'vision': True,
                'function_calling': True
            },
            required_config=['api_key']
        )
        
        # Ollama template
        self.templates['ollama'] = ConfigTemplate(
            provider_name='ollama',
            default_model='llama2',
            base_url='http://localhost:11434',
            supported_features={
                'streaming': True,
                'embeddings': True,
                'vision': False,
                'function_calling': False
            }
        )
        
        # Transformers template
        self.templates['transformers'] = ConfigTemplate(
            provider_name='transformers',
            default_model='microsoft/DialoGPT-medium',
            supported_features={
                'streaming': False,
                'embeddings': True,
                'vision': False,
                'function_calling': False
            },
            required_config=['model_path']
        )
    
    def add_template(self, template: ConfigTemplate):
        """Add a configuration template"""
        self.templates[template.provider_name] = template
    
    def validate_config(self, config: AdapterConfig) -> bool:
        """Validate configuration against template"""
        template = self.templates.get(config.provider_name)
        
        if not template:
            logger.warning(f"No template found for provider: {config.provider_name}")
            # Still do basic validation
            return config.validate()
        
        # Check required configuration
        for required_field in template.required_config:
            value = getattr(config, required_field, None)
            if not value:
                # Try to get from provider_specific
                value = config.provider_specific.get(required_field)
            
            if not value:
                raise AdapterConfigurationError(
                    f"Required field missing: {required_field}",
                    provider=config.provider_name
                )
        
        # Validate feature support
        if config.supports_streaming and not template.supported_features.get('streaming'):
            logger.warning(f"{config.provider_name} does not support streaming")
        
        if config.supports_embeddings and not template.supported_features.get('embeddings'):
            logger.warning(f"{config.provider_name} does not support embeddings")
        
        if config.supports_vision and not template.supported_features.get('vision'):
            logger.warning(f"{config.provider_name} does not support vision")
        
        # Basic validation
        return config.validate()
    
    def get_template(self, provider_name: str) -> Optional[ConfigTemplate]:
        """Get configuration template for provider"""
        return self.templates.get(provider_name)
    
    def list_templates(self) -> List[str]:
        """List available configuration templates"""
        return list(self.templates.keys())


class ConfigManager:
    """Manages adapter configuration loading and creation"""
    
    def __init__(self):
        self.validator = ConfigValidator()
        self.env_loader = EnvironmentLoader()
        self.json_util = JSONUtilities()
    
    def create_config(
        self,
        provider_name: str,
        model_name: str = None,
        config_overrides: Dict[str, Any] = None,
        load_from_env: bool = True,
        **kwargs
    ) -> AdapterConfig:
        """Create adapter configuration"""
        # Get template
        template = self.validator.get_template(provider_name)
        
        # Start with template defaults
        config_data = {}
        if template:
            config_data.update({
                'model_name': model_name or template.default_model,
                'max_tokens': template.default_max_tokens,
                'temperature': template.default_temperature,
                'supports_streaming': template.supported_features.get('streaming', False),
                'supports_embeddings': template.supported_features.get('embeddings', False),
                'supports_vision': template.supported_features.get('vision', False),
                'supports_function_calling': template.supported_features.get('function_calling', False)
            })
            
            if template.base_url:
                config_data['base_url'] = template.base_url
        
        # Load from environment if requested
        if load_from_env:
            # Load API key
            api_key = self.env_loader.load_api_key(
                provider_name,
                template.api_key_env_var if template else None
            )
            if api_key:
                config_data['api_key'] = api_key
            
            # Load base URL
            base_url = self.env_loader.load_base_url(provider_name)
            if base_url:
                config_data['base_url'] = base_url
            
            # Load other config
            env_config = self.env_loader.load_model_config(provider_name)
            config_data.update(env_config)
        
        # Apply overrides
        if config_overrides:
            config_data.update(config_overrides)
        
        # Apply kwargs
        config_data.update(kwargs)
        
        # Ensure required fields
        config_data['provider_name'] = provider_name
        if not config_data.get('model_name'):
            if template:
                config_data['model_name'] = template.default_model
            else:
                raise AdapterConfigurationError(
                    "model_name is required",
                    provider=provider_name
                )
        
        # Create config
        config = AdapterConfig(**config_data)
        
        # Validate
        self.validator.validate_config(config)
        
        return config
    
    def load_config_from_file(self, file_path: str) -> AdapterConfig:
        """Load configuration from JSON file"""
        config_data = self.json_util.load_file(file_path)
        
        if not config_data:
            raise AdapterConfigurationError(f"Could not load config from {file_path}")
        
        return AdapterConfig(**config_data)
    
    def save_config_to_file(self, config: AdapterConfig, file_path: str) -> None:
        """Save configuration to JSON file"""
        config_data = asdict(config)
        self.json_util.save_file(config_data, file_path)
    
    def create_config_template_file(self, provider_name: str, file_path: str) -> None:
        """Create a configuration template file"""
        template = self.validator.get_template(provider_name)
        
        if not template:
            raise AdapterConfigurationError(f"No template found for {provider_name}")
        
        template_config = {
            'provider_name': template.provider_name,
            'model_name': template.default_model,
            'max_tokens': template.default_max_tokens,
            'temperature': template.default_temperature,
            'api_key': f"${{{template.api_key_env_var}}}" if template.api_key_env_var else None,
            'base_url': template.base_url,
            'supports_streaming': template.supported_features.get('streaming'),
            'supports_embeddings': template.supported_features.get('embeddings'),
            'supports_vision': template.supported_features.get('vision'),
            'supports_function_calling': template.supported_features.get('function_calling'),
            '_template_info': {
                'description': f"Configuration template for {provider_name}",
                'required_fields': template.required_config,
                'supported_features': template.supported_features
            }
        }
        
        self.json_util.save_file(template_config, file_path)
        logger.info(f"Created config template: {file_path}")
    
    def validate_config_file(self, file_path: str) -> bool:
        """Validate a configuration file"""
        try:
            config = self.load_config_from_file(file_path)
            self.validator.validate_config(config)
            return True
        except Exception as e:
            logger.error(f"Config validation failed for {file_path}: {e}")
            return False
    
    def get_config_summary(self, config: AdapterConfig) -> Dict[str, Any]:
        """Get a summary of configuration"""
        return {
            'provider': config.provider_name,
            'model': config.model_name,
            'has_api_key': bool(config.api_key),
            'base_url': config.base_url,
            'max_tokens': config.max_tokens,
            'temperature': config.temperature,
            'features': {
                'streaming': config.supports_streaming,
                'embeddings': config.supports_embeddings,
                'vision': config.supports_vision,
                'function_calling': config.supports_function_calling
            },
            'timeout': config.timeout,
            'max_retries': config.max_retries
        }


# Export all public classes
__all__ = [
    'ConfigValidator',
    'ConfigManager',
    'ConfigTemplate',
    'EnvironmentLoader'
]
