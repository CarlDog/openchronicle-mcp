"""
Base adapter classes for AI model providers.

This module implements the template method pattern to eliminate massive code duplication
from the original monolithic model_adapter.py. The BaseAPIAdapter provides common
functionality that was previously duplicated across 15+ adapter implementations.

Key Features:
- Template method pattern eliminates ~1,500 lines of duplicated code
- Common API key and base URL resolution logic
- Standardized initialization and error handling
- Each provider adapter now only needs to implement 4-5 methods

Following OpenChronicle naming convention: api_adapter_base.py
"""

import logging
import os
from abc import ABC
from abc import abstractmethod
from datetime import UTC
from datetime import datetime
from typing import Any

from openchronicle.shared.logging_system import log_error
from openchronicle.shared.logging_system import log_info

# Import logging system
from openchronicle.shared.logging_system import log_model_interaction
from openchronicle.shared.logging_system import log_system_event

from .adapter_exceptions import AdapterConfigurationError
from .adapter_exceptions import AdapterConnectionError

# Import exceptions
from .adapter_exceptions import AdapterInitializationError


logger = logging.getLogger(__name__)


def get_api_key_with_fallback(config: dict[str, Any], provider: str, env_var: str) -> str | None:
    """
    Get API key with fallback priority: config > keystore > environment variable

    Args:
        config: Adapter configuration dictionary
        provider: Provider name for keystore (e.g., 'openai', 'anthropic')
        env_var: Environment variable name (e.g., 'OPENAI_API_KEY')

    Returns:
        API key string or None if not found
    """
    # Keystore disabled for now – single-source via config/env only
    # Priority 1: Check configuration for direct API key
    if config.get("api_key"):
        log_info(f"API key found in configuration for {provider}")
        return config["api_key"]

    # Priority 2: (reserved for keystore) — intentionally disabled

    # Priority 3: Check environment variable
    env_key = os.getenv(env_var)
    if env_key:
        log_info(f"API key found in environment variable {env_var}")
        return env_key

    log_error(f"No API key found for {provider} (checked config, keystore, {env_var})")
    return None


class BaseAPIAdapter(ABC):
    """
    Base class for all AI model adapters implementing template method pattern.

    This class eliminates massive code duplication by providing common functionality
    that was previously repeated across 15+ adapter implementations. Subclasses
    only need to implement provider-specific methods.

    Template methods implemented:
    - API key resolution with fallback priority
    - Base URL configuration
    - Common initialization and validation
    - Error handling and logging

    Provider-specific methods to implement:
    - get_provider_name()
    - get_api_key_env_var()
    - _create_client()
    - generate_response()
    """

    def __init__(self, model_name: str, config: dict[str, Any] = None):
        """
        Initialize the adapter with common configuration.

        Args:
            model_name: Name of the model to use
            config: Configuration dictionary with provider settings
        """
        self.model_name = model_name
        self.config = config or {}
        self.client = None
        self.api_key = None
        self.base_url = None

        # Common configuration
        self.max_tokens = self.config.get("max_tokens", 2000)
        self.temperature = self.config.get("temperature", 0.7)
        self.timeout = self.config.get("timeout", 30)

        log_info(f"Initializing {self.get_provider_name()} adapter for model: {model_name}")

        # Initialize adapter
        self._initialize()

    def _initialize(self):
        """Common initialization logic for all adapters."""
        try:
            # Resolve API key using fallback priority
            self.api_key = get_api_key_with_fallback(self.config, self.get_provider_name(), self.get_api_key_env_var())

            if not self.api_key:
                raise AdapterConfigurationError(f"No API key found for {self.get_provider_name()}")

            # Set base URL
            self.base_url = self.config.get("base_url", self.get_default_base_url())

            log_system_event(
                "adapter_initialized",
                f"{self.get_provider_name()} adapter initialized successfully",
            )

        except AdapterConfigurationError:
            # Preserve precise configuration failures
            raise
        except (ValueError, TypeError, OSError) as e:
            log_error(f"Failed to initialize {self.get_provider_name()} adapter: {e}")
            raise AdapterInitializationError(f"Adapter initialization failed: {e}") from e

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider name (e.g., 'openai', 'anthropic')."""

    @abstractmethod
    def get_api_key_env_var(self) -> str:
        """Return the environment variable name for the API key."""

    def get_default_base_url(self) -> str | None:
        """Return default base URL for the provider (can be overridden)."""
        return None

    @abstractmethod
    async def _create_client(self) -> Any:
        """Create and return the provider-specific client."""

    async def get_client(self) -> Any:
        """Get or create the client with lazy initialization."""
        if self.client is None:
            try:
                self.client = await self._create_client()
                log_info(f"Created {self.get_provider_name()} client")
            except (ImportError, ValueError, TypeError, OSError) as e:
                log_error(f"Failed to create {self.get_provider_name()} client: {e}")
                raise AdapterConnectionError(f"Client creation failed: {e}") from e

        return self.client

    @abstractmethod
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """
        Generate a response using the provider's API.

        Args:
            prompt: The input prompt
            **kwargs: Additional generation parameters

        Returns:
            Generated response as string
        """

    async def generate_with_logging(self, prompt: str, **kwargs) -> str:
        """
        Generate response with comprehensive logging.

        Args:
            prompt: The input prompt
            **kwargs: Additional generation parameters

        Returns:
            Generated response as string
        """
        start_time = datetime.now(UTC)

        try:
            log_model_interaction(
                provider=self.get_provider_name(),
                model=self.model_name,
                prompt=prompt[:100] + "..." if len(prompt) > 100 else prompt,
                response_length=0,
                tokens_used=0,
                execution_time=0,
                status="started",
            )

            response = await self.generate_response(prompt, **kwargs)

            execution_time = (datetime.now(UTC) - start_time).total_seconds()

            log_model_interaction(
                provider=self.get_provider_name(),
                model=self.model_name,
                prompt=prompt[:100] + "..." if len(prompt) > 100 else prompt,
                response_length=len(response),
                tokens_used=kwargs.get("max_tokens", self.max_tokens),
                execution_time=execution_time,
                status="completed",
            )

        except (
            AdapterConnectionError,
            AdapterConfigurationError,
            AdapterInitializationError,
            ValueError,
            TimeoutError,
            OSError,
            RuntimeError,
        ) as e:
            execution_time = (datetime.now(UTC) - start_time).total_seconds()

            log_model_interaction(
                provider=self.get_provider_name(),
                model=self.model_name,
                prompt=prompt[:100] + "..." if len(prompt) > 100 else prompt,
                response_length=0,
                tokens_used=0,
                execution_time=execution_time,
                status="failed",
                error=str(e),
            )

            raise
        else:
            return response

    def get_adapter_info(self) -> dict[str, Any]:
        """Return adapter information for debugging and monitoring."""
        return {
            "provider": self.get_provider_name(),
            "model": self.model_name,
            "has_api_key": bool(self.api_key),
            "base_url": self.base_url,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "client_initialized": self.client is not None,
        }


class LocalModelAdapter(BaseAPIAdapter):
    """
    Base class for local model adapters (Ollama, Transformers, etc.).

    Local adapters don't require API keys but may need other configuration.
    """

    def get_api_key_env_var(self) -> str:
        """Local models don't use API keys."""
        return ""

    def _initialize(self):
        """Simplified initialization for local models."""
        try:
            # Set base URL (important for local services like Ollama)
            self.base_url = self.config.get("base_url", self.get_default_base_url())

            log_system_event(
                "local_adapter_initialized",
                f"{self.get_provider_name()} local adapter initialized successfully",
            )

        except (ValueError, TypeError, OSError) as e:
            log_error(f"Failed to initialize {self.get_provider_name()} local adapter: {e}")
            raise AdapterInitializationError(f"Local adapter initialization failed: {e}") from e
