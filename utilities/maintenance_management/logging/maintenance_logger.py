"""
Maintenance Logging Implementation
Specialized logging for maintenance operations following Single Responsibility Principle.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from ..interfaces.maintenance_interfaces import (
    IMaintenanceLogger, MaintenanceResult, MaintenanceTaskType
)

# Graceful logging import
try:
    from utilities.logging_system import get_logger, log_maintenance_action, log_system_event, log_error_with_context
except ImportError:
    import logging
    
    def get_logger():
        return logging.getLogger(__name__)
    
    def log_maintenance_action(action: str, details: Dict[str, Any], status: str):
        logging.info(f"MAINTENANCE_ACTION: {action} - {status} - {details}")
    
    def log_system_event(event: str, details: str):
        logging.info(f"SYSTEM_EVENT: {event} - {details}")
    
    def log_error_with_context(error: Exception, context: Dict[str, Any]):
        logging.error(f"ERROR: {error} - Context: {context}")


class MaintenanceLogger(IMaintenanceLogger):
    """Comprehensive maintenance logger implementation."""
    
    def __init__(self, log_file_path: Optional[Path] = None, logger=None):
        self.logger = logger or get_logger()
        self.maintenance_log_entries = []
        
        # Set up dedicated maintenance log file
        if log_file_path is None:
            log_file_path = Path("logs/maintenance.log")
        
        self.log_file_path = Path(log_file_path)
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Rotation settings
        self.max_log_file_size = 50 * 1024 * 1024  # 50MB
        self.max_log_files = 10
        
        self._initialize_log_file()
    
    def log_maintenance_start(self, task_type: MaintenanceTaskType, parameters: Dict[str, Any]) -> None:
        """Log start of maintenance task."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "maintenance_start",
            "task_type": task_type.value,
            "parameters": parameters,
            "session_id": self._generate_session_id()
        }
        
        self.maintenance_log_entries.append(entry)
        self._write_log_entry(entry)
        
        # Use centralized logging
        self.logger.info(f"Maintenance task started: {task_type.value}")
        log_system_event("maintenance_start", f"Task: {task_type.value}, Params: {parameters}")
    
    def log_maintenance_result(self, result: MaintenanceResult) -> None:
        """Log maintenance task result."""
        entry = {
            "timestamp": result.timestamp.isoformat(),
            "event_type": "maintenance_result",
            "task_type": result.request.task_type.value,
            "status": result.status.value,
            "message": result.message,
            "details": result.details,
            "errors": result.errors,
            "warnings": result.warnings,
            "execution_time_ms": result.execution_time_ms,
            "dry_run": result.request.dry_run
        }
        
        self.maintenance_log_entries.append(entry)
        self._write_log_entry(entry)
        
        # Use centralized logging
        status_str = "success" if result.status.value == "success" else "error"
        self.logger.info(f"Maintenance task completed: {result.request.task_type.value} - {result.status.value}")
        log_maintenance_action(
            result.request.task_type.value,
            {
                "status": result.status.value,
                "execution_time_ms": result.execution_time_ms,
                "error_count": len(result.errors),
                "warning_count": len(result.warnings)
            },
            status_str
        )
        
        # Log errors if any
        for error in result.errors:
            self.logger.error(f"Maintenance error in {result.request.task_type.value}: {error}")
        
        # Log warnings if any
        for warning in result.warnings:
            self.logger.warning(f"Maintenance warning in {result.request.task_type.value}: {warning}")
    
    def log_maintenance_error(self, task_type: MaintenanceTaskType, error: Exception, context: Dict[str, Any]) -> None:
        """Log maintenance error with context."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "maintenance_error",
            "task_type": task_type.value,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "stack_trace": self._get_stack_trace(error)
        }
        
        self.maintenance_log_entries.append(entry)
        self._write_log_entry(entry)
        
        # Use centralized logging
        self.logger.error(f"Maintenance error in {task_type.value}: {error}")
        log_error_with_context(error, {"task_type": task_type.value, **context})
    
    def get_maintenance_log(self, task_type: Optional[MaintenanceTaskType] = None, 
                           since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get maintenance log entries with optional filtering."""
        filtered_entries = self.maintenance_log_entries.copy()
        
        # Filter by task type
        if task_type is not None:
            filtered_entries = [
                entry for entry in filtered_entries 
                if entry.get("task_type") == task_type.value
            ]
        
        # Filter by time
        if since is not None:
            since_iso = since.isoformat()
            filtered_entries = [
                entry for entry in filtered_entries 
                if entry.get("timestamp", "") >= since_iso
            ]
        
        return filtered_entries
    
    def get_maintenance_statistics(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Get maintenance operation statistics."""
        entries = self.get_maintenance_log(since=since)
        
        stats = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "warning_operations": 0,
            "task_type_counts": {},
            "average_execution_time_ms": 0,
            "total_errors": 0,
            "total_warnings": 0,
            "time_period": {
                "start": since.isoformat() if since else None,
                "end": datetime.now().isoformat()
            }
        }
        
        execution_times = []
        
        for entry in entries:
            if entry.get("event_type") == "maintenance_result":
                stats["total_operations"] += 1
                
                # Count by status
                status = entry.get("status", "unknown")
                if status == "success":
                    stats["successful_operations"] += 1
                elif status == "failed":
                    stats["failed_operations"] += 1
                elif status == "warning":
                    stats["warning_operations"] += 1
                
                # Count by task type
                task_type = entry.get("task_type", "unknown")
                stats["task_type_counts"][task_type] = stats["task_type_counts"].get(task_type, 0) + 1
                
                # Track execution time
                exec_time = entry.get("execution_time_ms")
                if exec_time is not None:
                    execution_times.append(exec_time)
                
                # Count errors and warnings
                stats["total_errors"] += len(entry.get("errors", []))
                stats["total_warnings"] += len(entry.get("warnings", []))
        
        # Calculate average execution time
        if execution_times:
            stats["average_execution_time_ms"] = sum(execution_times) / len(execution_times)
        
        return stats
    
    def rotate_log_files(self) -> None:
        """Rotate maintenance log files if needed."""
        if not self.log_file_path.exists():
            return
        
        # Check if rotation is needed
        file_size = self.log_file_path.stat().st_size
        if file_size < self.max_log_file_size:
            return
        
        self.logger.info(f"Rotating maintenance log file (size: {file_size} bytes)")
        
        # Create rotated filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rotated_name = f"{self.log_file_path.stem}_{timestamp}.log"
        rotated_path = self.log_file_path.parent / rotated_name
        
        # Move current log to rotated name
        self.log_file_path.rename(rotated_path)
        
        # Clean up old log files
        self._cleanup_old_log_files()
        
        # Reinitialize log file
        self._initialize_log_file()
    
    def export_maintenance_log(self, output_path: Path, format_type: str = "json") -> Path:
        """Export maintenance log to file."""
        output_path = Path(output_path)
        
        if format_type == "json":
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "export_timestamp": datetime.now().isoformat(),
                    "total_entries": len(self.maintenance_log_entries),
                    "entries": self.maintenance_log_entries
                }, f, indent=2, default=str)
        
        elif format_type == "csv":
            import csv
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                if self.maintenance_log_entries:
                    writer = csv.DictWriter(f, fieldnames=self.maintenance_log_entries[0].keys())
                    writer.writeheader()
                    for entry in self.maintenance_log_entries:
                        # Convert complex fields to strings for CSV
                        csv_entry = {k: json.dumps(v) if isinstance(v, (dict, list)) else v 
                                   for k, v in entry.items()}
                        writer.writerow(csv_entry)
        
        elif format_type == "text":
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"Maintenance Log Export - {datetime.now().isoformat()}\n")
                f.write("=" * 60 + "\n\n")
                
                for entry in self.maintenance_log_entries:
                    f.write(f"Timestamp: {entry.get('timestamp', 'Unknown')}\n")
                    f.write(f"Event Type: {entry.get('event_type', 'Unknown')}\n")
                    f.write(f"Task Type: {entry.get('task_type', 'Unknown')}\n")
                    
                    if entry.get("event_type") == "maintenance_result":
                        f.write(f"Status: {entry.get('status', 'Unknown')}\n")
                        f.write(f"Message: {entry.get('message', '')}\n")
                        if entry.get('execution_time_ms'):
                            f.write(f"Execution Time: {entry['execution_time_ms']}ms\n")
                    
                    f.write("-" * 40 + "\n")
        
        else:
            raise ValueError(f"Unsupported export format: {format_type}")
        
        self.logger.info(f"Maintenance log exported to: {output_path}")
        return output_path
    
    def _initialize_log_file(self) -> None:
        """Initialize maintenance log file."""
        if not self.log_file_path.exists():
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                f.write(f"# OpenChronicle Maintenance Log - Created: {datetime.now().isoformat()}\n")
        
        # Log initialization
        init_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "logger_initialized",
            "log_file": str(self.log_file_path)
        }
        self._write_log_entry(init_entry)
    
    def _write_log_entry(self, entry: Dict[str, Any]) -> None:
        """Write log entry to file."""
        try:
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, default=str) + "\n")
            
            # Check if rotation is needed after writing
            if self.log_file_path.stat().st_size > self.max_log_file_size:
                self.rotate_log_files()
                
        except Exception as e:
            self.logger.error(f"Failed to write maintenance log entry: {e}")
    
    def _cleanup_old_log_files(self) -> None:
        """Clean up old rotated log files."""
        try:
            log_pattern = f"{self.log_file_path.stem}_*.log"
            log_files = list(self.log_file_path.parent.glob(log_pattern))
            
            # Sort by modification time (newest first)
            log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Remove excess files
            for old_file in log_files[self.max_log_files:]:
                try:
                    old_file.unlink()
                    self.logger.info(f"Removed old maintenance log file: {old_file}")
                except Exception as e:
                    self.logger.error(f"Failed to remove old log file {old_file}: {e}")
        
        except Exception as e:
            self.logger.error(f"Failed to cleanup old log files: {e}")
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID for maintenance run."""
        return f"maint_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(self) % 10000:04d}"
    
    def _get_stack_trace(self, error: Exception) -> Optional[str]:
        """Get stack trace from exception."""
        try:
            import traceback
            return traceback.format_exc()
        except Exception:
            return None


class InMemoryMaintenanceLogger(IMaintenanceLogger):
    """In-memory maintenance logger for testing and temporary use."""
    
    def __init__(self, logger=None):
        self.logger = logger or get_logger()
        self.log_entries = []
        self.session_id = f"mem_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def log_maintenance_start(self, task_type: MaintenanceTaskType, parameters: Dict[str, Any]) -> None:
        """Log start of maintenance task."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "maintenance_start",
            "task_type": task_type.value,
            "parameters": parameters,
            "session_id": self.session_id
        }
        self.log_entries.append(entry)
        self.logger.info(f"Maintenance started: {task_type.value}")
    
    def log_maintenance_result(self, result: MaintenanceResult) -> None:
        """Log maintenance task result."""
        entry = {
            "timestamp": result.timestamp.isoformat(),
            "event_type": "maintenance_result",
            "task_type": result.request.task_type.value,
            "status": result.status.value,
            "message": result.message,
            "execution_time_ms": result.execution_time_ms
        }
        self.log_entries.append(entry)
        self.logger.info(f"Maintenance completed: {result.request.task_type.value} - {result.status.value}")
    
    def log_maintenance_error(self, task_type: MaintenanceTaskType, error: Exception, context: Dict[str, Any]) -> None:
        """Log maintenance error with context."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "maintenance_error",
            "task_type": task_type.value,
            "error_message": str(error),
            "context": context
        }
        self.log_entries.append(entry)
        self.logger.error(f"Maintenance error: {task_type.value} - {error}")
    
    def get_maintenance_log(self, task_type: Optional[MaintenanceTaskType] = None, 
                           since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get maintenance log entries."""
        filtered_entries = self.log_entries.copy()
        
        if task_type is not None:
            filtered_entries = [
                entry for entry in filtered_entries 
                if entry.get("task_type") == task_type.value
            ]
        
        if since is not None:
            since_iso = since.isoformat()
            filtered_entries = [
                entry for entry in filtered_entries 
                if entry.get("timestamp", "") >= since_iso
            ]
        
        return filtered_entries
    
    def clear_log(self) -> None:
        """Clear all log entries (testing convenience method)."""
        self.log_entries.clear()
    
    def get_log_count(self) -> int:
        """Get total number of log entries (testing convenience method)."""
        return len(self.log_entries)


class NoOpMaintenanceLogger(IMaintenanceLogger):
    """No-operation logger that does nothing - for performance-critical scenarios."""
    
    def log_maintenance_start(self, task_type: MaintenanceTaskType, parameters: Dict[str, Any]) -> None:
        pass
    
    def log_maintenance_result(self, result: MaintenanceResult) -> None:
        pass
    
    def log_maintenance_error(self, task_type: MaintenanceTaskType, error: Exception, context: Dict[str, Any]) -> None:
        pass
    
    def get_maintenance_log(self, task_type: Optional[MaintenanceTaskType] = None, 
                           since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        return []
