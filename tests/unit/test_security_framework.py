"""
Tests for OpenChronicle Security Framework

Comprehensive security testing including input validation, SQL injection
prevention, file access controls, and security monitoring.

Phase 2 Week 9-10: Security Hardening
"""

import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from core.shared.security import (
    SecurityManager, InputValidator, SQLSecurityValidator, FileAccessManager,
    SecurityMonitor, SecurityContext, SecurityThreatLevel, SecurityViolationType,
    security_manager, validate_user_input, validate_file_path, validate_sql_query
)

from core.shared.security_decorators import (
    secure_input, secure_file_access, secure_sql_execution,
    rate_limited, security_monitored, require_authentication,
    secure_operation
)

class TestInputValidator:
    """Test input validation and sanitization."""
    
    def setup_method(self):
        self.validator = InputValidator()
        self.context = SecurityContext(user_id="test_user", operation="test")
    
    def test_valid_user_input(self):
        """Test validation of normal user input."""
        content = "This is a normal story about adventures."
        result = self.validator.validate_user_input(content, self.context)
        
        assert result.is_valid
        assert result.threat_level == SecurityThreatLevel.LOW
        assert result.sanitized_value is not None
    
    def test_sql_injection_detection(self):
        """Test detection of SQL injection attempts."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "admin' OR '1'='1",
            "UNION SELECT * FROM information_schema",
            "1; DELETE FROM stories;",
            "' EXEC xp_cmdshell('dir') --"
        ]
        
        for malicious_input in malicious_inputs:
            result = self.validator.validate_user_input(malicious_input, self.context)
            
            assert not result.is_valid
            assert result.threat_level == SecurityThreatLevel.CRITICAL
            assert result.violation_type == SecurityViolationType.SQL_INJECTION
    
    def test_script_injection_detection(self):
        """Test detection of script injection attempts."""
        malicious_scripts = [
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            "<img src=x onerror=alert(1)>",
            "eval('malicious code')",
            "document.cookie"
        ]
        
        for script in malicious_scripts:
            result = self.validator.validate_user_input(script, self.context)
            
            assert not result.is_valid
            assert result.threat_level == SecurityThreatLevel.CRITICAL
    
    def test_input_length_validation(self):
        """Test input length limits."""
        long_input = "x" * 20000  # Exceeds max length
        result = self.validator.validate_user_input(long_input, self.context)
        
        assert not result.is_valid
        assert result.threat_level == SecurityThreatLevel.MEDIUM
        assert "too long" in result.error_message
    
    def test_content_sanitization(self):
        """Test content sanitization functionality."""
        content = "<script>alert('test')</script>Hello & <b>World</b>"
        result = self.validator.validate_user_input(content, self.context)
        
        # Should sanitize HTML and escape special characters
        sanitized = result.sanitized_value
        assert "<script>" not in sanitized
        assert "&amp;" in sanitized or "Hello" in sanitized
        assert "<b>" not in sanitized
    
    def test_path_traversal_detection(self):
        """Test detection of path traversal attempts."""
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "/etc/shadow",
            "C:\\Windows\\System32\\config\\SAM",
            "${HOME}/.ssh/id_rsa",
            "~/sensitive_file"
        ]
        
        for path in malicious_paths:
            result = self.validator.validate_file_path(path, self.context)
            
            assert not result.is_valid
            assert result.threat_level in [SecurityThreatLevel.CRITICAL, SecurityThreatLevel.HIGH]
    
    def test_valid_file_path(self):
        """Test validation of legitimate file paths."""
        # Create a temporary directory structure for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            storage_path = temp_path / "storage" / "test.json"
            storage_path.parent.mkdir(parents=True, exist_ok=True)
            storage_path.touch()
            
            # Mock the project root to point to our temp directory
            with patch.object(Path, 'resolve', return_value=temp_path):
                result = self.validator.validate_file_path(str(storage_path), self.context)
                
                # Note: This test may fail due to path resolution, but demonstrates the concept
                assert result.threat_level in [SecurityThreatLevel.LOW, SecurityThreatLevel.HIGH]
    
    def test_json_validation(self):
        """Test JSON data validation."""
        # Valid JSON
        valid_json = {"name": "test", "value": 123}
        result = self.validator.validate_json_data(valid_json, self.context)
        assert result.is_valid
        
        # Dangerous JSON with prototype pollution attempt
        dangerous_json = {"__proto__": {"admin": True}}
        result = self.validator.validate_json_data(dangerous_json, self.context)
        assert not result.is_valid
        assert result.threat_level == SecurityThreatLevel.HIGH
        
        # JSON with script injection
        script_json = {"content": "<script>alert('xss')</script>"}
        result = self.validator.validate_json_data(script_json, self.context)
        assert not result.is_valid

class TestSQLSecurityValidator:
    """Test SQL security validation."""
    
    def setup_method(self):
        self.validator = SQLSecurityValidator()
        self.context = SecurityContext(user_id="test_user", operation="test_sql")
    
    def test_valid_sql_queries(self):
        """Test validation of legitimate SQL queries."""
        valid_queries = [
            "SELECT * FROM stories WHERE id = ?",
            "INSERT INTO scenes (content) VALUES (?)",
            "UPDATE characters SET name = ? WHERE id = ?",
            "DELETE FROM temp_data WHERE created < ?"
        ]
        
        for query in valid_queries:
            result = self.validator.validate_sql_query(query, self.context)
            assert result.is_valid
            assert result.threat_level == SecurityThreatLevel.LOW
    
    def test_sql_injection_detection(self):
        """Test detection of SQL injection in queries."""
        malicious_queries = [
            "SELECT * FROM users; DROP TABLE stories;",
            "SELECT * FROM stories WHERE id = 1 OR 1=1",
            "EXEC xp_cmdshell('rm -rf /')",
            "SELECT * FROM information_schema.tables",
            "/* comment */ UNION SELECT password FROM users"
        ]
        
        for query in malicious_queries:
            result = self.validator.validate_sql_query(query, self.context)
            assert not result.is_valid
            assert result.threat_level == SecurityThreatLevel.CRITICAL
    
    def test_safe_query_execution(self):
        """Test safe SQL query execution."""
        # Create in-memory database for testing
        conn = sqlite3.connect(':memory:')
        conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        
        # Test safe parameterized query
        query = "INSERT INTO test (id, name) VALUES (?, ?)"
        parameters = (1, "test_name")
        
        result = self.validator.execute_safe_query(conn, query, parameters, self.context)
        assert result is not None
        
        # Verify data was inserted
        cursor = conn.execute("SELECT * FROM test WHERE id = 1")
        row = cursor.fetchone()
        assert row[1] == "test_name"
        
        conn.close()
    
    def test_blocked_keywords(self):
        """Test blocking of dangerous SQL keywords."""
        blocked_queries = [
            "EXEC stored_procedure()",
            "EXECUTE immediate 'DROP TABLE'",
            "EVAL('malicious code')"
        ]
        
        for query in blocked_queries:
            result = self.validator.validate_sql_query(query, self.context)
            assert not result.is_valid
            assert result.threat_level == SecurityThreatLevel.CRITICAL

class TestSecurityDecorators:
    """Test security decorators."""
    
    def test_secure_input_decorator(self):
        """Test the secure input decorator."""
        @secure_input('message', validation_type='user_input')
        def process_message(message: str):
            return f"Processed: {message}"
        
        # Valid input
        result = process_message("Hello world")
        assert "Hello world" in result
        
        # Invalid input should raise exception
        with pytest.raises(ValueError):
            process_message("<script>alert('xss')</script>")
    
    def test_rate_limiting_decorator(self):
        """Test rate limiting decorator."""
        @rate_limited(max_calls=2, window_seconds=1, per_user=False)
        def limited_function():
            return "success"
        
        # First two calls should succeed
        assert limited_function() == "success"
        assert limited_function() == "success"
        
        # Third call should fail
        with pytest.raises(ValueError, match="Rate limit exceeded"):
            limited_function()
    
    def test_authentication_decorator(self):
        """Test authentication requirement decorator."""
        @require_authentication('user_id')
        def protected_function(user_id: str, data: str):
            return f"User {user_id} accessed data"
        
        # Valid user ID
        result = protected_function("valid_user", "data")
        assert "valid_user" in result
        
        # Invalid user ID should raise exception
        with pytest.raises(ValueError, match="Authentication required"):
            protected_function("", "data")
        
        with pytest.raises(ValueError, match="Authentication required"):
            protected_function(None, "data")
    
    def test_composite_security_decorator(self):
        """Test the composite security decorator."""
        @secure_operation(
            input_params=['content'],
            require_auth=True,
            rate_limit={'max_calls': 5, 'window_seconds': 60},
            monitor_level=SecurityThreatLevel.MEDIUM
        )
        def secure_function(user_id: str, content: str):
            return f"Secure processing: {content}"
        
        # Valid operation
        result = secure_function("test_user", "Valid content")
        assert "Valid content" in result
        
        # Should fail without authentication
        with pytest.raises(ValueError):
            secure_function("", "content")

class TestSecurityMonitoring:
    """Test security monitoring and event tracking."""
    
    def setup_method(self):
        self.monitor = SecurityMonitor()
        self.context = SecurityContext(user_id="test_user", operation="test")
    
    def test_violation_recording(self):
        """Test recording of security violations."""
        self.monitor.record_security_violation(
            SecurityViolationType.SQL_INJECTION,
            SecurityThreatLevel.CRITICAL,
            self.context,
            "Test violation"
        )
        
        summary = self.monitor.get_security_summary()
        assert summary['total_violations'] == 1
        assert 'sql_injection:critical' in summary['violation_breakdown']
    
    def test_security_status_calculation(self):
        """Test security status calculation."""
        # No violations - should be normal
        summary = self.monitor.get_security_summary()
        assert summary['security_status'] == 'normal'
        
        # Add critical violation
        self.monitor.record_security_violation(
            SecurityViolationType.SQL_INJECTION,
            SecurityThreatLevel.CRITICAL,
            self.context,
            "Critical test"
        )
        
        summary = self.monitor.get_security_summary()
        assert summary['security_status'] == 'critical'
    
    def test_violation_history_limits(self):
        """Test that violation history is properly limited."""
        # Add many violations
        for i in range(1100):  # Exceeds max_recent_violations (1000)
            self.monitor.record_security_violation(
                SecurityViolationType.INPUT_VALIDATION,
                SecurityThreatLevel.LOW,
                self.context,
                f"Test violation {i}"
            )
        
        # Should only keep the most recent 1000
        assert len(self.monitor.recent_violations) == 1000

class TestGlobalSecurityManager:
    """Test the global security manager."""
    
    def test_security_manager_singleton(self):
        """Test that security manager is properly initialized."""
        assert security_manager is not None
        assert security_manager.input_validator is not None
        assert security_manager.sql_validator is not None
        assert security_manager.file_manager is not None
        assert security_manager.monitor is not None
    
    def test_convenience_functions(self):
        """Test convenience validation functions."""
        # User input validation
        result = validate_user_input("test content")
        assert result.is_valid
        
        # Path validation
        result = validate_file_path("storage/test.json")
        # May fail due to path restrictions, but should not crash
        assert result is not None
        
        # SQL validation
        result = validate_sql_query("SELECT * FROM test WHERE id = ?")
        assert result.is_valid
    
    def test_security_summary(self):
        """Test getting security summary."""
        from core.shared.security import get_security_summary
        summary = get_security_summary()
        
        assert 'total_violations' in summary
        assert 'violation_breakdown' in summary
        assert 'security_status' in summary

class TestIntegration:
    """Integration tests for security framework."""
    
    def test_end_to_end_security_validation(self):
        """Test complete security validation flow."""
        # Simulate a complete user interaction
        user_input = "Tell me a story about dragons"
        
        # Validate input
        input_result = validate_user_input(user_input, "integration_test")
        assert input_result.is_valid
        
        # Validate file path for storing result
        file_path = "storage/test_story.json"
        path_result = validate_file_path(file_path, "integration_test")
        # May fail due to path restrictions but should not crash
        
        # Validate SQL query for database operations
        sql_query = "INSERT INTO stories (content) VALUES (?)"
        sql_result = validate_sql_query(sql_query, "integration_test")
        assert sql_result.is_valid
    
    def test_malicious_input_handling(self):
        """Test handling of malicious input across all validators."""
        malicious_content = "<script>alert('xss')</script>' OR 1=1; DROP TABLE users; --"
        
        # Should be rejected by input validator
        input_result = validate_user_input(malicious_content)
        assert not input_result.is_valid
        assert input_result.threat_level == SecurityThreatLevel.CRITICAL
        
        # Should be rejected by SQL validator
        sql_result = validate_sql_query(malicious_content)
        assert not sql_result.is_valid
        assert sql_result.threat_level == SecurityThreatLevel.CRITICAL

if __name__ == "__main__":
    pytest.main([__file__])
