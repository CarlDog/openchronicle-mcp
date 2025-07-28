"""
Model adapter system for OpenChronicle.
Provides a unified interface for different LLM backends (OpenAI, Ollama, local models).
"""

import asyncio
import json
import os
import sys
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, UTC
from pathlib import Path

# Optional imports for enhanced error handling
try:
    import httpx
except ImportError:
    httpx = None

# Import logging system
from utilities.logging_system import log_model_interaction, log_system_event, log_info, log_error

# log_debug is not available in logging_system, use log_info instead
def log_debug(message: str) -> None:
    """Debug logging fallback to log_info."""
    log_info(f"DEBUG: {message}")

# Import keystore for secure API key retrieval
try:
    from utilities.api_key_manager import get_api_key
except ImportError:
    get_api_key = None

def get_api_key_with_fallback(config: Dict[str, Any], provider: str, env_var: str) -> Optional[str]:
    """
    Get API key with fallback priority: config > keystore > environment variable
    
    Args:
        config: Adapter configuration dictionary
        provider: Provider name for keystore (e.g., 'openai', 'anthropic')
        env_var: Environment variable name (e.g., 'OPENAI_API_KEY')
    
    Returns:
        API key string or None if not found
    """
    # First priority: explicit config
    api_key = config.get("api_key")
    if api_key:
        return api_key
    
    # Second priority: secure keystore
    if get_api_key:
        try:
            keystore_key = get_api_key(provider)
            if keystore_key:
                return keystore_key
        except Exception:
            pass  # Fallback to environment variable
    
    # Third priority: environment variable
    return os.getenv(env_var)

class ModelAdapter(ABC):
    """Abstract base class for model adapters."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model_name = config.get("model_name", "unknown")
        # Only set max_tokens for text models, not image models
        if config.get("type") != "image":
            self.max_tokens = config.get("max_tokens", 2048)
        self.temperature = config.get("temperature", 0.7)
        self.initialized = False
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the model adapter."""
        pass
    
    @abstractmethod
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate a response from the model."""
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the model."""
        pass
    
    def log_interaction(self, story_id: str, prompt: str, response: str, metadata: Optional[Dict[str, Any]] = None):
        """Log the interaction for debugging/analysis."""
        # Use centralized logging system
        log_model_interaction(
            story_id=story_id,
            model=self.model_name,
            prompt_length=len(prompt),
            response_length=len(response),
            metadata=metadata or {}
        )
        
        # Maintain backward compatibility with local file logging
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "story_id": story_id,
            "model": self.model_name,
            "prompt_length": len(prompt),
            "response_length": len(response),
            "metadata": metadata or {}
        }
        
        # Create logs directory if it doesn't exist
        logs_dir = os.path.join("storage", "temp", "test_data", story_id, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        
        # Log to file
        log_file = os.path.join(logs_dir, "model_interactions.jsonl")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

class OpenAIAdapter(ModelAdapter):
    """OpenAI GPT adapter."""
    
    def __init__(self, config: Dict[str, Any], model_manager=None):
        super().__init__(config)
        self.api_key = get_api_key_with_fallback(config, "openai", "OPENAI_API_KEY")
        self.model_manager = model_manager
        self.base_url = self._get_base_url(config)
        self.client = None
    
    def _get_base_url(self, config: Dict[str, Any]) -> str:
        """Get base URL from config or model manager."""
        # Check explicit config first
        if "base_url" in config:
            return config["base_url"]
        
        # Use model manager if available
        if self.model_manager:
            try:
                return self.model_manager.get_provider_base_url("openai")
            except Exception:
                pass
        
        # Fallback to environment variable only
        env_url = os.getenv("OPENAI_BASE_URL")
        if env_url:
            return env_url
            
        raise ValueError("No base URL configured for OpenAI. Please set OPENAI_BASE_URL or configure in registry.")
    
    async def initialize(self) -> bool:
        """Initialize OpenAI client."""
        if not self.api_key:
            raise ValueError("OpenAI API key required")
        
        try:
            import openai
            self.client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("openai package required for OpenAI adapter")
        except Exception as e:
            log_error(f"Failed to initialize OpenAI adapter: {e}")
            return False
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using OpenAI."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            response = await self.client.chat.completions.create(  # type: ignore
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a creative storytelling assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature),
                stop=kwargs.get("stop_sequences", None)
            )
            
            content = response.choices[0].message.content
            if content is None:
                return ""
            return content.strip()
        except Exception as e:
            raise RuntimeError(f"OpenAI generation failed: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get OpenAI model information."""
        return {
            "provider": "OpenAI",
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "initialized": self.initialized
        }

class OllamaAdapter(ModelAdapter):
    """Ollama local model adapter."""
    
    def __init__(self, config: Dict[str, Any], model_manager=None):
        super().__init__(config)
        self.model_manager = model_manager
        self.base_url = self._get_base_url(config)
        self.client = None
    
    def _get_base_url(self, config: Dict[str, Any]) -> str:
        """Get base URL from config or model manager."""
        # Check explicit config first
        if "base_url" in config:
            return config["base_url"]
        
        # Use model manager if available
        if self.model_manager:
            try:
                return self.model_manager.get_provider_base_url("ollama")
            except Exception:
                pass
        
        # Fallback to environment variable only
        env_url = os.getenv("OLLAMA_HOST")
        if env_url:
            return env_url
            
        raise ValueError("No base URL configured for Ollama. Please set OLLAMA_HOST or configure in registry.")
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize Ollama client."""
        try:
            import httpx
            timeout = self.config.get('timeout', 30.0)
            self.client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)
            
            # Test connection
            response = await self.client.get("/api/tags")
            if response.status_code == 200:
                self.initialized = True
                log_info(f"Ollama adapter initialized successfully for {self.model_name}")
                return True
            else:
                log_error(f"Ollama connection failed: {response.status_code}")
                return False
        except ImportError:
            raise ImportError("httpx package required for Ollama adapter")
        except Exception as e:
            log_error(f"Failed to initialize Ollama adapter: {e}")
            return False
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Ollama."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", self.temperature),
                    "num_predict": kwargs.get("max_tokens", self.max_tokens)
                }
            }
            
            log_info(f"Ollama request: POST {self.base_url}/api/generate with model={self.model_name}")
            response = await self.client.post("/api/generate", json=payload)  # type: ignore
            response.raise_for_status()
            
            result = response.json()
            return result.get("response", "").strip()
        except Exception as e:
            # Check if this is a model-not-found error (common when user removes model)
            error_msg = str(e).lower()
            if "not found" in error_msg or "does not exist" in error_msg or "404" in error_msg:
                log_error(f"Ollama model '{self.model_name}' not found - user may have removed it from Ollama")
                raise RuntimeError(f"Ollama model '{self.model_name}' not found. Model may have been removed from Ollama server.")
            else:
                log_error(f"Ollama generation failed - base_url: {self.base_url}, model: {self.model_name}, error: {e}")
                raise RuntimeError(f"Ollama generation failed: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Ollama model information."""
        return {
            "provider": "Ollama",
            "model_name": self.model_name,
            "base_url": self.base_url,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "initialized": self.initialized
        }

class ModelManager:
    """Manages model adapters and provides unified access."""
    
    def __init__(self):
        self.adapters: Dict[str, ModelAdapter] = {}
        self.default_adapter: Optional[str] = None
        self.global_config = self._load_global_config()
        self.config = self._load_config()
        
        # Initialize performance monitoring
        self.performance_monitor = None
        self._initialize_performance_monitoring()
        
        # Enhanced adapter status tracking
        self.adapter_status: Dict[str, Dict[str, Any]] = {}
        self.disabled_adapters: Dict[str, Dict[str, Any]] = {}
        self.api_key_status: Dict[str, Dict[str, Any]] = {}
        
        # Validate all configured adapters during initialization
        self._validate_all_configured_adapters()
    
    def _load_global_config(self) -> Dict[str, Any]:
        """Load global configuration from registry."""
        registry_file = os.path.join("config", "model_registry.json")
        
        if not os.path.exists(registry_file):
            raise FileNotFoundError(f"Model registry not found at {registry_file}. Please ensure the registry exists.")
        
        try:
            with open(registry_file, "r", encoding="utf-8") as f:
                registry = json.load(f)
            
            return self._process_global_config(registry)
            
        except Exception as e:
            log_error(f"Failed to load global config from registry: {e}")
            raise

    def _process_global_config(self, registry: Dict[str, Any]) -> Dict[str, Any]:
        """Process registry format for global configuration."""
        env_config = registry.get("environment_config", {})
        global_settings = registry.get("global_settings", {})
        defaults = registry.get("defaults", {})
        
        # Build discovery config with environment variable resolution
        providers = env_config.get("providers", {})
        discovery_config = {}
        
        for provider_name, provider_info in providers.items():
            base_url_env = provider_info.get("base_url_env")
            default_base_url = provider_info.get("default_base_url")
            
            discovery_config[provider_name] = {
                "enabled": True,
                "default_base_url": default_base_url,
                "env_var": base_url_env,
                "timeout": provider_info.get("timeout", 30.0),
                "health_check_enabled": provider_info.get("health_check_enabled", True)
            }
            
            # Apply environment variable override
            if base_url_env:
                env_value = os.getenv(base_url_env)
                if env_value:
                    discovery_config[provider_name]["resolved_base_url"] = env_value
                    log_info(f"Using environment override for {provider_name}: {env_value}")
                else:
                    discovery_config[provider_name]["resolved_base_url"] = default_base_url
        
        global_config = {
            "discovery": discovery_config,
            "defaults": {
                "text_model": defaults.get("text_model", "ollama"),
                "analyzer_model": defaults.get("analyzer_model", "ollama"),
                "image_model": defaults.get("image_model", "openai_dalle"),
                "timeout": 30.0,
                "max_tokens": 2048,
                "temperature": 0.7,
                "enable_logging": global_settings.get("enable_logging", True),
                "enable_fallbacks": global_settings.get("enable_fallbacks", True),
                "enable_health_checks": global_settings.get("enable_health_checks", True)
            }
        }
        
        log_system_event("global_config_loaded", "Global configuration loaded from registry")
        return global_config

    def get_provider_base_url(self, provider: str) -> str:
        """Get the base URL for a provider from registry environment config."""
        try:
            registry_file = os.path.join("config", "model_registry.json")
            if not os.path.exists(registry_file):
                raise FileNotFoundError(f"Model registry not found at {registry_file}")
            
            with open(registry_file, "r", encoding="utf-8") as f:
                registry = json.load(f)
            
            env_config = registry.get("environment_config", {})
            providers = env_config.get("providers", {})
            
            if provider not in providers:
                raise ValueError(f"Provider '{provider}' not found in environment_config")
            
            provider_info = providers[provider]
            base_url_env = provider_info.get("base_url_env")
            default_base_url = provider_info.get("default_base_url")
            
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
                        
        except Exception as e:
            log_error(f"Error getting base URL for provider {provider}: {e}")
            raise

    def get_global_default(self, key: str, fallback: Any = None) -> Any:
        """Get a global default configuration value."""
        return self.global_config.get("defaults", {}).get(key, fallback)
    
    def get_intelligent_routing_config(self) -> Dict[str, Any]:
        """Get intelligent routing configuration from the registry."""
        try:
            registry_file = os.path.join("config", "model_registry.json")
            if os.path.exists(registry_file):
                with open(registry_file, "r", encoding="utf-8") as f:
                    registry = json.load(f)
                
                global_settings = registry.get("global_settings", {})
                return global_settings.get("intelligent_routing", {})
                    
        except Exception as e:
            log_error(f"Error getting intelligent routing config: {e}")
        
        return {"enabled": False}
    
    def get_content_routing_config(self) -> Dict[str, Any]:
        """Get content routing configuration from the registry."""
        try:
            registry_file = os.path.join("config", "model_registry.json")
            if os.path.exists(registry_file):
                with open(registry_file, "r", encoding="utf-8") as f:
                    registry = json.load(f)
                
                return registry.get("content_routing", {})
                    
        except Exception as e:
            log_error(f"Error getting content routing config: {e}")
        
        return {}
    
    def get_performance_config(self) -> Dict[str, Any]:
        """Get performance tuning configuration from the registry."""
        try:
            registry_file = os.path.join("config", "model_registry.json")
            if os.path.exists(registry_file):
                with open(registry_file, "r", encoding="utf-8") as f:
                    registry = json.load(f)
                
                return registry.get("performance_tuning", {})
                    
        except Exception as e:
            log_error(f"Error getting performance config: {e}")
        
        return {}
    
    def get_enabled_models_by_type(self, model_type: str = "text") -> List[Dict[str, Any]]:
        """Get all enabled models of a specific type from the registry."""
        enabled_models = []
        
        try:
            registry_file = os.path.join("config", "model_registry.json")
            if os.path.exists(registry_file):
                with open(registry_file, "r", encoding="utf-8") as f:
                    registry = json.load(f)
                
                if model_type == "text":
                    text_models = registry.get("text_models", {})
                    for priority_group in ["high_priority", "standard_priority", "testing"]:
                        if priority_group in text_models:
                            for model in text_models[priority_group]:
                                if model.get("enabled", True):
                                    enabled_models.append(model)
                elif model_type == "image":
                    image_models = registry.get("image_models", {})
                    for priority_group in ["primary", "testing"]:
                        if priority_group in image_models:
                            for model in image_models[priority_group]:
                                if model.get("enabled", True):
                                    enabled_models.append(model)
                    
        except Exception as e:
            log_error(f"Error getting enabled models: {e}")
        
        return enabled_models

    def _load_config(self) -> Dict[str, Any]:
        """Load model configuration from registry."""
        registry_file = os.path.join("config", "model_registry.json")
        
        if not os.path.exists(registry_file):
            raise FileNotFoundError(f"Model registry not found at {registry_file}. Please ensure the registry exists.")
        
        log_system_event("model_config_loading", "Loading model configuration from registry")
        return self._load_plugin_config(registry_file)

    def _load_plugin_config(self, registry_file: str) -> Dict[str, Any]:
        """Load model configuration from registry."""
        log_info("Loading registry model configuration")
        log_system_event("plugin_config_loading", f"Loading registry model configuration from {registry_file}")
        
        # Load the registry
        with open(registry_file, "r", encoding="utf-8") as f:
            registry = json.load(f)
        
        # Get models from hierarchical structure
        all_models = []
        text_models = registry.get("text_models", {})
        image_models = registry.get("image_models", {})
        
        # Collect all text models from different priority groups
        for priority_group in ["high_priority", "standard_priority", "testing"]:
            if priority_group in text_models:
                for model in text_models[priority_group]:
                    model["type"] = "text"  # Ensure type is set
                    all_models.append(model)
        
        # Collect all image models from different priority groups
        for priority_group in ["primary", "testing"]:
            if priority_group in image_models:
                for model in image_models[priority_group]:
                    model["type"] = "image"  # Ensure type is set
                    all_models.append(model)
                    
        log_system_event("plugin_config_registry", f"Loaded registry with {len(all_models)} model entries")
        
        # Build adapters directly from registry entries
        adapters = {}
        
        for model_entry in all_models:
            if not model_entry.get("enabled", True):
                continue
                
            provider = model_entry["name"]
            
            # PRODUCTION SAFETY: Auto-disable mock adapters in production
            # Mock adapters should only be available for testing
            if provider in ["mock", "mock_image"]:
                # Check if we're in a testing environment
                import os
                is_testing = (
                    os.getenv("TESTING", "").lower() in ["true", "1", "yes"] or
                    os.getenv("PYTEST_CURRENT_TEST") is not None or
                    "pytest" in sys.modules or
                    "test" in sys.argv[0].lower()
                )
                
                if not is_testing:
                    log_system_event("production_safety", 
                                   f"Auto-disabling {provider} adapter - mock adapters not available in production")
                    continue  # Skip mock adapters in production
            
            try:
                # Create adapter config directly from registry entry
                # Determine the actual adapter type - prefer explicit type, otherwise use provider name
                actual_type = model_entry.get("type")
                if actual_type in ["text", "image"]:
                    # These are category types, not adapter types - use provider name instead
                    actual_type = provider
                elif actual_type is None:
                    actual_type = provider
                
                adapter_config = {
                    "type": actual_type,
                    "provider": model_entry.get("provider", provider),  # Add provider field for validation
                    "model_name": model_entry.get("model_name", provider),
                    "enabled": model_entry.get("enabled", False),  # Copy enabled status from registry
                    "priority": model_entry.get("priority", 999),  # Copy priority from registry
                    "temperature": model_entry.get("temperature", 0.7),
                    "supports_nsfw": model_entry.get("supports_nsfw", False),
                    "content_types": model_entry.get("content_types", ["general"]),
                    "description": model_entry.get("description", f"{provider} model adapter")
                }
                
                # Merge config section if it exists
                if "config" in model_entry:
                    adapter_config.update(model_entry["config"])
                
                # Add max_tokens only for text models, not image models
                if model_entry.get("type") != "image":
                    adapter_config["max_tokens"] = model_entry.get("max_tokens", 2048)
                
                # Add image-specific parameters for image models
                if model_entry.get("type") == "image":
                    if "size" in model_entry:
                        adapter_config["size"] = model_entry["size"]
                    if "quality" in model_entry:
                        adapter_config["quality"] = model_entry["quality"]
                    if "style" in model_entry:
                        adapter_config["style"] = model_entry["style"]
                    if "width" in model_entry:
                        adapter_config["width"] = model_entry["width"]
                    if "height" in model_entry:
                        adapter_config["height"] = model_entry["height"]
                    if "steps" in model_entry:
                        adapter_config["steps"] = model_entry["steps"]
                
                # Add provider-specific configurations
                if provider == "mock":
                    adapter_config["responses"] = [
                        "The story continues with rich detail and engaging narrative.",
                        "Your character moves forward, discovering new possibilities.",
                        "The world around you shifts as the tale unfolds."
                    ]
                elif provider == "mock_image":
                    adapter_config["responses"] = [
                        "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0iIzMzNzNkYyIvPgogIDx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmaWxsPSJ3aGl0ZSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zNWVtIj5Nb2NrIEltYWdlPC90ZXh0Pgo8L3N2Zz4K"
                    ]
                
                adapters[provider] = adapter_config
                log_info(f"Loaded model configuration for {provider}")
                log_system_event("model_config_loaded", f"Loaded model configuration for {provider}")
                        
            except Exception as e:
                log_error(f"Failed to load model config for {provider}: {e}")
                log_system_event("model_config_error", f"Failed to load model config for {provider}: {e}")
        
        # NO AUTOMATIC MOCK ADAPTER - User must explicitly enable in registry
        # Mock adapters should only be available when explicitly configured by the user
        if not adapters:
            log_system_event("no_adapters_loaded", 
                           "No adapters loaded from configuration. Configure real AI services or explicitly enable mock adapters in the registry.")
            log_system_event("production_safety", 
                           "Production safety: Not auto-adding mock adapters. Add mock adapters to registry if desired for testing.")
        
        # Build fallback chains from registry
        fallback_chains = registry.get("fallback_chains", {})
        
        # Build content routing
        content_routing = {}
        if "content_routing" in registry:
            content_routing = registry["content_routing"]
        else:
            # Create basic content routing from available models
            enabled_models = [m["name"] for m in all_models if m.get("enabled", True)]
            nsfw_models = [m["name"] for m in all_models if m.get("supports_nsfw", False)]
            safe_models = [m["name"] for m in all_models if not m.get("supports_nsfw", False)]
            
            content_routing = {
                "nsfw_content": {
                    "allowed_models": nsfw_models if nsfw_models else ["mock"],
                    "default_model": nsfw_models[0] if nsfw_models else "mock"
                },
                "safe_content": {
                    "allowed_models": safe_models if safe_models else enabled_models,
                    "default_model": safe_models[0] if safe_models else (enabled_models[0] if enabled_models else "mock")
                }
            }
        
        # Determine default adapter from registry format - NO MOCK FALLBACK
        default_adapter = None
        if "defaults" in registry:
            default_adapter = registry["defaults"].get("text_model")
        elif "default_model" in registry:
            default_adapter = registry["default_model"]
        
        # If the default adapter didn't load, find the first available one (excluding mock)
        if default_adapter not in adapters:
            if adapters:
                # Prefer non-mock adapters
                non_mock_adapters = [name for name in adapters.keys() if not name.startswith("mock")]
                if non_mock_adapters:
                    default_adapter = non_mock_adapters[0]
                    log_info(f"Default adapter not available, using first non-mock adapter '{default_adapter}'")
                else:
                    # Only use mock if user explicitly configured it and no other options
                    default_adapter = list(adapters.keys())[0]
                    log_info(f"Only mock adapters available, using '{default_adapter}'")
            else:
                default_adapter = None
                log_info("No adapters loaded, no default adapter available")
        
        config = {
            "default_adapter": default_adapter,
            "adapters": adapters,
            "fallback_chains": fallback_chains,
            "content_routing": content_routing
        }
        
        log_info(f"Registry-only configuration loaded with {len(adapters)} adapters")
        return config
    
    def _validate_all_configured_adapters(self):
        """Validate all configured adapters and track their status without initializing them."""
        try:
            for name, adapter_config in self.config.get("adapters", {}).items():
                adapter_type = adapter_config.get("type", "unknown")
                
                # Validate prerequisites for this adapter
                validation_result = self._validate_adapter_prerequisites(name, adapter_config, adapter_type)
                
                if not validation_result["valid"]:
                    # Track as disabled
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
                else:
                    # Track as validated and potentially usable
                    if adapter_type in ["openai", "anthropic", "gemini", "groq", "cohere", "mistral"]:
                        self.api_key_status[adapter_type] = {
                            "available": True,
                            "reason": "API key validated successfully",
                            "recommendation": f"{adapter_type.title()} adapter ready for use",
                            "last_validated": datetime.now(UTC).isoformat()
                        }
            
            # Count only truly available adapters (not just configured ones)
            available_count = len(self.get_available_adapters())
            configured_count = len(self.config.get('adapters', {}))
            disabled_count = len(self.disabled_adapters)
            
            log_info(f"Validated {configured_count} configured adapters: "
                    f"{disabled_count} disabled, "
                    f"{configured_count - disabled_count} passed validation, "
                    f"{available_count} actually available")
                    
        except Exception as e:
            log_error(f"Error during adapter validation: {e}")
    
    
    def register_adapter(self, name: str, adapter: ModelAdapter):
        """Register a model adapter."""
        self.adapters[name] = adapter
    
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
            error_msg = f"Adapter '{name}' not found in configuration"
            log_system_event("adapter_initialization_error", error_msg)
            if graceful_degradation:
                log_error(f"Skipping missing adapter: {name}")
                return False
            else:
                raise ValueError(error_msg)
        
        adapter_config = self.config["adapters"][name]
        adapter_type = adapter_config.get("type", "unknown")
        
        log_system_event("adapter_initialization", f"Initializing {adapter_type} adapter: {name}")
        
        # Start performance tracking for initialization
        async with self.track_model_operation(name, "initialize") as tracker:
            
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
                        if self.default_adapter is None:
                            self.default_adapter = name
                        
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
    
    def _validate_adapter_prerequisites(self, name: str, adapter_config: Dict[str, Any], adapter_type: str) -> Dict[str, Any]:
        """
        Enhanced validation with smart API key validation and graceful skipping.
        
        Returns:
            Dict with 'valid' (bool), 'reason' (str), 'can_enable_later' (bool), and 'recommendation' (str) keys
        """
        try:
            # Check for required Python packages first
            required_packages = {
                "openai": ["openai"],
                "anthropic": ["anthropic"],
                "gemini": ["google.generativeai"],
                "groq": ["groq"],
                "cohere": ["cohere"],
                "mistral": ["mistralai"],
                "huggingface": ["transformers", "torch"],
                "transformers": ["transformers", "torch"],  # Add transformers type
                "stability": ["stability_sdk"],
                "replicate": ["replicate"]
            }
            
            # For validation purposes, use the provider field if it exists (for openai_dalle -> openai)
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
            
            # Smart API key validation for API-based adapters - use validation_type
            if validation_type in ["openai", "anthropic", "gemini", "groq", "cohere", "mistral"]:
                api_validation = self._validate_api_key_smart(name, adapter_config, validation_type)
                if not api_validation["valid"]:
                    return api_validation
            
            # Check for network connectivity and service availability for ALL adapters
            # This ensures we don't claim capabilities when services aren't actually working
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
                
                # Additional check: ensure Ollama has models available
                if not self._test_ollama_models(default_base_url):
                    return {
                        "valid": False,
                        "reason": f"Ollama service running but no models installed",
                        "can_enable_later": True,
                        "recommendation": "Install models with: ollama pull llama2 (or similar)"
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
        """
        Registry-driven API key validation that works with any provider defined in the model registry.
        
        Returns:
            Dict with validation result including recommendations for missing/invalid keys
        """
        # Get provider validation config from registry
        provider_config = self.global_config.get("environment_config", {}).get("providers", {}).get(provider_type)
        if not provider_config:
            # For standalone-first architecture: if we don't have validation config, 
            # we can't verify the adapter actually works
            return {
                "valid": False, 
                "reason": f"No validation configuration found for provider type: {provider_type}", 
                "can_enable_later": True, 
                "recommendation": f"Add validation config for {provider_type} in model registry"
            }
        
        validation_config = provider_config.get("validation", {})
        if not validation_config.get("requires_api_key", False):
            # Even local adapters need connectivity validation (handled in _validate_adapter_prerequisites)
            return {"valid": True, "reason": "No API key required", "can_enable_later": False, "recommendation": "Local adapter ready"}
        
        # Check if API key is provided
        api_key_env = provider_config.get("api_key_env")
        api_key = adapter_config.get("api_key")
        if not api_key and api_key_env:
            api_key = os.getenv(api_key_env)
        
        if not api_key:
            env_var_info = f" ({api_key_env})" if api_key_env else ""
            setup_url = validation_config.get("setup_url", "provider's website")
            service_name = validation_config.get("service_name", provider_type.title())
            
            return {
                "valid": False,
                "reason": f"Missing API key for {provider_type}",
                "can_enable_later": True,
                "recommendation": f"Set {api_key_env or 'API key'} environment variable or add api_key to config. Get your key at: {setup_url} for {service_name}"
            }
        
        # Validate API key format if specified
        api_key_format = validation_config.get("api_key_format")
        if api_key_format and not self._validate_api_key_format_regex(api_key, api_key_format):
            setup_url = validation_config.get("setup_url", "provider's website")
            return {
                "valid": False,
                "reason": f"Invalid API key format for {provider_type}",
                "can_enable_later": True,
                "recommendation": f"Check your API key format. Expected pattern: {api_key_format}. Get a valid key at: {setup_url}"
            }
        
        # Test API key with provider's health endpoint
        try:
            is_valid, error_msg = self._test_api_key_generic(api_key, provider_type, provider_config, validation_config)
            if not is_valid:
                setup_url = validation_config.get("setup_url", "provider's website")
                return {
                    "valid": False,
                    "reason": f"API key validation failed: {error_msg}",
                    "can_enable_later": True,
                    "recommendation": f"Verify your API key is active and has appropriate permissions. Get a new key at: {setup_url}"
                }
        except Exception as e:
            # If API test fails due to network/other issues, allow the adapter but log the issue
            log_error(f"Could not validate {provider_type} API key due to network error: {e}")
            return {
                "valid": True,
                "reason": f"API key present but could not validate due to network error",
                "can_enable_later": False,
                "recommendation": "Network validation failed, proceeding with provided API key"
            }
        
        service_name = validation_config.get("service_name", provider_type.title())
        return {
            "valid": True,
            "reason": "API key validated successfully",
            "can_enable_later": False,
            "recommendation": f"{service_name} adapter ready for use"
        }
    
    def _validate_api_key_format_regex(self, api_key: str, pattern: str) -> bool:
        """Validate API key format using regex pattern from registry."""
        if not api_key or len(api_key.strip()) < 10:
            return False
        
        try:
            import re
            return bool(re.match(pattern, api_key.strip()))
        except Exception:
            # If regex fails, fall back to basic validation
            return len(api_key.strip()) > 10
    
    def _test_api_key_generic(self, api_key: str, provider_type: str, provider_config: Dict[str, Any], validation_config: Dict[str, Any]) -> tuple[bool, str]:
        """
        Generic API key testing using configuration from the model registry.
        Works with any provider that has validation config defined.
        """
        try:
            if httpx is None:
                return True, "httpx not available, skipping validation"
            
            # Build the URL
            base_url = provider_config.get("default_base_url", "")
            health_endpoint = validation_config.get("health_endpoint", "/")
            
            # Handle different auth formats
            auth_format = validation_config.get("auth_format", "Bearer {api_key}")
            headers = {}
            params = {}
            url = base_url + health_endpoint
            
            # Set up authentication
            if "?" in auth_format:
                # Query parameter auth (like Gemini)
                url += auth_format.format(api_key=api_key)
            else:
                # Header auth
                auth_header = validation_config.get("auth_header", "Authorization")
                headers[auth_header] = auth_format.format(api_key=api_key)
            
            # Add extra headers if specified
            extra_headers = validation_config.get("extra_headers", {})
            headers.update(extra_headers)
            
            # Add default content type if not specified
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"
            
            timeout = provider_config.get("timeout", 10)
            method = validation_config.get("method", "GET").upper()
            test_payload = validation_config.get("test_payload")
            
            with httpx.Client(timeout=timeout) as client:
                if method == "POST" and test_payload:
                    response = client.post(url, headers=headers, json=test_payload)
                elif method == "POST":
                    response = client.post(url, headers=headers)
                else:
                    response = client.get(url, headers=headers)
                
                # Check response status
                if response.status_code == 200:
                    return True, "API key valid"
                elif response.status_code == 401:
                    return False, "Invalid API key"
                elif response.status_code == 403:
                    return False, "API key lacks required permissions"
                elif response.status_code == 429:
                    return False, "API key rate limited or quota exceeded"
                else:
                    return False, f"API returned status {response.status_code}"
                    
        except Exception as e:
            return False, f"API test failed: {e}"
    
    # Note: All API key validation methods have been consolidated into registry-driven approach
    # See _validate_api_key_smart(), _validate_api_key_format_regex(), and _test_api_key_generic()
    
    def get_adapter_status_summary(self) -> Dict[str, Any]:
        """
        Get a comprehensive summary of adapter status including disabled adapters and recommendations.
        
        Returns:
            Dict with detailed status information and user-friendly recommendations
        """
        active_adapters = len(self.adapters)
        disabled_adapters = len(self.disabled_adapters)
        total_configured = active_adapters + disabled_adapters
        
        # Categorize disabled adapters by reason
        missing_api_keys = []
        missing_packages = []
        network_issues = []
        other_issues = []
        
        for name, info in self.disabled_adapters.items():
            reason = info["reason"].lower()
            if "api key" in reason:
                missing_api_keys.append({
                    "name": name,
                    "type": info["type"],
                    "recommendation": info.get("recommendation", "")
                })
            elif "package" in reason:
                missing_packages.append({
                    "name": name,
                    "type": info["type"],
                    "recommendation": info.get("recommendation", "")
                })
            elif "connect" in reason or "network" in reason:
                network_issues.append({
                    "name": name,
                    "type": info["type"],
                    "recommendation": info.get("recommendation", "")
                })
            else:
                other_issues.append({
                    "name": name,
                    "type": info["type"],
                    "reason": info["reason"],
                    "recommendation": info.get("recommendation", "")
                })
        
        # Generate user-friendly summary
        summary = {
            "overview": {
                "total_configured": total_configured,
                "active_adapters": active_adapters,
                "disabled_adapters": disabled_adapters,
                "health_status": "excellent" if disabled_adapters == 0 else ("good" if active_adapters > 0 else "poor")
            },
            "active_adapters": {
                name: {
                    "type": info["type"],
                    "model_name": info["model_name"],
                    "description": info["description"],
                    "supports_nsfw": info["supports_nsfw"],
                    "content_types": info["content_types"],
                    "initialized_at": info["initialized_at"]
                }
                for name, info in self.adapter_status.items()
            },
            "disabled_adapters": {
                "missing_api_keys": missing_api_keys,
                "missing_packages": missing_packages,
                "network_issues": network_issues,
                "other_issues": other_issues
            },
            "api_key_status": self.api_key_status,
            "recommendations": self._generate_status_recommendations(missing_api_keys, missing_packages, network_issues, other_issues),
            "default_adapter": self.default_adapter
        }
        
        return summary
    
    def _generate_status_recommendations(self, missing_api_keys: List[Dict], missing_packages: List[Dict], 
                                        network_issues: List[Dict], other_issues: List[Dict]) -> List[str]:
        """Generate user-friendly recommendations for improving adapter availability."""
        recommendations = []
        
        if missing_api_keys:
            api_types = {item["type"] for item in missing_api_keys}
            recommendations.append(
                f"🔑 Set up API keys for {', '.join(sorted(api_types))} to enable advanced AI models. "
                f"This will unlock {len(missing_api_keys)} additional adapters."
            )
        
        if missing_packages:
            package_count = len(missing_packages)
            recommendations.append(
                f"📦 Install missing Python packages to enable {package_count} adapter(s). "
                f"Run 'pip install' commands shown in the detailed status."
            )
        
        if network_issues:
            service_count = len(network_issues)
            recommendations.append(
                f"🌐 Check network connectivity - {service_count} service(s) are unreachable. "
                f"Verify internet connection and service status."
            )
        
        if other_issues:
            issue_count = len(other_issues)
            recommendations.append(
                f"⚠️ Resolve {issue_count} configuration issue(s). "
                f"Check detailed status for specific solutions."
            )
        
        if not any([missing_api_keys, missing_packages, network_issues, other_issues]):
            recommendations.append("✅ All configured adapters are working properly!")
        
        return recommendations
    
    def get_api_key_setup_guide(self) -> Dict[str, Any]:
        """
        Generate a comprehensive API key setup guide for users using model registry configuration.
        
        Returns:
            Dict with setup instructions for each provider from the model registry
        """
        api_providers = {}
        
        # Build provider info from model registry
        for adapter_name, config in self.config.get("adapters", {}).items():
            if isinstance(config, dict) and "type" in config:
                provider_type = config["type"]
                
                # Skip local/self-hosted providers that don't need API keys
                if provider_type in ["local", "ollama", "litellm"]:
                    continue
                
                validation_config = config.get("validation", {})
                if not validation_config.get("requires_api_key", False):
                    continue
                
                # Extract provider info from registry
                provider_info = {
                    "service_name": config.get("description", f"{provider_type.title()} AI"),
                    "setup_url": validation_config.get("setup_url", f"https://{provider_type}.com/api-keys"),
                    "env_var": validation_config.get("env_var", f"{provider_type.upper()}_API_KEY"),
                    "description": config.get("description", f"Access to {config.get('model_name', 'AI models')}"),
                    "pricing": validation_config.get("pricing", "Pay-per-use"),
                    "api_key_format": validation_config.get("api_key_format", ""),
                    "steps": [
                        f"1. Visit {validation_config.get('setup_url', f'https://{provider_type}.com/api-keys')}",
                        f"2. Sign in or create a {provider_type.title()} account",
                        "3. Generate a new API key",
                        f"4. Copy the key{' (format: ' + validation_config.get('api_key_format', '') + ')' if validation_config.get('api_key_format') else ''}",
                        f"5. Set environment variable: {validation_config.get('env_var', f'{provider_type.upper()}_API_KEY')}=your_key_here"
                    ]
                }
                
                # Avoid duplicates - use the first adapter of each type
                if provider_type not in api_providers:
                    api_providers[provider_type] = provider_info
        
        # Add status information
        setup_guide = {
            "providers": api_providers,
            "current_status": self.api_key_status,
            "disabled_due_to_api_keys": [
                {
                    "adapter": name,
                    "provider": info["type"],
                    "recommendation": info.get("recommendation", "")
                }
                for name, info in self.disabled_adapters.items()
                if "api key" in info["reason"].lower()
            ],
            "general_instructions": [
                "Environment variables can be set in your system or in a .env file",
                "Restart OpenChronicle after setting new API keys",
                "API keys are sensitive - never share them publicly",
                "Each provider has different pricing - check their websites for current rates",
                "Free tiers are often sufficient for testing and light usage"
            ]
        }
        
        return setup_guide
    
    def check_for_new_api_keys(self) -> Dict[str, Any]:
        """
        Check if any previously missing API keys are now available and can enable disabled adapters.
        
        Returns:
            Dict with information about newly available adapters
        """
        newly_available = []
        still_disabled = []
        
        for name, info in self.disabled_adapters.copy().items():
            if info.get("can_enable_later", False):
                adapter_type = info["type"]
                adapter_config = info["config"]
                
                # Re-validate prerequisites
                validation_result = self._validate_adapter_prerequisites(name, adapter_config, adapter_type)
                
                if validation_result["valid"]:
                    newly_available.append({
                        "name": name,
                        "type": adapter_type,
                        "previous_reason": info["reason"],
                        "now_available": True
                    })
                    
                    # Update status
                    self.disabled_adapters[name]["can_enable_later"] = False
                    self.disabled_adapters[name]["status"] = "ready_to_initialize"
                    
                else:
                    still_disabled.append({
                        "name": name,
                        "type": adapter_type,
                        "reason": validation_result["reason"],
                        "recommendation": validation_result.get("recommendation", "")
                    })
        
        result = {
            "newly_available": newly_available,
            "still_disabled": still_disabled,
            "can_initialize_now": len(newly_available) > 0,
            "check_timestamp": datetime.now(UTC).isoformat()
        }
        
        if newly_available:
            log_info(f"Found {len(newly_available)} adapters that can now be initialized")
            log_system_event("api_keys_newly_available", f"Can now initialize: {[item['name'] for item in newly_available]}")
        
        return result
    
    async def auto_initialize_available_adapters(self) -> Dict[str, Any]:
        """
        Automatically initialize any adapters that were previously disabled but are now available.
        
        Returns:
            Dict with initialization results
        """
        check_result = self.check_for_new_api_keys()
        
        if not check_result["can_initialize_now"]:
            return {
                "success": True,
                "message": "No new adapters available for initialization",
                "newly_initialized": [],
                "failed_initializations": []
            }
        
        newly_initialized = []
        failed_initializations = []
        
        for adapter_info in check_result["newly_available"]:
            name = adapter_info["name"]
            try:
                success = await self.initialize_adapter(name, graceful_degradation=True)
                if success:
                    newly_initialized.append({
                        "name": name,
                        "type": adapter_info["type"],
                        "status": "initialized_successfully"
                    })
                else:
                    failed_initializations.append({
                        "name": name,
                        "type": adapter_info["type"],
                        "reason": "Initialization returned False"
                    })
            except Exception as e:
                failed_initializations.append({
                    "name": name,
                    "type": adapter_info["type"],
                    "reason": str(e)
                })
        
        log_info(f"Auto-initialization complete: {len(newly_initialized)} successful, {len(failed_initializations)} failed")
        
        return {
            "success": True,
            "message": f"Initialized {len(newly_initialized)} adapter(s)",
            "newly_initialized": newly_initialized,
            "failed_initializations": failed_initializations,
            "total_active_adapters": len(self.adapters)
        }
    
    def _is_standalone_mode(self) -> bool:
        """
        Detect if we're in standalone mode (no external AI services available).
        
        Standalone mode is detected when:
        1. No external adapters are working (all in disabled_adapters)
        2. No valid API keys for external services
        3. Network connectivity issues
        4. Only mock/local adapters are available
        
        Returns:
            True if we should operate in standalone mode, False otherwise
        """
        # Count available external vs local adapters (check configured, not just initialized)
        external_adapters = 0
        local_adapters = 0
        
        # Check all configured adapters, not just initialized ones
        for name, adapter_config in self.config.get("adapters", {}).items():
            # Skip disabled adapters
            if name in self.disabled_adapters:
                continue
            
            # Skip mock adapters (they shouldn't count for production mode detection)
            adapter_type = adapter_config.get("type", name)
            if adapter_type in ["mock", "mock_image"]:
                continue  # Mock adapters don't count for mode detection
                
            # Check if adapter is enabled
            if not adapter_config.get("enabled", False):
                continue
            
            if adapter_type in ["local", "transformers"]:
                local_adapters += 1
            elif adapter_type == "ollama":
                # Ollama is local but requires service to be running
                # Count as local if not disabled
                if name not in self.disabled_adapters:
                    local_adapters += 1
            else:
                external_adapters += 1
        
        # We're in standalone mode if:
        # 1. No external adapters are available, OR
        # 2. Only local adapters are available
        if external_adapters == 0:
            if local_adapters > 0:
                log_system_event("standalone_mode_detected", 
                               f"Standalone mode: {local_adapters} local adapters available, {external_adapters} external")
            else:
                log_system_event("standalone_mode_detected", 
                               "Standalone mode: No working adapters detected")
            return True
        
        return False  
        # 3. Only local/mock adapters are working
        if external_adapters == 0:
            if local_adapters > 0:
                log_system_event("standalone_mode_detected", 
                               f"Standalone mode: {local_adapters} local adapters, {external_adapters} external")
            else:
                log_system_event("standalone_mode_detected", 
                               "Standalone mode: No working adapters detected")
            return True
        
        return False

    def _test_connectivity(self, base_url: str, timeout: float = 5.0) -> bool:
        """Test basic connectivity to a URL - strict validation for standalone-first architecture."""
        try:
            if httpx is None:
                log_debug(f"httpx not available - cannot test connectivity to {base_url}")
                return False  # Fail strictly if we can't test connectivity
            with httpx.Client(timeout=timeout) as client:
                response = client.get(base_url, timeout=timeout)
                return response.status_code < 500  # Accept any non-server-error status
        except Exception as e:
            log_debug(f"Connectivity test failed for {base_url}: {e}")
            return False
    
    def _test_ollama_models(self, base_url: str, timeout: float = 5.0) -> bool:
        """Test if Ollama has any models installed - strict validation for standalone-first."""
        try:
            if httpx is None:
                log_debug(f"httpx not available - cannot test Ollama models at {base_url}")
                return False
            
            models_url = f"{base_url.rstrip('/')}/api/tags"
            with httpx.Client(timeout=timeout) as client:
                response = client.get(models_url, timeout=timeout)
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    return len(models) > 0  # Must have at least one model
                return False
        except Exception as e:
            log_debug(f"Ollama models test failed for {base_url}: {e}")
            return False
    
    def _create_adapter_instance(self, adapter_type: str, adapter_config: Dict[str, Any]):
        """Create an adapter instance based on type."""
        if adapter_type == "openai":
            return OpenAIAdapter(adapter_config, self)
        elif adapter_type == "ollama":
            return OllamaAdapter(adapter_config, self)
        elif adapter_type == "anthropic":
            return AnthropicAdapter(adapter_config, self)
        elif adapter_type == "gemini":
            return GeminiAdapter(adapter_config)
        elif adapter_type == "groq":
            return GroqAdapter(adapter_config)
        elif adapter_type == "cohere":
            return CohereAdapter(adapter_config)
        elif adapter_type == "mistral":
            return MistralAdapter(adapter_config)
        elif adapter_type == "huggingface":
            return HuggingFaceAdapter(adapter_config)
        elif adapter_type == "azure_openai":
            return AzureOpenAIAdapter(adapter_config)
        elif adapter_type == "transformers":
            return TransformersAdapter(adapter_config, self)
        elif adapter_type == "openai_image":
            return OpenAIImageAdapter(adapter_config, self)
        elif adapter_type == "stability":
            return StabilityAdapter(adapter_config, self)
        elif adapter_type == "replicate":
            return ReplicateAdapter(adapter_config)
        else:
            raise ValueError(f"Unknown adapter type: {adapter_type}")
    
    def _is_potentially_transient_error(self, error: Exception) -> bool:
        """Determine if an error might be transient and worth retrying."""
        error_str = str(error).lower()
        transient_indicators = [
            "timeout", "connection", "network", "temporary", "rate limit",
            "service unavailable", "too many requests", "server error",
            "502", "503", "504", "gateway", "proxy"
        ]
        return any(indicator in error_str for indicator in transient_indicators)
    
    async def initialize_adapter_safe(self, name: str) -> bool:
        """
        Safe wrapper for adapter initialization that always uses graceful degradation.
        
        This method never raises exceptions and is safe to call during startup.
        """
        try:
            return await self.initialize_adapter(name, graceful_degradation=True)
        except Exception as e:
            log_error(f"Unexpected error in safe adapter initialization for {name}: {e}")
            log_system_event("adapter_initialization_safe_fallback", f"Safe initialization failed for {name}: {e}")
            return False
    
    async def generate_response(self, prompt: str, adapter_name: Optional[str] = None, story_id: Optional[str] = None, **kwargs) -> str:
        """Generate response using specified or default adapter with fallback support."""
        adapter_name = adapter_name or self.default_adapter
        
        if not adapter_name:
            raise RuntimeError("No adapter specified and no default adapter available. Configure AI services or specify an adapter.")
        
        # Start performance tracking
        async with self.track_model_operation(adapter_name, "generate", prompt_length=len(prompt)) as tracker:
            
            # Use fallback chain if configured
            if "fallback_chains" in self.config and adapter_name in self.config["fallback_chains"]:
                chain = self.config["fallback_chains"][adapter_name]
                log_info(f"Using fallback chain for {adapter_name}: {chain}")
                log_system_event("fallback_chain_usage", f"Using fallback chain for {adapter_name}: {chain}")
                
                for attempt_adapter in chain:
                    try:
                        if attempt_adapter not in self.adapters:
                            # Try to initialize the adapter
                            if not await self.initialize_adapter(attempt_adapter):
                                log_error(f"Failed to initialize adapter: {attempt_adapter}")
                                continue
                        
                        adapter = self.adapters[attempt_adapter]
                        response = await adapter.generate_response(prompt, **kwargs)
                        
                        # Track performance metrics
                        tracker.set_tokens_processed(len(response.split()) if response else 0)
                        tracker.set_response_size(len(response.encode('utf-8')) if response else 0)
                        
                        # Log interaction if story_id provided
                        if story_id:
                            metadata = {"adapter": attempt_adapter, "kwargs": kwargs, "fallback_position": chain.index(attempt_adapter)}
                            adapter.log_interaction(story_id, prompt, response, metadata)
                        
                        log_info(f"Successfully generated response using {attempt_adapter}")
                        log_system_event("fallback_chain_success", f"Successfully generated response using {attempt_adapter} (fallback position {chain.index(attempt_adapter)})")
                        return response
                        
                    except Exception as e:
                        log_error(f"Adapter {attempt_adapter} failed: {e}")
                        log_system_event("fallback_chain_failure", f"Adapter {attempt_adapter} failed: {e}")
                        continue
                
                # If all adapters in chain failed, raise error
                log_system_event("fallback_chain_exhausted", f"All adapters in fallback chain failed for {adapter_name}")
                raise RuntimeError(f"All adapters in fallback chain failed for {adapter_name}")
            
            # Original single adapter logic
            if adapter_name not in self.adapters:
                # Try to initialize the adapter
                if not await self.initialize_adapter(adapter_name):
                    raise RuntimeError(f"Failed to initialize adapter: {adapter_name}")
            
            adapter = self.adapters[adapter_name]
            response = await adapter.generate_response(prompt, **kwargs)
            
            # Track performance metrics
            tracker.set_tokens_processed(len(response.split()) if response else 0)
            tracker.set_response_size(len(response.encode('utf-8')) if response else 0)
            
            # Log interaction if story_id provided
            if story_id:
                metadata = {"adapter": adapter_name, "kwargs": kwargs}
                adapter.log_interaction(story_id, prompt, response, metadata)
            
            return response
    
    def get_available_adapters(self, standalone_mode: Optional[bool] = None) -> List[str]:
        """
        Get list of actually available and working adapters (standalone-first architecture).
        
        Only returns adapters that are:
        1. Successfully initialized (in self.adapters) OR configured and validated
        2. Not in disabled_adapters
        3. Match standalone mode requirements
        
        Args:
            standalone_mode: If True, only return local/mock adapters. 
                           If False, return all working adapters.
                           If None (default), auto-detect based on environment.
        
        Returns:
            List of adapter names that are actually available and working.
        """
        # Auto-detect standalone mode if not specified
        if standalone_mode is None:
            standalone_mode = self._is_standalone_mode()
        
        available = []
        
        # Check both initialized adapters and configured (validated) adapters
        all_adapter_names = set(self.adapters.keys()) | set(self.config.get("adapters", {}).keys())
        
        for name in all_adapter_names:
            # Skip disabled adapters
            if name in self.disabled_adapters:
                continue
                
            # Get adapter type from config
            adapter_config = self.config.get("adapters", {}).get(name, {})
            adapter_type = adapter_config.get("type", name)
            
            # Skip mock adapters in production unless explicitly allowed
            if adapter_type in ["mock", "mock_image"]:
                # Check if we're in a testing environment
                import os
                is_testing = (
                    os.getenv("TESTING", "").lower() in ["true", "1", "yes"] or
                    os.getenv("PYTEST_CURRENT_TEST") is not None or
                    "pytest" in sys.modules or
                    "test" in sys.argv[0].lower()
                )
                if not is_testing:
                    continue  # Skip mock adapters in production
            
            if standalone_mode:
                # In standalone mode, only include local/mock adapters
                if adapter_type in ["mock", "mock_image", "local", "transformers", "ollama"]:
                    # For ollama, only include if it's actually accessible (not disabled)
                    if adapter_type == "ollama" and name in self.disabled_adapters:
                        continue
                    available.append(name)
            else:
                # In normal mode, include all working (non-disabled) adapters
                available.append(name)
        
        # NO AUTOMATIC MOCK FALLBACK - User must explicitly enable mock adapters
        # This ensures production safety and transparency about available AI capabilities
        if not available:
            log_system_event("no_adapters_available", 
                           "No AI adapters available. Configure API keys, enable local services, or explicitly enable mock adapters if desired.")
        
        return available
    
    def get_adapter_info(self, name: str) -> Dict[str, Any]:
        """Get information about a specific adapter."""
        if name in self.adapters:
            return self.adapters[name].get_model_info()
        elif name in self.config["adapters"]:
            config = self.config["adapters"][name]
            return {
                "provider": config["type"],
                "model_name": config.get("model_name", "unknown"),
                "initialized": False
            }
        else:
            raise ValueError(f"Adapter '{name}' not found")
    
    async def check_adapter_health(self, adapter_name: str) -> Dict[str, Any]:
        """Check the health of a specific adapter."""
        if adapter_name not in self.config["adapters"]:
            return {"status": "unknown", "error": "Adapter not found in configuration"}
        
        adapter_config = self.config["adapters"][adapter_name]
        health_check = adapter_config.get("health_check", {})
        
        if not health_check:
            return {"status": "unknown", "error": "No health check configured"}
        
        try:
            import httpx
            
            async with httpx.AsyncClient(timeout=health_check.get("timeout", 10)) as client:
                if health_check["method"] == "GET":
                    response = await client.get(health_check["endpoint"])
                else:
                    response = await client.post(health_check["endpoint"], json={"test": "health_check"})
                
                if response.status_code == health_check["expected_status"]:
                    return {"status": "healthy", "response_time": response.elapsed.total_seconds()}
                else:
                    return {"status": "unhealthy", "error": f"Unexpected status: {response.status_code}"}
        
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    def get_adapter_for_content(self, content_type: str, content_flags: Optional[Dict[str, Any]] = None) -> str:
        """Get the best adapter for specific content type based on content routing rules."""
        if "content_routing" not in self.config:
            return self.default_adapter or "mock"
        
        routing_rules = self.config["content_routing"]
        content_flags = content_flags or {}
        
        # Check for NSFW content routing
        if content_flags.get("nsfw", False):
            nsfw_adapters = [adapter for adapter in self.get_available_adapters() 
                           if self.config["adapters"][adapter].get("content_filtering", {}).get("supports_nsfw", False)]
            if nsfw_adapters:
                return nsfw_adapters[0]
        
        # Check content type specific routing
        if content_type in routing_rules:
            preferred_adapter = routing_rules[content_type]
            if preferred_adapter in self.get_available_adapters():
                return preferred_adapter
        
        # Default routing
        return routing_rules.get("default", self.default_adapter or "mock")
    
    def get_fallback_chain(self, adapter_name: str) -> List[str]:
        """Get the fallback chain for a specific adapter."""
        if "fallback_chains" not in self.config:
            return [adapter_name]
        
        return self.config["fallback_chains"].get(adapter_name, [adapter_name])
    
    async def generate_image(self, prompt: str, adapter_name: Optional[str] = None, **kwargs) -> str:
        """Generate image using specified or default image adapter."""
        # Use image_adapter from config if no adapter specified
        if adapter_name is None:
            adapter_name = self.config.get("image_adapter", "mock_image")
        
        # At this point adapter_name is guaranteed to be a string
        assert adapter_name is not None  # Type hint for VS Code
        
        if adapter_name not in self.adapters:
            # Try to initialize the adapter
            if not await self.initialize_adapter(adapter_name):
                raise RuntimeError(f"Failed to initialize image adapter: {adapter_name}")
        
        adapter = self.adapters[adapter_name]
        
        # Check if this is actually an image adapter
        if not hasattr(adapter, 'generate_image'):
            raise RuntimeError(f"Adapter '{adapter_name}' does not support image generation")
        
        # Type assertion for VS Code
        assert isinstance(adapter, ImageAdapter), f"Adapter {adapter_name} is not an image adapter"
        return await adapter.generate_image(prompt, **kwargs)

    # ================================
    # DYNAMIC MODEL MANAGEMENT
    # ================================
    
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
                        "text_model": "mock",
                        "image_model": "mock_image"
                    },
                    "text_models": {
                        "testing": []
                    },
                    "image_models": {
                        "testing": []
                    },
                    "content_routing": {
                        "nsfw_content": {"allowed_models": ["mock"], "default_model": "mock"},
                        "safe_content": {"allowed_models": ["mock"], "default_model": "mock"}
                    },
                    "fallback_chains": {
                        "mock": ["mock"]
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
                    registry["image_models"]["testing"].append(model_entry)
            else:
                # Text model
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
                    registry["text_models"]["testing"].append(model_entry)
            
            # Save updated registry
            with open(registry_file, "w", encoding="utf-8") as f:
                json.dump(registry, f, indent=2)
            
            # Reload configuration
            self.config = self._load_config()
            
            # Sync to runtime state for immediate tracking
            self.sync_dynamic_models_to_runtime_state([name])
            
            log_system_event("dynamic_model_add", f"Added model configuration: {name}")
            return True
            
        except Exception as e:
            log_system_event("dynamic_model_add_error", f"Failed to add model {name}: {e}")
            return False
    
    def remove_model_config(self, name: str) -> bool:
        """Remove a model configuration dynamically from the registry."""
        try:
            # Remove from runtime if initialized
            if name in self.adapters:
                del self.adapters[name]
            
            # Update registry
            registry_file = os.path.join("config", "model_registry.json")
            
            if not os.path.exists(registry_file):
                return True  # Nothing to remove
            
            with open(registry_file, "r", encoding="utf-8") as f:
                registry = json.load(f)
            
            # Remove from text_models and image_models
            model_removed = False
            
            # Check text models
            text_models = registry.get("text_models", {})
            for priority_group in ["high_priority", "standard_priority", "testing"]:
                if priority_group in text_models:
                    original_count = len(text_models[priority_group])
                    text_models[priority_group] = [
                        model for model in text_models[priority_group] 
                        if model["name"] != name
                    ]
                    if len(text_models[priority_group]) < original_count:
                        model_removed = True
            
            # Check image models
            image_models = registry.get("image_models", {})
            for priority_group in ["primary", "testing"]:
                if priority_group in image_models:
                    original_count = len(image_models[priority_group])
                    image_models[priority_group] = [
                        model for model in image_models[priority_group] 
                        if model["name"] != name
                    ]
                    if len(image_models[priority_group]) < original_count:
                        model_removed = True
            
            # Remove from fallback chains
            if "fallback_chains" in registry:
                for chain_name, chain in registry["fallback_chains"].items():
                    if isinstance(chain, list) and name in chain:
                        registry["fallback_chains"][chain_name] = [
                            adapter for adapter in chain if adapter != name
                        ]
            
            # Remove from content routing
            if "content_routing" in registry:
                for route_type, route_config in registry["content_routing"].items():
                    if isinstance(route_config, dict):
                        if "allowed_models" in route_config and isinstance(route_config["allowed_models"], list):
                            if name in route_config["allowed_models"]:
                                route_config["allowed_models"] = [
                                    model for model in route_config["allowed_models"] if model != name
                                ]
                        if route_config.get("default_model") == name:
                            # Set to first available model or mock
                            if route_config["allowed_models"]:
                                route_config["default_model"] = route_config["allowed_models"][0]
                            else:
                                route_config["default_model"] = "mock"
            
            # Save updated registry if a model was actually removed
            if model_removed:
                with open(registry_file, "w", encoding="utf-8") as f:
                    json.dump(registry, f, indent=2)
                
                # Reload configuration
                self.config = self._load_config()
                
                # Remove from runtime state
                self.sync_dynamic_models_to_runtime_state([], [name])
                
                # Update default adapter if needed
                if self.default_adapter == name:
                    available = self.get_available_adapters()
                    self.default_adapter = available[0] if available else "mock"
                
                log_system_event("dynamic_model_remove", f"Removed model configuration: {name}")
            else:
                log_system_event("dynamic_model_remove", f"Model {name} not found in registry")
                
            return True
            
        except Exception as e:
            log_system_event("dynamic_model_remove_error", f"Failed to remove model {name}: {e}")
            return False
    
    def enable_model(self, name: str) -> bool:
        """Enable a model in the registry."""
        return self._update_registry_enable_model(name, True)
    
    def disable_model(self, name: str) -> bool:
        """Disable a model in the registry."""
        return self._update_registry_enable_model(name, False)
    
    def _update_registry_enable_model(self, name: str, enabled: bool) -> bool:
        """Enable or disable a model in the registry."""
        try:
            registry_file = os.path.join("config", "model_registry.json")
            
            if not os.path.exists(registry_file):
                return False
            
            with open(registry_file, "r", encoding="utf-8") as f:
                registry = json.load(f)
            
            # Search in text_models and image_models
            model_found = False
            
            # Check text models
            text_models = registry.get("text_models", {})
            for priority_group in ["high_priority", "standard_priority", "testing"]:
                if priority_group in text_models:
                    for model in text_models[priority_group]:
                        if model["name"] == name:
                            model["enabled"] = enabled
                            model_found = True
                            break
                    if model_found:
                        break
            
            # Check image models if not found in text
            if not model_found:
                image_models = registry.get("image_models", {})
                for priority_group in ["primary", "testing"]:
                    if priority_group in image_models:
                        for model in image_models[priority_group]:
                            if model["name"] == name:
                                model["enabled"] = enabled
                                model_found = True
                                break
                        if model_found:
                            break
            
            if not model_found:
                return False  # Model not found
            
            # Save updated registry
            with open(registry_file, "w", encoding="utf-8") as f:
                json.dump(registry, f, indent=2)
            
            # Reload configuration
            self.config = self._load_config()
            
            # Remove from runtime if disabled
            if not enabled and name in self.adapters:
                del self.adapters[name]
            
            action = "enabled" if enabled else "disabled"
            log_system_event("dynamic_model_toggle", f"Model {name} {action}")
            return True
            
        except Exception as e:
            action = "enabled" if enabled else "disabled"
            log_system_event("registry_enable_error", f"Failed to {action} model {name}: {e}")
            return False
    
    def list_model_configs(self) -> Dict[str, Any]:
        """List all model configurations with their status from the registry."""
        models_info = {}
        
        # Get registry information
        registry_file = os.path.join("config", "model_registry.json")
        
        if os.path.exists(registry_file):
            try:
                with open(registry_file, "r", encoding="utf-8") as f:
                    registry = json.load(f)
                
                # Collect all models from registry structure
                all_models = []
                
                # Collect text models from different priority groups
                text_models = registry.get("text_models", {})
                for priority_group in ["high_priority", "standard_priority", "testing"]:
                    if priority_group in text_models:
                        for model in text_models[priority_group]:
                            model["type"] = "text"  # Ensure type is set
                            all_models.append(model)
                
                # Collect image models from different priority groups
                image_models = registry.get("image_models", {})
                for priority_group in ["primary", "testing"]:
                    if priority_group in image_models:
                        for model in image_models[priority_group]:
                            model["type"] = "image"  # Ensure type is set
                            all_models.append(model)
                
                for model_entry in all_models:
                    model_name = model_entry["name"]
                    models_info[model_name] = {
                        "type": model_entry.get("type", "text"),
                        "provider": model_entry.get("provider", model_name),
                        "model_name": model_entry.get("model_name", model_name),
                        "enabled": model_entry.get("enabled", False),
                        "initialized": model_name in self.adapters,
                        "supports_nsfw": model_entry.get("supports_nsfw", False),
                        "content_types": model_entry.get("content_types", ["general"]),
                        "description": model_entry.get("description", f"{model_name} model adapter"),
                        "priority": model_entry.get("priority", 99),
                        "fallbacks": model_entry.get("fallbacks", [])
                    }
                    
            except Exception as e:
                log_error(f"Failed to read registry: {e}")
                models_info["error"] = {
                    "type": "error",
                    "error": f"Failed to read registry: {e}"
                }
        else:
            models_info["error"] = {
                "type": "error", 
                "error": "Model registry not found"
            }
        
        return models_info

    async def sync_ollama_models(self, auto_enable: bool = True, remove_missing: bool = False) -> Dict[str, Any]:
        """
        Synchronize registry with currently available Ollama models.
        
        Args:
            auto_enable: Whether to enable newly discovered models
            remove_missing: Whether to disable models no longer available in Ollama
            
        Returns:
            Dictionary with sync results
        """
        try:
            # Discover current models
            discovery_result = await self.discover_ollama_models()
            if "error" in discovery_result:
                return {"error": f"Failed to discover models: {discovery_result['error']}"}
            
            current_ollama_models = set(discovery_result["models"].keys())
            
            # Get registered Ollama models
            registry_file = os.path.join("config", "model_registry.json")
            if not os.path.exists(registry_file):
                return {"error": "Model registry not found"}
            
            with open(registry_file, "r", encoding="utf-8") as f:
                registry = json.load(f)
            
            registered_ollama_models = set()
            text_models = registry.get("text_models", {})
            
            for priority_group in ["high_priority", "standard_priority", "testing"]:
                if priority_group in text_models:
                    for model_entry in text_models[priority_group]:
                        if model_entry.get("provider") == "ollama":
                            model_name = model_entry.get("model_name", "")
                            if model_name:
                                registered_ollama_models.add(model_name)
            
            # Find differences
            new_models = current_ollama_models - registered_ollama_models
            missing_models = registered_ollama_models - current_ollama_models
            
            results = {
                "current_models": len(current_ollama_models),
                "registered_models": len(registered_ollama_models),
                "new_models": list(new_models),
                "missing_models": list(missing_models),
                "added_count": 0,
                "disabled_count": 0,
                "errors": []
            }
            
            # Add new models
            if new_models:
                add_result = await self.add_discovered_ollama_models(auto_enable=auto_enable)
                if "error" not in add_result:
                    results["added_count"] = len(add_result.get("added_models", []))
                else:
                    results["errors"].append(f"Failed to add new models: {add_result['error']}")
            
            # Disable missing models if requested
            if remove_missing and missing_models:
                for model_name in missing_models:
                    # Find the registry name for this model
                    registry_name = None
                    for priority_group in ["high_priority", "standard_priority", "testing"]:
                        if priority_group in text_models:
                            for model_entry in text_models[priority_group]:
                                if (model_entry.get("provider") == "ollama" and 
                                    model_entry.get("model_name") == model_name):
                                    registry_name = model_entry["name"]
                                    break
                        if registry_name:
                            break
                    
                    if registry_name:
                        if self.disable_model(registry_name):
                            results["disabled_count"] += 1
                            log_info(f"Disabled missing Ollama model: {registry_name} ({model_name})")
                        else:
                            results["errors"].append(f"Failed to disable missing model: {registry_name}")
            
            log_system_event("ollama_sync", f"Synced Ollama models: +{results['added_count']} new, -{results['disabled_count']} missing")
            return results
            
        except Exception as e:
            error_msg = f"Failed to sync Ollama models: {e}"
            log_error(error_msg)
            return {"error": error_msg}

    def sync_dynamic_models_to_runtime_state(self, added_models: Optional[List[str]] = None, removed_models: Optional[List[str]] = None) -> bool:
        """
        Synchronize dynamic models with runtime state for complete tracking and monitoring.
        
        Args:
            added_models: List of model names that were added (optional, will sync all if None)
            removed_models: List of model names that were removed (optional)
            
        Returns:
            bool: True if synchronization was successful
        """
        try:
            runtime_state_file = os.path.join("storage", "data", "runtime", "runtime_state.json")
            
            # Load existing runtime state or create new one
            if os.path.exists(runtime_state_file):
                with open(runtime_state_file, "r", encoding="utf-8") as f:
                    runtime_state = json.load(f)
            else:
                # Create basic runtime state structure
                os.makedirs(os.path.dirname(runtime_state_file), exist_ok=True)
                runtime_state = {
                    "metadata": {
                        "name": "OpenChronicle Model Runtime State",
                        "description": "Dynamic runtime state and analytics for AI models",
                        "last_updated": datetime.now(UTC).isoformat(),
                        "auto_generated": True
                    },
                    "global_runtime": {
                        "intelligent_routing_active": True,
                        "learning_mode_active": True,
                        "last_recommendation_update": datetime.now(UTC).isoformat(),
                        "total_requests_today": 0,
                        "system_performance_score": 0.5
                    },
                    "model_states": {},
                    "content_routing_state": {
                        "nsfw_content": {"current_recommendation": "mock", "recommendation_confidence": 0.5},
                        "safe_content": {"current_recommendation": "mock", "recommendation_confidence": 0.5}
                    },
                    "performance_analytics": {
                        "daily_stats": {
                            "date": datetime.now(UTC).strftime("%Y-%m-%d"),
                            "total_requests": 0,
                            "total_tokens": 0,
                            "total_images": 0,
                            "average_response_time": 0,
                            "overall_success_rate": 1.0,
                            "total_cost": 0.0
                        }
                    }
                }
            
            # If no specific models provided, sync all current models from registry
            if added_models is None:
                all_models = self.get_available_adapters()
                added_models = [model for model in all_models if model not in runtime_state.get("model_states", {})]
            
            # Add new models to runtime state
            for model_name in (added_models or []):
                if model_name not in runtime_state["model_states"]:
                    # Get model info from config
                    model_config = self.config["adapters"].get(model_name, {})
                    provider = model_config.get("type", "unknown")
                    
                    # Create default runtime state entry
                    runtime_state["model_states"][model_name] = {
                        "health_status": "unknown",
                        "last_health_check": None,
                        "average_response_time": 0,
                        "success_rate": 0,
                        "cost_per_request": model_config.get("cost_per_token", 0.0) * 1000,  # Estimate per request
                        "requests_today": 0,
                        "total_tokens_used": 0,
                        "average_quality_score": 0,
                        "user_preference_score": 0.5,
                        "consecutive_failures": 0,
                        "auto_disabled": False,
                        "user_overrides": {
                            "enabled": None,
                            "priority": None,
                            "model_name": None,
                            "supports_nsfw": None,
                            "last_modified": None,
                            "override_reason": None
                        }
                    }
                    
                    # Add image-specific fields for image models
                    if model_config.get("type") == "image":
                        runtime_state["model_states"][model_name]["total_images_generated"] = 0
                    
                    log_info(f"Added runtime state entry for dynamic model: {model_name}")
            
            # Remove models from runtime state
            for model_name in (removed_models or []):
                if model_name in runtime_state["model_states"]:
                    del runtime_state["model_states"][model_name]
                    log_info(f"Removed runtime state entry for model: {model_name}")
                
                # Update content routing recommendations if they pointed to removed model
                for route_type, route_config in runtime_state.get("content_routing_state", {}).items():
                    if isinstance(route_config, dict) and route_config.get("current_recommendation") == model_name:
                        # Find alternative model
                        available_models = list(runtime_state["model_states"].keys())
                        route_config["current_recommendation"] = available_models[0] if available_models else "mock"
                        route_config["last_recommendation_change"] = datetime.now(UTC).isoformat()
                        route_config["recommendation_confidence"] = 0.5  # Reset confidence
            
            # Update metadata
            runtime_state["metadata"]["last_updated"] = datetime.now(UTC).isoformat()
            
            # Save updated runtime state
            with open(runtime_state_file, "w", encoding="utf-8") as f:
                json.dump(runtime_state, f, indent=2)
            
            log_system_event("runtime_state_sync", f"Synchronized runtime state: +{len(added_models or [])} added, -{len(removed_models or [])} removed")
            return True
            
        except Exception as e:
            log_error(f"Failed to sync runtime state: {e}")
            log_system_event("runtime_state_sync_error", f"Failed to sync runtime state: {e}")
            return False

    async def discover_ollama_models(self, base_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Discover available Ollama models by querying the /api/tags endpoint.
        
        Args:
            base_url: Ollama server base URL (optional, uses config if not provided)
            
        Returns:
            Dictionary with discovered models and metadata
        """
        # Use provided URL or get from configuration
        if base_url is None:
            try:
                base_url = self.get_provider_base_url("ollama")
            except FileNotFoundError as e:
                log_error(f"Error getting base URL for provider ollama: {e}")
                return {"error": f"Model registry not found. {e}"}
            
            if not base_url:
                return {"error": "No Ollama base URL configured. Set OLLAMA_HOST environment variable or update registry."}
        
        # Get timeout from global config
        timeout = self.global_config.get("discovery", {}).get("ollama", {}).get("timeout", 10.0)
        
        try:
            import httpx
            
            log_info(f"Discovering Ollama models at {base_url} (timeout: {timeout}s)")
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(f"{base_url}/api/tags")
                response.raise_for_status()
                
                data = response.json()
                models = data.get("models", [])
                
                discovered = {
                    "server_url": base_url,
                    "total_models": len(models),
                    "models": {},
                    "timestamp": datetime.now(UTC).isoformat(),
                    "config_source": "environment" if base_url == self.get_provider_base_url("ollama") else "parameter"
                }
                
                for model in models:
                    model_name = model.get("name", "unknown")
                    size_bytes = model.get("size", 0)
                    modified_at = model.get("modified_at", "")
                    
                    # Convert size to human readable
                    if size_bytes > 1024**3:  # GB
                        size_str = f"{size_bytes / (1024**3):.1f} GB"
                    elif size_bytes > 1024**2:  # MB
                        size_str = f"{size_bytes / (1024**2):.1f} MB"
                    else:
                        size_str = f"{size_bytes} bytes"
                    
                    # Extract base model name (remove tags like :latest, :7b, etc.)
                    base_name = model_name.split(":")[0] if ":" in model_name else model_name
                    
                    discovered["models"][model_name] = {
                        "name": model_name,
                        "base_name": base_name,
                        "size": size_bytes,
                        "size_human": size_str,
                        "modified_at": modified_at,
                        "family": self._guess_model_family(base_name),
                        "capabilities": self._guess_model_capabilities(model_name)
                    }
                
                log_system_event("ollama_discovery", f"Discovered {len(models)} Ollama models from {base_url}")
                return discovered
                
        except ImportError:
            error_msg = "httpx package required for Ollama model discovery"
            log_error(error_msg)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Failed to discover Ollama models from {base_url}: {e}"
            log_error(error_msg)
            return {"error": error_msg}

    def _guess_model_family(self, model_name: str) -> str:
        """Guess the model family based on the model name."""
        model_lower = model_name.lower()
        
        # Check more specific models first
        if "codellama" in model_lower:
            return "codellama"
        elif "llama" in model_lower:
            return "llama"
        elif "gemma" in model_lower:
            return "gemma"
        elif "mistral" in model_lower:
            return "mistral"
        elif "phi" in model_lower:
            return "phi"
        elif "qwen" in model_lower:
            return "qwen"
        elif "neural" in model_lower:
            return "neural-chat"
        elif "orca" in model_lower:
            return "orca"
        elif "vicuna" in model_lower:
            return "vicuna"
        else:
            return "unknown"

    def _guess_model_capabilities(self, model_name: str) -> Dict[str, bool]:
        """Guess model capabilities based on the model name."""
        model_lower = model_name.lower()
        
        capabilities = {
            "text_generation": True,  # All models can generate text
            "code_generation": False,
            "instruction_following": False,
            "conversation": False,
            "analysis": False
        }
        
        # Code generation models
        if any(term in model_lower for term in ["code", "coder", "starcoder", "deepseek-coder"]):
            capabilities["code_generation"] = True
        
        # Instruction following models (check for instruct, chat, it)
        if any(term in model_lower for term in ["instruct", "chat", "it"]):
            capabilities["instruction_following"] = True
            capabilities["conversation"] = True
        
        # Analysis capable models (larger models typically better at analysis)
        if any(term in model_lower for term in ["13b", "30b", "70b", "8x7b", "gemma", "llama"]):
            capabilities["analysis"] = True
        
        return capabilities

    async def add_discovered_ollama_models(
        self, 
        base_url: Optional[str] = None,
        auto_enable: bool = True,
        priority_start: int = 10
    ) -> Dict[str, Any]:
        """
        Discover Ollama models and add them to the model registry.
        
        Args:
            base_url: Ollama server base URL (optional, uses config if not provided)
            auto_enable: Whether to enable discovered models by default
            priority_start: Starting priority number for discovered models
            
        Returns:
            Dictionary with results of the discovery and addition process
        """
        discovery_result = await self.discover_ollama_models(base_url)
        
        if "error" in discovery_result:
            return discovery_result
        
        # Get the actual base URL used for discovery
        actual_base_url = discovery_result["server_url"]
        
        results = {
            "discovered_count": discovery_result["total_models"],
            "added_models": [],
            "skipped_models": [],
            "errors": [],
            "base_url": actual_base_url,
            "config_source": discovery_result.get("config_source", "unknown")
        }
        
        # Load current registry
        registry_file = os.path.join("config", "model_registry.json")
        if not os.path.exists(registry_file):
            results["errors"].append("Model registry not found")
            return results
        
        try:
            with open(registry_file, "r", encoding="utf-8") as f:
                registry = json.load(f)
        except Exception as e:
            results["errors"].append(f"Failed to load registry: {e}")
            return results
        
        # Check existing models to avoid duplicates
        existing_ollama_models = set()
        
        # Check for existing Ollama models in registry
        text_models = registry.get("text_models", {})
        for priority_group in ["high_priority", "standard_priority", "testing"]:
            if priority_group in text_models:
                for model_entry in text_models[priority_group]:
                    if (model_entry.get("provider") == "ollama" or 
                        model_entry["name"].startswith("ollama_")):
                        model_name = model_entry.get("model_name", "")
                        if model_name:
                            existing_ollama_models.add(model_name)
        
        current_priority = priority_start
        
        # Get global defaults
        default_timeout = self.get_global_default("timeout", 120)
        default_max_tokens = self.get_global_default("max_tokens", 2048)
        default_temperature = self.get_global_default("temperature", 0.7)
        
        # Add each discovered model to registry
        for model_name, model_info in discovery_result["models"].items():
            if model_name in existing_ollama_models:
                results["skipped_models"].append({
                    "name": model_name,
                    "reason": "Already exists in registry"
                })
                continue
            
            # Create registry entry for the model
            registry_name = f"ollama_{model_info['base_name']}_{model_name.split(':')[-1] if ':' in model_name else 'latest'}"
            
            new_model_entry = {
                "name": registry_name,
                "provider": "ollama",
                "enabled": auto_enable,
                "priority": current_priority,
                "model_name": model_name,
                "supports_nsfw": True,  # Ollama models typically support NSFW
                "content_types": ["general", "fantasy", "sci-fi", "creative"],
                "description": f"Ollama {model_info['family']} model - {model_info['size_human']}",
                "fallbacks": ["mock"],
                "config": {
                    "base_url": actual_base_url,
                    "timeout": default_timeout,
                    "max_tokens": default_max_tokens,
                    "temperature": default_temperature
                },
                "metadata": {
                    "family": model_info["family"],
                    "size": model_info["size"],
                    "capabilities": model_info["capabilities"],
                    "discovered_at": discovery_result["timestamp"],
                    "config_source": discovery_result.get("config_source", "unknown")
                }
            }
            
            # Add enhanced content types based on capabilities
            if model_info["capabilities"]["code_generation"]:
                new_model_entry["content_types"].extend(["code", "technical"])
            
            if model_info["capabilities"]["analysis"]:
                new_model_entry["content_types"].append("analysis")
            
            # Add to text_models testing section
            if "text_models" not in registry:
                registry["text_models"] = {"testing": []}
            if "testing" not in registry["text_models"]:
                registry["text_models"]["testing"] = []
            
            registry["text_models"]["testing"].append(new_model_entry)
            
            results["added_models"].append({
                "registry_name": registry_name,
                "model_name": model_name,
                "family": model_info["family"],
                "size": model_info["size_human"],
                "capabilities": model_info["capabilities"]
            })
            
            current_priority += 1
        
        # Save updated registry
        try:
            # Create backup
            backup_file = f"{registry_file}.backup.{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
            with open(registry_file, "r", encoding="utf-8") as f:
                backup_content = f.read()
            with open(backup_file, "w", encoding="utf-8") as f:
                f.write(backup_content)
            
            # Write updated registry
            with open(registry_file, "w", encoding="utf-8") as f:
                json.dump(registry, f, indent=2, ensure_ascii=False)
            
            log_system_event(
                "ollama_models_added", 
                f"Added {len(results['added_models'])} Ollama models to registry from {actual_base_url}"
            )
            
            # Reload configuration to pick up new models
            self.global_config = self._load_global_config()
            self.config = self._load_config()
            
        except Exception as e:
            results["errors"].append(f"Failed to save registry: {e}")
        
        return results

    # ================================
    # RUNTIME STATE HELPER METHODS
    # ================================
    
    def _load_runtime_state(self) -> Dict[str, Any]:
        """Load runtime state from storage."""
        try:
            runtime_state_file = os.path.join("storage", "data", "runtime", "runtime_state.json")
            
            if os.path.exists(runtime_state_file):
                with open(runtime_state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                # Return empty structure if file doesn't exist
                return {
                    "model_states": {},
                    "adapter_performance": {},
                    "task_recommendations": {},
                    "content_routing_state": {},
                    "performance_analytics": {},
                    "metadata": {
                        "created": datetime.now(UTC).isoformat(),
                        "last_updated": datetime.now(UTC).isoformat(),
                        "version": "1.0"
                    }
                }
        except Exception as e:
            log_error(f"Failed to load runtime state: {e}")
            return {"model_states": {}, "adapter_performance": {}, "task_recommendations": {}}
    
    def _save_runtime_state(self, runtime_state: Dict[str, Any]) -> bool:
        """Save runtime state to storage."""
        try:
            runtime_state_file = os.path.join("storage", "data", "runtime", "runtime_state.json")
            os.makedirs(os.path.dirname(runtime_state_file), exist_ok=True)
            
            # Update metadata
            if "metadata" not in runtime_state:
                runtime_state["metadata"] = {}
            runtime_state["metadata"]["last_updated"] = datetime.now(UTC).isoformat()
            
            with open(runtime_state_file, "w", encoding="utf-8") as f:
                json.dump(runtime_state, f, indent=2)
            
            return True
        except Exception as e:
            log_error(f"Failed to save runtime state: {e}")
            return False

    def _initialize_performance_monitoring(self):
        """Initialize performance monitoring system."""
        try:
            from utilities.performance_monitor import PerformanceMonitor
            self.performance_monitor = PerformanceMonitor()
            self.performance_monitor.start_monitoring()
            log_system_event("performance_monitoring_init", "Performance monitoring system initialized")
        except ImportError:
            log_system_event("performance_monitoring_disabled", "Performance monitoring disabled - psutil not available")
            self.performance_monitor = None
        except Exception as e:
            log_error(f"Failed to initialize performance monitoring: {e}")
            self.performance_monitor = None

    # ================================
    # PERFORMANCE DIAGNOSTIC AND OPTIMIZATION SYSTEM
    # ================================
    
    async def generate_performance_report(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """
        Generate comprehensive performance diagnostic report.
        
        Args:
            time_window_hours: Hours to include in analysis
            
        Returns:
            Dictionary containing performance report and optimization recommendations
        """
        if not self.performance_monitor:
            return {
                "success": False,
                "error": "Performance monitoring not available",
                "recommendations": ["Install psutil package to enable performance monitoring"]
            }
        
        try:
            # Generate comprehensive report
            report = self.performance_monitor.generate_performance_report(time_window_hours)
            
            # Save report to file
            report_file = self.performance_monitor.save_report_to_file(report)
            
            # Get current system health
            health_summary = self.performance_monitor.get_system_health_summary()
            
            # Generate model registry updates
            registry_updates = self._generate_registry_performance_updates(report)
            
            # Apply automatic optimizations if enabled
            optimizations_applied = await self._apply_automatic_optimizations(report)
            
            log_system_event(
                "performance_report_generated",
                f"Performance report generated: {report.total_operations} operations analyzed, "
                f"{len(report.bottlenecks)} bottlenecks found, {len(report.optimization_recommendations)} recommendations"
            )
            
            return {
                "success": True,
                "report": report,
                "report_file": report_file,
                "health_summary": health_summary,
                "registry_updates": registry_updates,
                "optimizations_applied": optimizations_applied,
                "summary": {
                    "time_period": report.time_period,
                    "total_operations": report.total_operations,
                    "success_rate": report.successful_operations / max(report.total_operations, 1),
                    "avg_duration": report.avg_duration,
                    "efficiency_score": report.avg_efficiency_score,
                    "bottlenecks_found": len(report.bottlenecks),
                    "recommendations_count": len(report.optimization_recommendations),
                    "performance_trend": report.performance_trend,
                    "trend_confidence": report.trend_confidence,
                    "fastest_models": report.fastest_models[:3],
                    "most_efficient_models": report.most_efficient_models[:3],
                    "critical_issues": [
                        b.description for b in report.bottlenecks 
                        if b.severity in ["critical", "high"]
                    ]
                }
            }
            
        except Exception as e:
            log_error(f"Failed to generate performance report: {e}")
            return {
                "success": False,
                "error": str(e),
                "recommendations": ["Check performance monitoring system configuration"]
            }
    
    async def get_model_performance_analytics(self, adapter_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get detailed performance analytics for specific adapter or all adapters.
        
        Args:
            adapter_name: Specific adapter to analyze, or None for all adapters
            
        Returns:
            Dictionary containing performance analytics and rankings
        """
        if not self.performance_monitor:
            return {
                "success": False,
                "error": "Performance monitoring not available"
            }
        
        try:
            if adapter_name:
                # Get statistics for specific adapter
                stats = self.performance_monitor.get_adapter_statistics(adapter_name)
                if not stats:
                    return {
                        "success": False,
                        "error": f"No performance data available for adapter '{adapter_name}'"
                    }
                
                return {
                    "success": True,
                    "adapter_name": adapter_name,
                    "statistics": stats,
                    "rankings": {
                        "efficiency_rank": self._get_adapter_rank(adapter_name, "efficiency"),
                        "speed_rank": self._get_adapter_rank(adapter_name, "speed"),
                        "reliability_rank": self._get_adapter_rank(adapter_name, "reliability")
                    }
                }
            else:
                # Get analytics for all adapters
                all_stats = self.performance_monitor.get_all_adapter_statistics()
                rankings = {
                    "efficiency": self.performance_monitor.get_model_rankings("efficiency"),
                    "speed": self.performance_monitor.get_model_rankings("speed"),
                    "reliability": self.performance_monitor.get_model_rankings("reliability"),
                    "overall": self.performance_monitor.get_model_rankings("overall")
                }
                
                return {
                    "success": True,
                    "all_adapters": all_stats,
                    "rankings": rankings,
                    "summary": {
                        "total_adapters_tracked": len(all_stats),
                        "adapters_with_sufficient_data": len([
                            name for name, stats in all_stats.items()
                            if stats.get("total_operations", 0) >= 3
                        ]),
                        "best_overall": rankings["overall"][0] if rankings["overall"] else None,
                        "fastest": rankings["speed"][0] if rankings["speed"] else None,
                        "most_reliable": rankings["reliability"][0] if rankings["reliability"] else None
                    }
                }
                
        except Exception as e:
            log_error(f"Failed to get model performance analytics: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def analyze_performance_bottlenecks(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """
        Analyze current performance bottlenecks and provide specific recommendations.
        
        Args:
            time_window_hours: Hours to analyze for bottlenecks
            
        Returns:
            Dictionary containing bottleneck analysis and recommendations
        """
        if not self.performance_monitor:
            return {
                "success": False,
                "error": "Performance monitoring not available"
            }
        
        try:
            # Analyze bottlenecks
            bottlenecks = self.performance_monitor.analyze_bottlenecks(time_window_hours)
            
            # Get current system health
            health = self.performance_monitor.get_system_health_summary()
            
            # Get active operations that might be causing issues
            active_ops = self.performance_monitor.get_active_operations()
            
            # Categorize bottlenecks by severity
            critical_bottlenecks = [b for b in bottlenecks if b.severity == "critical"]
            high_bottlenecks = [b for b in bottlenecks if b.severity == "high"]
            medium_bottlenecks = [b for b in bottlenecks if b.severity == "medium"]
            
            # Generate immediate action recommendations
            immediate_actions = self._generate_immediate_action_recommendations(
                critical_bottlenecks, high_bottlenecks, health
            )
            
            log_system_event(
                "bottleneck_analysis_completed",
                f"Analyzed performance bottlenecks: {len(critical_bottlenecks)} critical, "
                f"{len(high_bottlenecks)} high, {len(medium_bottlenecks)} medium severity"
            )
            
            return {
                "success": True,
                "analysis_period": f"Last {time_window_hours} hours",
                "system_health": health,
                "bottlenecks": {
                    "critical": critical_bottlenecks,
                    "high": high_bottlenecks,
                    "medium": medium_bottlenecks,
                    "total_count": len(bottlenecks)
                },
                "active_operations": active_ops,
                "immediate_actions": immediate_actions,
                "summary": {
                    "health_status": health.get("health_status", "unknown"),
                    "critical_issues_count": len(critical_bottlenecks),
                    "needs_immediate_attention": len(critical_bottlenecks) > 0 or health.get("health_status") == "critical",
                    "cpu_usage": health.get("cpu_usage_percent", 0),
                    "memory_usage": health.get("memory_usage_percent", 0),
                    "recent_success_rate": health.get("recent_success_rate", 1.0)
                }
            }
            
        except Exception as e:
            log_error(f"Failed to analyze performance bottlenecks: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_optimization_recommendations(self, target_use_case: str = "general") -> Dict[str, Any]:
        """
        Get specific optimization recommendations based on use case and current performance.
        
        Args:
            target_use_case: "speed", "efficiency", "reliability", or "general"
            
        Returns:
            Dictionary containing targeted optimization recommendations
        """
        if not self.performance_monitor:
            return {
                "success": False,
                "error": "Performance monitoring not available",
                "recommendations": ["Install psutil package to enable performance monitoring"]
            }
        
        try:
            # Get current performance data
            report = self.performance_monitor.generate_performance_report(24)
            health = self.performance_monitor.get_system_health_summary()
            
            # Get model rankings for the target use case
            if target_use_case == "speed":
                rankings = self.performance_monitor.get_model_rankings("speed")
            elif target_use_case == "efficiency":
                rankings = self.performance_monitor.get_model_rankings("efficiency")
            elif target_use_case == "reliability":
                rankings = self.performance_monitor.get_model_rankings("reliability")
            else:  # general
                rankings = self.performance_monitor.get_model_rankings("overall")
            
            # Generate targeted recommendations
            recommendations = []
            
            # Model selection recommendations
            if rankings:
                top_models = rankings[:3]
                recommendations.append({
                    "category": "model_selection",
                    "priority": "high",
                    "title": f"Optimize for {target_use_case}",
                    "description": f"Based on performance data, these models perform best for {target_use_case} use cases",
                    "action": f"Consider using: {', '.join([name for name, _ in top_models])}",
                    "expected_impact": "20-50% improvement in target metric",
                    "evidence": {
                        "top_models": top_models,
                        "data_points": sum(
                            (self.performance_monitor.get_adapter_statistics(name) or {}).get("total_operations", 0)
                            for name, _ in top_models
                        ) if self.performance_monitor else 0
                    }
                })
            
            # System resource recommendations
            cpu_usage = health.get("cpu_usage_percent", 0)
            memory_usage = health.get("memory_usage_percent", 0)
            
            if cpu_usage > 80:
                recommendations.append({
                    "category": "system_resources",
                    "priority": "critical" if cpu_usage > 90 else "high",
                    "title": "High CPU Usage Detected",
                    "description": f"CPU usage is {cpu_usage:.1f}%, which may impact performance",
                    "action": "Reduce concurrent operations or use lighter models",
                    "expected_impact": "Reduced latency and improved stability",
                    "evidence": {"cpu_usage": cpu_usage}
                })
            
            if memory_usage > 85:
                recommendations.append({
                    "category": "system_resources",
                    "priority": "critical" if memory_usage > 95 else "high",
                    "title": "High Memory Usage Detected",
                    "description": f"Memory usage is {memory_usage:.1f}%, which may cause system instability",
                    "action": "Implement memory cleanup or use models with lower memory requirements",
                    "expected_impact": "Improved stability and reduced risk of crashes",
                    "evidence": {"memory_usage": memory_usage}
                })
            
            # Performance trend recommendations
            if report.performance_trend == "degrading" and report.trend_confidence > 0.6:
                recommendations.append({
                    "category": "performance_trend",
                    "priority": "medium",
                    "title": "Performance Degradation Detected",
                    "description": f"Performance has been degrading with {report.trend_confidence:.1%} confidence",
                    "action": "Review recent changes and consider system maintenance",
                    "expected_impact": "Restore previous performance levels",
                    "evidence": {
                        "trend": report.performance_trend,
                        "confidence": report.trend_confidence
                    }
                })
            
            # Configuration recommendations based on bottlenecks
            for bottleneck in report.bottlenecks:
                if bottleneck.severity in ["critical", "high"]:
                    recommendations.append({
                        "category": "configuration",
                        "priority": bottleneck.severity,
                        "title": f"{bottleneck.bottleneck_type.title()} Bottleneck",
                        "description": bottleneck.description,
                        "action": bottleneck.recommendation,
                        "expected_impact": f"Reduce {bottleneck.bottleneck_type} impact by {bottleneck.impact_score:.1%}",
                        "evidence": bottleneck.evidence
                    })
            
            # Sort recommendations by priority
            priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            recommendations.sort(key=lambda x: priority_order.get(x["priority"], 4))
            
            log_system_event(
                "optimization_recommendations_generated",
                f"Generated {len(recommendations)} optimization recommendations for {target_use_case} use case"
            )
            
            return {
                "success": True,
                "target_use_case": target_use_case,
                "recommendations": recommendations,
                "current_performance": {
                    "avg_duration": report.avg_duration,
                    "success_rate": report.successful_operations / max(report.total_operations, 1),
                    "efficiency_score": report.avg_efficiency_score,
                    "system_health": health.get("health_status", "unknown")
                },
                "summary": {
                    "total_recommendations": len(recommendations),
                    "critical_issues": len([r for r in recommendations if r["priority"] == "critical"]),
                    "high_priority": len([r for r in recommendations if r["priority"] == "high"]),
                    "expected_overall_impact": "Significant improvement expected" if len(recommendations) > 2 else "Moderate improvement expected"
                }
            }
            
        except Exception as e:
            log_error(f"Failed to generate optimization recommendations: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _generate_registry_performance_updates(self, report) -> Dict[str, Any]:
        """Generate performance-based updates for model registry."""
        try:
            updates = {}
            
            # Update performance ratings for each model
            for adapter_name, rating in report.model_rankings.items():
                updates[adapter_name] = {
                    "performance_rating": rating,
                    "last_benchmark": datetime.now(UTC).isoformat(),
                    "operations_count": report.total_operations
                }
            
            # Add speed rankings
            for i, (adapter_name, speed_score) in enumerate(report.fastest_models):
                if adapter_name in updates:
                    updates[adapter_name]["speed_rank"] = i + 1
                    updates[adapter_name]["speed_score"] = speed_score
            
            # Add efficiency rankings
            for i, (adapter_name, efficiency_score) in enumerate(report.most_efficient_models):
                if adapter_name in updates:
                    updates[adapter_name]["efficiency_rank"] = i + 1
                    updates[adapter_name]["efficiency_score"] = efficiency_score
            
            # Add reliability rankings
            for i, (adapter_name, reliability_score) in enumerate(report.most_reliable_models):
                if adapter_name in updates:
                    updates[adapter_name]["reliability_rank"] = i + 1
                    updates[adapter_name]["reliability_score"] = reliability_score
            
            return {
                "success": True,
                "updates": updates,
                "timestamp": datetime.now(UTC).isoformat()
            }
            
        except Exception as e:
            log_error(f"Failed to generate registry performance updates: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _apply_automatic_optimizations(self, report) -> List[str]:
        """Apply automatic optimizations based on performance report."""
        optimizations_applied = []
        
        try:
            # Auto-disable consistently failing adapters
            for adapter_name in self.adapters:
                if not self.performance_monitor:
                    continue
                stats = self.performance_monitor.get_adapter_statistics(adapter_name)
                if stats and stats.get("success_rate", 1.0) < 0.3 and stats.get("total_operations", 0) > 5:
                    # Don't actually disable, just log the recommendation
                    optimizations_applied.append(
                        f"Recommended: Disable {adapter_name} (success rate: {stats['success_rate']:.1%})"
                    )
            
            # Update default model based on performance
            if report.most_efficient_models:
                best_model = report.most_efficient_models[0][0]
                if best_model in self.adapters and best_model != self.default_adapter:
                    # Don't automatically change default, just recommend
                    optimizations_applied.append(
                        f"Recommended: Consider setting {best_model} as default adapter"
                    )
            
            # Log memory cleanup recommendation if needed
            if report.avg_memory_usage > 1000:  # > 1GB
                optimizations_applied.append(
                    "Recommended: Implement periodic memory cleanup"
                )
            
        except Exception as e:
            log_error(f"Failed to apply automatic optimizations: {e}")
            optimizations_applied.append(f"Error applying optimizations: {str(e)}")
        
        return optimizations_applied
    
    def _get_adapter_rank(self, adapter_name: str, criteria: str) -> Optional[int]:
        """Get the rank of an adapter for specific criteria."""
        try:
            if not self.performance_monitor:
                return None
            rankings = self.performance_monitor.get_model_rankings(criteria)
            for i, (name, _) in enumerate(rankings):
                if name == adapter_name:
                    return i + 1
            return None
        except Exception:
            return None
    
    def _generate_immediate_action_recommendations(self, critical_bottlenecks, high_bottlenecks, health) -> List[str]:
        """Generate immediate action recommendations for critical issues."""
        actions = []
        
        # Critical bottlenecks
        for bottleneck in critical_bottlenecks:
            actions.append(f"CRITICAL: {bottleneck.recommendation}")
        
        # High priority bottlenecks
        for bottleneck in high_bottlenecks:
            actions.append(f"HIGH: {bottleneck.recommendation}")
        
        # System health issues
        health_status = health.get("health_status", "unknown")
        if health_status == "critical":
            cpu_usage = health.get("cpu_usage_percent", 0)
            memory_usage = health.get("memory_usage_percent", 0)
            
            if cpu_usage > 90:
                actions.append("IMMEDIATE: Reduce system load - CPU usage critical")
            if memory_usage > 95:
                actions.append("IMMEDIATE: Free memory - system instability risk")
        
        # Success rate issues
        success_rate = health.get("recent_success_rate", 1.0)
        if success_rate < 0.7:
            actions.append("URGENT: Investigate adapter failures - low success rate")
        
        return actions

    def track_model_operation(self, adapter_name: str, operation_type: str, **kwargs):
        """
        Context manager for tracking model operation performance.
        
        Usage:
            async with model_manager.track_model_operation("gpt4", "generate") as tracker:
                result = await adapter.generate_response(prompt)
                tracker.set_tokens_processed(len(result.split()))
        """
        if self.performance_monitor:
            return self.performance_monitor.track_operation(adapter_name, operation_type, **kwargs)
        else:
            # Return a no-op context manager if monitoring is disabled
            from contextlib import asynccontextmanager
            
            @asynccontextmanager
            async def dummy_tracker():
                class DummyTracker:
                    def set_tokens_processed(self, count): pass
                    def set_response_size(self, size): pass
                    def set_network_latency(self, latency): pass
                    def set_processing_time(self, time): pass
                    def set_quality_score(self, score): pass
                
                yield DummyTracker()
            
            return dummy_tracker()

    # ================================

    # ================================
    # INTELLIGENT MODEL RECOMMENDATION SYSTEM
    # ================================
    
    async def profile_system_and_generate_recommendations(self) -> Dict[str, Any]:
        """Profile system capabilities and generate personalized model recommendations."""
        try:
            # Import here to avoid circular imports
            from utilities.system_profiler import SystemProfiler
            
            log_system_event("system_profiling_started", f"Starting system profiling with manager {id(self)}")
            
            # Create profiler and run complete analysis
            profiler = SystemProfiler()
            
            # Step 1: Profile hardware
            system_specs = profiler.profile_system_hardware()
            log_info(f"System profiled: {system_specs.cpu_cores} cores, {system_specs.total_memory:.1f}GB RAM")
            
            # Step 2: Benchmark available models
            benchmarks = await profiler.benchmark_available_models(self)
            log_info(f"Benchmarked {len(benchmarks)} models")
            
            # Step 3: Generate recommendations
            recommendations = profiler.generate_model_recommendations()
            log_info(f"Generated {len(recommendations)} recommendations")
            
            # Step 4: Save profile results
            profile_file = profiler.save_profile_results()
            
            # Step 5: Update runtime state with recommendations
            await self._update_runtime_recommendations(recommendations)
            
            results = {
                "success": True,
                "system_specs": system_specs,
                "benchmarks": benchmarks,
                "recommendations": recommendations,
                "profile_file": profile_file,
                "summary": profiler.get_system_summary()
            }
            
            log_system_event("system_profiling_completed", 
                           f"System profiling completed: {profiler._categorize_system_tier()} tier, "
                           f"{len(benchmarks)} models tested, {len(recommendations)} recommendations generated")
            
            return results
            
        except Exception as e:
            log_error(f"System profiling failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "recommendations": []
            }
    
    async def get_model_recommendation_for_task(self, task_type: str = "general") -> Optional[str]:
        """Get the best model recommendation for a specific task type."""
        try:
            # Check if we have cached recommendations in runtime state
            runtime_state = self._load_runtime_state()
            
            task_recommendations = runtime_state.get("task_recommendations", {})
            task_rec = task_recommendations.get(task_type, {})
            
            if task_rec.get("current_recommendation"):
                model_name = task_rec["current_recommendation"]
                confidence = task_rec.get("recommendation_confidence", 0.0)
                
                # Return recommendation if confidence is reasonable and model is available
                if confidence > 0.5 and model_name in self.get_available_adapters():
                    log_info(f"Using cached recommendation for {task_type}: {model_name} (confidence: {confidence:.2f})")
                    return model_name
                else:
                    log_info(f"Cached recommendation for {task_type} has low confidence or unavailable model")
            
            # If no good cached recommendation, try to find best available
            return await self._find_best_available_model_for_task(task_type)
            
        except Exception as e:
            log_error(f"Failed to get model recommendation for {task_type}: {e}")
            return None
    
    async def _find_best_available_model_for_task(self, task_type: str) -> Optional[str]:
        """Find the best available model for a specific task without full profiling."""
        available_adapters = self.get_available_adapters()
        
        if not available_adapters:
            return None
        
        # Simple heuristics based on model names and runtime performance data
        runtime_state = self._load_runtime_state()
        adapter_stats = runtime_state.get("adapter_performance", {})
        
        scored_models = []
        
        for adapter_name in available_adapters:
            try:
                # Get adapter info
                info = self.get_adapter_info(adapter_name)
                
                # Skip non-text models for most tasks
                if task_type in ["fast_responses", "analysis", "creative", "general"] and info.get("type") == "image":
                    continue
                
                score = 0.0
                
                # Performance-based scoring from runtime stats
                stats = adapter_stats.get(adapter_name, {})
                
                # Response time factor (prefer faster models for some tasks)
                avg_response_time = stats.get("average_response_time", 10.0)
                if task_type == "fast_responses":
                    score += max(0, (10.0 - avg_response_time) / 10.0) * 0.4
                else:
                    score += max(0, (20.0 - avg_response_time) / 20.0) * 0.2
                
                # Success rate factor
                success_rate = stats.get("success_rate", 0.5)
                score += success_rate * 0.3
                
                # Quality score factor
                quality_score = stats.get("average_quality_score", 2.5)
                score += (quality_score / 5.0) * 0.2
                
                # Model name heuristics
                model_lower = adapter_name.lower()
                
                if task_type == "fast_responses":
                    if any(term in model_lower for term in ["groq", "fast", "turbo"]):
                        score += 0.2
                elif task_type == "analysis":
                    if any(term in model_lower for term in ["gpt-4", "claude", "sonnet", "opus"]):
                        score += 0.3
                    elif any(term in model_lower for term in ["gemini", "llama-2"]):
                        score += 0.15
                elif task_type == "creative":
                    if any(term in model_lower for term in ["gpt", "claude", "gemini"]):
                        score += 0.25
                elif task_type == "general":
                    if any(term in model_lower for term in ["gpt", "claude"]):
                        score += 0.2
                
                # Health status bonus
                if stats.get("health_status") == "healthy":
                    score += 0.1
                
                scored_models.append((adapter_name, score))
                
            except Exception as e:
                log_info(f"Error scoring model {adapter_name}: {e}")
                continue
        
        if not scored_models:
            # Fallback to first available model
            return available_adapters[0] if available_adapters else None
        
        # Sort by score and return best
        scored_models.sort(key=lambda x: x[1], reverse=True)
        best_model = scored_models[0][0]
        
        log_info(f"Selected {best_model} for {task_type} (score: {scored_models[0][1]:.2f})")
        return best_model
    
    async def _update_runtime_recommendations(self, recommendations: List) -> None:
        """Update runtime state with new model recommendations."""
        try:
            runtime_state = self._load_runtime_state()
            
            # Create task recommendations mapping
            task_recommendations = runtime_state.get("task_recommendations", {})
            current_time = datetime.now(UTC).isoformat()
            
            # Group recommendations by task type
            for rec in recommendations:
                for task_type in rec.recommended_for:
                    if task_type not in task_recommendations:
                        task_recommendations[task_type] = {}
                    
                    # Update if this is a better recommendation
                    current_confidence = task_recommendations[task_type].get("recommendation_confidence", 0.0)
                    if rec.confidence_score > current_confidence:
                        task_recommendations[task_type].update({
                            "current_recommendation": rec.model_name,
                            "last_recommendation_change": current_time,
                            "recommendation_confidence": rec.confidence_score,
                            "user_override_active": False,
                            "rationale": rec.rationale,
                            "configuration_suggestions": rec.configuration_suggestions
                        })
            
            # Ensure all standard task types exist
            standard_tasks = ["fast_responses", "analysis", "creative", "general"]
            for task_type in standard_tasks:
                if task_type not in task_recommendations:
                    # Try to find a fallback recommendation
                    fallback = await self._find_best_available_model_for_task(task_type)
                    if fallback:
                        task_recommendations[task_type] = {
                            "current_recommendation": fallback,
                            "last_recommendation_change": current_time,
                            "recommendation_confidence": 0.5,
                            "user_override_active": False,
                            "rationale": "Fallback recommendation based on availability",
                            "configuration_suggestions": {}
                        }
            
            runtime_state["task_recommendations"] = task_recommendations
            
            # Add profiling metadata
            runtime_state["last_system_profile"] = current_time
            runtime_state["profiling_version"] = "1.0"
            
            self._save_runtime_state(runtime_state)
            
            log_system_event("runtime_recommendations_updated", 
                           f"Updated {len(task_recommendations)} task recommendations at {current_time}")
            
        except Exception as e:
            log_error(f"Failed to update runtime recommendations: {e}")
    
    def get_system_recommendations_summary(self) -> Dict[str, Any]:
        """Get a summary of current system recommendations."""
        try:
            runtime_state = self._load_runtime_state()
            task_recommendations = runtime_state.get("task_recommendations", {})
            
            summary = {
                "available": bool(task_recommendations),
                "last_profile": runtime_state.get("last_system_profile"),
                "recommendations": {},
                "system_info": {}
            }
            
            # Add recommendations for each task type
            for task_type, rec_data in task_recommendations.items():
                summary["recommendations"][task_type] = {
                    "model": rec_data.get("current_recommendation"),
                    "confidence": rec_data.get("recommendation_confidence", 0.0),
                    "rationale": rec_data.get("rationale", ""),
                    "last_updated": rec_data.get("last_recommendation_change")
                }
            
            # Add quick system info
            try:
                from utilities.system_profiler import get_quick_system_info
                summary["system_info"] = get_quick_system_info()
            except Exception:
                summary["system_info"] = {"error": "Unable to get system info"}
            
            return summary
            
        except Exception as e:
            log_error(f"Failed to get recommendations summary: {e}")
            return {"available": False, "error": str(e)}
    
    async def auto_configure_optimal_settings(self, adapter_name: str, task_type: str = "general") -> Dict[str, Any]:
        """Auto-configure optimal settings for a model based on system capabilities and task type."""
        try:
            # Get system info
            from utilities.system_profiler import get_quick_system_info
            system_info = get_quick_system_info()
            
            # Get runtime performance data
            runtime_state = self._load_runtime_state()
            adapter_stats = runtime_state.get("adapter_performance", {}).get(adapter_name, {})
            task_recommendations = runtime_state.get("task_recommendations", {})
            
            # Base configuration
            config = {
                "model_name": adapter_name,
                "temperature": 0.7,
                "max_tokens": 800,
                "timeout": 30
            }
            
            # Adjust based on system tier
            memory_gb = system_info.get("memory_gb", 8)
            cpu_cores = system_info.get("cpu_cores", 4)
            
            if memory_gb < 8 or cpu_cores < 4:
                # Low-end system
                config.update({
                    "max_tokens": 400,
                    "timeout": 20,
                    "batch_size": 1
                })
            elif memory_gb >= 16 and cpu_cores >= 8:
                # High-end system
                config.update({
                    "max_tokens": 1500,
                    "timeout": 60,
                    "batch_size": 2
                })
            
            # Task-specific adjustments
            if task_type == "fast_responses":
                config.update({
                    "temperature": 0.5,
                    "max_tokens": min(config["max_tokens"], 200),
                    "timeout": 15
                })
            elif task_type == "analysis":
                config.update({
                    "temperature": 0.3,
                    "max_tokens": max(config["max_tokens"], 1000),
                    "timeout": 45
                })
            elif task_type == "creative":
                config.update({
                    "temperature": 0.8,
                    "max_tokens": max(config["max_tokens"], 800),
                    "timeout": 60
                })
            
            # Apply recommendations from profiling if available
            task_rec = task_recommendations.get(task_type, {})
            if task_rec.get("configuration_suggestions"):
                suggestions = task_rec["configuration_suggestions"]
                for key, value in suggestions.items():
                    if key in config:
                        config[key] = value
            
            # Performance-based adjustments
            avg_response_time = adapter_stats.get("average_response_time", 5.0)
            if avg_response_time > 10.0:
                # Slow model, reduce max_tokens and timeout
                config["max_tokens"] = int(config["max_tokens"] * 0.7)
                config["timeout"] = min(config["timeout"], 30)
            elif avg_response_time < 2.0:
                # Fast model, can afford higher limits
                config["max_tokens"] = int(config["max_tokens"] * 1.2)
                config["timeout"] = min(config["timeout"] + 15, 90)
            
            log_info(f"Auto-configured optimal settings for {adapter_name} ({task_type}): {config}")
            
            return {
                "success": True,
                "configuration": config,
                "system_tier": "high_end" if memory_gb >= 16 and cpu_cores >= 8 else ("mid_range" if memory_gb >= 8 else "low_end"),
                "task_type": task_type,
                "reasoning": f"Optimized for {task_type} on {system_info.get('platform', 'unknown')} system"
            }
            
        except Exception as e:
            log_error(f"Failed to auto-configure settings for {adapter_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "configuration": {"temperature": 0.7, "max_tokens": 800, "timeout": 30}
            }

    async def shutdown(self):
        """Shutdown all adapters."""
        for adapter in self.adapters.values():
            # Use getattr with default to avoid type checker issues
            client = getattr(adapter, 'client', None)
            if client:
                if hasattr(client, 'aclose'):
                    await client.aclose()  # type: ignore

# Global model manager instance
model_manager = ModelManager()

# ================================
# TEXT GENERATION ADAPTERS
# ================================

class AnthropicAdapter(ModelAdapter):
    """Anthropic Claude adapter."""
    
    def __init__(self, config: Dict[str, Any], model_manager=None):
        super().__init__(config)
        self.api_key = get_api_key_with_fallback(config, "anthropic", "ANTHROPIC_API_KEY")
        self.model_manager = model_manager
        self.base_url = self._get_base_url(config)
        self.client = None
    
    def _get_base_url(self, config: Dict[str, Any]) -> str:
        """Get base URL from config or model manager."""
        # Check explicit config first
        if "base_url" in config:
            return config["base_url"]
        
        # Use model manager if available
        if self.model_manager:
            try:
                return self.model_manager.get_provider_base_url("anthropic")
            except Exception:
                pass
        
        # Fallback to environment variable only
        env_url = os.getenv("ANTHROPIC_BASE_URL")
        if env_url:
            return env_url
            
        raise ValueError("No base URL configured for Anthropic. Please set ANTHROPIC_BASE_URL or configure in registry.")
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize Anthropic client."""
        if not self.api_key:
            raise ValueError("Anthropic API key required")
        
        try:
            import anthropic
            self.client = anthropic.AsyncAnthropic(
                api_key=self.api_key,
                base_url=self.base_url
            )
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("anthropic package required for Anthropic adapter")
        except Exception as e:
            log_error(f"Failed to initialize Anthropic adapter: {e}")
            return False
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Anthropic Claude."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            response = await self.client.messages.create(  # type: ignore
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature)
            )
            # Handle response content properly for Anthropic
            if hasattr(response, 'content') and len(response.content) > 0:
                content_block = response.content[0]
                if hasattr(content_block, 'text'):
                    return content_block.text  # type: ignore
            return ""
        except Exception as e:
            raise RuntimeError(f"Anthropic API error: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Anthropic model information."""
        return {
            "provider": "Anthropic",
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "initialized": self.initialized
        }

class GeminiAdapter(ModelAdapter):
    """Google Gemini adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = get_api_key_with_fallback(config, "google", "GOOGLE_API_KEY")
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize Gemini client."""
        if not self.api_key:
            raise ValueError("Google API key required")
        
        try:
            import google.generativeai as genai  # type: ignore
            genai.configure(api_key=self.api_key)  # type: ignore
            self.client = genai.GenerativeModel(self.model_name)  # type: ignore
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("google-generativeai package required for Gemini adapter")
        except Exception as e:
            log_error(f"Failed to initialize Gemini adapter: {e}")
            return False
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Google Gemini."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            response = self.client.generate_content(  # type: ignore
                prompt,
                generation_config={
                    "temperature": kwargs.get("temperature", self.temperature),
                    "max_output_tokens": kwargs.get("max_tokens", self.max_tokens),
                }
            )
            return response.text
        except Exception as e:
            raise RuntimeError(f"Gemini API error: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Gemini model information."""
        return {
            "provider": "Google",
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "initialized": self.initialized
        }

class GroqAdapter(ModelAdapter):
    """Groq fast inference adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = get_api_key_with_fallback(config, "groq", "GROQ_API_KEY")
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize Groq client."""
        if not self.api_key:
            raise ValueError("Groq API key required")
        
        try:
            import groq
            self.client = groq.AsyncGroq(api_key=self.api_key)
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("groq package required for Groq adapter")
        except Exception as e:
            log_error(f"Failed to initialize Groq adapter: {e}")
            return False
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Groq."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            response = await self.client.chat.completions.create(  # type: ignore
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature)
            )
            content = response.choices[0].message.content
            if content is None:
                return ""
            return content
        except Exception as e:
            raise RuntimeError(f"Groq API error: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Groq model information."""
        return {
            "provider": "Groq",
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "initialized": self.initialized
        }

class CohereAdapter(ModelAdapter):
    """Cohere Command adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = get_api_key_with_fallback(config, "cohere", "COHERE_API_KEY")
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize Cohere client."""
        if not self.api_key:
            raise ValueError("Cohere API key required")
        
        try:
            import cohere  # type: ignore
            self.client = cohere.AsyncClient(api_key=self.api_key)
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("cohere package required for Cohere adapter")
        except Exception as e:
            log_error(f"Failed to initialize Cohere adapter: {e}")
            return False
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Cohere."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            response = await self.client.generate(  # type: ignore
                model=self.model_name,
                prompt=prompt,
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature)
            )
            return response.generations[0].text
        except Exception as e:
            raise RuntimeError(f"Cohere API error: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Cohere model information."""
        return {
            "provider": "Cohere",
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "initialized": self.initialized
        }

class MistralAdapter(ModelAdapter):
    """Mistral AI adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = get_api_key_with_fallback(config, "mistral", "MISTRAL_API_KEY")
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize Mistral client."""
        if not self.api_key:
            raise ValueError("Mistral API key required")
        
        try:
            from mistralai.async_client import MistralAsyncClient
            self.client = MistralAsyncClient(api_key=self.api_key)
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("mistralai package required for Mistral adapter")
        except Exception as e:
            log_error(f"Failed to initialize Mistral adapter: {e}")
            return False
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Mistral."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            from mistralai.models.chat_completion import ChatMessage  # type: ignore
            response = await self.client.chat(  # type: ignore
                model=self.model_name,
                messages=[ChatMessage(role="user", content=prompt)],
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature)
            )
            return response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"Mistral API error: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Mistral model information."""
        return {
            "provider": "Mistral",
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "initialized": self.initialized
        }

class HuggingFaceAdapter(ModelAdapter):
    """Hugging Face Inference API adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = get_api_key_with_fallback(config, "huggingface", "HUGGINGFACE_API_KEY")
        self.base_url = config.get("base_url", "https://api-inference.huggingface.co/models/")
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize Hugging Face client."""
        if not self.api_key:
            raise ValueError("Hugging Face API key required")
        
        try:
            import httpx
            self.client = httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("httpx package required for Hugging Face adapter")
        except Exception as e:
            log_error(f"Failed to initialize Hugging Face adapter: {e}")
            return False
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Hugging Face."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            response = await self.client.post(  # type: ignore[attr-defined]
                f"{self.base_url}{self.model_name}",
                json={
                    "inputs": prompt,
                    "parameters": {
                        "max_new_tokens": kwargs.get("max_tokens", self.max_tokens),
                        "temperature": kwargs.get("temperature", self.temperature)
                    }
                }
            )
            result = response.json()
            return result[0]["generated_text"]
        except Exception as e:
            raise RuntimeError(f"Hugging Face API error: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Hugging Face model information."""
        return {
            "provider": "Hugging Face",
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "initialized": self.initialized
        }

class AzureOpenAIAdapter(ModelAdapter):
    """Azure OpenAI adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = get_api_key_with_fallback(config, "azure", "AZURE_OPENAI_API_KEY")
        self.azure_endpoint = config.get("azure_endpoint") or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_version = config.get("api_version", "2024-02-01")
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize Azure OpenAI client."""
        if not self.api_key or not self.azure_endpoint:
            raise ValueError("Azure OpenAI API key and endpoint required")
        
        try:
            from openai import AsyncAzureOpenAI
            self.client = AsyncAzureOpenAI(
                api_key=self.api_key,
                azure_endpoint=self.azure_endpoint,
                api_version=self.api_version
            )
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("openai package required for Azure OpenAI adapter")
        except Exception as e:
            log_error(f"Failed to initialize Azure OpenAI adapter: {e}")
            return False
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using Azure OpenAI."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            response = await self.client.chat.completions.create(  # type: ignore
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature)
            )
            content = response.choices[0].message.content
            if content is None:
                return ""
            return content
        except Exception as e:
            raise RuntimeError(f"Azure OpenAI API error: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Azure OpenAI model information."""
        return {
            "provider": "Azure OpenAI",
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "initialized": self.initialized
        }

class TransformersAdapter(ModelAdapter):
    """Local Transformers adapter for standalone text generation."""
    
    def __init__(self, config: Dict[str, Any], model_manager=None):
        super().__init__(config)
        self.model_manager = model_manager
        self.generator = None
        self.model_id = config.get("model_name", "gpt2")
        self.max_length = config.get("max_length", 512)
        self.device = -1  # CPU by default for broad compatibility
        
    async def initialize(self) -> bool:
        """Initialize local transformers model."""
        try:
            # Use correct import for pipeline
            try:
                from transformers.pipelines import pipeline
            except ImportError:
                from transformers import pipeline  # type: ignore
            import torch
            
            # Use CPU for maximum compatibility
            self.device = -1
            
            log_info(f"Initializing local transformers model: {self.model_id}")
            
            # Suppress model loading output
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                
                # Create text generation pipeline
                self.generator = pipeline(
                    'text-generation',
                    model=self.model_id,
                    device=self.device,
                    truncation=True,
                    pad_token_id=50256,  # GPT-2 EOS token
                    max_length=self.max_length
                )
            
            self.initialized = True
            log_info(f"Successfully initialized transformers model: {self.model_id}")
            return True
            
        except ImportError as e:
            log_error(f"Transformers library not available: {e}")
            return False
        except Exception as e:
            log_error(f"Failed to initialize transformers adapter: {e}")
            return False
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate response using local transformers model."""
        if not self.initialized or not self.generator:
            raise RuntimeError("Transformers adapter not initialized")
        
        try:
            # Configure generation parameters
            max_new_tokens = min(kwargs.get("max_tokens", 150), 300)  # Reasonable limit
            temperature = kwargs.get("temperature", 0.7)
            do_sample = temperature > 0.0
            
            # Generate response
            result = self.generator(
                prompt,
                max_new_tokens=max_new_tokens,
                temperature=temperature if do_sample else 1.0,
                do_sample=do_sample,
                truncation=True,
                pad_token_id=50256,
                num_return_sequences=1,
                return_full_text=False  # Only return generated text
            )
            
            if result and len(result) > 0:
                generated_text = result[0]['generated_text']
                # Clean up the response
                generated_text = generated_text.strip()
                return generated_text
            else:
                return ""
                
        except Exception as e:
            log_error(f"Transformers generation failed: {e}")
            raise RuntimeError(f"Transformers generation failed: {e}")
    
    async def health_check(self) -> bool:
        """Check if transformers model is healthy."""
        if not self.initialized or not self.generator:
            return False
        
        try:
            # Quick test generation
            test_result = self.generator("Test", max_new_tokens=5, do_sample=False, return_full_text=False)
            return len(test_result) > 0
        except Exception:
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get adapter information."""
        return {
            "provider": "Transformers (Local)",
            "model_name": self.model_id,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "initialized": self.initialized,
            "device": "CPU" if self.device == -1 else f"CUDA:{self.device}",
            "description": "Local text generation using Hugging Face Transformers"
        }

# ================================
# IMAGE GENERATION ADAPTERS
# ================================

class ImageAdapter(ModelAdapter):
    """Abstract base class for image generation adapters."""
    
    @abstractmethod
    async def generate_image(self, prompt: str, **kwargs) -> str:
        """Generate an image from a text prompt. Returns base64 or URL."""
        pass
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Redirect to image generation for compatibility."""
        return await self.generate_image(prompt, **kwargs)

class OpenAIImageAdapter(ImageAdapter):
    """OpenAI DALL-E image adapter."""
    
    def __init__(self, config: Dict[str, Any], model_manager=None):
        super().__init__(config)
        self.api_key = get_api_key_with_fallback(config, "openai", "OPENAI_API_KEY")
        self.model_manager = model_manager
        self.base_url = self._get_base_url(config)
        self.size = config.get("size", "1024x1024")
        self.quality = config.get("quality", "standard")
        self.style = config.get("style", "vivid")
        self.client = None
    
    def _get_base_url(self, config: Dict[str, Any]) -> str:
        """Get base URL from config or model manager."""
        # Check explicit config first
        if "base_url" in config:
            return config["base_url"]
        
        # Use model manager if available
        if self.model_manager:
            try:
                return self.model_manager.get_provider_base_url("openai")
            except Exception:
                pass
        
        # Fallback to environment variable only
        env_url = os.getenv("OPENAI_BASE_URL")
        if env_url:
            return env_url
            
        raise ValueError("No base URL configured for OpenAI. Please set OPENAI_BASE_URL or configure in registry.")
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize OpenAI client."""
        if not self.api_key:
            raise ValueError("OpenAI API key required")
        
        try:
            import openai
            self.client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("openai package required for OpenAI image adapter")
        except Exception as e:
            log_error(f"Failed to initialize OpenAI image adapter: {e}")
            return False
    
    async def generate_image(self, prompt: str, **kwargs) -> str:
        """Generate image using DALL-E."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            response = await self.client.images.generate(  # type: ignore
                model=self.model_name,
                prompt=prompt,
                size=kwargs.get("size", self.size),
                quality=kwargs.get("quality", self.quality),
                style=kwargs.get("style", self.style),
                n=1
            )
            if response and response.data and len(response.data) > 0:
                url = response.data[0].url
                if url is None:
                    return ""
                return str(url)
            return ""
        except Exception as e:
            raise RuntimeError(f"OpenAI Image API error: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get OpenAI image model information."""
        return {
            "provider": "OpenAI",
            "model_name": self.model_name,
            "size": self.size,
            "quality": self.quality,
            "style": self.style,
            "initialized": self.initialized
        }

class StabilityAdapter(ImageAdapter):
    """Stability AI Stable Diffusion adapter."""
    
    def __init__(self, config: Dict[str, Any], model_manager=None):
        super().__init__(config)
        self.api_key = get_api_key_with_fallback(config, "stability", "STABILITY_API_KEY")
        self.model_manager = model_manager
        self.base_url = self._get_base_url(config)
        self.width = config.get("width", 1024)
        self.height = config.get("height", 1024)
        self.steps = config.get("steps", 30)
        self.cfg_scale = config.get("cfg_scale", 7)
        self.client = None
    
    def _get_base_url(self, config: Dict[str, Any]) -> str:
        """Get base URL from config or model manager."""
        # Check explicit config first
        if "base_url" in config:
            return config["base_url"]
        
        # Use model manager if available
        if self.model_manager:
            try:
                return self.model_manager.get_provider_base_url("stability")
            except Exception:
                pass
        
        # Fallback to environment variable only
        env_url = os.getenv("STABILITY_BASE_URL")
        if env_url:
            return env_url
            
        raise ValueError("No base URL configured for Stability. Please set STABILITY_BASE_URL or configure in registry.")
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize Stability client."""
        if not self.api_key:
            raise ValueError("Stability API key required")
        
        try:
            import httpx
            self.client = httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("httpx package required for Stability adapter")
        except Exception as e:
            log_error(f"Failed to initialize Stability adapter: {e}")
            return False
    
    async def generate_image(self, prompt: str, **kwargs) -> str:
        """Generate image using Stability AI."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            response = await self.client.post(  # type: ignore
                f"{self.base_url}/generation/{self.model_name}/text-to-image",
                json={
                    "text_prompts": [{"text": prompt}],
                    "cfg_scale": kwargs.get("cfg_scale", self.cfg_scale),
                    "height": kwargs.get("height", self.height),
                    "width": kwargs.get("width", self.width),
                    "steps": kwargs.get("steps", self.steps),
                    "samples": 1
                }
            )
            result = response.json()
            return f"data:image/png;base64,{result['artifacts'][0]['base64']}"
        except Exception as e:
            raise RuntimeError(f"Stability API error: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Stability model information."""
        return {
            "provider": "Stability AI",
            "model_name": self.model_name,
            "width": self.width,
            "height": self.height,
            "steps": self.steps,
            "cfg_scale": self.cfg_scale,
            "initialized": self.initialized
        }

class ReplicateAdapter(ImageAdapter):
    """Replicate API adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = get_api_key_with_fallback(config, "replicate", "REPLICATE_API_TOKEN")
        self.width = config.get("width", 1024)
        self.height = config.get("height", 1024)
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize Replicate client."""
        if not self.api_key:
            raise ValueError("Replicate API token required")
        
        try:
            import replicate  # type: ignore
            replicate.api_token = self.api_key  # type: ignore
            self.client = replicate
            self.initialized = True
            return True
        except ImportError:
            raise ImportError("replicate package required for Replicate adapter")
        except Exception as e:
            log_error(f"Failed to initialize Replicate adapter: {e}")
            return False
    
    async def generate_image(self, prompt: str, **kwargs) -> str:
        """Generate image using Replicate."""
        if not self.initialized:
            raise RuntimeError("Adapter not initialized")
        
        try:
            output = self.client.run(  # type: ignore
                self.model_name,
                input={
                    "prompt": prompt,
                    "width": kwargs.get("width", self.width),
                    "height": kwargs.get("height", self.height)
                }
            )
            return output[0] if isinstance(output, list) else output
        except Exception as e:
            raise RuntimeError(f"Replicate API error: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Replicate model information."""
        return {
            "provider": "Replicate",
            "model_name": self.model_name,
            "width": self.width,
            "height": self.height,
            "initialized": self.initialized
        }
