"""
OpenChronicle Core Module

Central orchestration and management systems for the OpenChronicle
narrative AI engine.
"""

# Import security framework for easy access
from .shared.security import (
    security_manager, validate_user_input, validate_file_path, 
    validate_sql_query, safe_read_file, safe_write_file,
    get_security_summary, SecurityThreatLevel, SecurityViolationType
)

from .shared.security_decorators import (
    secure_input, secure_file_access, secure_sql_execution,
    rate_limited, security_monitored, require_authentication,
    secure_operation
)

from .shared.dependency_injection import DIContainer, get_container
from .shared.error_handling import OpenChronicleError

__all__ = [
    # Security
    'security_manager', 'validate_user_input', 'validate_file_path',
    'validate_sql_query', 'safe_read_file', 'safe_write_file',
    'get_security_summary', 'SecurityThreatLevel', 'SecurityViolationType',
    
    # Security Decorators
    'secure_input', 'secure_file_access', 'secure_sql_execution',
    'rate_limited', 'security_monitored', 'require_authentication',
    'secure_operation',
    
    # Dependency Injection
    'DIContainer', 'get_container',
    
    # Error Handling
    'OpenChronicleError'
]