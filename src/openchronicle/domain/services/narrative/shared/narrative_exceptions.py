"""
Narrative Systems Exceptions

Common exception classes for the narrative systems architecture.
"""


class NarrativeSystemError(Exception):
    """Base exception for narrative system errors."""

    pass


class NarrativeOrchestrationError(NarrativeSystemError):
    """Exception raised during narrative orchestration operations."""

    pass


class NarrativeStateError(NarrativeSystemError):
    """Exception raised during narrative state management."""

    pass


class NarrativeConfigurationError(NarrativeSystemError):
    """Exception raised for narrative system configuration issues."""

    pass


class NarrativeOperationError(NarrativeSystemError):
    """Exception raised during narrative operation processing."""

    pass


class NarrativeValidationError(NarrativeSystemError):
    """Exception raised during narrative validation operations."""

    pass
