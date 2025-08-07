"""
Maintenance Orchestrator Implementation
Coordinates all maintenance operations using dependency injection following SOLID principles.
"""

import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

from .interfaces.maintenance_interfaces import (
    IMaintenanceOrchestrator, IHealthChecker, IConfigurationValidator, IMaintenanceLogger, IMaintenanceReporter,
    MaintenanceRequest, MaintenanceResult, MaintenanceReport, MaintenanceTaskType, MaintenanceStatus, HealthCheckType
)

# Graceful logging import
try:
    from utilities.logging_system import get_logger, log_system_event
except ImportError:
    import logging
    
    def get_logger():
        return logging.getLogger(__name__)
    
    def log_system_event(event: str, details: str):
        logging.info(f"SYSTEM_EVENT: {event} - {details}")


class MaintenanceOrchestrator(IMaintenanceOrchestrator):
    """
    Comprehensive maintenance orchestrator coordinating all maintenance operations.
    Uses dependency injection for all components following Dependency Inversion Principle.
    """
    
    def __init__(
        self,
        health_checker: IHealthChecker,
        config_validator: IConfigurationValidator,
        maintenance_logger: IMaintenanceLogger,
        reporter: IMaintenanceReporter,
        base_path: Path,
        logger=None
    ):
        """Initialize orchestrator with all required dependencies."""
        self.health_checker = health_checker
        self.config_validator = config_validator
        self.maintenance_logger = maintenance_logger
        self.reporter = reporter
        self.base_path = Path(base_path).resolve()
        self.logger = logger or get_logger()
        
        # Statistics tracking
        self.execution_stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "warning_executions": 0,
            "task_type_counts": {},
            "average_execution_time_ms": 0,
            "last_execution": None
        }
        
        # Initialize orchestrator
        log_system_event("maintenance_orchestrator_initialized", f"Base path: {self.base_path}")
        self.logger.info(f"Maintenance orchestrator initialized with base path: {self.base_path}")
    
    async def execute_maintenance(self, request: MaintenanceRequest) -> MaintenanceResult:
        """Execute single maintenance task."""
        start_time = datetime.now()
        
        # Log maintenance start
        self.maintenance_logger.log_maintenance_start(request.task_type, request.parameters)
        self.logger.info(f"Executing maintenance task: {request.task_type.value}")
        
        try:
            # Route to appropriate handler based on task type
            if request.task_type == MaintenanceTaskType.HEALTH_CHECK:
                result = await self._execute_health_check(request)
            elif request.task_type == MaintenanceTaskType.CONFIGURATION_VALIDATION:
                result = await self._execute_configuration_validation(request)
            elif request.task_type == MaintenanceTaskType.REPORT_GENERATION:
                result = await self._execute_report_generation(request)
            elif request.task_type == MaintenanceTaskType.FULL_MAINTENANCE:
                result = await self._execute_full_maintenance_task(request)
            else:
                result = MaintenanceResult(
                    request=request,
                    status=MaintenanceStatus.FAILED,
                    message=f"Unknown maintenance task type: {request.task_type.value}",
                    errors=[f"Task type '{request.task_type.value}' is not supported"]
                )
        
        except Exception as e:
            # Handle unexpected errors
            self.logger.error(f"Maintenance task failed with exception: {e}")
            self.maintenance_logger.log_maintenance_error(request.task_type, e, {
                "request_parameters": request.parameters,
                "base_path": str(self.base_path)
            })
            
            result = MaintenanceResult(
                request=request,
                status=MaintenanceStatus.FAILED,
                message=f"Maintenance task failed: {e}",
                errors=[str(e)]
            )
        
        # Calculate execution time
        end_time = datetime.now()
        execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
        result.execution_time_ms = execution_time_ms
        result.timestamp = end_time
        
        # Log result
        self.maintenance_logger.log_maintenance_result(result)
        
        # Update statistics
        self._update_execution_stats(result)
        
        self.logger.info(f"Maintenance task completed: {request.task_type.value} - {result.status.value} ({execution_time_ms}ms)")
        
        return result
    
    async def execute_full_maintenance(self, dry_run: bool = False) -> MaintenanceReport:
        """Execute comprehensive maintenance routine."""
        start_time = datetime.now()
        
        self.logger.info(f"Starting full maintenance routine (dry_run: {dry_run})")
        log_system_event("full_maintenance_start", f"Dry run: {dry_run}")
        
        # Create full maintenance request
        request = MaintenanceRequest(
            task_type=MaintenanceTaskType.FULL_MAINTENANCE,
            dry_run=dry_run,
            parameters={"comprehensive": True}
        )
        
        try:
            # Execute health check
            health_result = await self.execute_health_check()
            
            # Execute configuration validation
            config_result = await self.execute_configuration_validation()
            
            # Generate comprehensive report
            report = await self.reporter.generate_report()
            
            # Update report with execution results
            report.sections["execution_results"] = {
                "health_check": health_result.to_dict(),
                "configuration_validation": config_result.to_dict(),
                "dry_run": dry_run,
                "timestamp": datetime.now().isoformat()
            }
            
            # Calculate total duration
            end_time = datetime.now()
            total_duration_ms = int((end_time - start_time).total_seconds() * 1000)
            report.duration_ms = total_duration_ms
            
            # Update summary with execution info
            report.summary.update({
                "full_maintenance_duration_ms": total_duration_ms,
                "health_check_status": health_result.status.value,
                "config_validation_status": config_result.status.value,
                "overall_status": self._determine_overall_status([health_result, config_result])
            })
            
            self.logger.info(f"Full maintenance completed in {total_duration_ms}ms")
            log_system_event("full_maintenance_complete", f"Duration: {total_duration_ms}ms, Status: {report.summary.get('overall_status')}")
            
            return report
        
        except Exception as e:
            self.logger.error(f"Full maintenance failed: {e}")
            self.maintenance_logger.log_maintenance_error(MaintenanceTaskType.FULL_MAINTENANCE, e, {
                "dry_run": dry_run,
                "base_path": str(self.base_path)
            })
            
            # Return error report
            return MaintenanceReport(
                timestamp=start_time,
                dry_run=dry_run,
                sections={"error": {"message": str(e), "status": "failed"}},
                summary={"error": True, "message": str(e)},
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
    
    async def execute_health_check(self, check_types: Optional[List[HealthCheckType]] = None) -> MaintenanceResult:
        """Execute health check operations."""
        request = MaintenanceRequest(
            task_type=MaintenanceTaskType.HEALTH_CHECK,
            parameters={"check_types": [ct.value for ct in check_types] if check_types else None}
        )
        return await self.execute_maintenance(request)
    
    async def execute_configuration_validation(self, config_paths: Optional[List[Path]] = None) -> MaintenanceResult:
        """Execute configuration validation."""
        request = MaintenanceRequest(
            task_type=MaintenanceTaskType.CONFIGURATION_VALIDATION,
            parameters={"config_paths": [str(p) for p in config_paths] if config_paths else None}
        )
        return await self.execute_maintenance(request)
    
    def get_maintenance_statistics(self) -> Dict[str, Any]:
        """Get maintenance operation statistics."""
        stats = self.execution_stats.copy()
        
        # Add logger statistics if available
        if hasattr(self.maintenance_logger, 'get_maintenance_statistics'):
            try:
                logger_stats = self.maintenance_logger.get_maintenance_statistics()
                stats["logger_statistics"] = logger_stats
            except Exception as e:
                self.logger.warning(f"Could not get logger statistics: {e}")
        
        # Add additional runtime info
        stats["runtime_info"] = {
            "base_path": str(self.base_path),
            "components": {
                "health_checker": type(self.health_checker).__name__,
                "config_validator": type(self.config_validator).__name__,
                "maintenance_logger": type(self.maintenance_logger).__name__,
                "reporter": type(self.reporter).__name__
            }
        }
        
        return stats
    
    async def _execute_health_check(self, request: MaintenanceRequest) -> MaintenanceResult:
        """Execute health check task."""
        try:
            # Parse check types from request parameters
            check_types = None
            if "check_types" in request.parameters and request.parameters["check_types"]:
                check_types = [HealthCheckType(ct) for ct in request.parameters["check_types"]]
            
            # Execute health checks
            health_results = await self.health_checker.check_health(check_types)
            
            # Analyze results
            successful_checks = sum(1 for r in health_results.values() if r.status == MaintenanceStatus.SUCCESS)
            failed_checks = sum(1 for r in health_results.values() if r.status == MaintenanceStatus.FAILED)
            warning_checks = sum(1 for r in health_results.values() if r.status == MaintenanceStatus.WARNING)
            
            # Collect all issues
            all_issues = []
            all_warnings = []
            for result in health_results.values():
                all_issues.extend(result.issues)
                if result.status == MaintenanceStatus.WARNING:
                    all_warnings.extend(result.issues)
            
            # Determine overall status
            if failed_checks > 0:
                status = MaintenanceStatus.FAILED
                message = f"Health check failed: {failed_checks} checks failed, {warning_checks} warnings"
            elif warning_checks > 0:
                status = MaintenanceStatus.WARNING
                message = f"Health check completed with warnings: {warning_checks} warnings"
            else:
                status = MaintenanceStatus.SUCCESS
                message = f"Health check passed: {successful_checks} checks successful"
            
            return MaintenanceResult(
                request=request,
                status=status,
                message=message,
                details={
                    "total_checks": len(health_results),
                    "successful": successful_checks,
                    "failed": failed_checks,
                    "warnings": warning_checks,
                    "check_results": {ct.value: result.to_dict() for ct, result in health_results.items()}
                },
                errors=all_issues if failed_checks > 0 else [],
                warnings=all_warnings
            )
        
        except Exception as e:
            return MaintenanceResult(
                request=request,
                status=MaintenanceStatus.FAILED,
                message=f"Health check execution failed: {e}",
                errors=[str(e)]
            )
    
    async def _execute_configuration_validation(self, request: MaintenanceRequest) -> MaintenanceResult:
        """Execute configuration validation task."""
        try:
            # Parse config paths from request parameters
            config_paths = None
            if "config_paths" in request.parameters and request.parameters["config_paths"]:
                config_paths = [Path(p) for p in request.parameters["config_paths"]]
            
            # Execute configuration validation
            validation_result = await self.config_validator.validate_configuration(config_paths)
            
            # Determine status
            if validation_result.valid:
                if validation_result.warnings:
                    status = MaintenanceStatus.WARNING
                    message = f"Configuration validation passed with {len(validation_result.warnings)} warnings"
                else:
                    status = MaintenanceStatus.SUCCESS
                    message = "Configuration validation passed"
            else:
                status = MaintenanceStatus.FAILED
                message = f"Configuration validation failed with {len(validation_result.issues)} issues"
            
            return MaintenanceResult(
                request=request,
                status=status,
                message=message,
                details={
                    "validation_result": validation_result.to_dict(),
                    "validated_files_count": len(validation_result.validated_files),
                    "issues_count": len(validation_result.issues),
                    "warnings_count": len(validation_result.warnings)
                },
                errors=validation_result.issues,
                warnings=validation_result.warnings
            )
        
        except Exception as e:
            return MaintenanceResult(
                request=request,
                status=MaintenanceStatus.FAILED,
                message=f"Configuration validation failed: {e}",
                errors=[str(e)]
            )
    
    async def _execute_report_generation(self, request: MaintenanceRequest) -> MaintenanceResult:
        """Execute report generation task."""
        try:
            # Parse include sections from request parameters
            include_sections = request.parameters.get("include_sections")
            
            # Generate report
            report = await self.reporter.generate_report(include_sections)
            
            # Determine status based on report content
            failed_sections = report.summary.get("failed_sections", 0)
            warnings_count = report.summary.get("warnings_count", 0)
            
            if failed_sections > 0:
                status = MaintenanceStatus.FAILED
                message = f"Report generated with {failed_sections} failed sections"
            elif warnings_count > 0:
                status = MaintenanceStatus.WARNING
                message = f"Report generated with {warnings_count} warnings"
            else:
                status = MaintenanceStatus.SUCCESS
                message = "Report generated successfully"
            
            return MaintenanceResult(
                request=request,
                status=status,
                message=message,
                details={
                    "report_summary": report.summary,
                    "sections_count": len(report.sections),
                    "report_duration_ms": report.duration_ms
                }
            )
        
        except Exception as e:
            return MaintenanceResult(
                request=request,
                status=MaintenanceStatus.FAILED,
                message=f"Report generation failed: {e}",
                errors=[str(e)]
            )
    
    async def _execute_full_maintenance_task(self, request: MaintenanceRequest) -> MaintenanceResult:
        """Execute full maintenance as a single task."""
        try:
            # Execute full maintenance
            report = await self.execute_full_maintenance(request.dry_run)
            
            # Determine status from report
            overall_status = report.summary.get("overall_status", "unknown")
            
            if overall_status == "failed":
                status = MaintenanceStatus.FAILED
                message = "Full maintenance completed with failures"
            elif overall_status == "warning":
                status = MaintenanceStatus.WARNING
                message = "Full maintenance completed with warnings"
            else:
                status = MaintenanceStatus.SUCCESS
                message = "Full maintenance completed successfully"
            
            return MaintenanceResult(
                request=request,
                status=status,
                message=message,
                details={
                    "report_summary": report.summary,
                    "sections_generated": len(report.sections),
                    "total_duration_ms": report.duration_ms
                }
            )
        
        except Exception as e:
            return MaintenanceResult(
                request=request,
                status=MaintenanceStatus.FAILED,
                message=f"Full maintenance failed: {e}",
                errors=[str(e)]
            )
    
    def _update_execution_stats(self, result: MaintenanceResult) -> None:
        """Update execution statistics."""
        self.execution_stats["total_executions"] += 1
        self.execution_stats["last_execution"] = result.timestamp.isoformat()
        
        # Count by status
        if result.status == MaintenanceStatus.SUCCESS:
            self.execution_stats["successful_executions"] += 1
        elif result.status == MaintenanceStatus.FAILED:
            self.execution_stats["failed_executions"] += 1
        elif result.status == MaintenanceStatus.WARNING:
            self.execution_stats["warning_executions"] += 1
        
        # Count by task type
        task_type = result.request.task_type.value
        self.execution_stats["task_type_counts"][task_type] = (
            self.execution_stats["task_type_counts"].get(task_type, 0) + 1
        )
        
        # Update average execution time
        if result.execution_time_ms is not None:
            current_avg = self.execution_stats["average_execution_time_ms"]
            total_executions = self.execution_stats["total_executions"]
            
            # Calculate new average
            new_avg = ((current_avg * (total_executions - 1)) + result.execution_time_ms) / total_executions
            self.execution_stats["average_execution_time_ms"] = new_avg
    
    def _determine_overall_status(self, results: List[MaintenanceResult]) -> str:
        """Determine overall status from multiple results."""
        if any(r.status == MaintenanceStatus.FAILED for r in results):
            return "failed"
        elif any(r.status == MaintenanceStatus.WARNING for r in results):
            return "warning"
        else:
            return "success"


class QuickMaintenanceOrchestrator(IMaintenanceOrchestrator):
    """Quick maintenance orchestrator for basic operations."""
    
    def __init__(self, base_path: Path, logger=None):
        self.base_path = Path(base_path).resolve()
        self.logger = logger or get_logger()
        self.execution_count = 0
    
    async def execute_maintenance(self, request: MaintenanceRequest) -> MaintenanceResult:
        """Execute quick maintenance task."""
        self.execution_count += 1
        
        # Simple mock execution
        if request.task_type == MaintenanceTaskType.HEALTH_CHECK:
            status = MaintenanceStatus.SUCCESS if self.base_path.exists() else MaintenanceStatus.FAILED
            message = f"Quick health check: {'passed' if self.base_path.exists() else 'failed'}"
        else:
            status = MaintenanceStatus.SUCCESS
            message = f"Quick execution: {request.task_type.value}"
        
        return MaintenanceResult(
            request=request,
            status=status,
            message=message,
            execution_time_ms=50  # Mock execution time
        )
    
    async def execute_full_maintenance(self, dry_run: bool = False) -> MaintenanceReport:
        """Execute quick full maintenance."""
        return MaintenanceReport(
            timestamp=datetime.now(),
            dry_run=dry_run,
            sections={"quick": {"status": "success", "message": "Quick maintenance completed"}},
            summary={"total_sections": 1, "successful_sections": 1, "failed_sections": 0},
            duration_ms=100
        )
    
    async def execute_health_check(self, check_types: Optional[List[HealthCheckType]] = None) -> MaintenanceResult:
        """Execute quick health check."""
        request = MaintenanceRequest(task_type=MaintenanceTaskType.HEALTH_CHECK)
        return await self.execute_maintenance(request)
    
    async def execute_configuration_validation(self, config_paths: Optional[List[Path]] = None) -> MaintenanceResult:
        """Execute quick configuration validation."""
        request = MaintenanceRequest(task_type=MaintenanceTaskType.CONFIGURATION_VALIDATION)
        return await self.execute_maintenance(request)
    
    def get_maintenance_statistics(self) -> Dict[str, Any]:
        """Get quick statistics."""
        return {
            "total_executions": self.execution_count,
            "base_path": str(self.base_path),
            "type": "quick_orchestrator"
        }
