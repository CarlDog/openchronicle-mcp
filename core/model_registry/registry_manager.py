"""
Registry management for OpenChronicle model configuration.

This module consolidates registry loading functionality with clean separation of concerns.
It provides centralized access to the sophisticated configuration system including
provider settings, content routing, performance tuning, and intelligent routing capabilities.

Following OpenChronicle naming convention: registry_manager.py

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
    
    This class consolidates registry management functionality, providing a focused
    interface for configuration access. It supports the existing sophisticated
    registry structure while maintaining clean organizational standards.
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
            
            schema_version = self._registry.get('schema_version', 'unknown') if self._registry else 'unknown'
            log_info(f"Loaded registry with schema version {schema_version}")
            
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
    
    def get_model_config(self, provider: str, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Get model-specific configuration.
        
        Args:
            provider: Provider name
            model_name: Model name
            
        Returns:
            Model configuration dictionary or None if not found
        """
        try:
            provider_config = self.get_provider_config(provider)
            models = provider_config.get("models", {})
            return models.get(model_name)
        except Exception as e:
            log_error(f"Error getting model config for {provider}/{model_name}: {e}")
            return None
    
    def get_validation_rules(self, provider: str) -> Optional[Dict[str, Any]]:
        """
        Get validation rules for a provider.
        
        Args:
            provider: Provider name
            
        Returns:
            Validation rules dictionary or None if not found
        """
        try:
            provider_config = self.get_provider_config(provider)
            return provider_config.get("validation")
        except Exception:
            return None
    
    def get_health_check_config(self, provider: str) -> Optional[Dict[str, Any]]:
        """
        Get health check configuration for a provider.
        
        Args:
            provider: Provider name
            
        Returns:
            Health check configuration or None if not found
        """
        try:
            provider_config = self.get_provider_config(provider)
            return provider_config.get("health_check")
        except Exception:
            return None
    
    def get_rate_limit_config(self, provider: str) -> Optional[Dict[str, Any]]:
        """
        Get rate limiting configuration for a provider.
        
        Args:
            provider: Provider name
            
        Returns:
            Rate limit configuration or None if not found
        """
        try:
            provider_config = self.get_provider_config(provider)
            return provider_config.get("rate_limits")
        except Exception:
            return None
    
    def get_fallback_chain(self, provider: str) -> List[str]:
        """
        Get fallback chain for a provider.
        
        Args:
            provider: Provider name
            
        Returns:
            List of provider names in fallback order
        """
        try:
            provider_config = self.get_provider_config(provider)
            fallback_chain = provider_config.get("fallback_chain", [])
            
            # Ensure primary provider is first in chain
            if provider not in fallback_chain:
                fallback_chain.insert(0, provider)
            
            return fallback_chain
        except Exception:
            return [provider]  # Return single provider as fallback
    
    def get_content_routing_rules(self) -> Optional[Dict[str, Any]]:
        """
        Get content routing rules from registry.
        
        Returns:
            Content routing rules or None if not found
        """
        if not self._registry:
            return None
        
        return self._registry.get("content_routing")
    
    def get_routing_rule_for_content(self, content_type: str) -> Optional[Dict[str, Any]]:
        """
        Get routing rule for specific content type.
        
        Args:
            content_type: Content type to route
            
        Returns:
            Routing rule or None if not found
        """
        routing_rules = self.get_content_routing_rules()
        if not routing_rules:
            return None
        
        return routing_rules.get("rules", {}).get(content_type)
    
    def get_available_providers(self) -> List[str]:
        """
        Get list of all available providers in registry.
        
        Returns:
            List of provider names
        """
        if not self._registry:
            return []
        
        env_config = self._registry.get("environment_config", {})
        providers = env_config.get("providers", {})
        return list(providers.keys())
    
    def get_available_models(self, provider: str) -> List[str]:
        """
        Get list of available models for a provider.
        
        Args:
            provider: Provider name
            
        Returns:
            List of model names
        """
        try:
            provider_config = self.get_provider_config(provider)
            models = provider_config.get("models", {})
            return list(models.keys())
        except Exception:
            return []
    
    def validate_provider_model(self, provider: str, model_name: str) -> bool:
        """
        Validate that a provider/model combination is configured.
        
        Args:
            provider: Provider name
            model_name: Model name
            
        Returns:
            True if valid combination
        """
        try:
            available_models = self.get_available_models(provider)
            return model_name in available_models
        except Exception:
            return False
    
    def get_registry_info(self) -> Dict[str, Any]:
        """
        Get registry information and statistics.
        
        Returns:
            Registry information dictionary
        """
        if not self._registry:
            return {"status": "not_loaded"}
        
        providers = self.get_available_providers()
        total_models = sum(len(self.get_available_models(p)) for p in providers)
        
        return {
            "status": "loaded",
            "schema_version": self._registry.get("schema_version", "unknown"),
            "last_loaded": self._last_loaded.isoformat() if self._last_loaded else None,
            "registry_path": self.registry_path,
            "total_providers": len(providers),
            "total_models": total_models,
            "providers": providers,
            "has_content_routing": bool(self.get_content_routing_rules()),
            "file_size": os.path.getsize(self.registry_path) if os.path.exists(self.registry_path) else 0
        }
    
    def get_status(self) -> str:
        """
        Get simple status string.
        
        Returns:
            Status string: 'loaded', 'not_loaded', or 'error'
        """
        if not self._registry:
            return "not_loaded"
        try:
            # Quick validation
            env_config = self._registry.get("environment_config", {})
            providers = env_config.get("providers", {})
            return "loaded" if providers else "error"
        except Exception:
            return "error"
