"""
Custom exceptions for the adapter system.

Provides specific exception types for better error handling and debugging
in the modular adapter architecture.
"""


class AdapterError(Exception):
    """Base exception for adapter-related errors."""
    pass


class AdapterNotFoundError(AdapterError):
    """Raised when a requested adapter type is not found."""
    
    def __init__(self, provider: str):
        self.provider = provider
        super().__init__(f"Adapter not found for provider: {provider}")


class AdapterInitializationError(AdapterError):
    """Raised when an adapter fails to initialize properly."""
    
    def __init__(self, provider: str, reason: str):
        self.provider = provider
        self.reason = reason
        super().__init__(f"Failed to initialize {provider} adapter: {reason}")


class AdapterConfigurationError(AdapterError):
    """Raised when adapter configuration is invalid."""
    
    def __init__(self, provider: str, config_issue: str):
        self.provider = provider
        self.config_issue = config_issue
        super().__init__(f"Configuration error for {provider} adapter: {config_issue}")


class AdapterConnectionError(AdapterError):
    """Raised when adapter cannot connect to its service."""
    
    def __init__(self, provider: str, connection_issue: str):
        self.provider = provider
        self.connection_issue = connection_issue
        super().__init__(f"Connection error for {provider} adapter: {connection_issue}")


class AdapterResponseError(AdapterError):
    """Raised when adapter receives an invalid response."""
    
    def __init__(self, provider: str, response_issue: str):
        self.provider = provider
        self.response_issue = response_issue
        super().__init__(f"Response error from {provider} adapter: {response_issue}")
