"""
System health monitoring commands for OpenChronicle CLI.

Provides comprehensive health checks, monitoring, and diagnostic capabilities.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import typer
from openchronicle.interfaces.cli.support.base_command import SystemCommand
from openchronicle.interfaces.cli.support.output_manager import OutputManager


class SystemHealthCommand(SystemCommand):
    """Command to perform system health checks."""

    def execute(self, comprehensive: bool = False) -> dict[str, Any]:
        """Perform system health diagnostics."""
        health_results = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "checks": {},
        }

        issues_found = []

        # Basic environment checks
        checks = {
            "core_directory": self.get_core_path().exists(),
            "config_directory": self.get_config_path().exists(),
            "main_py_exists": (Path.cwd() / "main.py").exists(),
            "requirements_exists": (Path.cwd() / "requirements.txt").exists(),
        }

        for check_name, result in checks.items():
            health_results["checks"][check_name] = {
                "status": "pass" if result else "fail",
                "result": result,
            }
            if not result:
                issues_found.append(f"Failed: {check_name}")

        # Core module availability checks
        core_modules = [
            "models",
            "narrative",
            "characters",
            "memory",
            "timeline",
            "scenes",
        ]

        module_status = {}
        for module in core_modules:
            try:
                self.import_core_module(module)
                module_status[module] = {"status": "available", "error": None}
            except ImportError as e:
                module_status[module] = {"status": "missing", "error": str(e)}
                issues_found.append(f"Module unavailable: {module}")

        health_results["checks"]["core_modules"] = module_status

        if comprehensive:
            # Comprehensive checks
            try:
                # Check database files
                db_files = list(Path.cwd().glob("**/*.db"))
                health_results["checks"]["databases"] = {
                    "count": len(db_files),
                    "files": [str(f) for f in db_files],
                    "status": "pass" if db_files else "warning",
                }

                # Check log files
                log_files = list(Path.cwd().glob("logs/*.log"))
                health_results["checks"]["logs"] = {
                    "count": len(log_files),
                    "recent_logs": [str(f) for f in log_files[-5:]],
                    "status": "pass",
                }

                # Check configuration files
                config_files = list(self.get_config_path().glob("*.json"))
                health_results["checks"]["configuration"] = {
                    "count": len(config_files),
                    "files": [f.name for f in config_files],
                    "status": "pass" if config_files else "warning",
                }

            except Exception as e:
                health_results["checks"]["comprehensive_error"] = {
                    "status": "error",
                    "error": str(e),
                }
                issues_found.append(f"Comprehensive check error: {e}")

        # Determine overall status
        if len(issues_found) == 0:
            health_results["overall_status"] = "healthy"
        elif len(issues_found) <= 2:
            health_results["overall_status"] = "warning"
        else:
            health_results["overall_status"] = "unhealthy"

        health_results["issues_found"] = issues_found
        health_results["issue_count"] = len(issues_found)

        return health_results


def health_check(
    comprehensive: bool = typer.Option(
        False,
        "--comprehensive",
        "-c",
        help="Run comprehensive health checks",
    ),
    output_format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format (table, json)",
    ),
    save_report: bool = typer.Option(
        False,
        "--save-report",
        "-s",
        help="Save health report to file",
    ),
) -> None:
    """Run comprehensive system health checks."""
    try:
        command = SystemHealthCommand()
        health_results = command.execute(comprehensive=comprehensive)

        output_manager = OutputManager()

        if output_format == "json":
            output = json.dumps(health_results, indent=2)
        else:
            output = output_manager.format_health_report(health_results)

        if save_report:
            report_file = f"health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            Path(report_file).write_text(json.dumps(health_results, indent=2))
            output_manager.success(f"Health report saved to {report_file}")

        typer.echo(output)

        # Exit with appropriate code based on health status
        if health_results["overall_status"] == "unhealthy":
            raise typer.Exit(1)
        elif health_results["overall_status"] == "warning":
            raise typer.Exit(2)

    except Exception as e:
        output_manager = OutputManager()
        output_manager.error(f"Health check failed: {e}")
        raise typer.Exit(1)
