"""
Dynamic Registry Manager for OpenChronicle Model Configuration

This module implements dynamic discovery and management of AI provider
configurations using individual JSON files in config/models/ directory.

Key Features:
- Content-driven processing (uses "provider" field, not filename)
- Runtime provider addition/removal
- Multi-model support per provider
- Schema validation and error handling
- Cross-platform safe filenames
- Dynamic provider discovery
- User freedom in naming files
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timezone

from core.shared.logging_system import log_system_event, log_error, log_info, log_warning
from .schema_validation import (
    RegistryValidator, 
    SchemaValidationError, 
    ModelRegistrySchema,
    ProviderConfig,
    validate_registry_config,
    validate_provider_config
)

# UTC for consistent timezone handling
UTC = timezone.utc


class ConfigurationError(Exception):
    """Raised when configuration validation or loading fails."""
    pass


class ProviderNotFoundError(Exception):
    """Raised when a requested provider configuration is not found."""
    pass


class RegistryValidationError(Exception):
    """Raised when registry schema validation fails."""
    pass


class RegistryManager:
    """
    Manages dynamic discovery and loading of AI provider configurations.
    
    This class implements the core of Phase 2.0's dynamic configuration system,
    providing content-driven discovery of provider configurations stored in
    individual JSON files.
    """
    
    def __init__(self, models_dir: str = "config/models/", settings_file: str = "config/registry_settings.json"):
        """
        Initialize the dynamic registry manager.
        
        Args:
            models_dir: Directory containing individual provider config files
            settings_file: Path to global registry settings
        """
        self.models_dir = Path(models_dir)
        self.settings_file = Path(settings_file)
        self.providers = {}
        self.model_configs = {}
        self.global_settings = {}
        self.last_scan_time = None
        
        # Initialize schema validator
        self.validator = RegistryValidator()
        
        # Ensure models directory exists
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Load initial configuration
        self._load_global_settings()
        self.discover_providers()
        
        log_system_event("dynamic_registry_init", f"Dynamic registry manager initialized with {len(self.providers)} providers")
    
    def _load_global_settings(self) -> Dict[str, Any]:
        """Load global registry settings from configuration file."""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    self.global_settings = json.load(f)
                log_info(f"Loaded global settings from {self.settings_file}")
            else:
                # Create default global settings
                self.global_settings = self._create_default_global_settings()
                self._save_global_settings()
                log_info(f"Created default global settings at {self.settings_file}")
            
            return self.global_settings
            
        except Exception as e:
            log_error(f"Failed to load global settings: {e}")
            self.global_settings = self._create_default_global_settings()
            return self.global_settings
    
    def _create_default_global_settings(self) -> Dict[str, Any]:
        """Create default global registry settings."""
        return {
            "schema_version": "3.1.0",
            "metadata": {
                "name": "OpenChronicle Dynamic Model Registry",
                "description": "Dynamic configuration system for AI models and providers",
                "last_updated": datetime.now(UTC).isoformat(),
                "maintainer": "OpenChronicle Team"
            },
            "defaults": {
                "text_model": "transformers",
                "analyzer_model": "transformers", 
                "image_model": "openai_dalle"
            },
            "global_settings": {
                "enable_fallbacks": True,
                "enable_health_checks": True,
                "enable_logging": True,
                "intelligent_routing": {
                    "enabled": True,
                    "learning_mode": True,
                    "user_feedback_weight": 0.3,
                    "performance_history_days": 7,
                    "recommendation_confidence_threshold": 0.75,
                    "auto_switch_on_failure": True,
                    "preserve_user_overrides": True,
                    "runtime_state_file": "config/model_runtime_state.json"
                }
            }
        }
    
    def _save_global_settings(self):
        """Save global settings to configuration file with automatic backup."""
        try:
            # Create backup before saving
            if self.settings_file.exists():
                backup_path = self._create_settings_backup()
                if backup_path:
                    log_info(f"Created settings backup: {backup_path.name}",
                            context_tags=["registry", "backup"])
            
            # Save current settings
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.global_settings, f, indent=2, ensure_ascii=False)
            
            log_info(f"Saved global settings to {self.settings_file}",
                    context_tags=["registry", "save"])
            log_system_event("registry_settings_saved", 
                           "Global registry settings saved with backup",
                           {"settings_file": str(self.settings_file)})
                           
        except Exception as e:
            log_error(f"Failed to save global settings: {e}",
                     context_tags=["registry", "error"])
    
    def _create_settings_backup(self) -> Optional[Path]:
        """Create backup of current settings file."""
        try:
            backup_dir = self.settings_file.parent / "backups"
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"registry_settings_{timestamp}.json"
            backup_path = backup_dir / backup_filename
            
            # Copy current settings to backup
            import shutil
            shutil.copy2(self.settings_file, backup_path)
            
            return backup_path
            
        except Exception as e:
            log_warning(f"Failed to create settings backup: {e}",
                       context_tags=["registry", "backup", "error"])
            return None
    
    def discover_providers(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Scan models directory for provider JSON files and group by provider.
        
        This is the core of content-driven discovery - we examine the "provider"
        field in each JSON file to determine grouping, not the filename.
        
        Returns:
            Dictionary mapping provider names to lists of their model configurations
        """
        try:
            discovered_providers = {}
            discovered_models = {}
            
            if not self.models_dir.exists():
                log_warning(f"Models directory {self.models_dir} does not exist")
                return discovered_providers
            
            # Scan all JSON files in models directory
            for json_file in self.models_dir.glob("*.json"):
                try:
                    model_config = self._load_model_config(json_file)
                    
                    if not model_config:
                        continue
                    
                    # Content-driven processing: use "provider" field, not filename
                    provider_name = model_config.get("provider")
                    if not provider_name:
                        log_warning(f"Config file {json_file} missing 'provider' field, skipping")
                        continue
                    
                    # Group models by provider
                    if provider_name not in discovered_providers:
                        discovered_providers[provider_name] = []
                    
                    # Add model configuration to provider group
                    model_config["config_file"] = str(json_file)
                    model_config["config_name"] = json_file.stem
                    discovered_providers[provider_name].append(model_config)
                    
                    # Also store by config name for direct access
                    discovered_models[json_file.stem] = model_config
                    
                except Exception as e:
                    log_error(f"Failed to process config file {json_file}: {e}")
                    continue
            
            # Update internal state
            self.providers = discovered_providers
            self.model_configs = discovered_models
            self.last_scan_time = datetime.now(UTC)
            
            # Log discovery results
            total_models = sum(len(models) for models in discovered_providers.values())
            log_system_event(
                "provider_discovery_complete",
                f"Discovered {len(discovered_providers)} providers with {total_models} model configurations"
            )
            
            return discovered_providers
            
        except Exception as e:
            log_error(f"Failed to discover providers: {e}")
            return {}
    
    def _load_model_config(self, config_file: Path) -> Optional[Dict[str, Any]]:
        """
        Load and validate a single model configuration file.
        
        Args:
            config_file: Path to the JSON configuration file
            
        Returns:
            Dictionary containing model configuration, or None if invalid
        """
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Basic validation
            if not self._validate_model_config(config, config_file):
                return None
            
            return config
            
        except json.JSONDecodeError as e:
            log_error(f"Invalid JSON in {config_file}: {e}")
            return None
        except Exception as e:
            log_error(f"Failed to load config {config_file}: {e}")
            return None
    
    def _validate_model_config(self, config: Dict[str, Any], config_file: Path) -> bool:
        """
        Validate that a model configuration contains required fields using pydantic schema.
        
        Args:
            config: Configuration dictionary to validate
            config_file: Path to config file (for error reporting)
            
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Use pydantic schema validation for comprehensive validation
            validated_config = validate_provider_config(config)
            log_info(f"Config {config_file} passed schema validation")
            return True
            
        except SchemaValidationError as e:
            log_error(f"Config {config_file} failed schema validation: {e}")
            return False
        except Exception as e:
            log_error(f"Unexpected error validating config {config_file}: {e}")
            return False
    
    def get_provider_models(self, provider_name: str) -> List[Dict[str, Any]]:
        """
        Get all model configurations for a specific provider.
        
        Args:
            provider_name: Name of the provider
            
        Returns:
            List of model configurations for the provider
            
        Raises:
            ValueError: If provider is not found
        """
        if provider_name not in self.providers:
            raise ValueError(f"Provider '{provider_name}' not found")
        
        return self.providers[provider_name]
    
    def get_model_config(self, config_name: str) -> Dict[str, Any]:
        """
        Get a specific model configuration by its config name (filename without extension).
        
        Args:
            config_name: Name of the configuration file (without .json extension)
            
        Returns:
            Model configuration dictionary
            
        Raises:
            ValueError: If configuration is not found
        """
        if config_name not in self.model_configs:
            raise ValueError(f"Model configuration '{config_name}' not found")
        
        return self.model_configs[config_name]
    
    def get_available_providers(self) -> List[str]:
        """Get list of all discovered provider names."""
        return list(self.providers.keys())
    
    def get_enabled_providers(self) -> List[str]:
        """Get list of provider names that have at least one enabled model."""
        enabled_providers = []
        
        for provider_name, models in self.providers.items():
            if any(model.get("enabled", False) for model in models):
                enabled_providers.append(provider_name)
        
        return enabled_providers
    
    def add_model_config(self, config_name: str, config: Dict[str, Any]) -> bool:
        """
        Add a new model configuration at runtime.
        
        Args:
            config_name: Name for the configuration file (without .json extension)
            config: Model configuration dictionary
            
        Returns:
            True if configuration was added successfully, False otherwise
        """
        try:
            # Validate configuration
            if not self._validate_model_config(config, Path(config_name)):
                return False
            
            # Create config file path
            config_path = self.models_dir / f"{config_name}.json"
            
            # Check if file already exists
            if config_path.exists():
                log_warning(f"Configuration file {config_path} already exists, will overwrite")
            
            # Save configuration to file
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            # Re-discover providers to include new configuration
            self.discover_providers()
            
            log_system_event("model_config_added", f"Added model configuration: {config_name}")
            return True
            
        except Exception as e:
            log_error(f"Failed to add model configuration {config_name}: {e}")
            return False
    
    def remove_model_config(self, config_name: str) -> bool:
        """
        Remove a model configuration at runtime.
        
        Args:
            config_name: Name of the configuration to remove (without .json extension)
            
        Returns:
            True if configuration was removed successfully, False otherwise
        """
        try:
            config_path = self.models_dir / f"{config_name}.json"
            
            if not config_path.exists():
                log_warning(f"Configuration file {config_path} does not exist")
                return False
            
            # Remove configuration file
            config_path.unlink()
            
            # Re-discover providers to update internal state
            self.discover_providers()
            
            log_system_event("model_config_removed", f"Removed model configuration: {config_name}")
            return True
            
        except Exception as e:
            log_error(f"Failed to remove model configuration {config_name}: {e}")
            return False
    
    def refresh_providers(self) -> bool:
        """
        Refresh provider discovery (useful for detecting externally added configs).
        
        Returns:
            True if refresh was successful, False otherwise
        """
        try:
            log_info("Refreshing provider discovery...")
            self.discover_providers()
            return True
        except Exception as e:
            log_error(f"Failed to refresh providers: {e}")
            return False
    
    def get_fallback_chain(self, provider_name: str) -> List[str]:
        """
        Get fallback chain for a provider based on global settings and provider configs.
        
        Args:
            provider_name: Name of the primary provider
            
        Returns:
            List of provider names in fallback order
        """
        try:
            fallback_chain = [provider_name]
            
            # Check if provider has specific fallback configuration
            if provider_name in self.providers:
                provider_models = self.providers[provider_name]
                if provider_models:
                    # Use fallback chain from first model config (they should be consistent)
                    model_fallbacks = provider_models[0].get("fallback_chain", [])
                    fallback_chain.extend(model_fallbacks)
            
            # Add global fallbacks if enabled
            global_settings = self.global_settings.get("global_settings", {})
            if global_settings.get("enable_fallbacks", True):
                # Add all enabled providers as ultimate fallbacks (excluding primary)
                enabled_providers = [p for p in self.get_enabled_providers() if p != provider_name]
                for provider in enabled_providers:
                    if provider not in fallback_chain:
                        fallback_chain.append(provider)
            
            return fallback_chain
            
        except Exception as e:
            log_error(f"Failed to get fallback chain for {provider_name}: {e}")
            return [provider_name]  # Return at least the primary provider
    
    def get_status(self) -> str:
        """Get registry status."""
        try:
            provider_count = len(self.providers)
            config_count = len(self.model_configs)
            if provider_count > 0 and config_count > 0:
                return f"loaded ({provider_count} providers, {config_count} configs)"
            elif provider_count > 0:
                return f"loaded ({provider_count} providers, no configs)"
            else:
                return "empty"
        except Exception:
            return "error"
    
    def validate_registry(self, registry_file: Optional[Union[str, Path]] = None) -> bool:
        """
        Validate the complete registry configuration using pydantic schema.
        
        Args:
            registry_file: Optional path to registry file to validate. 
                          If None, validates the main .copilot/config/model_registry.json
            
        Returns:
            True if validation passes, False otherwise
        """
        try:
            if registry_file is None:
                # Check the main registry file
                registry_file = Path(".copilot/config/model_registry.json")
            else:
                registry_file = Path(registry_file)
            
            if not registry_file.exists():
                log_warning(f"Registry file not found: {registry_file}")
                return False
            
            # Validate using pydantic schema
            validated_registry = self.validator.validate_registry_file(registry_file)
            log_info(f"Registry validation successful: {registry_file}")
            return True
            
        except SchemaValidationError as e:
            log_error(f"Registry validation failed: {e}")
            return False
        except Exception as e:
            log_error(f"Unexpected error during registry validation: {e}")
            return False
    
    def create_backup(self, file_path: Union[str, Path]) -> Optional[Path]:
        """
        Create backup of configuration file before modification.
        
        Args:
            file_path: Path to file to backup
            
        Returns:
            Path to backup file, or None if backup failed
        """
        try:
            backup_path = self.validator.create_backup(file_path)
            return backup_path
        except Exception as e:
            log_error(f"Failed to create backup: {e}")
            return None
    
    def safe_save_config(self, config_name: str, config: Dict[str, Any]) -> bool:
        """
        Safely save provider configuration with validation and backup.
        
        Args:
            config_name: Name of the configuration file
            config: Configuration data to save
            
        Returns:
            True if save was successful, False otherwise
        """
        try:
            # Validate configuration first
            validated_config = validate_provider_config(config)
            
            # Create file path
            config_file = self.models_dir / f"{config_name}.json"
            
            # Save using validator (includes backup)
            self.validator.safe_save_provider(validated_config, config_file)
            
            # Refresh providers to pick up changes
            self.refresh_providers()
            
            log_info(f"Configuration saved successfully: {config_file}")
            return True
            
        except SchemaValidationError as e:
            log_error(f"Configuration validation failed: {e}")
            return False
        except Exception as e:
            log_error(f"Failed to save configuration: {e}")
            return False
    
    @property
    def models_dir_path(self) -> str:
        """Return the models directory path for compatibility."""
        return str(self.models_dir)


# Convenience function for backward compatibility
def load_dynamic_registry(models_dir: str = "config/models/") -> RegistryManager:
    """
    Load the dynamic registry manager with default settings.
    
    Args:
        models_dir: Directory containing model configuration files
        
    Returns:
        Initialized RegistryManager instance
    """
    return RegistryManager(models_dir)


# Export main classes
__all__ = [
    "RegistryManager",
    "ConfigurationError", 
    "ProviderNotFoundError",
    "load_dynamic_registry"
]
