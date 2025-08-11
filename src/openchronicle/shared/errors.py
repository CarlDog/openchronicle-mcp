"""Central error taxonomy for OpenChronicle."""


class BaseAppError(Exception):
    """Base error for OpenChronicle."""


class ConfigurationError(BaseAppError):
    """Raised for configuration-related problems."""


class ProviderError(BaseAppError):
    """Raised when external provider/model errors occur."""


class ValidationError(BaseAppError):
    """Raised for input/data validation issues."""


class PersistenceError(BaseAppError):
    """Raised for storage/database errors."""
