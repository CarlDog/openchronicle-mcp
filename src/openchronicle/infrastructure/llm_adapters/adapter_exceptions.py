"""
Custom exceptions for the adapter system.

Provides specific exception types for better error handling and debugging
in the modular adapter architecture.

Following OpenChronicle naming convention: adapter_exceptions.py
"""



class AdapterError(Exception):
    """Base exception for adapter-related errors."""



class AdapterNotFoundError(AdapterError):
    """Raised when a requested adapter type is not found."""

    def __init__(self, provider: str):
        self.provider = provider
        super().__init__(f"Adapter not found for provider: {provider}")


class AdapterInitializationError(AdapterError):
    """Raised when an adapter fails to initialize properly."""

    def __init__(self, provider: str | None = None, reason: str | None = None):
        self.provider = provider
        self.reason = reason
        if provider and reason:
            super().__init__(f"Failed to initialize {provider} adapter: {reason}")
        elif reason:
            super().__init__(f"Adapter initialization failed: {reason}")
        else:
            super().__init__("Adapter initialization failed")


class AdapterConfigurationError(AdapterError):
    """Raised when adapter configuration is invalid."""

    def __init__(
        self, provider: str | None = None, config_issue: str | None = None
    ):
        self.provider = provider
        self.config_issue = config_issue
        if provider and config_issue:
            super().__init__(
                f"Configuration error for {provider} adapter: {config_issue}"
            )
        elif config_issue:
            super().__init__(f"Adapter configuration error: {config_issue}")
        else:
            super().__init__("Adapter configuration error")


class AdapterConnectionError(AdapterError):
    """Raised when adapter cannot connect to its service."""

    def __init__(
        self, provider: str | None = None, connection_issue: str | None = None
    ):
        self.provider = provider
        self.connection_issue = connection_issue
        if provider and connection_issue:
            super().__init__(
                f"Connection error for {provider} adapter: {connection_issue}"
            )
        elif connection_issue:
            super().__init__(f"Adapter connection error: {connection_issue}")
        else:
            super().__init__("Adapter connection error")


class AdapterResponseError(AdapterError):
    """Raised when adapter receives an invalid response."""

    def __init__(
        self, provider: str | None = None, response_issue: str | None = None
    ):
        self.provider = provider
        self.response_issue = response_issue
        if provider and response_issue:
            super().__init__(f"Response error for {provider} adapter: {response_issue}")
        elif response_issue:
            super().__init__(f"Adapter response error: {response_issue}")
        else:
            super().__init__("Adapter response error")


class AdapterTimeoutError(AdapterError):
    """Raised when adapter operation times out."""

    def __init__(
        self, provider: str | None = None, timeout_duration: float | None = None
    ):
        self.provider = provider
        self.timeout_duration = timeout_duration
        if provider and timeout_duration:
            super().__init__(
                f"Timeout error for {provider} adapter after {timeout_duration}s"
            )
        elif timeout_duration:
            super().__init__(f"Adapter timeout after {timeout_duration}s")
        else:
            super().__init__("Adapter timeout error")


class AdapterRateLimitError(AdapterError):
    """Raised when adapter hits rate limits."""

    def __init__(
        self, provider: str | None = None, retry_after: int | None = None
    ):
        self.provider = provider
        self.retry_after = retry_after
        if provider and retry_after:
            super().__init__(
                f"Rate limit error for {provider} adapter, retry after {retry_after}s"
            )
        elif provider:
            super().__init__(f"Rate limit error for {provider} adapter")
        else:
            super().__init__("Adapter rate limit error")
