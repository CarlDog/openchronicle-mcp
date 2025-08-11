#!/usr/bin/env python3
"""
ConfigurationManager - Refactored to use existing components

Simplified to coordinate existing specialized components instead of being monolithic:
- Uses core.shared.centralized_config for typed configuration
- Uses core.registry.registry_manager for dynamic discovery
- Uses core.registry.schema_validation for validation
- Focuses on coordination rather than doing everything

Following EMBRACE BREAKING CHANGES philosophy for better architecture.
"""

import os
import sys
from pathlib import Path
from typing import Any
from typing import Optional

from src.openchronicle.domain.ports.registry_port import IRegistryPort
from src.openchronicle.shared.centralized_config import SystemConfig
from src.openchronicle.shared.logging_system import log_error

# Import existing specialized components
from src.openchronicle.shared.logging_system import log_system_event
from src.openchronicle.shared.logging_system import log_warning


class ConfigurationManager:
    """
    Configuration manager using dependency injection following hexagonal architecture.

    Uses registry port interface instead of directly importing infrastructure:
    - IRegistryPort handles dynamic model discovery
    - centralized_config provides typed configuration classes
    - Follows dependency inversion principle
    """

    def __init__(
        self,
        config: Optional[SystemConfig] = None,
        registry_port: Optional[IRegistryPort] = None,
    ):
        """
        Initialize configuration manager.

        Args:
            config: System configuration instance
            registry_port: Registry interface implementation (injected)
        """
        self.config = config or SystemConfig()

        # If no registry port provided, this violates hexagonal architecture
        # The caller should always provide implementations
        if registry_port is None:
            raise ValueError(
                "ConfigurationManager requires a registry_port implementation. "
                "This follows hexagonal architecture - domain should not import infrastructure."
            )
        self.registry = registry_port

    def __init__(self, config_path: str = "config"):
        """Initialize with existing components."""
        self.config_path = Path(config_path)

        # Use existing RegistryManager for dynamic discovery
        self.registry_manager = RegistryManager(
            models_dir=str(self.config_path / "models"),
            settings_file=str(self.config_path / "registry_settings.json"),
        )

        # Use existing SystemConfig for typed configuration
        self.system_config = SystemConfig()

        # Build configuration from dynamic discovery
        self.registry = self._discover_models()
        self.global_config = self._build_global_config()
        self.config = self._build_adapters_config()

        log_system_event(
            "configuration_manager_initialized",
            "Simplified configuration manager ready",
        )

    def _discover_models(self) -> dict[str, Any]:
        """Discover models using existing RegistryManager."""
        try:
            discovered_providers = self.registry.discover_providers()

            if not discovered_providers:
                log_warning("No providers discovered")
                return {"providers": {}, "fallback_chains": {}}

            # Simple registry structure - no complex hierarchies needed
            registry = {"providers": discovered_providers, "fallback_chains": {}}

            # Extract fallback chains from model configs
            for provider_name, models in discovered_providers.items():
                for model_config in models:
                    model_name = model_config.get(
                        "name", model_config.get("config_name")
                    )
                    fallbacks = model_config.get("fallback_chain", [model_name])
                    if fallbacks and model_name:
                        registry["fallback_chains"][model_name] = fallbacks

            total_models = sum(len(models) for models in discovered_providers.values())
            log_system_event(
                "models_discovered",
                f"Discovered {len(discovered_providers)} providers with {total_models} models",
            )

            return registry

        except Exception as e:
            log_error(f"Model discovery failed: {e}")
            return {"providers": {}, "fallback_chains": {}}

    def _build_global_config(self) -> dict[str, Any]:
        """Build global configuration using existing SystemConfig."""
        return {
            "defaults": {
                "text_model": self.system_config.model.default_text_model,
                "image_model": self.system_config.model.default_image_model,
                "timeout": self.system_config.performance.request_timeout_seconds,
                "max_tokens": self.system_config.model.max_tokens,
                "temperature": self.system_config.model.temperature,
            },
            "fallback_chains": self.registry.get("fallback_chains", {}),
            "performance": {
                "max_concurrent_requests": self.system_config.performance.max_concurrent_requests,
                "enable_caching": self.system_config.performance.enable_request_caching,
            },
        }

    def _build_adapters_config(self) -> dict[str, Any]:
        """Build adapters configuration from discovered models."""
        adapters = {}

        providers = self.registry.get("providers", {})
        for provider_name, models in providers.items():
            for model_config in models:
                if not model_config.get("enabled", True):
                    continue

                model_name = model_config.get("name", model_config.get("config_name"))
                if not model_name:
                    continue

                # Skip mock adapters in production
                if model_name in ["mock", "mock_image"] and not self._is_testing():
                    log_system_event(
                        "production_safety",
                        f"Skipping {model_name} - not available in production",
                    )
                    continue

                adapters[model_name] = {
                    "type": model_config.get("provider", provider_name),
                    "enabled": True,
                    **{
                        k: v
                        for k, v in model_config.items()
                        if k not in ["name", "enabled", "config_name"]
                    },
                }

        return {"adapters": adapters}

    def _is_testing(self) -> bool:
        """Check if we're in a testing environment."""
        return (
            os.getenv("TESTING", "").lower() in ["true", "1", "yes"]
            or os.getenv("PYTEST_CURRENT_TEST") is not None
            or "pytest" in sys.modules
            or "test" in sys.argv[0].lower()
        )

    # Simplified API methods using existing components
    def get_global_default(self, key: str, fallback: Any = None) -> Any:
        """Get global default value."""
        return self.global_config.get("defaults", {}).get(key, fallback)

    def get_fallback_chain(self, model_name: str) -> list[str]:
        """Get fallback chain for a model."""
        return self.global_config.get("fallback_chains", {}).get(
            model_name, [model_name]
        )

    def get_model_configuration(
        self, adapter_name: str
    ) -> Optional["ModelConfiguration"]:
        """Get configuration for specific model adapter."""
        from .model_interfaces import ModelConfiguration

        # Look up the adapter in our configuration
        adapters = self.config.get("adapters", {})
        if adapter_name not in adapters:
            return None

        adapter_config = adapters[adapter_name]

        # Convert to ModelConfiguration format
        return ModelConfiguration(
            provider_name=adapter_config.get("type", "unknown"),
            model_name=adapter_name,
            enabled=adapter_config.get("enabled", True),
            config=adapter_config,
            fallback_chain=self.get_fallback_chain(adapter_name),
            metadata=adapter_config.get("metadata", {}),
        )

    def get_adapters_config(self) -> dict[str, Any]:
        """Get adapters configuration."""
        return self.config

    def list_model_configs(self) -> dict[str, Any]:
        """List all available model configurations."""
        all_models = {}
        providers = self.registry.get("providers", {})

        for provider_name, models in providers.items():
            for model_config in models:
                model_name = model_config.get("name", model_config.get("config_name"))
                if model_name:
                    all_models[model_name] = model_config

        return all_models

    def validate_model_config(
        self, config: dict[str, Any], name: str = ""
    ) -> dict[str, Any]:
        """Validate model configuration using existing schema validation."""
        try:
            # Use existing schema validation
            self.registry.validate_config("unknown", config)
            return {"valid": True, "errors": [], "warnings": []}
        except Exception as e:
            return {"valid": False, "errors": [str(e)], "warnings": []}

    def get_configuration_summary(self) -> dict[str, Any]:
        """Get summary of current configuration."""
        adapters = self.config.get("adapters", {})
        providers = self.registry.get("providers", {})

        return {
            "total_providers": len(providers),
            "total_models": len(adapters),
            "enabled_models": len(
                [
                    name
                    for name, config in adapters.items()
                    if config.get("enabled", True)
                ]
            ),
            "providers_list": list(providers.keys()),
        }

    def reload_configuration(self) -> bool:
        """Reload configuration from dynamic discovery."""
        try:
            self.registry = self._discover_models()
            self.global_config = self._build_global_config()
            self.config = self._build_adapters_config()

            log_system_event(
                "configuration_reloaded", "Configuration reloaded successfully"
            )
            return True
        except Exception as e:
            log_error(f"Failed to reload configuration: {e}")
            return False

    # Simplified stubs for compatibility (can be extended if needed)
    def get_content_routing_config(self) -> dict[str, Any]:
        """Get content routing configuration."""
        return {}

    def get_performance_config(self) -> dict[str, Any]:
        """Get performance configuration."""
        return self.global_config.get("performance", {})

    def get_intelligent_routing_config(self) -> dict[str, Any]:
        """Get intelligent routing configuration."""
        return {"enabled": False}

    def get_base_url_for_provider(self, provider: str) -> str | None:
        """Get base URL for a provider."""
        # Could be enhanced by reading from model configs if needed
        return None

    def get_enabled_models_by_type(
        self, model_type: str = "text"
    ) -> list[dict[str, Any]]:
        """Get enabled models of a specific type."""
        models = []
        for model_name, model_config in self.list_model_configs().items():
            if model_config.get("type") == model_type and model_config.get(
                "enabled", True
            ):
                models.append(model_config)
        return models

    # Dynamic model management (simplified - no file persistence)
    def add_model_config(
        self, name: str, config: dict[str, Any], enabled: bool = True
    ) -> bool:
        """Add model configuration (runtime only)."""
        try:
            # Validate using existing schema validation
            validation = self.validate_model_config(config, name)
            if not validation["valid"]:
                log_error(f"Model validation failed: {validation['errors']}")
                return False

            # Add to runtime adapters
            self.config["adapters"][name] = {
                "type": config.get("provider", name),
                "enabled": enabled,
                **config,
            }

            log_system_event("model_added", f"Added runtime model: {name}")
            return True

        except Exception as e:
            log_error(f"Failed to add model {name}: {e}")
            return False

    def remove_model_config(self, name: str) -> bool:
        """Remove model configuration (runtime only)."""
        try:
            if name in self.config.get("adapters", {}):
                del self.config["adapters"][name]
                log_system_event("model_removed", f"Removed runtime model: {name}")
                return True
            return False
        except Exception as e:
            log_error(f"Failed to remove model {name}: {e}")
            return False

    def enable_model(self, name: str) -> bool:
        """Enable model (runtime only)."""
        return self._toggle_model(name, True)

    def disable_model(self, name: str) -> bool:
        """Disable model (runtime only)."""
        return self._toggle_model(name, False)

    def _toggle_model(self, name: str, enabled: bool) -> bool:
        """Toggle model enabled state."""
        try:
            adapters = self.config.get("adapters", {})
            if name in adapters:
                adapters[name]["enabled"] = enabled
                action = "enabled" if enabled else "disabled"
                log_system_event("model_toggled", f"Model {name} {action}")
                return True
            return False
        except Exception as e:
            log_error(f"Failed to toggle model {name}: {e}")
            return False

    @property
    def adapters_config(self) -> dict[str, Any]:
        """Get adapters configuration."""
        return self.config

    def validate_model_config(
        self, config: dict[str, Any], name: str = ""
    ) -> dict[str, Any]:
        """Validate model configuration using existing schema validation."""
        try:
            # Use existing schema validation
            self.registry.validate_config("unknown", config)
            return {"valid": True, "errors": [], "warnings": []}
        except Exception as e:
            return {"valid": False, "errors": [str(e)], "warnings": []}
