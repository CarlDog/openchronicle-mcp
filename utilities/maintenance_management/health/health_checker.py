"""
System Health Checking Implementation
Comprehensive health checks following Single Responsibility Principle.
"""

import sys
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

from ..interfaces.maintenance_interfaces import (
    IHealthChecker, HealthCheckResult, HealthCheckType, MaintenanceStatus
)

# Graceful logging import
try:
    from utilities.logging_system import get_logger, log_system_event, log_error_with_context
except ImportError:
    import logging
    
    def get_logger():
        return logging.getLogger(__name__)
    
    def log_system_event(event: str, details: str):
        logging.info(f"SYSTEM_EVENT: {event} - {details}")
    
    def log_error_with_context(error: Exception, context: Dict[str, Any]):
        logging.error(f"ERROR: {error} - Context: {context}")


class SystemHealthChecker(IHealthChecker):
    """Comprehensive system health checker implementation."""
    
    def __init__(self, base_path: Path, logger=None):
        self.base_path = Path(base_path).resolve()
        self.logger = logger or get_logger()
        
        # Configuration for health checks
        self.required_config_files = [
            "config/model_registry.json",
            "config/system_config.json",
            "main.py",
            "requirements.txt"
        ]
        
        self.required_directories = [
            "storage",
            "config",
            "core",
            "utilities"
        ]
        
        self.required_python_modules = [
            "sqlite3",
            "json",
            "pathlib",
            "datetime",
            "asyncio",
            "typing"
        ]
    
    async def check_health(self, check_types: Optional[List[HealthCheckType]] = None) -> Dict[HealthCheckType, HealthCheckResult]:
        """Perform comprehensive health checks."""
        if check_types is None:
            check_types = list(HealthCheckType)
        
        results = {}
        
        self.logger.info(f"Starting health checks: {[ct.value for ct in check_types]}")
        log_system_event("health_check_start", f"Checking {len(check_types)} health categories")
        
        for check_type in check_types:
            try:
                if check_type == HealthCheckType.FILE_SYSTEM:
                    results[check_type] = self.check_file_system(self.base_path)
                elif check_type == HealthCheckType.CONFIGURATION:
                    results[check_type] = self.check_configuration_files()
                elif check_type == HealthCheckType.STORAGE:
                    results[check_type] = self.check_storage_structure()
                elif check_type == HealthCheckType.DATABASE:
                    results[check_type] = self.check_database_accessibility()
                elif check_type == HealthCheckType.PYTHON_ENVIRONMENT:
                    results[check_type] = self.check_python_environment()
                elif check_type == HealthCheckType.DISK_SPACE:
                    results[check_type] = self.check_disk_space(self.base_path)
                elif check_type == HealthCheckType.MODULES:
                    results[check_type] = self.check_required_modules()
                else:
                    results[check_type] = HealthCheckResult(
                        check_type=check_type,
                        status=MaintenanceStatus.SKIPPED,
                        details={"reason": "Unknown check type"}
                    )
                
            except Exception as e:
                self.logger.error(f"Health check failed for {check_type.value}: {e}")
                log_error_with_context(e, {"check_type": check_type.value, "base_path": str(self.base_path)})
                
                results[check_type] = HealthCheckResult(
                    check_type=check_type,
                    status=MaintenanceStatus.FAILED,
                    details={"error": str(e)},
                    issues=[f"Health check failed: {e}"]
                )
        
        # Log summary
        success_count = sum(1 for r in results.values() if r.status == MaintenanceStatus.SUCCESS)
        self.logger.info(f"Health checks completed: {success_count}/{len(results)} successful")
        
        return results
    
    def check_file_system(self, base_path: Path) -> HealthCheckResult:
        """Check file system integrity and required files."""
        details = {
            "base_path": str(base_path),
            "exists": base_path.exists(),
            "is_directory": base_path.is_dir() if base_path.exists() else False,
            "required_files": {},
            "required_directories": {}
        }
        
        issues = []
        
        if not base_path.exists():
            issues.append(f"Base path does not exist: {base_path}")
            return HealthCheckResult(
                check_type=HealthCheckType.FILE_SYSTEM,
                status=MaintenanceStatus.FAILED,
                details=details,
                issues=issues
            )
        
        # Check required files
        for file_path in self.required_config_files:
            full_path = base_path / file_path
            file_exists = full_path.exists()
            file_info = {
                "exists": file_exists,
                "path": str(full_path)
            }
            
            if file_exists:
                try:
                    stat = full_path.stat()
                    file_info.update({
                        "size": stat.st_size,
                        "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                except Exception as e:
                    file_info["stat_error"] = str(e)
            else:
                issues.append(f"Required file missing: {file_path}")
            
            details["required_files"][file_path] = file_info
        
        # Check required directories
        for dir_path in self.required_directories:
            full_path = base_path / dir_path
            dir_exists = full_path.exists()
            dir_info = {
                "exists": dir_exists,
                "path": str(full_path)
            }
            
            if dir_exists and full_path.is_dir():
                try:
                    # Count items in directory
                    items = list(full_path.iterdir())
                    dir_info["item_count"] = len(items)
                except Exception as e:
                    dir_info["access_error"] = str(e)
            elif dir_exists:
                issues.append(f"Required directory is not a directory: {dir_path}")
            else:
                issues.append(f"Required directory missing: {dir_path}")
            
            details["required_directories"][dir_path] = dir_info
        
        status = MaintenanceStatus.SUCCESS if not issues else MaintenanceStatus.WARNING
        
        return HealthCheckResult(
            check_type=HealthCheckType.FILE_SYSTEM,
            status=status,
            details=details,
            issues=issues
        )
    
    def check_disk_space(self, path: Path, warning_threshold: float = 20.0) -> HealthCheckResult:
        """Check available disk space."""
        details = {"path": str(path)}
        issues = []
        
        try:
            total, used, free = shutil.disk_usage(path)
            free_percent = (free / total * 100) if total > 0 else 0
            
            details.update({
                "total_bytes": total,
                "used_bytes": used,
                "free_bytes": free,
                "free_percent": round(free_percent, 2),
                "warning_threshold": warning_threshold
            })
            
            # Determine status based on free space
            if free_percent < 5:
                status = MaintenanceStatus.FAILED
                issues.append(f"Critical: Very low disk space ({free_percent:.1f}% free)")
            elif free_percent < warning_threshold:
                status = MaintenanceStatus.WARNING
                issues.append(f"Warning: Low disk space ({free_percent:.1f}% free)")
            else:
                status = MaintenanceStatus.SUCCESS
            
            # Add human-readable sizes
            details["total_human"] = self._format_bytes(total)
            details["used_human"] = self._format_bytes(used)
            details["free_human"] = self._format_bytes(free)
            
        except Exception as e:
            status = MaintenanceStatus.FAILED
            details["error"] = str(e)
            issues.append(f"Failed to check disk space: {e}")
        
        return HealthCheckResult(
            check_type=HealthCheckType.DISK_SPACE,
            status=status,
            details=details,
            issues=issues
        )
    
    def check_python_environment(self) -> HealthCheckResult:
        """Check Python environment and version."""
        details = {}
        issues = []
        
        try:
            # Get Python version
            details["python_version"] = sys.version
            details["python_executable"] = sys.executable
            details["python_version_info"] = {
                "major": sys.version_info.major,
                "minor": sys.version_info.minor,
                "micro": sys.version_info.micro
            }
            
            # Check Python version requirements (3.8+)
            if sys.version_info < (3, 8):
                issues.append(f"Python version too old: {sys.version_info.major}.{sys.version_info.minor} (requires 3.8+)")
            
            # Check if we can execute Python commands
            try:
                result = subprocess.run(
                    [sys.executable, "--version"], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                details["subprocess_check"] = {
                    "return_code": result.returncode,
                    "stdout": result.stdout.strip(),
                    "stderr": result.stderr.strip()
                }
                
                if result.returncode != 0:
                    issues.append("Python subprocess execution failed")
                    
            except subprocess.TimeoutExpired:
                issues.append("Python subprocess execution timed out")
            except Exception as e:
                issues.append(f"Python subprocess check failed: {e}")
            
            # Check Python path and sys.path
            details["sys_path"] = sys.path[:5]  # First 5 entries
            details["working_directory"] = str(Path.cwd())
            
        except Exception as e:
            issues.append(f"Python environment check failed: {e}")
            details["error"] = str(e)
        
        status = MaintenanceStatus.SUCCESS if not issues else MaintenanceStatus.WARNING
        
        return HealthCheckResult(
            check_type=HealthCheckType.PYTHON_ENVIRONMENT,
            status=status,
            details=details,
            issues=issues
        )
    
    def check_configuration_files(self) -> HealthCheckResult:
        """Check configuration files integrity."""
        details = {"config_files": {}}
        issues = []
        
        config_files_to_check = [
            "config/model_registry.json",
            "config/system_config.json"
        ]
        
        for config_file in config_files_to_check:
            file_path = self.base_path / config_file
            file_details = {
                "path": str(file_path),
                "exists": file_path.exists()
            }
            
            if file_path.exists():
                try:
                    # Check if it's valid JSON
                    with open(file_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                    
                    file_details["valid_json"] = True
                    file_details["size"] = file_path.stat().st_size
                    
                    # Basic structure checks for model registry
                    if config_file == "config/model_registry.json":
                        if isinstance(config_data, dict):
                            file_details["has_models"] = "models" in config_data
                            file_details["has_default_model"] = "default_model" in config_data
                            
                            if "models" not in config_data:
                                issues.append(f"{config_file}: Missing 'models' field")
                        else:
                            issues.append(f"{config_file}: Root should be a JSON object")
                    
                    # Basic structure checks for system config  
                    elif config_file == "config/system_config.json":
                        if isinstance(config_data, dict):
                            file_details["keys"] = list(config_data.keys())[:10]  # First 10 keys
                        else:
                            issues.append(f"{config_file}: Root should be a JSON object")
                    
                except json.JSONDecodeError as e:
                    file_details["valid_json"] = False
                    file_details["json_error"] = str(e)
                    issues.append(f"{config_file}: Invalid JSON - {e}")
                except Exception as e:
                    file_details["read_error"] = str(e)
                    issues.append(f"{config_file}: Read error - {e}")
            else:
                issues.append(f"Configuration file missing: {config_file}")
            
            details["config_files"][config_file] = file_details
        
        status = MaintenanceStatus.SUCCESS if not issues else MaintenanceStatus.WARNING
        
        return HealthCheckResult(
            check_type=HealthCheckType.CONFIGURATION,
            status=status,
            details=details,
            issues=issues
        )
    
    def check_storage_structure(self) -> HealthCheckResult:
        """Check storage directory structure."""
        details = {}
        issues = []
        
        storage_path = self.base_path / "storage"
        details["storage_path"] = str(storage_path)
        details["exists"] = storage_path.exists()
        
        if not storage_path.exists():
            issues.append("Storage directory does not exist")
            status = MaintenanceStatus.WARNING
        else:
            try:
                # Count story directories
                story_dirs = [d for d in storage_path.iterdir() if d.is_dir()]
                details["story_count"] = len(story_dirs)
                details["story_names"] = [d.name for d in story_dirs[:10]]  # First 10
                
                # Check for common files
                common_files = ["README.md", ".gitkeep"]
                details["common_files"] = {}
                for file_name in common_files:
                    file_path = storage_path / file_name
                    details["common_files"][file_name] = file_path.exists()
                
                # Basic space analysis
                total_size = 0
                file_count = 0
                
                for item in storage_path.rglob("*"):
                    if item.is_file():
                        try:
                            total_size += item.stat().st_size
                            file_count += 1
                        except (OSError, PermissionError):
                            pass  # Skip files we can't access
                
                details["total_files"] = file_count
                details["total_size_bytes"] = total_size
                details["total_size_human"] = self._format_bytes(total_size)
                
                status = MaintenanceStatus.SUCCESS
                
            except Exception as e:
                issues.append(f"Storage analysis failed: {e}")
                details["error"] = str(e)
                status = MaintenanceStatus.FAILED
        
        return HealthCheckResult(
            check_type=HealthCheckType.STORAGE,
            status=status,
            details=details,
            issues=issues
        )
    
    def check_database_accessibility(self) -> HealthCheckResult:
        """Check database files and accessibility."""
        details = {"databases": []}
        issues = []
        
        # Look for SQLite database files
        try:
            db_patterns = ["*.db", "*.sqlite", "*.sqlite3"]
            db_files = []
            
            for pattern in db_patterns:
                db_files.extend(self.base_path.rglob(pattern))
            
            details["database_count"] = len(db_files)
            
            for db_file in db_files[:20]:  # Check first 20 databases
                db_info = {
                    "path": str(db_file.relative_to(self.base_path)),
                    "size": db_file.stat().st_size,
                    "size_human": self._format_bytes(db_file.stat().st_size)
                }
                
                # Try to connect to SQLite database
                try:
                    import sqlite3
                    with sqlite3.connect(db_file) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                        tables = cursor.fetchall()
                        db_info["accessible"] = True
                        db_info["table_count"] = len(tables)
                        db_info["tables"] = [table[0] for table in tables[:10]]  # First 10 tables
                        
                except Exception as e:
                    db_info["accessible"] = False
                    db_info["error"] = str(e)
                    issues.append(f"Database not accessible: {db_file.name} - {e}")
                
                details["databases"].append(db_info)
            
            if not db_files:
                issues.append("No database files found")
            
        except Exception as e:
            issues.append(f"Database check failed: {e}")
            details["error"] = str(e)
        
        status = MaintenanceStatus.SUCCESS if not issues else MaintenanceStatus.WARNING
        
        return HealthCheckResult(
            check_type=HealthCheckType.DATABASE,
            status=status,
            details=details,
            issues=issues
        )
    
    def check_required_modules(self) -> HealthCheckResult:
        """Check availability of required Python modules."""
        details = {"modules": {}}
        issues = []
        
        for module_name in self.required_python_modules:
            module_info = {"name": module_name}
            
            try:
                module = __import__(module_name)
                module_info["available"] = True
                
                # Get version if available
                if hasattr(module, "__version__"):
                    module_info["version"] = module.__version__
                elif hasattr(module, "version"):
                    module_info["version"] = str(module.version)
                
                # Get file location
                if hasattr(module, "__file__") and module.__file__:
                    module_info["file"] = module.__file__
                
            except ImportError as e:
                module_info["available"] = False
                module_info["error"] = str(e)
                issues.append(f"Required module not available: {module_name}")
            except Exception as e:
                module_info["available"] = False
                module_info["error"] = str(e)
                issues.append(f"Module check failed: {module_name} - {e}")
            
            details["modules"][module_name] = module_info
        
        # Check some optional but useful modules
        optional_modules = ["requests", "aiohttp", "numpy", "pandas"]
        details["optional_modules"] = {}
        
        for module_name in optional_modules:
            try:
                module = __import__(module_name)
                details["optional_modules"][module_name] = {
                    "available": True,
                    "version": getattr(module, "__version__", "unknown")
                }
            except ImportError:
                details["optional_modules"][module_name] = {"available": False}
        
        status = MaintenanceStatus.SUCCESS if not issues else MaintenanceStatus.FAILED
        
        return HealthCheckResult(
            check_type=HealthCheckType.MODULES,
            status=status,
            details=details,
            issues=issues
        )
    
    def _format_bytes(self, bytes_value: int) -> str:
        """Format bytes in human readable format."""
        if bytes_value == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        i = 0
        size = float(bytes_value)
        
        while size >= 1024 and i < len(units) - 1:
            size /= 1024
            i += 1
        
        return f"{size:.1f} {units[i]}"


class QuickHealthChecker(IHealthChecker):
    """Quick health checker for basic checks."""
    
    def __init__(self, base_path: Path, logger=None):
        self.base_path = Path(base_path).resolve()
        self.logger = logger or get_logger()
    
    async def check_health(self, check_types: Optional[List[HealthCheckType]] = None) -> Dict[HealthCheckType, HealthCheckResult]:
        """Perform quick health checks."""
        results = {}
        
        # Quick file system check
        results[HealthCheckType.FILE_SYSTEM] = self.check_file_system(self.base_path)
        
        # Quick disk space check
        results[HealthCheckType.DISK_SPACE] = self.check_disk_space(self.base_path)
        
        # Quick Python environment check
        results[HealthCheckType.PYTHON_ENVIRONMENT] = self.check_python_environment()
        
        return results
    
    def check_file_system(self, base_path: Path) -> HealthCheckResult:
        """Quick file system check."""
        exists = base_path.exists()
        is_dir = base_path.is_dir() if exists else False
        
        status = MaintenanceStatus.SUCCESS if exists and is_dir else MaintenanceStatus.FAILED
        issues = [] if exists and is_dir else ["Base path not accessible"]
        
        return HealthCheckResult(
            check_type=HealthCheckType.FILE_SYSTEM,
            status=status,
            details={"exists": exists, "is_directory": is_dir},
            issues=issues
        )
    
    def check_disk_space(self, path: Path, warning_threshold: float = 20.0) -> HealthCheckResult:
        """Quick disk space check."""
        try:
            total, used, free = shutil.disk_usage(path)
            free_percent = (free / total * 100) if total > 0 else 0
            
            if free_percent < 10:
                status = MaintenanceStatus.FAILED
                issues = [f"Very low disk space: {free_percent:.1f}%"]
            elif free_percent < warning_threshold:
                status = MaintenanceStatus.WARNING
                issues = [f"Low disk space: {free_percent:.1f}%"]
            else:
                status = MaintenanceStatus.SUCCESS
                issues = []
            
            return HealthCheckResult(
                check_type=HealthCheckType.DISK_SPACE,
                status=status,
                details={"free_percent": round(free_percent, 1)},
                issues=issues
            )
            
        except Exception as e:
            return HealthCheckResult(
                check_type=HealthCheckType.DISK_SPACE,
                status=MaintenanceStatus.FAILED,
                details={"error": str(e)},
                issues=[f"Disk space check failed: {e}"]
            )
    
    def check_python_environment(self) -> HealthCheckResult:
        """Quick Python environment check."""
        version_ok = sys.version_info >= (3, 8)
        
        status = MaintenanceStatus.SUCCESS if version_ok else MaintenanceStatus.FAILED
        issues = [] if version_ok else [f"Python version too old: {sys.version_info.major}.{sys.version_info.minor}"]
        
        return HealthCheckResult(
            check_type=HealthCheckType.PYTHON_ENVIRONMENT,
            status=status,
            details={
                "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "version_ok": version_ok
            },
            issues=issues
        )
