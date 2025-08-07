"""
Maintenance Reporting Implementation
Comprehensive reporting for maintenance operations following Single Responsibility Principle.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union

from ..interfaces.maintenance_interfaces import (
    IMaintenanceReporter, MaintenanceReport, HealthCheckResult, ConfigurationValidationResult,
    MaintenanceStatus, HealthCheckType
)

# Graceful logging import
try:
    from utilities.logging_system import get_logger
except ImportError:
    import logging
    
    def get_logger():
        return logging.getLogger(__name__)


class MaintenanceReporter(IMaintenanceReporter):
    """Comprehensive maintenance reporter implementation."""
    
    def __init__(self, base_path: Path, health_checker=None, config_validator=None, logger=None):
        self.base_path = Path(base_path).resolve()
        self.logger = logger or get_logger()
        self.health_checker = health_checker
        self.config_validator = config_validator
        
        # Report configuration
        self.report_sections = {
            "health": "System Health Analysis",
            "configuration": "Configuration Validation",
            "storage": "Storage Analysis", 
            "databases": "Database Analysis",
            "performance": "Performance Metrics",
            "maintenance_log": "Maintenance History"
        }
    
    async def generate_report(self, include_sections: Optional[List[str]] = None) -> MaintenanceReport:
        """Generate comprehensive maintenance report."""
        start_time = datetime.now()
        
        if include_sections is None:
            include_sections = list(self.report_sections.keys())
        
        self.logger.info(f"Generating maintenance report with {len(include_sections)} sections")
        
        report_sections = {}
        summary_stats = {
            "total_sections": len(include_sections),
            "successful_sections": 0,
            "failed_sections": 0,
            "warnings_count": 0,
            "errors_count": 0
        }
        
        # Generate each requested section
        for section in include_sections:
            try:
                if section == "health":
                    section_data = await self._generate_health_section()
                elif section == "configuration":
                    section_data = await self._generate_configuration_section()
                elif section == "storage":
                    section_data = await self._generate_storage_section()
                elif section == "databases":
                    section_data = await self._generate_database_section()
                elif section == "performance":
                    section_data = await self._generate_performance_section()
                elif section == "maintenance_log":
                    section_data = await self._generate_maintenance_log_section()
                else:
                    section_data = {
                        "status": "skipped",
                        "reason": f"Unknown section: {section}"
                    }
                
                report_sections[section] = section_data
                
                # Update summary stats
                if section_data.get("status") == "success":
                    summary_stats["successful_sections"] += 1
                elif section_data.get("status") == "failed":
                    summary_stats["failed_sections"] += 1
                
                # Count warnings and errors
                summary_stats["warnings_count"] += len(section_data.get("warnings", []))
                summary_stats["errors_count"] += len(section_data.get("errors", []))
                
            except Exception as e:
                self.logger.error(f"Failed to generate report section '{section}': {e}")
                report_sections[section] = {
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                summary_stats["failed_sections"] += 1
        
        # Calculate report duration
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        # Create comprehensive summary
        summary_stats.update({
            "generation_time": end_time.isoformat(),
            "duration_ms": duration_ms,
            "system_path": str(self.base_path),
            "report_completeness": (summary_stats["successful_sections"] / summary_stats["total_sections"] * 100) if summary_stats["total_sections"] > 0 else 0
        })
        
        return MaintenanceReport(
            timestamp=start_time,
            dry_run=False,  # Reports don't modify system
            sections=report_sections,
            summary=summary_stats,
            duration_ms=duration_ms
        )
    
    def format_report(self, report: MaintenanceReport, format_type: str = "text") -> str:
        """Format report for display or export."""
        if format_type == "text":
            return self._format_text_report(report)
        elif format_type == "html":
            return self._format_html_report(report)
        elif format_type == "markdown":
            return self._format_markdown_report(report)
        elif format_type == "json":
            return json.dumps(report.to_dict(), indent=2, default=str)
        else:
            raise ValueError(f"Unsupported format type: {format_type}")
    
    def save_report(self, report: MaintenanceReport, file_path: Optional[Path] = None) -> Path:
        """Save report to file."""
        if file_path is None:
            timestamp = report.timestamp.strftime("%Y%m%d_%H%M%S")
            file_path = self.base_path / "utilities" / f"maintenance_report_{timestamp}.json"
        
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, indent=2, default=str)
        
        self.logger.info(f"Maintenance report saved to: {file_path}")
        return file_path
    
    def export_report_data(self, report: MaintenanceReport) -> Dict[str, Any]:
        """Export report data for external use."""
        export_data = report.to_dict()
        
        # Add export metadata
        export_data["export_info"] = {
            "exported_at": datetime.now().isoformat(),
            "export_version": "1.0",
            "system_path": str(self.base_path)
        }
        
        # Add processed summaries for easy consumption
        export_data["processed_summaries"] = {
            "overall_health": self._assess_overall_health(report),
            "critical_issues": self._extract_critical_issues(report),
            "recommendations": self._generate_recommendations(report),
            "key_metrics": self._extract_key_metrics(report)
        }
        
        return export_data
    
    async def _generate_health_section(self) -> Dict[str, Any]:
        """Generate health check section."""
        section_data = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "title": self.report_sections["health"],
            "checks": {},
            "summary": {},
            "warnings": [],
            "errors": []
        }
        
        if self.health_checker:
            try:
                health_results = await self.health_checker.check_health()
                
                # Process health check results
                successful_checks = 0
                failed_checks = 0
                warning_checks = 0
                
                for check_type, result in health_results.items():
                    check_data = result.to_dict()
                    section_data["checks"][check_type.value] = check_data
                    
                    if result.status == MaintenanceStatus.SUCCESS:
                        successful_checks += 1
                    elif result.status == MaintenanceStatus.FAILED:
                        failed_checks += 1
                        section_data["errors"].extend(result.issues)
                    elif result.status == MaintenanceStatus.WARNING:
                        warning_checks += 1
                        section_data["warnings"].extend(result.issues)
                
                section_data["summary"] = {
                    "total_checks": len(health_results),
                    "successful": successful_checks,
                    "failed": failed_checks,
                    "warnings": warning_checks,
                    "overall_status": "healthy" if failed_checks == 0 else "unhealthy"
                }
                
                if failed_checks > 0:
                    section_data["status"] = "failed"
                elif warning_checks > 0:
                    section_data["status"] = "warning"
                
            except Exception as e:
                section_data["status"] = "failed"
                section_data["error"] = str(e)
                section_data["errors"].append(f"Health check generation failed: {e}")
        else:
            section_data["status"] = "skipped"
            section_data["reason"] = "No health checker available"
        
        return section_data
    
    async def _generate_configuration_section(self) -> Dict[str, Any]:
        """Generate configuration validation section."""
        section_data = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "title": self.report_sections["configuration"],
            "validation_results": {},
            "summary": {},
            "warnings": [],
            "errors": []
        }
        
        if self.config_validator:
            try:
                validation_result = await self.config_validator.validate_configuration()
                
                section_data["validation_results"] = validation_result.to_dict()
                section_data["summary"] = {
                    "overall_valid": validation_result.valid,
                    "validated_files": len(validation_result.validated_files),
                    "issues_count": len(validation_result.issues),
                    "warnings_count": len(validation_result.warnings)
                }
                
                section_data["errors"].extend(validation_result.issues)
                section_data["warnings"].extend(validation_result.warnings)
                
                if not validation_result.valid:
                    section_data["status"] = "failed"
                elif validation_result.warnings:
                    section_data["status"] = "warning"
                
            except Exception as e:
                section_data["status"] = "failed"
                section_data["error"] = str(e)
                section_data["errors"].append(f"Configuration validation failed: {e}")
        else:
            section_data["status"] = "skipped"
            section_data["reason"] = "No configuration validator available"
        
        return section_data
    
    async def _generate_storage_section(self) -> Dict[str, Any]:
        """Generate storage analysis section."""
        section_data = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "title": self.report_sections["storage"],
            "analysis": {},
            "summary": {},
            "warnings": [],
            "errors": []
        }
        
        try:
            storage_path = self.base_path / "storage"
            
            if not storage_path.exists():
                section_data["status"] = "warning"
                section_data["warnings"].append("Storage directory does not exist")
                return section_data
            
            # Analyze storage structure
            story_dirs = [d for d in storage_path.iterdir() if d.is_dir()]
            total_files = 0
            total_size = 0
            
            story_analysis = {}
            for story_dir in story_dirs:
                try:
                    story_files = list(story_dir.rglob("*"))
                    story_file_count = sum(1 for f in story_files if f.is_file())
                    story_size = sum(f.stat().st_size for f in story_files if f.is_file())
                    
                    story_analysis[story_dir.name] = {
                        "file_count": story_file_count,
                        "size_bytes": story_size,
                        "size_human": self._format_bytes(story_size)
                    }
                    
                    total_files += story_file_count
                    total_size += story_size
                    
                except Exception as e:
                    story_analysis[story_dir.name] = {"error": str(e)}
                    section_data["warnings"].append(f"Could not analyze story directory {story_dir.name}: {e}")
            
            section_data["analysis"] = {
                "storage_path": str(storage_path),
                "story_count": len(story_dirs),
                "stories": story_analysis,
                "total_files": total_files,
                "total_size_bytes": total_size,
                "total_size_human": self._format_bytes(total_size)
            }
            
            section_data["summary"] = {
                "story_directories": len(story_dirs),
                "total_files": total_files,
                "total_size": self._format_bytes(total_size),
                "average_story_size": self._format_bytes(total_size // len(story_dirs)) if story_dirs else "0 B"
            }
            
        except Exception as e:
            section_data["status"] = "failed"
            section_data["error"] = str(e)
            section_data["errors"].append(f"Storage analysis failed: {e}")
        
        return section_data
    
    async def _generate_database_section(self) -> Dict[str, Any]:
        """Generate database analysis section."""
        section_data = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "title": self.report_sections["databases"],
            "databases": [],
            "summary": {},
            "warnings": [],
            "errors": []
        }
        
        try:
            # Find database files
            db_patterns = ["*.db", "*.sqlite", "*.sqlite3"]
            db_files = []
            
            for pattern in db_patterns:
                db_files.extend(self.base_path.rglob(pattern))
            
            db_analysis = []
            accessible_count = 0
            total_size = 0
            
            for db_file in db_files:
                db_info = {
                    "path": str(db_file.relative_to(self.base_path)),
                    "size_bytes": db_file.stat().st_size,
                    "size_human": self._format_bytes(db_file.stat().st_size),
                    "last_modified": datetime.fromtimestamp(db_file.stat().st_mtime).isoformat()
                }
                
                # Try to analyze database
                try:
                    import sqlite3
                    with sqlite3.connect(db_file) as conn:
                        cursor = conn.cursor()
                        
                        # Get table count
                        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
                        table_count = cursor.fetchone()[0]
                        
                        # Get database size info
                        cursor.execute("PRAGMA page_count;")
                        page_count = cursor.fetchone()[0]
                        cursor.execute("PRAGMA page_size;")
                        page_size = cursor.fetchone()[0]
                        
                        db_info.update({
                            "accessible": True,
                            "table_count": table_count,
                            "page_count": page_count,
                            "page_size": page_size,
                            "database_size": page_count * page_size
                        })
                        
                        accessible_count += 1
                        
                except Exception as e:
                    db_info.update({
                        "accessible": False,
                        "error": str(e)
                    })
                    section_data["warnings"].append(f"Database not accessible: {db_file.name}")
                
                db_analysis.append(db_info)
                total_size += db_file.stat().st_size
            
            section_data["databases"] = db_analysis
            section_data["summary"] = {
                "total_databases": len(db_files),
                "accessible_databases": accessible_count,
                "inaccessible_databases": len(db_files) - accessible_count,
                "total_size": self._format_bytes(total_size),
                "average_size": self._format_bytes(total_size // len(db_files)) if db_files else "0 B"
            }
            
            if accessible_count < len(db_files):
                section_data["status"] = "warning"
            
        except Exception as e:
            section_data["status"] = "failed"
            section_data["error"] = str(e)
            section_data["errors"].append(f"Database analysis failed: {e}")
        
        return section_data
    
    async def _generate_performance_section(self) -> Dict[str, Any]:
        """Generate performance metrics section."""
        section_data = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "title": self.report_sections["performance"],
            "metrics": {},
            "summary": {},
            "warnings": [],
            "errors": []
        }
        
        try:
            import psutil
            import shutil
            
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk_usage = shutil.disk_usage(self.base_path)
            
            section_data["metrics"] = {
                "cpu": {
                    "usage_percent": cpu_percent,
                    "core_count": psutil.cpu_count(),
                    "frequency": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
                },
                "memory": {
                    "total_bytes": memory.total,
                    "available_bytes": memory.available,
                    "used_bytes": memory.used,
                    "percent_used": memory.percent,
                    "total_human": self._format_bytes(memory.total),
                    "available_human": self._format_bytes(memory.available),
                    "used_human": self._format_bytes(memory.used)
                },
                "disk": {
                    "total_bytes": disk_usage.total,
                    "used_bytes": disk_usage.used,
                    "free_bytes": disk_usage.free,
                    "percent_used": (disk_usage.used / disk_usage.total * 100) if disk_usage.total > 0 else 0,
                    "total_human": self._format_bytes(disk_usage.total),
                    "used_human": self._format_bytes(disk_usage.used),
                    "free_human": self._format_bytes(disk_usage.free)
                }
            }
            
            # Performance warnings
            if cpu_percent > 80:
                section_data["warnings"].append(f"High CPU usage: {cpu_percent}%")
            if memory.percent > 85:
                section_data["warnings"].append(f"High memory usage: {memory.percent}%")
            if (disk_usage.free / disk_usage.total * 100) < 10:
                section_data["warnings"].append("Low disk space: < 10% free")
            
            section_data["summary"] = {
                "cpu_usage": f"{cpu_percent}%",
                "memory_usage": f"{memory.percent}%",
                "disk_usage": f"{disk_usage.used / disk_usage.total * 100:.1f}%",
                "performance_status": "good" if not section_data["warnings"] else "needs_attention"
            }
            
            if section_data["warnings"]:
                section_data["status"] = "warning"
            
        except ImportError:
            section_data["status"] = "skipped"
            section_data["reason"] = "psutil module not available for performance metrics"
        except Exception as e:
            section_data["status"] = "failed"
            section_data["error"] = str(e)
            section_data["errors"].append(f"Performance analysis failed: {e}")
        
        return section_data
    
    async def _generate_maintenance_log_section(self) -> Dict[str, Any]:
        """Generate maintenance log section."""
        section_data = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "title": self.report_sections["maintenance_log"],
            "log_analysis": {},
            "summary": {},
            "warnings": [],
            "errors": []
        }
        
        try:
            # Look for maintenance log files
            log_files = list(self.base_path.glob("logs/maintenance*.log"))
            
            if not log_files:
                section_data["status"] = "warning"
                section_data["warnings"].append("No maintenance log files found")
                return section_data
            
            # Analyze recent log entries
            recent_entries = []
            total_entries = 0
            
            for log_file in log_files:
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                try:
                                    entry = json.loads(line)
                                    recent_entries.append(entry)
                                    total_entries += 1
                                except json.JSONDecodeError:
                                    pass  # Skip non-JSON lines
                except Exception as e:
                    section_data["warnings"].append(f"Could not read log file {log_file.name}: {e}")
            
            # Analyze recent entries (last 100)
            recent_entries = recent_entries[-100:]
            
            # Count by event type
            event_counts = {}
            status_counts = {}
            
            for entry in recent_entries:
                event_type = entry.get("event_type", "unknown")
                event_counts[event_type] = event_counts.get(event_type, 0) + 1
                
                if event_type == "maintenance_result":
                    status = entry.get("status", "unknown")
                    status_counts[status] = status_counts.get(status, 0) + 1
            
            section_data["log_analysis"] = {
                "total_log_files": len(log_files),
                "total_entries": total_entries,
                "recent_entries_analyzed": len(recent_entries),
                "event_type_counts": event_counts,
                "status_counts": status_counts
            }
            
            section_data["summary"] = {
                "log_files": len(log_files),
                "total_entries": total_entries,
                "recent_activity": len(recent_entries),
                "success_rate": f"{(status_counts.get('success', 0) / max(sum(status_counts.values()), 1) * 100):.1f}%" if status_counts else "N/A"
            }
            
        except Exception as e:
            section_data["status"] = "failed"
            section_data["error"] = str(e)
            section_data["errors"].append(f"Maintenance log analysis failed: {e}")
        
        return section_data
    
    def _format_text_report(self, report: MaintenanceReport) -> str:
        """Format report as text."""
        lines = []
        lines.append("=" * 80)
        lines.append("OPENCHRONICLE MAINTENANCE REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {report.timestamp.isoformat()}")
        lines.append(f"Duration: {report.duration_ms}ms")
        lines.append(f"System Path: {report.summary.get('system_path', 'Unknown')}")
        lines.append("")
        
        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Sections Generated: {report.summary.get('total_sections', 0)}")
        lines.append(f"Successful: {report.summary.get('successful_sections', 0)}")
        lines.append(f"Failed: {report.summary.get('failed_sections', 0)}")
        lines.append(f"Total Warnings: {report.summary.get('warnings_count', 0)}")
        lines.append(f"Total Errors: {report.summary.get('errors_count', 0)}")
        lines.append(f"Completeness: {report.summary.get('report_completeness', 0):.1f}%")
        lines.append("")
        
        # Sections
        for section_name, section_data in report.sections.items():
            lines.append(f"{section_data.get('title', section_name.upper())}")
            lines.append("-" * 40)
            lines.append(f"Status: {section_data.get('status', 'unknown')}")
            
            if "summary" in section_data:
                for key, value in section_data["summary"].items():
                    lines.append(f"  {key.replace('_', ' ').title()}: {value}")
            
            if section_data.get("warnings"):
                lines.append("  Warnings:")
                for warning in section_data["warnings"]:
                    lines.append(f"    - {warning}")
            
            if section_data.get("errors"):
                lines.append("  Errors:")
                for error in section_data["errors"]:
                    lines.append(f"    - {error}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_markdown_report(self, report: MaintenanceReport) -> str:
        """Format report as Markdown."""
        lines = []
        lines.append("# OpenChronicle Maintenance Report")
        lines.append("")
        lines.append(f"**Generated:** {report.timestamp.isoformat()}")
        lines.append(f"**Duration:** {report.duration_ms}ms")
        lines.append(f"**System Path:** `{report.summary.get('system_path', 'Unknown')}`")
        lines.append("")
        
        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Sections Generated:** {report.summary.get('total_sections', 0)}")
        lines.append(f"- **Successful:** {report.summary.get('successful_sections', 0)}")
        lines.append(f"- **Failed:** {report.summary.get('failed_sections', 0)}")
        lines.append(f"- **Total Warnings:** {report.summary.get('warnings_count', 0)}")
        lines.append(f"- **Total Errors:** {report.summary.get('errors_count', 0)}")
        lines.append(f"- **Completeness:** {report.summary.get('report_completeness', 0):.1f}%")
        lines.append("")
        
        # Sections
        for section_name, section_data in report.sections.items():
            lines.append(f"## {section_data.get('title', section_name.title())}")
            lines.append("")
            lines.append(f"**Status:** {section_data.get('status', 'unknown')}")
            lines.append("")
            
            if "summary" in section_data:
                for key, value in section_data["summary"].items():
                    lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
                lines.append("")
            
            if section_data.get("warnings"):
                lines.append("### Warnings")
                for warning in section_data["warnings"]:
                    lines.append(f"- ⚠️ {warning}")
                lines.append("")
            
            if section_data.get("errors"):
                lines.append("### Errors")
                for error in section_data["errors"]:
                    lines.append(f"- ❌ {error}")
                lines.append("")
        
        return "\n".join(lines)
    
    def _format_html_report(self, report: MaintenanceReport) -> str:
        """Format report as HTML."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>OpenChronicle Maintenance Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f0f0f0; padding: 15px; border-radius: 5px; }}
        .section {{ margin: 20px 0; border: 1px solid #ddd; border-radius: 5px; }}
        .section-header {{ background-color: #e8e8e8; padding: 10px; font-weight: bold; }}
        .section-content {{ padding: 15px; }}
        .success {{ color: #008000; }}
        .warning {{ color: #ff8800; }}
        .failed {{ color: #cc0000; }}
        .metric {{ display: inline-block; margin: 5px 10px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>OpenChronicle Maintenance Report</h1>
        <p><strong>Generated:</strong> {report.timestamp.isoformat()}</p>
        <p><strong>Duration:</strong> {report.duration_ms}ms</p>
        <p><strong>System Path:</strong> {report.summary.get('system_path', 'Unknown')}</p>
    </div>
    
    <div class="section">
        <div class="section-header">Summary</div>
        <div class="section-content">
            <div class="metric"><strong>Sections:</strong> {report.summary.get('total_sections', 0)}</div>
            <div class="metric"><strong>Successful:</strong> <span class="success">{report.summary.get('successful_sections', 0)}</span></div>
            <div class="metric"><strong>Failed:</strong> <span class="failed">{report.summary.get('failed_sections', 0)}</span></div>
            <div class="metric"><strong>Warnings:</strong> <span class="warning">{report.summary.get('warnings_count', 0)}</span></div>
            <div class="metric"><strong>Errors:</strong> <span class="failed">{report.summary.get('errors_count', 0)}</span></div>
            <div class="metric"><strong>Completeness:</strong> {report.summary.get('report_completeness', 0):.1f}%</div>
        </div>
    </div>
"""
        
        for section_name, section_data in report.sections.items():
            status_class = section_data.get('status', 'unknown')
            html += f"""
    <div class="section">
        <div class="section-header">{section_data.get('title', section_name.title())}</div>
        <div class="section-content">
            <p><strong>Status:</strong> <span class="{status_class}">{section_data.get('status', 'unknown')}</span></p>
"""
            
            if "summary" in section_data:
                for key, value in section_data["summary"].items():
                    html += f"            <div class='metric'><strong>{key.replace('_', ' ').title()}:</strong> {value}</div>\n"
            
            if section_data.get("warnings"):
                html += "            <h4>Warnings:</h4><ul>\n"
                for warning in section_data["warnings"]:
                    html += f"                <li class='warning'>{warning}</li>\n"
                html += "            </ul>\n"
            
            if section_data.get("errors"):
                html += "            <h4>Errors:</h4><ul>\n"
                for error in section_data["errors"]:
                    html += f"                <li class='failed'>{error}</li>\n"
                html += "            </ul>\n"
            
            html += "        </div>\n    </div>\n"
        
        html += "</body></html>"
        return html
    
    def _assess_overall_health(self, report: MaintenanceReport) -> str:
        """Assess overall system health from report."""
        failed_sections = report.summary.get('failed_sections', 0)
        warnings_count = report.summary.get('warnings_count', 0)
        errors_count = report.summary.get('errors_count', 0)
        
        if failed_sections > 0 or errors_count > 0:
            return "unhealthy"
        elif warnings_count > 0:
            return "needs_attention"
        else:
            return "healthy"
    
    def _extract_critical_issues(self, report: MaintenanceReport) -> List[str]:
        """Extract critical issues from report."""
        critical_issues = []
        
        for section_name, section_data in report.sections.items():
            if section_data.get("status") == "failed":
                critical_issues.append(f"{section_name}: {section_data.get('error', 'Unknown error')}")
            
            for error in section_data.get("errors", []):
                critical_issues.append(f"{section_name}: {error}")
        
        return critical_issues
    
    def _generate_recommendations(self, report: MaintenanceReport) -> List[str]:
        """Generate recommendations based on report."""
        recommendations = []
        
        # Check health section
        health_section = report.sections.get("health", {})
        if health_section.get("status") == "failed":
            recommendations.append("Run system health diagnostics and fix critical issues")
        
        # Check configuration section
        config_section = report.sections.get("configuration", {})
        if not config_section.get("validation_results", {}).get("valid", True):
            recommendations.append("Review and fix configuration file issues")
        
        # Check performance section
        performance_section = report.sections.get("performance", {})
        if performance_section.get("warnings"):
            recommendations.append("Monitor system performance and consider resource upgrades")
        
        # Check storage section
        storage_section = report.sections.get("storage", {})
        if storage_section.get("warnings"):
            recommendations.append("Review storage usage and clean up unnecessary files")
        
        if not recommendations:
            recommendations.append("System appears healthy - continue regular maintenance schedule")
        
        return recommendations
    
    def _extract_key_metrics(self, report: MaintenanceReport) -> Dict[str, Any]:
        """Extract key metrics from report."""
        metrics = {}
        
        # System health metrics
        health_section = report.sections.get("health", {})
        if "summary" in health_section:
            metrics["health"] = health_section["summary"]
        
        # Performance metrics
        performance_section = report.sections.get("performance", {})
        if "summary" in performance_section:
            metrics["performance"] = performance_section["summary"]
        
        # Storage metrics
        storage_section = report.sections.get("storage", {})
        if "summary" in storage_section:
            metrics["storage"] = storage_section["summary"]
        
        return metrics
    
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


class QuickMaintenanceReporter(IMaintenanceReporter):
    """Quick maintenance reporter for basic reports."""
    
    def __init__(self, base_path: Path, logger=None):
        self.base_path = Path(base_path).resolve()
        self.logger = logger or get_logger()
    
    async def generate_report(self, include_sections: Optional[List[str]] = None) -> MaintenanceReport:
        """Generate quick maintenance report."""
        start_time = datetime.now()
        
        # Basic system check
        sections = {
            "basic_health": {
                "status": "success" if self.base_path.exists() else "failed",
                "base_path_exists": self.base_path.exists(),
                "timestamp": start_time.isoformat()
            }
        }
        
        summary = {
            "total_sections": 1,
            "successful_sections": 1 if self.base_path.exists() else 0,
            "failed_sections": 0 if self.base_path.exists() else 1
        }
        
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return MaintenanceReport(
            timestamp=start_time,
            dry_run=False,
            sections=sections,
            summary=summary,
            duration_ms=duration_ms
        )
    
    def format_report(self, report: MaintenanceReport, format_type: str = "text") -> str:
        """Format quick report."""
        if format_type == "json":
            return json.dumps(report.to_dict(), indent=2, default=str)
        else:
            return f"Quick Maintenance Report - {report.timestamp.isoformat()}\nSections: {len(report.sections)}"
    
    def save_report(self, report: MaintenanceReport, file_path: Optional[Path] = None) -> Path:
        """Save quick report."""
        if file_path is None:
            timestamp = report.timestamp.strftime("%Y%m%d_%H%M%S")
            file_path = self.base_path / f"quick_maintenance_report_{timestamp}.json"
        
        file_path = Path(file_path)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, indent=2, default=str)
        
        return file_path
    
    def export_report_data(self, report: MaintenanceReport) -> Dict[str, Any]:
        """Export quick report data."""
        return report.to_dict()
