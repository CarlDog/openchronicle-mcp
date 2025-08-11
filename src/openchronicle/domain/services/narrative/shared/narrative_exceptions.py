"""
Narrative Systems Exceptions

Common exception classes for the narrative systems architecture.
"""


class NarrativeSystemError(Exception):
    """Base exception for narrative system errors."""



class NarrativeOrchestrationError(NarrativeSystemError):
    """Exception raised during narrative orchestration operations."""



class NarrativeStateError(NarrativeSystemError):
    """Exception raised during narrative state management."""



class NarrativeConfigurationError(NarrativeSystemError):
    """Exception raised for narrative system configuration issues."""



class NarrativeOperationError(NarrativeSystemError):
    """Exception raised during narrative operation processing."""



class NarrativeValidationError(NarrativeSystemError):
    """Exception raised during narrative validation operations."""

