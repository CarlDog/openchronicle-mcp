#!/usr/bin/env python3
"""
Phase 3.0 Day 2: LifecycleManager Component

Extracted from ModelManager to handle adapter initialization, validation,
and lifecycle management. Provides clean separation of concerns for adapter
state management and prerequisites validation.

File: core/model_management/lifecycle_manager.py
"""

import asyncio
import importlib
import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pathlib import Path

# Import system components
from utilities.logging_system import log_info, log_error, log_system_event

UTC = timezone.utc

try:
    import httpx
except ImportError:
    httpx = None


class LifecycleManager:
    """
    Manages adapter lifecycle: initialization, validation, and state tracking.
    
    Extracted from ModelManager to provide focused responsibility for adapter
    lifecycle management with clean interfaces and comprehensive error handling.
    """
    
    def __init__(self, adapters: Dict[str, Any], config: Dict[str, Any], global_config: Dict[str, Any] = None):
        """
        Initialize the LifecycleManager.
        
        Args:
            adapters: Reference to the main adapters dictionary
            config: Adapter configuration dictionary
            global_config: Global configuration with provider settings
        """
        self.adapters = adapters
        self.config = config
        self.global_config = global_config or {}
        
        # State tracking
        self.adapter_status = {}
        self.disabled_adapters = {}
        self.api_key_status = {}
        
        log_system_event("lifecycle_manager_initialized", "Adapter lifecycle management ready")
    
    async def initialize_adapter(self, name: str, max_retries: int = 2, graceful_degradation: bool = True) -> bool:
        """
        Initialize a specific adapter with enhanced error handling.
        
        Args:
            name: Adapter name to initialize
            max_retries: Number of retry attempts for transient failures
            graceful_degradation: If True, continue execution even if adapter fails
            
        Returns:
            bool: True if successful, False if failed (when graceful_degradation=True)
            
        Raises:
            ValueError: If adapter not found in configuration (only when graceful_degradation=False)
            RuntimeError: If initialization fails critically (only when graceful_degradation=False)
        """
        # Validate adapter exists in configuration
        if name not in self.config["adapters"]:
            # Check if adapter exists in global registry but is disabled
            disabled_reason = self._check_if_adapter_disabled(name)
            if disabled_reason:
                error_msg = disabled_reason
            else:
                # Check if it's a provider that needs to be in the model registry
                available_adapters = list(self.config["adapters"].keys())
                similar_adapters = [a for a in available_adapters if name.lower() in a.lower() or a.lower() in name.lower()]
                
                error_msg = f"Adapter '{name}' not found in configuration."
                if similar_adapters:
                    error_msg += f" Did you mean: {', '.join(similar_adapters)}?"
                else:
                    error_msg += f" Available adapters: {', '.join(sorted(available_adapters))}"
            
            log_system_event("adapter_initialization_error", error_msg)
            
            # Store the failure reason for better error reporting later
            self.disabled_adapters[name] = {
                "type": "unknown",
                "reason": error_msg,
                "can_enable_later": True,
                "recommendation": "Check configuration or enable in model registry",
                "last_check": datetime.now(UTC).isoformat()
            }
            
            if graceful_degradation:
                log_error(f"Skipping missing adapter: {name}")
                return False
            else:
                raise ValueError(error_msg)
        
        adapter_config = self.config["adapters"][name]
        adapter_type = adapter_config.get("type", "unknown")
        
        log_system_event("adapter_initialization", f"Initializing {adapter_type} adapter: {name}")
        
        # Attempt initialization with retry logic
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                # Pre-initialization validation with enhanced API key checking
                validation_result = self._validate_adapter_prerequisites(name, adapter_config, adapter_type)
                if not validation_result["valid"]:
                    # Track disabled adapter with detailed information
                    self.disabled_adapters[name] = {
                        "type": adapter_type,
                        "reason": validation_result["reason"],
                        "can_enable_later": validation_result.get("can_enable_later", True),
                        "recommendation": validation_result.get("recommendation", "Check configuration"),
                        "last_check": datetime.now(UTC).isoformat(),
                        "config": adapter_config
                    }
                    
                    # Update API key status if applicable
                    if adapter_type in ["openai", "anthropic", "gemini", "groq", "cohere", "mistral"]:
                        self.api_key_status[adapter_type] = {
                            "available": False,
                            "reason": validation_result["reason"],
                            "recommendation": validation_result.get("recommendation", ""),
                            "last_validated": datetime.now(UTC).isoformat()
                        }
                    
                    if graceful_degradation:
                        log_error(f"Skipping {name} due to failed prerequisites: {validation_result['reason']}")
                        log_system_event("adapter_initialization_skipped", f"Skipped {name}: {validation_result['reason']}")
                        return False
                    else:
                        raise RuntimeError(f"Adapter prerequisites failed: {validation_result['reason']}")
                else:
                    # Track successful validation
                    if adapter_type in ["openai", "anthropic", "gemini", "groq", "cohere", "mistral"]:
                        self.api_key_status[adapter_type] = {
                            "available": True,
                            "reason": "API key validated successfully",
                            "recommendation": f"{adapter_type.title()} adapter ready for use",
                            "last_validated": datetime.now(UTC).isoformat()
                        }
                
                # Create adapter instance
                adapter = self._create_adapter_instance(adapter_type, adapter_config)
                
                # Initialize with timeout protection
                initialization_timeout = adapter_config.get("initialization_timeout", 30.0)
                success = await asyncio.wait_for(
                    adapter.initialize(), 
                    timeout=initialization_timeout
                )
                
                if success:
                    self.adapters[name] = adapter
                    
                    # Track successful adapter status
                    self.adapter_status[name] = {
                        "type": adapter_type,
                        "status": "active",
                        "initialized_at": datetime.now(UTC).isoformat(),
                        "model_name": adapter_config.get("model_name", name),
                        "description": adapter_config.get("description", f"{adapter_type} adapter"),
                        "supports_nsfw": adapter_config.get("supports_nsfw", False),
                        "content_types": adapter_config.get("content_types", ["general"])
                    }
                    
                    # Remove from disabled adapters if it was there
                    if name in self.disabled_adapters:
                        del self.disabled_adapters[name]
                    
                    log_system_event("adapter_initialization_success", f"Successfully initialized {adapter_type} adapter: {name}")
                    return True
                else:
                    raise RuntimeError(f"Adapter initialization returned False")
                    
            except asyncio.TimeoutError as e:
                last_exception = e
                error_msg = f"Timeout initializing {adapter_type} adapter {name} (attempt {attempt + 1}/{max_retries + 1})"
                log_error(error_msg)
                log_system_event("adapter_initialization_timeout", error_msg)
                
            except ImportError as e:
                # Dependencies missing - don't retry
                error_msg = f"Missing dependencies for {adapter_type} adapter {name}: {e}"
                log_error(error_msg)
                log_system_event("adapter_initialization_dependency_error", error_msg)
                if graceful_degradation:
                    return False
                else:
                    raise RuntimeError(error_msg)
                    
            except (ConnectionError, OSError) as e:
                # Network/connection issues - retry (handle httpx.ConnectError if available)
                if httpx and hasattr(httpx, 'ConnectError') and isinstance(e, httpx.ConnectError):
                    pass  # This is also a connection error
                last_exception = e
                error_msg = f"Connection error initializing {adapter_type} adapter {name} (attempt {attempt + 1}/{max_retries + 1}): {e}"
                log_error(error_msg)
                log_system_event("adapter_initialization_connection_error", error_msg)
                
                if attempt < max_retries:
                    # Exponential backoff for retries
                    wait_time = 2 ** attempt
                    log_info(f"Retrying {name} initialization in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                # Other errors - handle based on graceful_degradation setting
                last_exception = e
                error_msg = f"Error initializing {adapter_type} adapter {name}: {e}"
                log_error(error_msg)
                log_system_event("adapter_initialization_error", error_msg)
                
                # For unknown errors, only retry if it might be transient
                if attempt < max_retries and self._is_potentially_transient_error(e):
                    wait_time = 1 + attempt
                    log_info(f"Retrying {name} initialization in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    break
        
        # All attempts failed
        final_error_msg = f"Failed to initialize {adapter_type} adapter {name} after {max_retries + 1} attempts"
        if last_exception:
            final_error_msg += f". Last error: {last_exception}"
            
        log_system_event("adapter_initialization_failed", final_error_msg)
        
        if graceful_degradation:
            log_error(f"Continuing without {name} adapter")
            return False
        else:
            raise RuntimeError(final_error_msg)
    
    async def initialize_adapter_safe(self, name: str) -> bool:
        """Safe wrapper for adapter initialization that always uses graceful degradation."""
        try:
            return await self.initialize_adapter(name, graceful_degradation=True)
        except Exception as e:
            log_error(f"Safe initialization failed for {name}: {e}")
            return False
    
    def add_model_config(self, name: str, config: Dict[str, Any], enabled: bool = True) -> bool:
        """Add a new model configuration dynamically to the registry."""
        try:
            registry_file = os.path.join("config", "model_registry.json")
            
            # Load existing registry or create new one
            if os.path.exists(registry_file):
                with open(registry_file, "r", encoding="utf-8") as f:
                    registry = json.load(f)
            else:
                # Create a basic registry structure
                registry = {
                    "metadata": {
                        "name": "OpenChronicle Model Registry",
                        "description": "Centralized configuration for all AI models and providers",
                        "maintainer": "OpenChronicle Team"
                    },
                    "defaults": {
                        "text_model": "transformers",
                        "image_model": "openai_dalle"
                    },
                    "text_models": {
                        "testing": []
                    },
                    "image_models": {
                        "testing": []
                    },
                    "content_routing": {
                        "nsfw_content": {"allowed_models": ["transformers"], "default_model": "transformers"},
                        "safe_content": {"allowed_models": ["transformers"], "default_model": "transformers"}
                    },
                    "fallback_chains": {
                        "transformers": ["transformers"]
                    }
                }
            
            # Prepare model entry
            model_entry = {
                "name": name,
                "enabled": enabled,
                **config  # Include all config fields in the model entry
            }
            
            # Determine if this is a text or image model
            model_type = config.get("type", "text")
            is_image_model = (model_type == "image" or 
                            name.endswith("_image") or 
                            name.endswith("_dalle") or 
                            "image" in config.get("content_types", []))
            
            # Add to appropriate section
            if is_image_model:
                if "image_models" not in registry:
                    registry["image_models"] = {"testing": []}
                if "testing" not in registry["image_models"]:
                    registry["image_models"]["testing"] = []
                
                # Check if model already exists
                existing_models = registry["image_models"]["testing"]
                for i, existing_model in enumerate(existing_models):
                    if existing_model["name"] == name:
                        existing_models[i] = model_entry
                        break
                else:
                    existing_models.append(model_entry)
            else:
                if "text_models" not in registry:
                    registry["text_models"] = {"testing": []}
                if "testing" not in registry["text_models"]:
                    registry["text_models"]["testing"] = []
                
                # Check if model already exists
                existing_models = registry["text_models"]["testing"]
                for i, existing_model in enumerate(existing_models):
                    if existing_model["name"] == name:
                        existing_models[i] = model_entry
                        break
                else:
                    existing_models.append(model_entry)
            
            # Add to runtime configuration
            if "adapters" not in self.config:
                self.config["adapters"] = {}
            self.config["adapters"][name] = config
            
            # Update fallback chains if needed
            if "fallback_chains" not in registry:
                registry["fallback_chains"] = {}
            if name not in registry["fallback_chains"]:
                registry["fallback_chains"][name] = [name]
            
            # Save updated registry
            with open(registry_file, "w", encoding="utf-8") as f:
                json.dump(registry, f, indent=2, ensure_ascii=False)
            
            log_system_event("model_config_added", f"Added model configuration: {name}")
            return True
            
        except Exception as e:
            log_error(f"Failed to add model config {name}: {e}")
            return False
    
    def get_adapter_status(self, name: str) -> Optional[Dict[str, Any]]:
        """Get status information for a specific adapter."""
        return self.adapter_status.get(name)
    
    def get_disabled_adapters(self) -> Dict[str, Any]:
        """Get information about disabled adapters."""
        return self.disabled_adapters.copy()
    
    def get_api_key_status(self) -> Dict[str, Any]:
        """Get API key validation status for all providers."""
        return self.api_key_status.copy()
    
    def _check_if_adapter_disabled(self, adapter_name: str) -> Optional[str]:
        """
        Check if an adapter exists in the global registry but is disabled.
        
        Returns:
            Optional[str]: Reason why adapter is disabled, None if not found
        """
        # Check if we have global registry information
        if not self.global_config:
            return None
        
        # Look through both text and image models
        for model_category in ["text_models", "image_models"]:
            models_config = self.global_config.get(model_category, {})
            for category, models in models_config.items():
                for model in models:
                    if model.get("name") == adapter_name:
                        if not model.get("enabled", True):
                            return f"Adapter '{adapter_name}' is disabled in global model registry"
        
        return None
    
    def _validate_adapter_prerequisites(self, name: str, adapter_config: Dict[str, Any], adapter_type: str) -> Dict[str, Any]:
        """
        Enhanced validation with smart API key validation and graceful skipping.
        
        Returns:
            Dict with 'valid' (bool), 'reason' (str), 'can_enable_later' (bool), and 'recommendation' (str) keys
        """
        try:
            # Check if adapter is explicitly disabled
            if not adapter_config.get("enabled", True):
                return {
                    "valid": False,
                    "reason": f"Adapter '{name}' is disabled in configuration",
                    "can_enable_later": True,
                    "recommendation": f"Enable '{name}' in model registry configuration or use: python utilities/api_key_manager.py --set {adapter_type}"
                }
            
            # Check for required Python packages first
            required_packages = {
                "openai": ["openai"],
                "anthropic": ["anthropic"],
                "gemini": ["google.generativeai"],
                "groq": ["groq"],
                "cohere": ["cohere"],
                "mistral": ["mistralai"],
                "huggingface": ["transformers", "torch"],
                "transformers": ["transformers", "torch"],
                "stability": ["stability_sdk"],
                "replicate": ["replicate"]
            }
            
            # For validation purposes, use the provider field if it exists
            validation_type = adapter_config.get("provider", adapter_type)
            
            packages = required_packages.get(validation_type, [])
            for package in packages:
                try:
                    __import__(package)
                except ImportError:
                    return {
                        "valid": False,
                        "reason": f"Missing required package: {package}",
                        "can_enable_later": True,
                        "recommendation": f"Install with: pip install {package}"
                    }
            
            # Smart API key validation for API-based adapters
            if validation_type in ["openai", "anthropic", "gemini", "groq", "cohere", "mistral"]:
                api_validation = self._validate_api_key_smart(name, adapter_config, validation_type)
                if not api_validation["valid"]:
                    return api_validation
            
            # Check for network connectivity and service availability
            base_url = adapter_config.get("base_url")
            if base_url:
                if not self._test_connectivity(base_url):
                    return {
                        "valid": False,
                        "reason": f"Cannot connect to {base_url}",
                        "can_enable_later": True,
                        "recommendation": "Check network connectivity and service status"
                    }
            
            # For Ollama specifically, test the default URL and verify it has models
            elif validation_type == "ollama":
                provider_config = self.global_config.get("environment_config", {}).get("providers", {}).get("ollama", {})
                default_base_url = provider_config.get("default_base_url", "http://localhost:11434")
                if not self._test_connectivity(default_base_url):
                    return {
                        "valid": False,
                        "reason": f"Ollama service not available at {default_base_url}",
                        "can_enable_later": True,
                        "recommendation": "Start Ollama service or check if it's running on a different port"
                    }
            
            return {
                "valid": True, 
                "reason": "Prerequisites validated",
                "can_enable_later": False,
                "recommendation": "Adapter ready for use"
            }
            
        except Exception as e:
            return {
                "valid": False,
                "reason": f"Prerequisite validation error: {e}",
                "can_enable_later": True,
                "recommendation": "Check system configuration and try again"
            }
    
    def _validate_api_key_smart(self, name: str, adapter_config: Dict[str, Any], provider_type: str) -> Dict[str, Any]:
        """Registry-driven API key validation that works with any provider defined in the model registry."""
        # Get provider validation config from registry
        provider_config = self.global_config.get("environment_config", {}).get("providers", {}).get(provider_type)
        if not provider_config:
            return {
                "valid": False, 
                "reason": f"No validation configuration found for provider type: {provider_type}", 
                "can_enable_later": True, 
                "recommendation": f"Add validation config for {provider_type} in model registry"
            }
        
        validation_config = provider_config.get("validation", {})
        if not validation_config.get("requires_api_key", False):
            # Provider doesn't require API key validation
            return {"valid": True, "reason": "No API key required", "recommendation": "Ready to use"}
        
        # Check for API key in configuration or environment
        api_key = adapter_config.get("api_key") or os.getenv(validation_config.get("env_var", ""))
        if not api_key:
            env_var = validation_config.get("env_var", f"{provider_type.upper()}_API_KEY")
            return {
                "valid": False,
                "reason": f"Missing API key for {provider_type}",
                "can_enable_later": True,
                "recommendation": f"Set {env_var} environment variable or use: python utilities/api_key_manager.py --set {provider_type}"
            }
        
        return {"valid": True, "reason": "API key found", "recommendation": "Ready to use"}
    
    def _test_connectivity(self, url: str) -> bool:
        """Test basic connectivity to a service URL."""
        try:
            import socket
            from urllib.parse import urlparse
            
            parsed = urlparse(url)
            host = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            
            return result == 0
        except Exception:
            return False
    
    def _is_potentially_transient_error(self, error: Exception) -> bool:
        """Determine if an error might be transient and worth retrying."""
        error_str = str(error).lower()
        transient_indicators = [
            "timeout", "connection", "network", "temporary", 
            "rate limit", "busy", "overloaded", "unavailable"
        ]
        return any(indicator in error_str for indicator in transient_indicators)
    
    def _create_adapter_instance(self, adapter_type: str, adapter_config: Dict[str, Any]):
        """Create an instance of the specified adapter type."""
        # This would normally import and create the appropriate adapter
        # For now, we'll return a mock that satisfies the interface
        class MockAdapter:
            async def initialize(self):
                return True
        
        return MockAdapter()
