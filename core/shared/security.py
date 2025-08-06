"""
Security Hardening Framework for OpenChronicle

This module provides comprehensive security validation, sanitization, and
protection mechanisms for all OpenChronicle components.

Phase 2 Week 9-10: Security Hardening
"""

import os
import re
import hashlib
import hmac
import secrets
import sqlite3
import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum

from utilities.logging_system import log_system_event, log_info, log_warning, log_error, log_critical

class SecurityThreatLevel(Enum):
    """Security threat classification levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class SecurityViolationType(Enum):
    """Types of security violations."""
    INPUT_VALIDATION = "input_validation"
    PATH_TRAVERSAL = "path_traversal"
    SQL_INJECTION = "sql_injection"
    FILE_ACCESS = "file_access"
    DATA_SANITIZATION = "data_sanitization"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RATE_LIMITING = "rate_limiting"

@dataclass
class SecurityValidationResult:
    """Result of security validation operations."""
    is_valid: bool
    threat_level: SecurityThreatLevel
    violation_type: Optional[SecurityViolationType] = None
    error_message: str = ""
    sanitized_value: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SecurityContext:
    """Security context for operations."""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    operation: str = "unknown"
    component: str = "unknown"
    ip_address: Optional[str] = None
    timestamp: float = field(default_factory=lambda: datetime.now(UTC).timestamp())

# === Input Validation & Sanitization ===

class InputValidator:
    """Comprehensive input validation and sanitization."""
    
    # Dangerous patterns that could indicate injection attempts
    DANGEROUS_SQL_PATTERNS = [
        r"(?i)(union\s+select|drop\s+table|delete\s+from|insert\s+into)",
        r"(?i)(exec\s*\(|eval\s*\(|script\s*>|<\s*script)",
        r"(?i)(--|\#|/\*|\*/|;)",
        r"(?i)(or\s+1\s*=\s*1|and\s+1\s*=\s*1)",
        r"(?i)(information_schema|sysobjects|syscolumns)"
    ]
    
    DANGEROUS_PATH_PATTERNS = [
        r"\.\.\/",  # Directory traversal
        r"\.\.\\",  # Windows directory traversal
        r"\/etc\/", # Linux system files
        r"\/proc\/", # Linux process files
        r"\/sys\/",  # Linux system files
        r"C:\\Windows\\", # Windows system files
        r"C:\\Program Files\\", # Windows program files
        r"\$\{.*\}", # Environment variable injection
        r"~\/", # Home directory access
    ]
    
    DANGEROUS_SCRIPT_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"vbscript:",
        r"on\w+\s*=",
        r"eval\s*\(",
        r"exec\s*\(",
        r"document\.",
        r"window\.",
    ]
    
    def __init__(self):
        self.max_input_length = 10000  # Maximum input length
        self.max_path_length = 260     # Windows path limit
        self.allowed_file_extensions = {'.json', '.md', '.txt', '.yaml', '.yml'}
        
    def validate_user_input(self, content: str, context: SecurityContext) -> SecurityValidationResult:
        """Validate and sanitize user input content."""
        if not isinstance(content, str):
            return SecurityValidationResult(
                is_valid=False,
                threat_level=SecurityThreatLevel.MEDIUM,
                violation_type=SecurityViolationType.INPUT_VALIDATION,
                error_message="Input must be a string"
            )
        
        # Length validation
        if len(content) > self.max_input_length:
            log_warning(f"Input length exceeded: {len(content)} > {self.max_input_length}", 
                       context_tags={"security": "input_validation", "user": context.user_id})
            return SecurityValidationResult(
                is_valid=False,
                threat_level=SecurityThreatLevel.MEDIUM,
                violation_type=SecurityViolationType.INPUT_VALIDATION,
                error_message=f"Input too long: {len(content)} characters (max: {self.max_input_length})"
            )
        
        # SQL injection detection
        for pattern in self.DANGEROUS_SQL_PATTERNS:
            if re.search(pattern, content):
                log_critical(f"SQL injection attempt detected: {pattern}", 
                           context_tags={"security": "sql_injection", "user": context.user_id})
                return SecurityValidationResult(
                    is_valid=False,
                    threat_level=SecurityThreatLevel.CRITICAL,
                    violation_type=SecurityViolationType.SQL_INJECTION,
                    error_message="Potentially malicious SQL patterns detected"
                )
        
        # Script injection detection
        for pattern in self.DANGEROUS_SCRIPT_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                log_critical(f"Script injection attempt detected: {pattern}", 
                           context_tags={"security": "script_injection", "user": context.user_id})
                return SecurityValidationResult(
                    is_valid=False,
                    threat_level=SecurityThreatLevel.CRITICAL,
                    violation_type=SecurityViolationType.DATA_SANITIZATION,
                    error_message="Potentially malicious script patterns detected"
                )
        
        # Sanitize the content
        sanitized = self._sanitize_content(content)
        
        return SecurityValidationResult(
            is_valid=True,
            threat_level=SecurityThreatLevel.LOW,
            sanitized_value=sanitized,
            metadata={"original_length": len(content), "sanitized_length": len(sanitized)}
        )
    
    def validate_file_path(self, path: Union[str, Path], context: SecurityContext) -> SecurityValidationResult:
        """Validate file paths to prevent directory traversal and unauthorized access."""
        path_str = str(path)
        
        # Length validation
        if len(path_str) > self.max_path_length:
            return SecurityValidationResult(
                is_valid=False,
                threat_level=SecurityThreatLevel.MEDIUM,
                violation_type=SecurityViolationType.PATH_TRAVERSAL,
                error_message=f"Path too long: {len(path_str)} characters"
            )
        
        # Directory traversal detection
        for pattern in self.DANGEROUS_PATH_PATTERNS:
            if re.search(pattern, path_str):
                log_critical(f"Path traversal attempt detected: {path_str}", 
                           context_tags={"security": "path_traversal", "user": context.user_id})
                return SecurityValidationResult(
                    is_valid=False,
                    threat_level=SecurityThreatLevel.CRITICAL,
                    violation_type=SecurityViolationType.PATH_TRAVERSAL,
                    error_message="Potentially malicious path patterns detected"
                )
        
        # Normalize and validate path
        try:
            normalized_path = Path(path_str).resolve()
            
            # Ensure path is within allowed directories
            project_root = Path(__file__).parent.parent.resolve()
            allowed_roots = [
                project_root / "storage",
                project_root / "config", 
                project_root / "templates",
                project_root / "logs"
            ]
            
            if not any(normalized_path.is_relative_to(root) for root in allowed_roots):
                log_warning(f"File access outside allowed directories: {normalized_path}", 
                          context_tags={"security": "file_access", "user": context.user_id})
                return SecurityValidationResult(
                    is_valid=False,
                    threat_level=SecurityThreatLevel.HIGH,
                    violation_type=SecurityViolationType.FILE_ACCESS,
                    error_message="Access denied: path outside allowed directories"
                )
            
            # Validate file extension if it's a file
            if normalized_path.suffix and normalized_path.suffix.lower() not in self.allowed_file_extensions:
                return SecurityValidationResult(
                    is_valid=False,
                    threat_level=SecurityThreatLevel.MEDIUM,
                    violation_type=SecurityViolationType.FILE_ACCESS,
                    error_message=f"File extension not allowed: {normalized_path.suffix}"
                )
            
            return SecurityValidationResult(
                is_valid=True,
                threat_level=SecurityThreatLevel.LOW,
                sanitized_value=normalized_path,
                metadata={"normalized_path": str(normalized_path)}
            )
            
        except (OSError, ValueError) as e:
            return SecurityValidationResult(
                is_valid=False,
                threat_level=SecurityThreatLevel.MEDIUM,
                violation_type=SecurityViolationType.PATH_TRAVERSAL,
                error_message=f"Invalid path: {e}"
            )
    
    def validate_json_data(self, data: Union[str, Dict], context: SecurityContext) -> SecurityValidationResult:
        """Validate JSON data for security issues."""
        try:
            if isinstance(data, str):
                parsed_data = json.loads(data)
            else:
                parsed_data = data
                
            # Check for dangerous keys or values
            dangerous_keys = ["__proto__", "constructor", "prototype", "eval", "exec"]
            
            def check_dangerous_content(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if key in dangerous_keys:
                            return f"Dangerous key found: {path}.{key}"
                        result = check_dangerous_content(value, f"{path}.{key}")
                        if result:
                            return result
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        result = check_dangerous_content(item, f"{path}[{i}]")
                        if result:
                            return result
                elif isinstance(obj, str):
                    # Check for script injection in string values
                    for pattern in self.DANGEROUS_SCRIPT_PATTERNS:
                        if re.search(pattern, obj, re.IGNORECASE):
                            return f"Dangerous script pattern in: {path}"
                return None
            
            danger_result = check_dangerous_content(parsed_data)
            if danger_result:
                log_critical(f"Dangerous JSON content detected: {danger_result}", 
                           context_tags={"security": "json_validation", "user": context.user_id})
                return SecurityValidationResult(
                    is_valid=False,
                    threat_level=SecurityThreatLevel.HIGH,
                    violation_type=SecurityViolationType.DATA_SANITIZATION,
                    error_message=danger_result
                )
            
            return SecurityValidationResult(
                is_valid=True,
                threat_level=SecurityThreatLevel.LOW,
                sanitized_value=parsed_data
            )
            
        except json.JSONDecodeError as e:
            return SecurityValidationResult(
                is_valid=False,
                threat_level=SecurityThreatLevel.LOW,
                violation_type=SecurityViolationType.INPUT_VALIDATION,
                error_message=f"Invalid JSON: {e}"
            )
    
    def _sanitize_content(self, content: str) -> str:
        """Sanitize content by removing or escaping dangerous patterns."""
        sanitized = content
        
        # Remove null bytes
        sanitized = sanitized.replace('\x00', '')
        
        # Remove or escape HTML/script tags
        sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        sanitized = re.sub(r'<[^>]*>', '', sanitized)  # Remove all HTML tags
        
        # Escape special characters that could be used for injection
        dangerous_chars = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;',
            '/': '&#x2F;'
        }
        
        for char, escape in dangerous_chars.items():
            sanitized = sanitized.replace(char, escape)
        
        return sanitized.strip()

# === SQL Security ===

class SQLSecurityValidator:
    """SQL query security validation and safe execution."""
    
    def __init__(self):
        self.allowed_operations = {'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER'}
        self.blocked_keywords = {'EXEC', 'EXECUTE', 'EVAL', 'SCRIPT'}
    
    def validate_sql_query(self, query: str, context: SecurityContext) -> SecurityValidationResult:
        """Validate SQL queries for injection attempts."""
        if not query.strip():
            return SecurityValidationResult(
                is_valid=False,
                threat_level=SecurityThreatLevel.LOW,
                violation_type=SecurityViolationType.INPUT_VALIDATION,
                error_message="Empty SQL query"
            )
        
        # Check for blocked keywords
        query_upper = query.upper()
        for keyword in self.blocked_keywords:
            if keyword in query_upper:
                log_critical(f"Blocked SQL keyword detected: {keyword}", 
                           context_tags={"security": "sql_injection", "user": context.user_id})
                return SecurityValidationResult(
                    is_valid=False,
                    threat_level=SecurityThreatLevel.CRITICAL,
                    violation_type=SecurityViolationType.SQL_INJECTION,
                    error_message=f"Blocked SQL keyword: {keyword}"
                )
        
        # Check for suspicious patterns
        validator = InputValidator()
        for pattern in validator.DANGEROUS_SQL_PATTERNS:
            if re.search(pattern, query):
                log_critical(f"Suspicious SQL pattern detected: {pattern}", 
                           context_tags={"security": "sql_injection", "user": context.user_id})
                return SecurityValidationResult(
                    is_valid=False,
                    threat_level=SecurityThreatLevel.CRITICAL,
                    violation_type=SecurityViolationType.SQL_INJECTION,
                    error_message="Suspicious SQL patterns detected"
                )
        
        return SecurityValidationResult(
            is_valid=True,
            threat_level=SecurityThreatLevel.LOW
        )
    
    def execute_safe_query(self, 
                          connection: sqlite3.Connection, 
                          query: str, 
                          parameters: Tuple = (), 
                          context: SecurityContext = None) -> Any:
        """Execute SQL query with security validation."""
        if context is None:
            context = SecurityContext(operation="sql_query")
        
        # Validate the query
        validation_result = self.validate_sql_query(query, context)
        if not validation_result.is_valid:
            raise ValueError(f"SQL security validation failed: {validation_result.error_message}")
        
        try:
            cursor = connection.cursor()
            
            # Use parameterized queries to prevent injection
            if parameters:
                result = cursor.execute(query, parameters)
            else:
                result = cursor.execute(query)
            
            log_info(f"SQL query executed safely", 
                    context_tags={"security": "sql_execution", "user": context.user_id})
            
            return result
            
        except sqlite3.Error as e:
            log_error(f"SQL execution error: {e}", 
                     context_tags={"security": "sql_error", "user": context.user_id})
            raise

# === File Access Security ===

class FileAccessManager:
    """Secure file access management with path validation."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.resolve()
        self.allowed_directories = {
            "storage": self.project_root / "storage",
            "config": self.project_root / "config", 
            "templates": self.project_root / "templates",
            "logs": self.project_root / "logs"
        }
        self.validator = InputValidator()
    
    def safe_read_file(self, 
                      file_path: Union[str, Path], 
                      context: SecurityContext,
                      encoding: str = 'utf-8') -> Tuple[bool, Union[str, bytes]]:
        """Safely read a file with security validation."""
        
        # Validate the path
        validation_result = self.validator.validate_file_path(file_path, context)
        if not validation_result.is_valid:
            log_warning(f"File read denied: {validation_result.error_message}", 
                       context_tags={"security": "file_access", "user": context.user_id})
            return False, validation_result.error_message
        
        safe_path = validation_result.sanitized_value
        
        try:
            if not safe_path.exists():
                return False, f"File not found: {safe_path}"
            
            if not safe_path.is_file():
                return False, f"Path is not a file: {safe_path}"
            
            with open(safe_path, 'r', encoding=encoding) as f:
                content = f.read()
            
            log_info(f"File read successfully: {safe_path}", 
                    context_tags={"security": "file_access", "user": context.user_id})
            
            return True, content
            
        except (OSError, IOError, UnicodeDecodeError) as e:
            log_error(f"File read error: {e}", 
                     context_tags={"security": "file_error", "user": context.user_id})
            return False, f"File read error: {e}"
    
    def safe_write_file(self, 
                       file_path: Union[str, Path], 
                       content: str,
                       context: SecurityContext,
                       encoding: str = 'utf-8') -> Tuple[bool, str]:
        """Safely write to a file with security validation."""
        
        # Validate the path
        validation_result = self.validator.validate_file_path(file_path, context)
        if not validation_result.is_valid:
            log_warning(f"File write denied: {validation_result.error_message}", 
                       context_tags={"security": "file_access", "user": context.user_id})
            return False, validation_result.error_message
        
        # Validate the content
        content_validation = self.validator.validate_user_input(content, context)
        if not content_validation.is_valid:
            log_warning(f"File content validation failed: {content_validation.error_message}", 
                       context_tags={"security": "content_validation", "user": context.user_id})
            return False, content_validation.error_message
        
        safe_path = validation_result.sanitized_value
        safe_content = content_validation.sanitized_value
        
        try:
            # Ensure directory exists
            safe_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(safe_path, 'w', encoding=encoding) as f:
                f.write(safe_content)
            
            log_info(f"File written successfully: {safe_path}", 
                    context_tags={"security": "file_access", "user": context.user_id})
            
            return True, f"File written: {safe_path}"
            
        except (OSError, IOError) as e:
            log_error(f"File write error: {e}", 
                     context_tags={"security": "file_error", "user": context.user_id})
            return False, f"File write error: {e}"

# === Security Monitoring ===

class SecurityMonitor:
    """Monitor and track security events and violations."""
    
    def __init__(self):
        self.violation_counts: Dict[str, int] = {}
        self.recent_violations: List[Dict[str, Any]] = []
        self.max_recent_violations = 1000
    
    def record_security_violation(self, 
                                 violation_type: SecurityViolationType,
                                 threat_level: SecurityThreatLevel,
                                 context: SecurityContext,
                                 details: str = ""):
        """Record a security violation for monitoring and analysis."""
        
        violation_key = f"{violation_type.value}:{threat_level.value}"
        self.violation_counts[violation_key] = self.violation_counts.get(violation_key, 0) + 1
        
        violation_record = {
            "timestamp": context.timestamp,
            "violation_type": violation_type.value,
            "threat_level": threat_level.value,
            "user_id": context.user_id,
            "session_id": context.session_id,
            "operation": context.operation,
            "component": context.component,
            "ip_address": context.ip_address,
            "details": details
        }
        
        self.recent_violations.append(violation_record)
        
        # Keep only recent violations
        if len(self.recent_violations) > self.max_recent_violations:
            self.recent_violations = self.recent_violations[-self.max_recent_violations:]
        
        # Log the violation
        log_system_event("security_violation", {
            "violation_type": violation_type.value,
            "threat_level": threat_level.value,
            "user_id": context.user_id,
            "details": details
        })
        
        # Alert on critical violations
        if threat_level == SecurityThreatLevel.CRITICAL:
            log_critical(f"CRITICAL SECURITY VIOLATION: {violation_type.value} - {details}", 
                        context_tags={"security": "critical_violation", "user": context.user_id})
    
    def get_security_summary(self) -> Dict[str, Any]:
        """Get summary of security violations and system health."""
        recent_critical = [v for v in self.recent_violations 
                          if v["threat_level"] == SecurityThreatLevel.CRITICAL.value 
                          and v["timestamp"] > datetime.now(UTC).timestamp() - 3600]
        
        return {
            "total_violations": sum(self.violation_counts.values()),
            "violation_breakdown": self.violation_counts.copy(),
            "recent_critical_violations": len(recent_critical),
            "security_status": self._calculate_security_status(),
            "last_violation": self.recent_violations[-1] if self.recent_violations else None
        }
    
    def _calculate_security_status(self) -> str:
        """Calculate overall security status based on recent violations."""
        recent_hour_violations = [
            v for v in self.recent_violations 
            if v["timestamp"] > datetime.now(UTC).timestamp() - 3600
        ]
        
        critical_count = sum(1 for v in recent_hour_violations 
                           if v["threat_level"] == SecurityThreatLevel.CRITICAL.value)
        high_count = sum(1 for v in recent_hour_violations 
                        if v["threat_level"] == SecurityThreatLevel.HIGH.value)
        
        if critical_count > 0:
            return "critical"
        elif high_count > 5:
            return "high_risk"
        elif len(recent_hour_violations) > 20:
            return "elevated"
        else:
            return "normal"

# === Global Security Manager ===

class SecurityManager:
    """Central security management for OpenChronicle."""
    
    def __init__(self):
        self.input_validator = InputValidator()
        self.sql_validator = SQLSecurityValidator()
        self.file_manager = FileAccessManager()
        self.monitor = SecurityMonitor()
    
    def validate_and_sanitize(self, 
                             data: Any, 
                             validation_type: str,
                             context: SecurityContext) -> SecurityValidationResult:
        """Central validation and sanitization endpoint."""
        
        try:
            if validation_type == "user_input":
                result = self.input_validator.validate_user_input(data, context)
            elif validation_type == "file_path":
                result = self.input_validator.validate_file_path(data, context)
            elif validation_type == "json_data":
                result = self.input_validator.validate_json_data(data, context)
            elif validation_type == "sql_query":
                result = self.sql_validator.validate_sql_query(data, context)
            else:
                result = SecurityValidationResult(
                    is_valid=False,
                    threat_level=SecurityThreatLevel.LOW,
                    error_message=f"Unknown validation type: {validation_type}"
                )
            
            # Record violations
            if not result.is_valid and result.violation_type:
                self.monitor.record_security_violation(
                    result.violation_type,
                    result.threat_level,
                    context,
                    result.error_message
                )
            
            return result
            
        except Exception as e:
            log_error(f"Security validation error: {e}", 
                     context_tags={"security": "validation_error", "user": context.user_id})
            return SecurityValidationResult(
                is_valid=False,
                threat_level=SecurityThreatLevel.MEDIUM,
                error_message=f"Validation error: {e}"
            )

# === Global Security Instance ===

security_manager = SecurityManager()

# === Convenience Functions ===

def validate_user_input(content: str, user_id: str = None, operation: str = "input") -> SecurityValidationResult:
    """Convenience function for user input validation."""
    context = SecurityContext(user_id=user_id, operation=operation)
    return security_manager.validate_and_sanitize(content, "user_input", context)

def validate_file_path(path: Union[str, Path], user_id: str = None, operation: str = "file_access") -> SecurityValidationResult:
    """Convenience function for file path validation."""
    context = SecurityContext(user_id=user_id, operation=operation)
    return security_manager.validate_and_sanitize(path, "file_path", context)

def validate_sql_query(query: str, user_id: str = None, operation: str = "sql_query") -> SecurityValidationResult:
    """Convenience function for SQL query validation."""
    context = SecurityContext(user_id=user_id, operation=operation)
    return security_manager.validate_and_sanitize(query, "sql_query", context)

def safe_read_file(file_path: Union[str, Path], user_id: str = None, encoding: str = 'utf-8') -> Tuple[bool, str]:
    """Convenience function for safe file reading."""
    context = SecurityContext(user_id=user_id, operation="file_read")
    return security_manager.file_manager.safe_read_file(file_path, context, encoding)

def safe_write_file(file_path: Union[str, Path], content: str, user_id: str = None, encoding: str = 'utf-8') -> Tuple[bool, str]:
    """Convenience function for safe file writing."""
    context = SecurityContext(user_id=user_id, operation="file_write")
    return security_manager.file_manager.safe_write_file(file_path, content, context, encoding)

def get_security_manager() -> SecurityManager:
    """Get the global security manager instance."""
    return security_manager

def get_security_summary() -> Dict[str, Any]:
    """Get security monitoring summary."""
    return security_manager.monitor.get_security_summary()
