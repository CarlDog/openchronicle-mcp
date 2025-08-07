"""
Maintenance Management Interfaces
Defines focused interfaces following Interface Segregation Principle.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from enum import Enum


class MaintenanceTaskType(Enum):
    """Types of maintenance tasks."""
    HEALTH_CHECK = "health_check"
    CONFIGURATION_VALIDATION = "configuration_validation"
    STORAGE_CLEANUP = "storage_cleanup"
    DATABASE_OPTIMIZATION = "database_optimization"
    REPORT_GENERATION = "report_generation"
    FULL_MAINTENANCE = "full_maintenance"


class MaintenanceStatus(Enum):
    """Status of maintenance operations."""
    SUCCESS = "success"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"
    IN_PROGRESS = "in_progress"


class HealthCheckType(Enum):
    """Types of system health checks."""
    FILE_SYSTEM = "file_system"
    CONFIGURATION = "configuration"
    STORAGE = "storage"
    DATABASE = "database"
    PYTHON_ENVIRONMENT = "python_environment"
    DISK_SPACE = "disk_space"
    MODULES = "modules"


@dataclass
class MaintenanceRequest:
    """Request for maintenance operation."""
    task_type: MaintenanceTaskType
    dry_run: bool = False
    target_path: Optional[Path] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MaintenanceResult:
    """Result of maintenance operation."""
    request: MaintenanceRequest
    status: MaintenanceStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    execution_time_ms: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "task_type": self.request.task_type.value,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "errors": self.errors,
            "warnings": self.warnings,
            "timestamp": self.timestamp.isoformat(),
            "execution_time_ms": self.execution_time_ms,
            "dry_run": self.request.dry_run
        }


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""
    check_type: HealthCheckType
    status: MaintenanceStatus
    details: Dict[str, Any] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "check_type": self.check_type.value,
            "status": self.status.value,
            "details": self.details,
            "issues": self.issues,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ConfigurationValidationResult:
    """Result of configuration validation."""
    valid: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validated_files: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "issues": self.issues,
            "warnings": self.warnings,
            "validated_files": self.validated_files,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class MaintenanceReport:
    """Comprehensive maintenance report."""
    timestamp: datetime
    dry_run: bool
    sections: Dict[str, Any] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "dry_run": self.dry_run,
            "sections": self.sections,
            "summary": self.summary,
            "duration_ms": self.duration_ms
        }


class IHealthChecker(ABC):
    """Interface for system health checking operations."""
    
    @abstractmethod
    async def check_health(self, check_types: Optional[List[HealthCheckType]] = None) -> Dict[HealthCheckType, HealthCheckResult]:
        """Perform health checks and return results."""
        pass
    
    @abstractmethod
    def check_file_system(self, base_path: Path) -> HealthCheckResult:
        """Check file system integrity and required files."""
        pass
    
    @abstractmethod
    def check_disk_space(self, path: Path, warning_threshold: float = 20.0) -> HealthCheckResult:
        """Check available disk space."""
        pass
    
    @abstractmethod
    def check_python_environment(self) -> HealthCheckResult:
        """Check Python environment and modules."""
        pass


class IConfigurationValidator(ABC):
    """Interface for configuration validation operations."""
    
    @abstractmethod
    async def validate_configuration(self, config_paths: Optional[List[Path]] = None) -> ConfigurationValidationResult:
        """Validate configuration files."""
        pass
    
    @abstractmethod
    def validate_model_registry(self, registry_path: Path) -> ConfigurationValidationResult:
        """Validate model registry configuration."""
        pass
    
    @abstractmethod
    def validate_system_config(self, config_path: Path) -> ConfigurationValidationResult:
        """Validate system configuration."""
        pass
    
    @abstractmethod
    def validate_json_file(self, file_path: Path, required_fields: Optional[List[str]] = None) -> ConfigurationValidationResult:
        """Validate JSON configuration file."""
        pass


class IMaintenanceLogger(ABC):
    """Interface for maintenance logging operations."""
    
    @abstractmethod
    def log_maintenance_start(self, task_type: MaintenanceTaskType, parameters: Dict[str, Any]) -> None:
        """Log start of maintenance task."""
        pass
    
    @abstractmethod
    def log_maintenance_result(self, result: MaintenanceResult) -> None:
        """Log maintenance task result."""
        pass
    
    @abstractmethod
    def log_maintenance_error(self, task_type: MaintenanceTaskType, error: Exception, context: Dict[str, Any]) -> None:
        """Log maintenance error with context."""
        pass
    
    @abstractmethod
    def get_maintenance_log(self, task_type: Optional[MaintenanceTaskType] = None, 
                           since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get maintenance log entries."""
        pass


class IMaintenanceReporter(ABC):
    """Interface for maintenance reporting operations."""
    
    @abstractmethod
    async def generate_report(self, include_sections: Optional[List[str]] = None) -> MaintenanceReport:
        """Generate comprehensive maintenance report."""
        pass
    
    @abstractmethod
    def format_report(self, report: MaintenanceReport, format_type: str = "text") -> str:
        """Format report for display or export."""
        pass
    
    @abstractmethod
    def save_report(self, report: MaintenanceReport, file_path: Optional[Path] = None) -> Path:
        """Save report to file."""
        pass
    
    @abstractmethod
    def export_report_data(self, report: MaintenanceReport) -> Dict[str, Any]:
        """Export report data for external use."""
        pass


class IMaintenanceOrchestrator(ABC):
    """Interface for coordinating maintenance operations."""
    
    @abstractmethod
    async def execute_maintenance(self, request: MaintenanceRequest) -> MaintenanceResult:
        """Execute maintenance task."""
        pass
    
    @abstractmethod
    async def execute_full_maintenance(self, dry_run: bool = False) -> MaintenanceReport:
        """Execute comprehensive maintenance routine."""
        pass
    
    @abstractmethod
    async def execute_health_check(self, check_types: Optional[List[HealthCheckType]] = None) -> MaintenanceResult:
        """Execute health check operations."""
        pass
    
    @abstractmethod
    async def execute_configuration_validation(self, config_paths: Optional[List[Path]] = None) -> MaintenanceResult:
        """Execute configuration validation."""
        pass
    
    @abstractmethod
    def get_maintenance_statistics(self) -> Dict[str, Any]:
        """Get maintenance operation statistics."""
        pass


# Mock implementations for testing
class MockHealthChecker(IHealthChecker):
    """Mock health checker for testing."""
    
    def __init__(self, check_results: Optional[Dict[HealthCheckType, HealthCheckResult]] = None):
        self.check_results = check_results or {}
    
    async def check_health(self, check_types: Optional[List[HealthCheckType]] = None) -> Dict[HealthCheckType, HealthCheckResult]:
        results = {}
        types_to_check = check_types or list(HealthCheckType)
        
        for check_type in types_to_check:
            results[check_type] = self.check_results.get(
                check_type,
                HealthCheckResult(check_type=check_type, status=MaintenanceStatus.SUCCESS)
            )
        
        return results
    
    def check_file_system(self, base_path: Path) -> HealthCheckResult:
        return HealthCheckResult(
            check_type=HealthCheckType.FILE_SYSTEM,
            status=MaintenanceStatus.SUCCESS,
            details={"path": str(base_path), "exists": True}
        )
    
    def check_disk_space(self, path: Path, warning_threshold: float = 20.0) -> HealthCheckResult:
        return HealthCheckResult(
            check_type=HealthCheckType.DISK_SPACE,
            status=MaintenanceStatus.SUCCESS,
            details={"free_percent": 50.0, "warning_threshold": warning_threshold}
        )
    
    def check_python_environment(self) -> HealthCheckResult:
        return HealthCheckResult(
            check_type=HealthCheckType.PYTHON_ENVIRONMENT,
            status=MaintenanceStatus.SUCCESS,
            details={"python_version": "3.13.5", "modules_available": True}
        )


class MockConfigurationValidator(IConfigurationValidator):
    """Mock configuration validator for testing."""
    
    def __init__(self, validation_results: Optional[Dict[str, ConfigurationValidationResult]] = None):
        self.validation_results = validation_results or {}
    
    async def validate_configuration(self, config_paths: Optional[List[Path]] = None) -> ConfigurationValidationResult:
        return ConfigurationValidationResult(valid=True, validated_files=["mock_config.json"])
    
    def validate_model_registry(self, registry_path: Path) -> ConfigurationValidationResult:
        return self.validation_results.get(
            str(registry_path),
            ConfigurationValidationResult(valid=True, validated_files=[str(registry_path)])
        )
    
    def validate_system_config(self, config_path: Path) -> ConfigurationValidationResult:
        return self.validation_results.get(
            str(config_path),
            ConfigurationValidationResult(valid=True, validated_files=[str(config_path)])
        )
    
    def validate_json_file(self, file_path: Path, required_fields: Optional[List[str]] = None) -> ConfigurationValidationResult:
        return ConfigurationValidationResult(valid=True, validated_files=[str(file_path)])


class MockMaintenanceLogger(IMaintenanceLogger):
    """Mock maintenance logger for testing."""
    
    def __init__(self):
        self.log_entries = []
    
    def log_maintenance_start(self, task_type: MaintenanceTaskType, parameters: Dict[str, Any]) -> None:
        self.log_entries.append({
            "type": "start",
            "task_type": task_type.value,
            "parameters": parameters,
            "timestamp": datetime.now().isoformat()
        })
    
    def log_maintenance_result(self, result: MaintenanceResult) -> None:
        self.log_entries.append({
            "type": "result",
            "task_type": result.request.task_type.value,
            "status": result.status.value,
            "timestamp": result.timestamp.isoformat()
        })
    
    def log_maintenance_error(self, task_type: MaintenanceTaskType, error: Exception, context: Dict[str, Any]) -> None:
        self.log_entries.append({
            "type": "error",
            "task_type": task_type.value,
            "error": str(error),
            "context": context,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_maintenance_log(self, task_type: Optional[MaintenanceTaskType] = None, 
                           since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        return self.log_entries


class MockMaintenanceReporter(IMaintenanceReporter):
    """Mock maintenance reporter for testing."""
    
    async def generate_report(self, include_sections: Optional[List[str]] = None) -> MaintenanceReport:
        return MaintenanceReport(
            timestamp=datetime.now(),
            dry_run=False,
            sections={"health": {"status": "success"}, "config": {"valid": True}},
            summary={"total_tasks": 2, "successful": 2, "failed": 0}
        )
    
    def format_report(self, report: MaintenanceReport, format_type: str = "text") -> str:
        if format_type == "text":
            return f"Maintenance Report - {report.timestamp.isoformat()}\nSections: {len(report.sections)}"
        return str(report.to_dict())
    
    def save_report(self, report: MaintenanceReport, file_path: Optional[Path] = None) -> Path:
        if file_path is None:
            file_path = Path(f"/tmp/maintenance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        return file_path
    
    def export_report_data(self, report: MaintenanceReport) -> Dict[str, Any]:
        return report.to_dict()


class MockMaintenanceOrchestrator(IMaintenanceOrchestrator):
    """Mock maintenance orchestrator for testing."""
    
    def __init__(self):
        self.execution_count = 0
        self.statistics = {"total_executions": 0, "successful": 0, "failed": 0}
    
    async def execute_maintenance(self, request: MaintenanceRequest) -> MaintenanceResult:
        self.execution_count += 1
        self.statistics["total_executions"] += 1
        self.statistics["successful"] += 1
        
        return MaintenanceResult(
            request=request,
            status=MaintenanceStatus.SUCCESS,
            message=f"Mock maintenance executed: {request.task_type.value}",
            execution_time_ms=100
        )
    
    async def execute_full_maintenance(self, dry_run: bool = False) -> MaintenanceReport:
        return MaintenanceReport(
            timestamp=datetime.now(),
            dry_run=dry_run,
            sections={"health": {"status": "success"}, "config": {"valid": True}},
            summary={"total_tasks": 2, "successful": 2, "failed": 0},
            duration_ms=1000
        )
    
    async def execute_health_check(self, check_types: Optional[List[HealthCheckType]] = None) -> MaintenanceResult:
        request = MaintenanceRequest(task_type=MaintenanceTaskType.HEALTH_CHECK)
        return await self.execute_maintenance(request)
    
    async def execute_configuration_validation(self, config_paths: Optional[List[Path]] = None) -> MaintenanceResult:
        request = MaintenanceRequest(task_type=MaintenanceTaskType.CONFIGURATION_VALIDATION)
        return await self.execute_maintenance(request)
    
    def get_maintenance_statistics(self) -> Dict[str, Any]:
        return self.statistics.copy()
