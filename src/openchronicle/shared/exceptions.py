"""
Exception hierarchy for OpenChronicle.

This module defines a comprehensive exception taxonomy that provides
clear error categorization and structured error handling throughout
the application.
"""

from typing import Any


class OpenChronicleError(Exception):
    """
    Base exception for all OpenChronicle errors.

    All custom exceptions in the application should inherit from this class
    to provide consistent error handling and identification.
    """

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
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

    def to_dict(self) -> dict[str, Any]:
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



class ValidationError(DomainError):
    """Raised when domain validation rules are violated."""



class BusinessRuleError(DomainError):
    """Raised when business rules are violated."""



class InvalidStateError(DomainError):
    """Raised when an object is in an invalid state for the requested operation."""



# Story and Narrative Exceptions
class StoryError(DomainError):
    """Base class for story-related errors."""



class StoryNotFoundError(StoryError):
    """Raised when a requested story cannot be found."""



class InvalidStoryFormatError(StoryError):
    """Raised when story data is in an invalid format."""



class StoryGenerationError(StoryError):
    """Raised when story generation fails."""



# Character Management Exceptions
class CharacterError(DomainError):
    """Base class for character-related errors."""



class CharacterNotFoundError(CharacterError):
    """Raised when a requested character cannot be found."""



class CharacterConsistencyError(CharacterError):
    """Raised when character consistency validation fails."""



class InvalidCharacterStateError(CharacterError):
    """Raised when a character is in an invalid state."""



# Memory System Exceptions
class MemoryError(DomainError):
    """Base class for memory system errors."""



class MemoryRetrievalError(MemoryError):
    """Raised when memory retrieval fails."""



class MemoryConsistencyError(MemoryError):
    """Raised when memory consistency checks fail."""



class MemoryStorageError(MemoryError):
    """Raised when memory storage operations fail."""



# Application Layer Exceptions
class ApplicationError(OpenChronicleError):
    """Base class for application layer errors."""



class CommandError(ApplicationError):
    """Raised when command execution fails."""



class QueryError(ApplicationError):
    """Raised when query execution fails."""



class OrchestrationError(ApplicationError):
    """Raised when service orchestration fails."""



class WorkflowError(ApplicationError):
    """Raised when workflow execution fails."""



# Infrastructure Layer Exceptions
class InfrastructureError(OpenChronicleError):
    """Base class for infrastructure-related errors."""



class DatabaseError(InfrastructureError):
    """Base class for database-related errors."""



class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""



class DatabaseQueryError(DatabaseError):
    """Raised when database query execution fails."""



class DatabaseMigrationError(DatabaseError):
    """Raised when database migration fails."""



# Model and AI Provider Exceptions
class ModelError(InfrastructureError):
    """Base class for AI model-related errors."""



class ModelNotFoundError(ModelError):
    """Raised when a requested model is not available."""



class ModelInitializationError(ModelError):
    """Raised when model initialization fails."""



class ModelResponseError(ModelError):
    """Raised when model response is invalid or empty."""



class RateLimitError(ModelError):
    """Raised when rate limits are exceeded."""



class APIKeyError(ModelError):
    """Raised when API key is invalid or missing."""



# Cache and Storage Exceptions
class CacheError(InfrastructureError):
    """Base class for cache-related errors."""



class CacheConnectionError(CacheError):
    """Raised when cache connection fails."""



class StorageError(InfrastructureError):
    """Base class for storage-related errors."""



class FileNotFoundError(StorageError):
    """Raised when a required file cannot be found."""



class FilePermissionError(StorageError):
    """Raised when file permissions prevent operation."""



# Interface Layer Exceptions
class InterfaceError(OpenChronicleError):
    """Base class for user interface errors."""



class CLIError(InterfaceError):
    """Raised when CLI operations fail."""



class APIError(InterfaceError):
    """Base class for API-related errors."""



class BadRequestError(APIError):
    """Raised when API request is malformed."""



class AuthenticationError(APIError):
    """Raised when authentication fails."""



class AuthorizationError(APIError):
    """Raised when authorization fails."""



class NotFoundError(APIError):
    """Raised when requested resource is not found."""



class ConflictError(APIError):
    """Raised when request conflicts with current state."""



# Configuration and System Exceptions
class ConfigurationError(OpenChronicleError):
    """Raised when configuration is invalid or missing."""



class MissingConfigurationError(ConfigurationError):
    """Raised when required configuration is missing."""



class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration values are invalid."""



class SystemError(OpenChronicleError):
    """Base class for system-level errors."""



class DependencyError(SystemError):
    """Raised when a required dependency is missing or incompatible."""



class EnvironmentError(SystemError):
    """Raised when the runtime environment is incompatible."""



class ResourceExhaustedError(SystemError):
    """Raised when system resources are exhausted."""



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
