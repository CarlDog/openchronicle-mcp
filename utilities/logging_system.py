#!/usr/bin/env python3
"""
OpenChronicle Centralized Logging System
Provides unified logging for all utilities and core components.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from logging.handlers import RotatingFileHandler

class OpenChronicleLogger:
    """Centralized logging system for OpenChronicle."""
    
    def __init__(self, name: str = "openchronicle", log_dir: Optional[Path] = None):
        self.name = name
        self.root_dir = Path(__file__).parent.parent
        
        # Determine log directory based on context
        if log_dir:
            self.log_dir = log_dir
        else:
            # Use tests/logs for test context, logs for production
            if self._is_test_context():
                self.log_dir = self.root_dir / "tests" / "logs"
            else:
                self.log_dir = self.root_dir / "logs"
        
        self.log_dir.mkdir(exist_ok=True)
        
        # Create loggers
        self.logger = self._setup_logger()
        self.maintenance_logger = self._setup_maintenance_logger()
    
    def _is_test_context(self) -> bool:
        """Detect if we're running in a test context."""
        import sys
        # Check if pytest is running or if we're in a test directory context
        return ('pytest' in sys.modules or 
                'unittest' in sys.modules or
                any('test' in module for module in sys.modules))
        
    def _setup_logger(self) -> logging.Logger:
        """Set up main application logger."""
        logger = logging.getLogger(self.name)
        logger.setLevel(logging.INFO)
        
        # Avoid duplicate handlers
        if logger.hasHandlers():
            logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # File handler with rotation
        file_handler = RotatingFileHandler(
            self.log_dir / f"{self.name}.log",
            maxBytes=5*1024*1024,  # 5MB
            backupCount=5
        )
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        return logger
        
    def _setup_maintenance_logger(self) -> logging.Logger:
        """Set up maintenance-specific logger."""
        logger = logging.getLogger(f"{self.name}.maintenance")
        logger.setLevel(logging.INFO)
        
        # Avoid duplicate handlers
        if logger.hasHandlers():
            logger.handlers.clear()
        
        # Maintenance file handler
        maintenance_handler = RotatingFileHandler(
            self.log_dir / "maintenance.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=10
        )
        maintenance_handler.setLevel(logging.INFO)
        maintenance_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        maintenance_handler.setFormatter(maintenance_formatter)
        logger.addHandler(maintenance_handler)
        
        return logger
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self.logger.info(message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.logger.debug(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message."""
        self.logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self.logger.critical(message, **kwargs)
    
    def log_maintenance_action(self, action: str, details: Optional[Dict[str, Any]] = None, status: str = "success"):
        """Log maintenance action with structured data."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "status": status,
            "details": details or {}
        }
        
        # Log to maintenance logger
        self.maintenance_logger.info(json.dumps(log_entry))
        
        # Also log to main logger for visibility
        self.logger.info(f"Maintenance: {action} - {status}")
    
    def log_model_interaction(self, story_id: str, model: str, prompt_length: int, 
                             response_length: int, metadata: Optional[Dict[str, Any]] = None):
        """Log model interaction for analytics."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "story_id": story_id,
            "model": model,
            "prompt_length": prompt_length,
            "response_length": response_length,
            "metadata": metadata or {}
        }
        
        # Write to model interactions log
        model_log_path = self.log_dir / "model_interactions.jsonl"
        with open(model_log_path, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def log_error_with_context(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """Log error with additional context."""
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context or {}
        }
        
        # Log to error file
        error_log_path = self.log_dir / "errors.jsonl"
        with open(error_log_path, 'a') as f:
            f.write(json.dumps(error_entry) + '\n')
        
        # Also log to main logger
        self.logger.error(f"Error: {error_entry['error_type']}: {error_entry['error_message']}")
    
    def log_system_event(self, event_type: str, description: str, data: Optional[Dict[str, Any]] = None):
        """Log system events (startup, shutdown, configuration changes, etc.)."""
        event_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "description": description,
            "data": data or {}
        }
        
        # Write to system events log
        system_log_path = self.log_dir / "system_events.jsonl"
        with open(system_log_path, 'a') as f:
            f.write(json.dumps(event_entry) + '\n')
        
        # Also log to main logger
        self.logger.info(f"System Event: {event_type} - {description}")
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """Get statistics about log files."""
        stats = {
            "log_directory": str(self.log_dir),
            "files": {}
        }
        
        if self.log_dir.exists():
            for log_file in self.log_dir.glob("*.log*"):
                if log_file.is_file():
                    file_stat = log_file.stat()
                    stats["files"][log_file.name] = {
                        "size": file_stat.st_size,
                        "modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                        "lines": self._count_lines(log_file) if log_file.suffix in ['.log', '.jsonl'] else 0
                    }
        
        return stats
    
    def _count_lines(self, file_path: Path) -> int:
        """Count lines in a file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return sum(1 for line in f)
        except Exception:
            return 0
    
    def cleanup_old_logs(self, max_age_days: int = 30) -> int:
        """Clean up old log files."""
        cutoff_date = datetime.now().timestamp() - (max_age_days * 24 * 60 * 60)
        cleaned_count = 0
        
        if self.log_dir.exists():
            for log_file in self.log_dir.glob("*.log.*"):  # Rotated log files
                if log_file.is_file() and log_file.stat().st_mtime < cutoff_date:
                    log_file.unlink()
                    cleaned_count += 1
                    self.logger.info(f"Cleaned old log file: {log_file.name}")
        
        return cleaned_count


# Global logger instance
_logger_instance = None

def get_logger(name: str = "openchronicle") -> OpenChronicleLogger:
    """Get the global logger instance."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = OpenChronicleLogger(name)
    return _logger_instance

def setup_logging(log_dir: Optional[Path] = None) -> OpenChronicleLogger:
    """Setup logging system."""
    global _logger_instance
    _logger_instance = OpenChronicleLogger(log_dir=log_dir)
    return _logger_instance

# Convenience functions
def log_info(message: str, **kwargs):
    """Log info message."""
    get_logger().info(message, **kwargs)

def log_error(message: str, **kwargs):
    """Log error message."""
    get_logger().error(message, **kwargs)

def log_warning(message: str, **kwargs):
    """Log warning message."""
    get_logger().warning(message, **kwargs)

def log_maintenance_action(action: str, details: Optional[Dict[str, Any]] = None, status: str = "success"):
    """Log maintenance action."""
    get_logger().log_maintenance_action(action, details, status)

def log_model_interaction(story_id: str, model: str, prompt_length: int, 
                         response_length: int, metadata: Optional[Dict[str, Any]] = None):
    """Log model interaction."""
    get_logger().log_model_interaction(story_id, model, prompt_length, response_length, metadata)

def log_system_event(event_type: str, description: str, data: Optional[Dict[str, Any]] = None):
    """Log system event."""
    get_logger().log_system_event(event_type, description, data)

def log_error_with_context(error: Exception, context: Optional[Dict[str, Any]] = None):
    """Log error with context."""
    get_logger().log_error_with_context(error, context)


if __name__ == "__main__":
    # Test the logging system
    logger = get_logger()
    
    logger.info("Testing centralized logging system")
    logger.log_maintenance_action("test_action", {"test": "data"})
    logger.log_model_interaction("test-story", "test-model", 100, 200)
    logger.log_system_event("startup", "System started successfully")
    
    # Show statistics
    stats = logger.get_log_statistics()
    print("Log Statistics:")
    print(json.dumps(stats, indent=2))
