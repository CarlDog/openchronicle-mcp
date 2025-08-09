"""
Security Decorators for OpenChronicle

Provides convenient decorators for automatic security validation and protection
in OpenChronicle components.

Phase 2 Week 9-10: Security Hardening
"""

import functools
import inspect
from typing import Any, Callable, Dict, List, Optional, Union
from pathlib import Path

from core.shared.security import (
    SecurityManager, SecurityContext, SecurityValidationResult,
    SecurityThreatLevel, SecurityViolationType, security_manager
)
from .logging_system import log_warning, log_error

def secure_input(*param_names: str, validation_type: str = "user_input"):
    """
    Decorator to automatically validate function parameters for security.
    
    Args:
        param_names: Names of parameters to validate
        validation_type: Type of validation to perform
    
    Example:
        @secure_input('user_message', 'story_content', validation_type='user_input')
        def process_story(story_id: str, user_message: str, story_content: str):
            # Function receives sanitized inputs
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get function signature
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Create security context
            context = SecurityContext(
                operation=func.__name__,
                component=func.__module__
            )
            
            # Validate specified parameters
            for param_name in param_names:
                if param_name in bound_args.arguments:
                    value = bound_args.arguments[param_name]
                    if value is not None:
                        result = security_manager.validate_and_sanitize(
                            value, validation_type, context
                        )
                        
                        if not result.is_valid:
                            raise ValueError(f"Security validation failed for {param_name}: {result.error_message}")
                        
                        # Replace with sanitized value if available
                        if result.sanitized_value is not None:
                            bound_args.arguments[param_name] = result.sanitized_value
            
            # Call function with validated arguments
            return func(*bound_args.args, **bound_args.kwargs)
        
        return wrapper
    return decorator

def secure_file_access(path_param: str = "file_path"):
    """
    Decorator to validate file path parameters.
    
    Args:
        path_param: Name of the file path parameter to validate
    
    Example:
        @secure_file_access('config_path')
        def load_config(config_path: str):
            # config_path is validated and normalized
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get function signature
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Create security context
            context = SecurityContext(
                operation=func.__name__,
                component=func.__module__
            )
            
            # Validate file path parameter
            if path_param in bound_args.arguments:
                path_value = bound_args.arguments[path_param]
                if path_value is not None:
                    result = security_manager.validate_and_sanitize(
                        path_value, "file_path", context
                    )
                    
                    if not result.is_valid:
                        raise ValueError(f"File path validation failed: {result.error_message}")
                    
                    # Replace with normalized path
                    if result.sanitized_value is not None:
                        bound_args.arguments[path_param] = result.sanitized_value
            
            return func(*bound_args.args, **bound_args.kwargs)
        
        return wrapper
    return decorator

def secure_sql_execution(query_param: str = "query", params_param: str = "parameters"):
    """
    Decorator to validate SQL queries before execution.
    
    Args:
        query_param: Name of the SQL query parameter
        params_param: Name of the parameters parameter
    
    Example:
        @secure_sql_execution('sql_query', 'sql_params')
        def execute_query(sql_query: str, sql_params: tuple = ()):
            # SQL query is validated for injection attempts
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get function signature
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Create security context
            context = SecurityContext(
                operation=func.__name__,
                component=func.__module__
            )
            
            # Validate SQL query
            if query_param in bound_args.arguments:
                query_value = bound_args.arguments[query_param]
                if query_value is not None:
                    result = security_manager.validate_and_sanitize(
                        query_value, "sql_query", context
                    )
                    
                    if not result.is_valid:
                        raise ValueError(f"SQL query validation failed: {result.error_message}")
            
            return func(*bound_args.args, **bound_args.kwargs)
        
        return wrapper
    return decorator

def rate_limited(max_calls: int = 100, window_seconds: int = 60, per_user: bool = True):
    """
    Decorator to implement rate limiting on function calls.
    
    Args:
        max_calls: Maximum number of calls allowed
        window_seconds: Time window in seconds
        per_user: Whether to apply rate limiting per user
    
    Example:
        @rate_limited(max_calls=10, window_seconds=60, per_user=True)
        def expensive_operation(user_id: str, data: str):
            # Function is rate limited per user
            pass
    """
    import time
    from collections import defaultdict, deque
    
    call_history = defaultdict(deque)
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time()
            
            # Determine rate limiting key
            if per_user:
                # Try to extract user_id from arguments
                sig = inspect.signature(func)
                bound_args = sig.bind(*args, **kwargs)
                user_id = bound_args.arguments.get('user_id', 'anonymous')
                rate_key = f"{func.__name__}:{user_id}"
            else:
                rate_key = func.__name__
            
            # Clean old calls outside the window
            while (call_history[rate_key] and 
                   current_time - call_history[rate_key][0] > window_seconds):
                call_history[rate_key].popleft()
            
            # Check rate limit
            if len(call_history[rate_key]) >= max_calls:
                context = SecurityContext(
                    operation=func.__name__,
                    component=func.__module__,
                    user_id=user_id if per_user else None
                )
                
                security_manager.monitor.record_security_violation(
                    SecurityViolationType.RATE_LIMITING,
                    SecurityThreatLevel.MEDIUM,
                    context,
                    f"Rate limit exceeded: {max_calls} calls in {window_seconds}s"
                )
                
                raise ValueError(f"Rate limit exceeded: {max_calls} calls per {window_seconds} seconds")
            
            # Record this call
            call_history[rate_key].append(current_time)
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

def security_monitored(threat_level: SecurityThreatLevel = SecurityThreatLevel.LOW):
    """
    Decorator to monitor function calls for security events.
    
    Args:
        threat_level: Threat level for monitoring this function
    
    Example:
        @security_monitored(SecurityThreatLevel.HIGH)
        def admin_operation(user_id: str, action: str):
            # Function calls are monitored for security
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create security context
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            user_id = bound_args.arguments.get('user_id', 'anonymous')
            
            context = SecurityContext(
                operation=func.__name__,
                component=func.__module__,
                user_id=user_id
            )
            
            try:
                result = func(*args, **kwargs)
                
                # Log successful security-monitored operation
                if threat_level in [SecurityThreatLevel.HIGH, SecurityThreatLevel.CRITICAL]:
                    from .logging_system import log_info
                    log_info(f"Security monitored operation completed: {func.__name__}", 
                            context_tags={"security": "monitored_operation", "user": user_id})
                
                return result
                
            except Exception as e:
                # Record security event for failed operations
                security_manager.monitor.record_security_violation(
                    SecurityViolationType.AUTHORIZATION,
                    threat_level,
                    context,
                    f"Operation failed: {str(e)}"
                )
                raise
        
        return wrapper
    return decorator

def require_authentication(user_param: str = "user_id"):
    """
    Decorator to require authentication for function access.
    
    Args:
        user_param: Name of the user ID parameter
    
    Example:
        @require_authentication('user_id')
        def protected_operation(user_id: str, data: str):
            # Function requires valid user_id
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get function signature
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Check for user authentication
            user_id = bound_args.arguments.get(user_param)
            if not user_id or user_id.strip() == "":
                context = SecurityContext(
                    operation=func.__name__,
                    component=func.__module__
                )
                
                security_manager.monitor.record_security_violation(
                    SecurityViolationType.AUTHENTICATION,
                    SecurityThreatLevel.HIGH,
                    context,
                    f"Unauthenticated access attempt to {func.__name__}"
                )
                
                raise ValueError(f"Authentication required for {func.__name__}")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

# === Composite Decorators ===

def secure_operation(
    input_params: Optional[List[str]] = None,
    file_path_params: Optional[List[str]] = None,
    sql_query_params: Optional[List[str]] = None,
    require_auth: bool = False,
    rate_limit: Optional[Dict[str, Any]] = None,
    monitor_level: SecurityThreatLevel = SecurityThreatLevel.LOW
):
    """
    Composite decorator that applies multiple security measures.
    
    Args:
        input_params: List of user input parameters to validate
        file_path_params: List of file path parameters to validate
        sql_query_params: List of SQL query parameters to validate
        require_auth: Whether to require authentication
        rate_limit: Rate limiting configuration {'max_calls': int, 'window_seconds': int}
        monitor_level: Security monitoring threat level
    
    Example:
        @secure_operation(
            input_params=['story_content', 'user_message'],
            file_path_params=['config_file'],
            require_auth=True,
            rate_limit={'max_calls': 5, 'window_seconds': 60},
            monitor_level=SecurityThreatLevel.MEDIUM
        )
        def process_story_data(user_id: str, story_content: str, config_file: str):
            # Fully secured function
            pass
    """
    def decorator(func: Callable) -> Callable:
        # Apply decorators in order
        secured_func = func
        
        # Security monitoring
        secured_func = security_monitored(monitor_level)(secured_func)
        
        # Rate limiting
        if rate_limit:
            secured_func = rate_limited(
                max_calls=rate_limit.get('max_calls', 100),
                window_seconds=rate_limit.get('window_seconds', 60),
                per_user=True
            )(secured_func)
        
        # Authentication
        if require_auth:
            secured_func = require_authentication()(secured_func)
        
        # Input validation
        if input_params:
            secured_func = secure_input(*input_params, validation_type="user_input")(secured_func)
        
        # File path validation
        if file_path_params:
            for param in file_path_params:
                secured_func = secure_file_access(param)(secured_func)
        
        # SQL query validation
        if sql_query_params:
            for param in sql_query_params:
                secured_func = secure_sql_execution(param)(secured_func)
        
        return secured_func
    
    return decorator

# === Helper Functions ===

def create_security_context(user_id: str = None, 
                          operation: str = "unknown",
                          component: str = "unknown") -> SecurityContext:
    """Create a security context for manual validation."""
    return SecurityContext(
        user_id=user_id,
        operation=operation,
        component=component
    )

def validate_and_raise(data: Any, 
                      validation_type: str,
                      context: SecurityContext = None,
                      param_name: str = "parameter") -> Any:
    """
    Validate data and raise exception if invalid, return sanitized value if valid.
    
    Args:
        data: Data to validate
        validation_type: Type of validation
        context: Security context
        param_name: Parameter name for error messages
    
    Returns:
        Sanitized data if valid
        
    Raises:
        ValueError: If validation fails
    """
    if context is None:
        context = SecurityContext()
    
    result = security_manager.validate_and_sanitize(data, validation_type, context)
    
    if not result.is_valid:
        raise ValueError(f"Security validation failed for {param_name}: {result.error_message}")
    
    return result.sanitized_value if result.sanitized_value is not None else data
