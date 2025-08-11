"""
Centralized logging configuration for OpenChronicle.

This module provides a standardized logging setup using Python's built-in
logging module with structured configuration and correlation ID support.
"""

import logging
import logging.config
import uuid
from contextvars import ContextVar
from typing import Any


# Context variable for correlation IDs
correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)

# Standard logging configuration
LOGGING_CONFIG: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(correlation_id)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "detailed": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(correlation_id)s - %(funcName)s:%(lineno)d - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "json": {
            "format": '{"timestamp": "%(asctime)s", "logger": "%(name)s", "level": "%(levelname)s", "correlation_id": "%(correlation_id)s", "message": "%(message)s"}',
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "filters": {
        "correlation": {"()": "src.openchronicle.shared.logging.CorrelationFilter"}
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "filters": ["correlation"],
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "detailed",
            "filters": ["correlation"],
            "filename": "logs/openchronicle.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "detailed",
            "filters": ["correlation"],
            "filename": "logs/openchronicle_errors.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "level": "ERROR",
        },
    },
    "loggers": {
        "openchronicle": {
            "level": "INFO",
            "handlers": ["console", "file", "error_file"],
            "propagate": False,
        },
        "openchronicle.domain": {"level": "DEBUG", "propagate": True},
        "openchronicle.infrastructure": {"level": "INFO", "propagate": True},
    },
    "root": {"level": "WARNING", "handlers": ["console"]},
}


class CorrelationFilter(logging.Filter):
    """Filter to add correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to the log record."""
        record.correlation_id = correlation_id.get() or "N/A"
        return True


def setup_logging(
    config: dict[str, Any] | None = None, log_level: str = "INFO"
) -> None:
    """
    Setup logging configuration for the application.

    Args:
        config: Optional custom logging configuration. If None, uses LOGGING_CONFIG.
        log_level: Default log level for the application logger.
    """
    import os

    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)

    # Use provided config or default
    config = config or LOGGING_CONFIG.copy()

    # Update log level if specified
    if "loggers" in config and "openchronicle" in config["loggers"]:
        config["loggers"]["openchronicle"]["level"] = log_level.upper()

    # Apply configuration
    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given name.

    Args:
        name: Logger name, typically __name__ from the calling module.

    Returns:
        Configured logger instance.
    """
    # Ensure basic logging is configured
    if not hasattr(get_logger, "_configured"):
        import os

        os.makedirs("logs", exist_ok=True)

        # Simple configuration that works reliably
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler("logs/openchronicle.log", encoding="utf-8"),
            ],
        )
        get_logger._configured = True

    logger = logging.getLogger(name)

    # Add correlation filter if not already present
    if not any(isinstance(f, CorrelationFilter) for f in logger.filters):
        logger.addFilter(CorrelationFilter())

    return logger


def set_correlation_id(correlation_id_value: str | None = None) -> str:
    """
    Set a correlation ID for tracking requests across the system.

    Args:
        correlation_id_value: Optional correlation ID. If None, generates a new UUID.

    Returns:
        The correlation ID that was set.
    """
    if correlation_id_value is None:
        correlation_id_value = str(uuid.uuid4())[:8]

    correlation_id.set(correlation_id_value)
    return correlation_id_value


def get_correlation_id() -> str | None:
    """Get the current correlation ID."""
    return correlation_id.get()


def clear_correlation_id() -> None:
    """Clear the current correlation ID."""
    correlation_id.set(None)


# Convenience functions for common logging patterns
def log_system_event(event_type: str, description: str, **kwargs) -> None:
    """Log a system event with structured information."""
    logger = get_logger("openchronicle.system")
    logger.info(f"[{event_type}] {description}", extra=kwargs)


def log_performance_metric(
    metric_name: str, value: float, unit: str = "ms", **kwargs
) -> None:
    """Log a performance metric."""
    logger = get_logger("openchronicle.performance")
    logger.info(f"METRIC {metric_name}={value}{unit}", extra=kwargs)


def log_error_with_context(error: Exception, context: str, **kwargs) -> None:
    """Log an error with additional context."""
    logger = get_logger("openchronicle.error")
    logger.error(f"Error in {context}: {error}", exc_info=True, extra=kwargs)


# Initialize logging on module import
if not logging.getLogger().handlers:
    setup_logging()
