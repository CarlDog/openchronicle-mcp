"""
Maintenance Management Package
Modular maintenance system following SOLID principles for OpenChronicle.
Provides comprehensive maintenance operations with dependency injection and focused interfaces.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any

# Core interfaces and data classes
from .interfaces.maintenance_interfaces import (
    # Interfaces
    IHealthChecker, IConfigurationValidator, IMaintenanceLogger, IMaintenanceReporter, IMaintenanceOrchestrator,
    
    # Data classes and enums
    MaintenanceRequest, MaintenanceResult, HealthCheckResult, ConfigurationValidationResult, MaintenanceReport,
    MaintenanceTaskType, MaintenanceStatus, HealthCheckType,
    
    # Mock implementations for testing
    MockHealthChecker, MockConfigurationValidator, MockMaintenanceLogger, MockMaintenanceReporter, MockMaintenanceOrchestrator
)

# Concrete implementations
from .health.health_checker import SystemHealthChecker, QuickHealthChecker
from .validation.configuration_validator import ConfigurationValidator, QuickConfigurationValidator
from .logging.maintenance_logger import MaintenanceLogger, InMemoryMaintenanceLogger, NoOpMaintenanceLogger
from .reporting.maintenance_reporter import MaintenanceReporter, QuickMaintenanceReporter
from .orchestrator import MaintenanceOrchestrator, QuickMaintenanceOrchestrator

# Version and metadata
__version__ = "1.0.0"
__author__ = "OpenChronicle Team"
__description__ = "Modular maintenance management system with SOLID architecture"

# Public API exports
__all__ = [
    # Interfaces
    "IHealthChecker", "IConfigurationValidator", "IMaintenanceLogger", "IMaintenanceReporter", "IMaintenanceOrchestrator",
    
    # Data classes and enums
    "MaintenanceRequest", "MaintenanceResult", "HealthCheckResult", "ConfigurationValidationResult", "MaintenanceReport",
    "MaintenanceTaskType", "MaintenanceStatus", "HealthCheckType",
    
    # Concrete implementations
    "SystemHealthChecker", "QuickHealthChecker",
    "ConfigurationValidator", "QuickConfigurationValidator", 
    "MaintenanceLogger", "InMemoryMaintenanceLogger", "NoOpMaintenanceLogger",
    "MaintenanceReporter", "QuickMaintenanceReporter",
    "MaintenanceOrchestrator", "QuickMaintenanceOrchestrator",
    
    # Mock implementations
    "MockHealthChecker", "MockConfigurationValidator", "MockMaintenanceLogger", "MockMaintenanceReporter", "MockMaintenanceOrchestrator",
    
    # Factory functions
    "create_maintenance_manager", "create_quick_maintenance_manager", "create_mock_maintenance_manager",
    "create_health_checker", "create_configuration_validator", "create_maintenance_logger", "create_maintenance_reporter",
    "create_maintenance_request", "create_health_check_request", "create_configuration_validation_request"
]


def create_maintenance_manager(
    base_path: Path,
    health_checker: Optional[IHealthChecker] = None,
    config_validator: Optional[IConfigurationValidator] = None,
    maintenance_logger: Optional[IMaintenanceLogger] = None,
    reporter: Optional[IMaintenanceReporter] = None,
    logger=None
) -> MaintenanceOrchestrator:
    """
    Create a production-ready maintenance manager with full functionality.
    
    Args:
        base_path: Base directory path for the system
        health_checker: Custom health checker (creates SystemHealthChecker if None)
        config_validator: Custom configuration validator (creates ConfigurationValidator if None)
        maintenance_logger: Custom maintenance logger (creates MaintenanceLogger if None)
        reporter: Custom reporter (creates MaintenanceReporter if None)
        logger: Custom logger for the orchestrator
    
    Returns:
        Fully configured MaintenanceOrchestrator
    """
    base_path = Path(base_path)
    
    # Create default components if not provided
    if health_checker is None:
        health_checker = SystemHealthChecker(base_path, logger)
    
    if config_validator is None:
        config_validator = ConfigurationValidator(base_path, logger)
    
    if maintenance_logger is None:
        log_file_path = base_path / "logs" / "maintenance.log"
        maintenance_logger = MaintenanceLogger(log_file_path, logger)
    
    if reporter is None:
        reporter = MaintenanceReporter(base_path, health_checker, config_validator, logger)
    
    return MaintenanceOrchestrator(
        health_checker=health_checker,
        config_validator=config_validator,
        maintenance_logger=maintenance_logger,
        reporter=reporter,
        base_path=base_path,
        logger=logger
    )


def create_quick_maintenance_manager(base_path: Path, logger=None) -> QuickMaintenanceOrchestrator:
    """
    Create a quick maintenance manager for basic operations.
    
    Args:
        base_path: Base directory path for the system
        logger: Custom logger
    
    Returns:
        QuickMaintenanceOrchestrator for lightweight operations
    """
    return QuickMaintenanceOrchestrator(Path(base_path), logger)


def create_mock_maintenance_manager(base_path: Optional[Path] = None) -> MockMaintenanceOrchestrator:
    """
    Create a mock maintenance manager for testing.
    
    Args:
        base_path: Optional base path (uses /tmp/test if None)
    
    Returns:
        MockMaintenanceOrchestrator for testing
    """
    if base_path is None:
        base_path = Path("/tmp/test")
    
    return MockMaintenanceOrchestrator()


def create_health_checker(base_path: Path, quick: bool = False, logger=None) -> IHealthChecker:
    """
    Create a health checker implementation.
    
    Args:
        base_path: Base directory path for the system
        quick: Whether to create quick or comprehensive health checker
        logger: Custom logger
    
    Returns:
        Health checker implementation
    """
    if quick:
        return QuickHealthChecker(base_path, logger)
    else:
        return SystemHealthChecker(base_path, logger)


def create_configuration_validator(base_path: Path, quick: bool = False, logger=None) -> IConfigurationValidator:
    """
    Create a configuration validator implementation.
    
    Args:
        base_path: Base directory path for the system
        quick: Whether to create quick or comprehensive validator
        logger: Custom logger
    
    Returns:
        Configuration validator implementation
    """
    if quick:
        return QuickConfigurationValidator(base_path, logger)
    else:
        return ConfigurationValidator(base_path, logger)


def create_maintenance_logger(
    log_file_path: Optional[Path] = None,
    in_memory: bool = False,
    no_op: bool = False,
    logger=None
) -> IMaintenanceLogger:
    """
    Create a maintenance logger implementation.
    
    Args:
        log_file_path: Path for log file (uses default if None)
        in_memory: Whether to create in-memory logger
        no_op: Whether to create no-operation logger
        logger: Custom logger
    
    Returns:
        Maintenance logger implementation
    """
    if no_op:
        return NoOpMaintenanceLogger()
    elif in_memory:
        return InMemoryMaintenanceLogger(logger)
    else:
        return MaintenanceLogger(log_file_path, logger)


def create_maintenance_reporter(
    base_path: Path,
    health_checker: Optional[IHealthChecker] = None,
    config_validator: Optional[IConfigurationValidator] = None,
    quick: bool = False,
    logger=None
) -> IMaintenanceReporter:
    """
    Create a maintenance reporter implementation.
    
    Args:
        base_path: Base directory path for the system
        health_checker: Health checker for report generation
        config_validator: Configuration validator for report generation
        quick: Whether to create quick or comprehensive reporter
        logger: Custom logger
    
    Returns:
        Maintenance reporter implementation
    """
    if quick:
        return QuickMaintenanceReporter(base_path, logger)
    else:
        return MaintenanceReporter(base_path, health_checker, config_validator, logger)


def create_maintenance_request(
    task_type: MaintenanceTaskType,
    dry_run: bool = False,
    target_path: Optional[Path] = None,
    **parameters
) -> MaintenanceRequest:
    """
    Create a maintenance request with specified parameters.
    
    Args:
        task_type: Type of maintenance task
        dry_run: Whether this is a dry run
        target_path: Optional target path for the operation
        **parameters: Additional parameters for the request
    
    Returns:
        Configured MaintenanceRequest
    """
    return MaintenanceRequest(
        task_type=task_type,
        dry_run=dry_run,
        target_path=target_path,
        parameters=parameters
    )


def create_health_check_request(
    check_types: Optional[List[HealthCheckType]] = None,
    dry_run: bool = False
) -> MaintenanceRequest:
    """
    Create a health check request.
    
    Args:
        check_types: Specific health check types to run
        dry_run: Whether this is a dry run
    
    Returns:
        Health check MaintenanceRequest
    """
    parameters = {}
    if check_types:
        parameters["check_types"] = [ct.value for ct in check_types]
    
    return MaintenanceRequest(
        task_type=MaintenanceTaskType.HEALTH_CHECK,
        dry_run=dry_run,
        parameters=parameters
    )


def create_configuration_validation_request(
    config_paths: Optional[List[Path]] = None,
    dry_run: bool = False
) -> MaintenanceRequest:
    """
    Create a configuration validation request.
    
    Args:
        config_paths: Specific configuration paths to validate
        dry_run: Whether this is a dry run
    
    Returns:
        Configuration validation MaintenanceRequest
    """
    parameters = {}
    if config_paths:
        parameters["config_paths"] = [str(p) for p in config_paths]
    
    return MaintenanceRequest(
        task_type=MaintenanceTaskType.CONFIGURATION_VALIDATION,
        dry_run=dry_run,
        parameters=parameters
    )


def create_report_generation_request(
    include_sections: Optional[List[str]] = None,
    format_type: str = "json"
) -> MaintenanceRequest:
    """
    Create a report generation request.
    
    Args:
        include_sections: Specific sections to include in report
        format_type: Output format for the report
    
    Returns:
        Report generation MaintenanceRequest
    """
    parameters: Dict[str, Any] = {
        "format_type": format_type
    }
    if include_sections:
        parameters["include_sections"] = include_sections
    
    return MaintenanceRequest(
        task_type=MaintenanceTaskType.REPORT_GENERATION,
        dry_run=False,  # Reports don't modify system
        parameters=parameters
    )


def create_full_maintenance_request(dry_run: bool = False) -> MaintenanceRequest:
    """
    Create a full maintenance request.
    
    Args:
        dry_run: Whether this is a dry run
    
    Returns:
        Full maintenance MaintenanceRequest
    """
    return MaintenanceRequest(
        task_type=MaintenanceTaskType.FULL_MAINTENANCE,
        dry_run=dry_run,
        parameters={"comprehensive": True}
    )


# Convenience functions for common operations
async def quick_health_check(base_path: Path) -> Dict[str, Any]:
    """
    Perform a quick health check and return results.
    
    Args:
        base_path: System base path
    
    Returns:
        Health check results dictionary
    """
    manager = create_quick_maintenance_manager(base_path)
    result = await manager.execute_health_check()
    return result.to_dict()


async def quick_maintenance_report(base_path: Path) -> Dict[str, Any]:
    """
    Generate a quick maintenance report.
    
    Args:
        base_path: System base path
    
    Returns:
        Maintenance report dictionary
    """
    manager = create_quick_maintenance_manager(base_path)
    report = await manager.execute_full_maintenance()
    return report.to_dict()


async def comprehensive_maintenance(base_path: Path, dry_run: bool = False) -> Dict[str, Any]:
    """
    Run comprehensive maintenance and return detailed report.
    
    Args:
        base_path: System base path
        dry_run: Whether to run in dry-run mode
    
    Returns:
        Comprehensive maintenance report dictionary
    """
    manager = create_maintenance_manager(base_path)
    report = await manager.execute_full_maintenance(dry_run)
    return report.to_dict()


# Component information for introspection
def get_component_info() -> Dict[str, Any]:
    """
    Get information about available maintenance components.
    
    Returns:
        Dictionary with component information
    """
    return {
        "version": __version__,
        "description": __description__,
        "interfaces": [
            "IHealthChecker", "IConfigurationValidator", "IMaintenanceLogger", 
            "IMaintenanceReporter", "IMaintenanceOrchestrator"
        ],
        "implementations": {
            "health_checkers": ["SystemHealthChecker", "QuickHealthChecker"],
            "config_validators": ["ConfigurationValidator", "QuickConfigurationValidator"],
            "loggers": ["MaintenanceLogger", "InMemoryMaintenanceLogger", "NoOpMaintenanceLogger"],
            "reporters": ["MaintenanceReporter", "QuickMaintenanceReporter"],
            "orchestrators": ["MaintenanceOrchestrator", "QuickMaintenanceOrchestrator"]
        },
        "task_types": [task_type.value for task_type in MaintenanceTaskType],
        "health_check_types": [check_type.value for check_type in HealthCheckType],
        "factory_functions": [
            "create_maintenance_manager", "create_quick_maintenance_manager", "create_mock_maintenance_manager",
            "create_health_checker", "create_configuration_validator", "create_maintenance_logger", 
            "create_maintenance_reporter"
        ]
    }
