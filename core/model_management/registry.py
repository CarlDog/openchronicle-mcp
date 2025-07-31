"""
Registry management for OpenChronicle model configuration.

This module extracts and modernizes the registry loading functionality from the
monolithic ModelManager. It provides clean access to the sophisticated configuration
system including provider settings, content routing, performance tuning, and
intelligent routing capabilities.

Key Features:
- Centralized configuration loading from model_registry.json
- Provider-specific configuration access
- Content routing rules and fallback chains
- Performance limits and health check settings
- Intelligent routing configuration
- Future-ready for modular registry structure
"""

import json
import os
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

from utilities.logging_system import log_system_event, log_info, log_error

logger = logging.getLogger(__name__)


class RegistryManager:
    """
    Manages model registry configuration with clean separation of concerns.
    
    This class extracts the registry management functionality from ModelManager,
    providing a focused interface for configuration access. It supports the
    existing sophisticated registry structure while preparing for future
    modular registry organization.
    """
    
    def __init__(self, registry_path: str = "config/model_registry.json"):
        self.registry_path = registry_path
        self._registry: Optional[Dict[str, Any]] = None
        self._last_loaded: Optional[datetime] = None
        
        # Load registry on initialization
        self._load_registry()
    
    def _load_registry(self) -> None:
        """Load the complete registry from disk."""
        if not os.path.exists(self.registry_path):
            raise FileNotFoundError(f"Model registry not found at {self.registry_path}")
        
        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                self._registry = json.load(f)
            
            self._last_loaded = datetime.now()
            log_system_event("registry_loaded", f"Registry loaded from {self.registry_path}")
            log_info(f"Loaded registry with schema version {self._registry.get('schema_version', 'unknown')}")
            
        except Exception as e:
            log_error(f"Failed to load registry from {self.registry_path}: {e}")
            raise
    
    def reload_if_changed(self) -> bool:
        """Reload registry if the file has been modified."""
        try:
            file_mtime = datetime.fromtimestamp(os.path.getmtime(self.registry_path))
            if self._last_loaded and file_mtime > self._last_loaded:
                log_info("Registry file changed, reloading...")
                self._load_registry()
                return True
            return False
        except Exception as e:
            log_error(f"Error checking registry file modification time: {e}")
            return False
    
    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """
        Get provider-specific configuration from environment_config.
        
        Args:
            provider: Provider name (e.g., 'openai', 'anthropic', 'ollama')
            
        Returns:
            Provider configuration dictionary
            
        Raises:
            ValueError: If provider not found in registry
        """
        if not self._registry:
            raise RuntimeError("Registry not loaded")
        
        env_config = self._registry.get("environment_config", {})
        providers = env_config.get("providers", {})
        
        if provider not in providers:
            available = list(providers.keys())
            raise ValueError(f"Provider '{provider}' not found in registry. Available: {available}")
        
        return providers[provider]
    
    def get_available_providers(self) -> List[str]:
        """Get list of available provider names."""
        if not self._registry:
            return []
        
        env_config = self._registry.get("environment_config", {})
        providers = env_config.get("providers", {})
        return list(providers.keys())
    
    def get_fallback_chains(self) -> Dict[str, List[str]]:
        """Get all fallback chains."""
        if not self._registry:
            return {}
        
        return self._registry.get("fallback_chains", {})
    
    def get_provider_base_url(self, provider: str) -> str:
        """
        Get the resolved base URL for a provider.
        
        Implements the same logic as ModelManager.get_provider_base_url() but
        in a focused, registry-aware manner.
        """
        provider_config = self.get_provider_config(provider)
        
        base_url_env = provider_config.get("base_url_env")
        default_base_url = provider_config.get("default_base_url")
        
        # Check environment variable first
        if base_url_env:
            env_value = os.getenv(base_url_env)
            if env_value:
                log_info(f"Using environment override for {provider}: {env_value}")
                return env_value
        
        # Fall back to default URL from registry
        if default_base_url:
            return default_base_url
        
        raise ValueError(f"No base URL configured for provider '{provider}'")
    
    def get_model_configs(self, model_type: str = "text", enabled_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get all model configurations by type.
        
        Args:
            model_type: Type of models to retrieve ('text' or 'image')
            enabled_only: If True, only return enabled models
            
        Returns:
            List of model configuration dictionaries
        """
        if not self._registry:
            raise RuntimeError("Registry not loaded")
        
        model_section = f"{model_type}_models"
        if model_section not in self._registry:
            return []
        
        all_models = []
        models_section = self._registry[model_section]
        
        # Collect models from all priority groups
        for priority_group in models_section.values():
            if isinstance(priority_group, list):
                for model in priority_group:
                    if enabled_only and not model.get("enabled", True):
                        continue
                    
                    # Ensure type is set
                    model_copy = model.copy()
                    model_copy["type"] = model_type
                    all_models.append(model_copy)
        
        return all_models
    
    def get_content_routing_rules(self, content_type: str) -> Dict[str, Any]:
        """Get routing rules for specific content type."""
        if not self._registry:
            raise RuntimeError("Registry not loaded")
        
        content_routing = self._registry.get("content_routing", {})
        return content_routing.get(content_type, {})
    
    def get_fallback_chain(self, chain_name: str) -> List[str]:
        """Get fallback chain configuration."""
        if not self._registry:
            raise RuntimeError("Registry not loaded")
        
        fallback_chains = self._registry.get("fallback_chains", {})
        return fallback_chains.get(chain_name, [])
    
    def get_performance_limits(self, provider: str) -> Dict[str, Any]:
        """Get performance limits and rate limiting for provider."""
        if not self._registry:
            raise RuntimeError("Registry not loaded")
        
        performance_tuning = self._registry.get("performance_tuning", {})
        
        return {
            "concurrent_limit": performance_tuning.get("concurrent_limits", {}).get(provider, 3),
            "rate_limits": performance_tuning.get("rate_limits", {}).get(provider, {}),
            "health_check_interval": performance_tuning.get("health_check_intervals", {}).get(provider, 300)
        }
    
    def get_intelligent_routing_config(self) -> Dict[str, Any]:
        """Get intelligent routing configuration."""
        if not self._registry:
            raise RuntimeError("Registry not loaded")
        
        global_settings = self._registry.get("global_settings", {})
        return global_settings.get("intelligent_routing", {})
    
    def get_global_defaults(self) -> Dict[str, Any]:
        """Get global default configuration values."""
        if not self._registry:
            raise RuntimeError("Registry not loaded")
        
        return self._registry.get("defaults", {})
    
    def get_global_default(self, key: str, fallback: Any = None) -> Any:
        """Get a specific global default value."""
        defaults = self.get_global_defaults()
        return defaults.get(key, fallback)
    
    def is_provider_enabled(self, provider: str) -> bool:
        """Check if a provider is enabled in the registry."""
        try:
            provider_config = self.get_provider_config(provider)
            return provider_config.get("enabled", True)
        except ValueError:
            return False
    
    def get_validation_rules(self, provider: str) -> Dict[str, Any]:
        """Get validation rules for a provider."""
        provider_config = self.get_provider_config(provider)
        return provider_config.get("validation", {})
    
    def get_health_check_config(self, provider: str) -> Dict[str, Any]:
        """Get health check configuration for a provider."""
        provider_config = self.get_provider_config(provider)
        validation = provider_config.get("validation", {})
        
        return {
            "enabled": provider_config.get("health_check_enabled", True),
            "endpoint": validation.get("health_endpoint", "/health"),
            "method": validation.get("method", "GET"),
            "timeout": provider_config.get("timeout", 30),
            "interval": self.get_performance_limits(provider).get("health_check_interval", 300)
        }
    
    def get_registry_metadata(self) -> Dict[str, Any]:
        """Get registry metadata and schema information."""
        if not self._registry:
            raise RuntimeError("Registry not loaded")
        
        return {
            "schema_version": self._registry.get("schema_version", "unknown"),
            "metadata": self._registry.get("metadata", {}),
            "last_loaded": self._last_loaded.isoformat() if self._last_loaded else None,
            "registry_path": self.registry_path,
            "providers_count": len(self._registry.get("environment_config", {}).get("providers", {})),
            "text_models_count": len(self.get_model_configs("text", enabled_only=False)),
            "image_models_count": len(self.get_model_configs("image", enabled_only=False))
        }
    
    def validate_registry_structure(self) -> List[str]:
        """
        Validate registry structure and return list of issues.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        if not self._registry:
            return ["Registry not loaded"]
        
        issues = []
        
        # Check required top-level sections
        required_sections = ["environment_config", "defaults", "global_settings"]
        for section in required_sections:
            if section not in self._registry:
                issues.append(f"Missing required section: {section}")
        
        # Check provider configurations
        env_config = self._registry.get("environment_config", {})
        providers = env_config.get("providers", {})
        
        for provider_name, provider_config in providers.items():
            if not isinstance(provider_config, dict):
                issues.append(f"Provider {provider_name} config is not a dictionary")
                continue
            
            # Check required provider fields
            if "default_base_url" not in provider_config and "base_url_env" not in provider_config:
                issues.append(f"Provider {provider_name} missing both default_base_url and base_url_env")
        
        return issues
