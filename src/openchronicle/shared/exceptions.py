"""
Exception hierarchy for OpenChronicle.

This module defines a comprehensive exception taxonomy that provides
clear error categorization and structured error handling throughout
the application.
"""

from typing import Optional, Dict, Any


class OpenChronicleError(Exception):
    """
    Base exception for all OpenChronicle errors.

    All custom exceptions in the application should inherit from this class
    to provide consistent error handling and identification.
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        """
        Initialize the exception.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code for categorization
            context: Additional context information about the error
            original_error: Original exception that caused this error (if any)
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
        self.original_error = original_error

    def __str__(self) -> str:
        """String representation of the error."""
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
            "original_error": str(self.original_error) if self.original_error else None,
        }


# Domain Layer Exceptions
class DomainError(OpenChronicleError):
    """Base class for domain logic errors."""

    pass


class ValidationError(DomainError):
    """Raised when domain validation rules are violated."""

    pass


class BusinessRuleError(DomainError):
    """Raised when business rules are violated."""

    pass


class InvalidStateError(DomainError):
    """Raised when an object is in an invalid state for the requested operation."""

    pass


# Story and Narrative Exceptions
class StoryError(DomainError):
    """Base class for story-related errors."""

    pass


class StoryNotFoundError(StoryError):
    """Raised when a requested story cannot be found."""

    pass


class InvalidStoryFormatError(StoryError):
    """Raised when story data is in an invalid format."""

    pass


class StoryGenerationError(StoryError):
    """Raised when story generation fails."""

    pass


# Character Management Exceptions
class CharacterError(DomainError):
    """Base class for character-related errors."""

    pass


class CharacterNotFoundError(CharacterError):
    """Raised when a requested character cannot be found."""

    pass


class CharacterConsistencyError(CharacterError):
    """Raised when character consistency validation fails."""

    pass


class InvalidCharacterStateError(CharacterError):
    """Raised when a character is in an invalid state."""

    pass


# Memory System Exceptions
class MemoryError(DomainError):
    """Base class for memory system errors."""

    pass


class MemoryRetrievalError(MemoryError):
    """Raised when memory retrieval fails."""

    pass


class MemoryConsistencyError(MemoryError):
    """Raised when memory consistency checks fail."""

    pass


class MemoryStorageError(MemoryError):
    """Raised when memory storage operations fail."""

    pass


# Application Layer Exceptions
class ApplicationError(OpenChronicleError):
    """Base class for application layer errors."""

    pass


class CommandError(ApplicationError):
    """Raised when command execution fails."""

    pass


class QueryError(ApplicationError):
    """Raised when query execution fails."""

    pass


class OrchestrationError(ApplicationError):
    """Raised when service orchestration fails."""

    pass


class WorkflowError(ApplicationError):
    """Raised when workflow execution fails."""

    pass


# Infrastructure Layer Exceptions
class InfrastructureError(OpenChronicleError):
    """Base class for infrastructure-related errors."""

    pass


class DatabaseError(InfrastructureError):
    """Base class for database-related errors."""

    pass


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""

    pass


class DatabaseQueryError(DatabaseError):
    """Raised when database query execution fails."""

    pass


class DatabaseMigrationError(DatabaseError):
    """Raised when database migration fails."""

    pass


# Model and AI Provider Exceptions
class ModelError(InfrastructureError):
    """Base class for AI model-related errors."""

    pass


class ModelNotFoundError(ModelError):
    """Raised when a requested model is not available."""

    pass


class ModelInitializationError(ModelError):
    """Raised when model initialization fails."""

    pass


class ModelResponseError(ModelError):
    """Raised when model response is invalid or empty."""

    pass


class RateLimitError(ModelError):
    """Raised when rate limits are exceeded."""

    pass


class APIKeyError(ModelError):
    """Raised when API key is invalid or missing."""

    pass


# Cache and Storage Exceptions
class CacheError(InfrastructureError):
    """Base class for cache-related errors."""

    pass


class CacheConnectionError(CacheError):
    """Raised when cache connection fails."""

    pass


class StorageError(InfrastructureError):
    """Base class for storage-related errors."""

    pass


class FileNotFoundError(StorageError):
    """Raised when a required file cannot be found."""

    pass


class FilePermissionError(StorageError):
    """Raised when file permissions prevent operation."""

    pass


# Interface Layer Exceptions
class InterfaceError(OpenChronicleError):
    """Base class for user interface errors."""

    pass


class CLIError(InterfaceError):
    """Raised when CLI operations fail."""

    pass


class APIError(InterfaceError):
    """Base class for API-related errors."""

    pass


class BadRequestError(APIError):
    """Raised when API request is malformed."""

    pass


class AuthenticationError(APIError):
    """Raised when authentication fails."""

    pass


class AuthorizationError(APIError):
    """Raised when authorization fails."""

    pass


class NotFoundError(APIError):
    """Raised when requested resource is not found."""

    pass


class ConflictError(APIError):
    """Raised when request conflicts with current state."""

    pass


# Configuration and System Exceptions
class ConfigurationError(OpenChronicleError):
    """Raised when configuration is invalid or missing."""

    pass


class MissingConfigurationError(ConfigurationError):
    """Raised when required configuration is missing."""

    pass


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration values are invalid."""

    pass


class SystemError(OpenChronicleError):
    """Base class for system-level errors."""

    pass


class DependencyError(SystemError):
    """Raised when a required dependency is missing or incompatible."""

    pass


class EnvironmentError(SystemError):
    """Raised when the runtime environment is incompatible."""

    pass


class ResourceExhaustedError(SystemError):
    """Raised when system resources are exhausted."""

    pass


# Utility functions for error handling
def wrap_external_error(error: Exception, context: str) -> OpenChronicleError:
    """
    Wrap an external exception in an OpenChronicle exception.

    Args:
        error: The original exception
        context: Context where the error occurred

    Returns:
        Wrapped OpenChronicle exception
    """
    if isinstance(error, OpenChronicleError):
        return error

    # Map common external exceptions to appropriate types
    error_type = type(error).__name__

    if "database" in context.lower() or error_type in (
        "sqlite3.Error",
        "psycopg2.Error",
    ):
        return DatabaseError(
            f"Database error in {context}: {error}",
            error_code="DATABASE_ERROR",
            context={"location": context},
            original_error=error,
        )

    if "model" in context.lower() or "api" in context.lower():
        return ModelError(
            f"Model error in {context}: {error}",
            error_code="MODEL_ERROR",
            context={"location": context},
            original_error=error,
        )

    if "file" in context.lower() or error_type in (
        "FileNotFoundError",
        "PermissionError",
    ):
        return StorageError(
            f"Storage error in {context}: {error}",
            error_code="STORAGE_ERROR",
            context={"location": context},
            original_error=error,
        )

    # Default to infrastructure error for unknown external errors
    return InfrastructureError(
        f"External error in {context}: {error}",
        error_code="EXTERNAL_ERROR",
        context={"location": context, "original_type": error_type},
        original_error=error,
    )
