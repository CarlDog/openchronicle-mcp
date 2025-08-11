"""
Standardized Error Handling Framework for OpenChronicle

This module provides a comprehensive error handling system with:
- Standardized exception hierarchy for all OpenChronicle components
- Consistent error handling decorators
- Error recovery mechanisms with fallback strategies
- Structured error logging and monitoring

Phase 2 Week 7-8: Error Handling Standardization
"""

import asyncio
import functools
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union
from .logging_system import log_system_event, log_info, log_warning, log_error

T = TypeVar("T")


class ErrorSeverity(Enum):
    """Error severity levels for consistent classification."""

    LOW = "low"  # Minor issues, system continues normally
    MEDIUM = "medium"  # Moderate issues, partial functionality affected
    HIGH = "high"  # Serious issues, major functionality affected
    CRITICAL = "critical"  # System-threatening issues, immediate attention required


class ErrorCategory(Enum):
    """Error categories for better organization and handling."""

    CONFIGURATION = "configuration"
    DATABASE = "database"
    MODEL = "model"
    MEMORY = "memory"
    SCENE = "scene"
    NARRATIVE = "narrative"
    TIMELINE = "timeline"
    CONTEXT = "context"
    SECURITY = "security"
    PERFORMANCE = "performance"
    INTEGRATION = "integration"


@dataclass
class ErrorContext:
    """Structured error context for consistent error reporting."""

    component: str
    operation: str
    story_id: Optional[str] = None
    scene_id: Optional[str] = None
    model_name: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_log_tags(self) -> Dict[str, str]:
        """Convert to logging context tags."""
        tags = {"component": self.component, "operation": self.operation}
        if self.story_id:
            tags["story"] = self.story_id
        if self.scene_id:
            tags["scene"] = self.scene_id
        if self.model_name:
            tags["model"] = self.model_name
        if self.user_id:
            tags["user"] = self.user_id
        if self.session_id:
            tags["session"] = self.session_id
        return tags


# === OpenChronicle Exception Hierarchy ===


class OpenChronicleError(Exception):
    """Base exception for all OpenChronicle errors."""

    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None,
        recoverable: bool = True,
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.context = context or ErrorContext(component="unknown", operation="unknown")
        self.cause = cause
        self.recoverable = recoverable
        self.timestamp = time.time()

    def __str__(self) -> str:
        return f"[{self.category.value}:{self.severity.value}] {self.message}"

    def get_error_info(self) -> Dict[str, Any]:
        """Get structured error information for logging/monitoring."""
        return {
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "component": self.context.component,
            "operation": self.context.operation,
            "recoverable": self.recoverable,
            "timestamp": self.timestamp,
            "context": self.context.metadata,
            "cause": str(self.cause) if self.cause else None,
        }


class ConfigurationError(OpenChronicleError):
    """Errors related to configuration issues."""

    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        kwargs.setdefault("category", ErrorCategory.CONFIGURATION)
        super().__init__(message, **kwargs)
        self.config_key = config_key


class DatabaseError(OpenChronicleError):
    """Errors related to database operations."""

    def __init__(self, message: str, database_path: Optional[str] = None, **kwargs):
        kwargs.setdefault("category", ErrorCategory.DATABASE)
        super().__init__(message, **kwargs)
        self.database_path = database_path


class ModelError(OpenChronicleError):
    """Errors related to model operations."""

    def __init__(self, message: str, model_name: Optional[str] = None, **kwargs):
        kwargs.setdefault("category", ErrorCategory.MODEL)
        super().__init__(message, **kwargs)
        self.model_name = model_name


class MemoryError(OpenChronicleError):
    """Errors related to memory management operations."""

    def __init__(self, message: str, character_id: Optional[str] = None, **kwargs):
        kwargs.setdefault("category", ErrorCategory.MEMORY)
        super().__init__(message, **kwargs)
        self.character_id = character_id


class SceneError(OpenChronicleError):
    """Errors related to scene management operations."""

    def __init__(self, message: str, scene_id: Optional[str] = None, **kwargs):
        kwargs.setdefault("category", ErrorCategory.SCENE)
        super().__init__(message, **kwargs)
        self.scene_id = scene_id


class NarrativeError(OpenChronicleError):
    """Errors related to narrative operations."""

    def __init__(self, message: str, narrative_id: Optional[str] = None, **kwargs):
        kwargs.setdefault("category", ErrorCategory.NARRATIVE)
        super().__init__(message, **kwargs)
        self.narrative_id = narrative_id


class TimelineError(OpenChronicleError):
    """Errors related to timeline operations."""

    def __init__(self, message: str, timeline_id: Optional[str] = None, **kwargs):
        kwargs.setdefault("category", ErrorCategory.TIMELINE)
        super().__init__(message, **kwargs)
        self.timeline_id = timeline_id


class ContextError(OpenChronicleError):
    """Errors related to context analysis operations."""

    def __init__(self, message: str, context_type: Optional[str] = None, **kwargs):
        kwargs.setdefault("category", ErrorCategory.CONTEXT)
        super().__init__(message, **kwargs)
        self.context_type = context_type


class SecurityError(OpenChronicleError):
    """Errors related to security violations."""

    def __init__(
        self, message: str, security_violation: Optional[str] = None, **kwargs
    ):
        kwargs.setdefault("category", ErrorCategory.SECURITY)
        kwargs.setdefault("severity", ErrorSeverity.HIGH)
        kwargs.setdefault("recoverable", False)
        super().__init__(message, **kwargs)
        self.security_violation = security_violation


class PerformanceError(OpenChronicleError):
    """Errors related to performance issues."""

    def __init__(
        self, message: str, operation_duration: Optional[float] = None, **kwargs
    ):
        kwargs.setdefault("category", ErrorCategory.PERFORMANCE)
        super().__init__(message, **kwargs)
        self.operation_duration = operation_duration


# === Error Recovery Framework ===


class ErrorRecoveryStrategy(ABC):
    """Abstract base class for error recovery strategies."""

    @abstractmethod
    async def can_recover(self, error: OpenChronicleError) -> bool:
        """Check if this strategy can recover from the given error."""
        pass

    @abstractmethod
    async def recover(
        self, error: OpenChronicleError, original_args: tuple, original_kwargs: dict
    ) -> Any:
        """Attempt to recover from the error."""
        pass


class FallbackValueStrategy(ErrorRecoveryStrategy):
    """Recovery strategy that returns a fallback value."""

    def __init__(
        self, fallback_value: Any, applicable_categories: List[ErrorCategory] = None
    ):
        self.fallback_value = fallback_value
        self.applicable_categories = applicable_categories or []

    async def can_recover(self, error: OpenChronicleError) -> bool:
        return (
            not self.applicable_categories
            or error.category in self.applicable_categories
        ) and error.recoverable

    async def recover(
        self, error: OpenChronicleError, original_args: tuple, original_kwargs: dict
    ) -> Any:
        log_warning(
            f"Using fallback value for error: {error}",
            context_tags=error.context.to_log_tags(),
        )
        return self.fallback_value


class RetryStrategy(ErrorRecoveryStrategy):
    """Recovery strategy that retries the operation with exponential backoff."""

    def __init__(
        self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def can_recover(self, error: OpenChronicleError) -> bool:
        return error.recoverable and error.category in [
            ErrorCategory.DATABASE,
            ErrorCategory.MODEL,
            ErrorCategory.PERFORMANCE,
        ]

    async def recover(
        self, error: OpenChronicleError, original_args: tuple, original_kwargs: dict
    ) -> Any:
        original_func = original_kwargs.get("_original_func")
        if not original_func:
            raise error

        for attempt in range(self.max_retries):
            delay = min(self.base_delay * (2**attempt), self.max_delay)
            await asyncio.sleep(delay)

            try:
                log_info(
                    f"Retry attempt {attempt + 1}/{self.max_retries} for {error.context.operation}",
                    context_tags=error.context.to_log_tags(),
                )
                return await original_func(
                    *original_args,
                    **{
                        k: v
                        for k, v in original_kwargs.items()
                        if k != "_original_func"
                    },
                )
            except Exception as retry_error:
                if attempt == self.max_retries - 1:
                    raise OpenChronicleError(
                        f"All retry attempts failed. Last error: {retry_error}",
                        category=error.category,
                        severity=ErrorSeverity.HIGH,
                        context=error.context,
                        cause=retry_error,
                        recoverable=False,
                    )
                continue


class ErrorRecoveryManager:
    """Manages error recovery strategies and execution."""

    def __init__(self):
        self.strategies: List[ErrorRecoveryStrategy] = [
            RetryStrategy(),
            FallbackValueStrategy(None),  # Default fallback to None
        ]

    def add_strategy(self, strategy: ErrorRecoveryStrategy):
        """Add a new recovery strategy."""
        self.strategies.insert(0, strategy)  # Insert at beginning for priority

    async def attempt_recovery(
        self, error: OpenChronicleError, original_args: tuple, original_kwargs: dict
    ) -> Any:
        """Attempt to recover from an error using available strategies."""
        for strategy in self.strategies:
            if await strategy.can_recover(error):
                try:
                    return await strategy.recover(error, original_args, original_kwargs)
                except Exception as recovery_error:
                    log_error(
                        f"Recovery strategy {type(strategy).__name__} failed: {recovery_error}"
                    )
                    continue

        # No recovery possible
        raise error


# === Error Handling Decorators ===

# Global error recovery manager
_error_recovery_manager = ErrorRecoveryManager()


def with_error_handling(
    context: Optional[ErrorContext] = None,
    fallback_result: Any = None,
    enable_recovery: bool = True,
    error_category: Optional[ErrorCategory] = None,
):
    """
    Decorator for standardized error handling with recovery capabilities.

    Args:
        context: Error context for logging and monitoring
        fallback_result: Fallback value to return on unrecoverable errors
        enable_recovery: Whether to attempt error recovery
        error_category: Default error category for exceptions
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            operation_context = context or ErrorContext(
                component=(
                    func.__module__.split(".")[-1]
                    if hasattr(func, "__module__")
                    else "unknown"
                ),
                operation=func.__name__,
            )

            # Store original function for retry strategies
            kwargs["_original_func"] = func

            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(
                        *args,
                        **{k: v for k, v in kwargs.items() if k != "_original_func"},
                    )
                else:
                    return func(
                        *args,
                        **{k: v for k, v in kwargs.items() if k != "_original_func"},
                    )

            except OpenChronicleError as oc_error:
                # Already a structured OpenChronicle error
                log_error(
                    f"OpenChronicle error in {operation_context.operation}: {oc_error}",
                    context_tags=oc_error.context.to_log_tags(),
                )

                if enable_recovery:
                    try:
                        # Create a temporary recovery manager with the specific fallback
                        temp_manager = ErrorRecoveryManager()
                        temp_manager.add_strategy(
                            FallbackValueStrategy(fallback_result)
                        )
                        return await temp_manager.attempt_recovery(
                            oc_error, args, kwargs
                        )
                    except Exception:
                        pass  # Fall through to fallback

                if fallback_result is not None:
                    return fallback_result
                raise

            except Exception as error:
                # Convert to structured OpenChronicle error
                oc_error = OpenChronicleError(
                    message=f"Unexpected error in {operation_context.operation}: {str(error)}",
                    category=error_category or ErrorCategory.INTEGRATION,
                    severity=ErrorSeverity.HIGH,
                    context=operation_context,
                    cause=error,
                    recoverable=True,
                )

                log_error(
                    f"Unexpected error in {operation_context.operation}: {error}",
                    context_tags=operation_context.to_log_tags(),
                )
                log_error(f"Traceback: {traceback.format_exc()}")

                # Log system event for monitoring
                log_system_event(
                    "error_occurred",
                    {
                        "component": operation_context.component,
                        "operation": operation_context.operation,
                        "error_type": type(error).__name__,
                        "error_message": str(error),
                        "severity": oc_error.severity.value,
                        "recoverable": oc_error.recoverable,
                    },
                )

                if enable_recovery:
                    try:
                        # Create a temporary recovery manager with the specific fallback
                        temp_manager = ErrorRecoveryManager()
                        temp_manager.add_strategy(
                            FallbackValueStrategy(fallback_result)
                        )
                        return await temp_manager.attempt_recovery(
                            oc_error, args, kwargs
                        )
                    except Exception:
                        pass  # Fall through to fallback

                if fallback_result is not None:
                    return fallback_result
                raise oc_error

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            operation_context = context or ErrorContext(
                component=(
                    func.__module__.split(".")[-1]
                    if hasattr(func, "__module__")
                    else "unknown"
                ),
                operation=func.__name__,
            )

            try:
                return func(*args, **kwargs)

            except OpenChronicleError as oc_error:
                log_error(
                    f"OpenChronicle error in {operation_context.operation}: {oc_error}",
                    context_tags=oc_error.context.to_log_tags(),
                )

                if fallback_result is not None:
                    return fallback_result
                raise

            except Exception as error:
                oc_error = OpenChronicleError(
                    message=f"Unexpected error in {operation_context.operation}: {str(error)}",
                    category=error_category or ErrorCategory.INTEGRATION,
                    severity=ErrorSeverity.HIGH,
                    context=operation_context,
                    cause=error,
                    recoverable=True,
                )

                log_error(
                    f"Unexpected error in {operation_context.operation}: {error}",
                    context_tags=operation_context.to_log_tags(),
                )

                log_system_event(
                    "error_occurred",
                    {
                        "component": operation_context.component,
                        "operation": operation_context.operation,
                        "error_type": type(error).__name__,
                        "error_message": str(error),
                        "severity": oc_error.severity.value,
                        "recoverable": oc_error.recoverable,
                    },
                )

                if fallback_result is not None:
                    return fallback_result
                raise oc_error

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def database_error_handling(fallback_result: Any = None):
    """Specialized error handling for database operations."""
    return with_error_handling(
        error_category=ErrorCategory.DATABASE,
        fallback_result=fallback_result,
        enable_recovery=True,
    )


def model_error_handling(fallback_result: Any = None):
    """Specialized error handling for model operations."""
    return with_error_handling(
        error_category=ErrorCategory.MODEL,
        fallback_result=fallback_result,
        enable_recovery=True,
    )


def memory_error_handling(fallback_result: Any = None):
    """Specialized error handling for memory operations."""
    return with_error_handling(
        error_category=ErrorCategory.MEMORY,
        fallback_result=fallback_result,
        enable_recovery=True,
    )


def scene_error_handling(fallback_result: Any = None):
    """Specialized error handling for scene operations."""
    return with_error_handling(
        error_category=ErrorCategory.SCENE,
        fallback_result=fallback_result,
        enable_recovery=True,
    )


def critical_operation(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator for critical operations that should never fail silently."""
    return with_error_handling(
        enable_recovery=False,
        fallback_result=None,  # Never use fallback for critical operations
    )(func)


# === Error Monitoring and Reporting ===


class ErrorMonitor:
    """Monitors and tracks error patterns for system health assessment."""

    def __init__(self):
        self.error_counts: Dict[str, int] = {}
        self.error_trends: List[Dict[str, Any]] = []
        self.last_error_check = time.time()

    def record_error(self, error: OpenChronicleError):
        """Record an error for monitoring and pattern analysis."""
        error_key = f"{error.category.value}:{error.severity.value}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1

        self.error_trends.append(
            {
                "timestamp": error.timestamp,
                "category": error.category.value,
                "severity": error.severity.value,
                "component": error.context.component,
                "operation": error.context.operation,
                "message": error.message,
            }
        )

        # Keep only last 1000 errors to prevent memory bloat
        if len(self.error_trends) > 1000:
            self.error_trends = self.error_trends[-1000:]

    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of error patterns and system health."""
        total_errors = sum(self.error_counts.values())
        recent_errors = [
            e for e in self.error_trends if e["timestamp"] > time.time() - 3600
        ]  # Last hour

        return {
            "total_errors": total_errors,
            "recent_errors_count": len(recent_errors),
            "error_breakdown": self.error_counts.copy(),
            "recent_error_categories": {},
            "health_status": (
                "healthy"
                if len(recent_errors) < 10
                else "degraded" if len(recent_errors) < 50 else "critical"
            ),
        }


# Global error monitor instance
error_monitor = ErrorMonitor()

# === Convenience Functions ===


def get_error_recovery_manager() -> ErrorRecoveryManager:
    """Get the global error recovery manager for custom strategy registration."""
    return _error_recovery_manager


def add_recovery_strategy(strategy: ErrorRecoveryStrategy):
    """Add a custom recovery strategy to the global manager."""
    _error_recovery_manager.add_strategy(strategy)


def get_error_monitor() -> ErrorMonitor:
    """Get the global error monitor for system health tracking."""
    return error_monitor
