"""
System information and basic diagnostics commands for OpenChronicle CLI.

Provides system information, environment details, and basic diagnostic capabilities.
"""

import json
import os
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil
import typer

from openchronicle.interfaces.cli.support.base_command import SystemCommand
from openchronicle.interfaces.cli.support.output_manager import OutputManager


class SystemInfoCommand(SystemCommand):
    """Command to display system information."""

    def execute(self, detailed: bool = False) -> dict[str, Any]:
        """Get comprehensive system information."""
        info = {
            "system": {
                "platform": platform.system(),
                "platform_release": platform.release(),
                "platform_version": platform.version(),
                "architecture": platform.machine(),
                "hostname": platform.node(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "python_implementation": platform.python_implementation(),
            },
            "openchronicle": {
                "version": "1.0.0",  # TODO: Get from package metadata
                "installation_path": str(Path(__file__).parent.parent.parent.parent.parent),
                "config_path": str(Path.home() / ".openchronicle"),
            },
            "runtime": {
                "timestamp": datetime.now().isoformat(),
                "uptime": None,  # TODO: Track application uptime
                "memory_usage": dict(psutil.virtual_memory()._asdict()),
                "disk_usage": dict(psutil.disk_usage("/")._asdict())
                if platform.system() != "Windows"
                else dict(psutil.disk_usage("C:\\")._asdict()),
                "cpu_count": psutil.cpu_count(),
                "cpu_usage": psutil.cpu_percent(interval=1),
            },
        }

        if detailed:
            info["detailed"] = {
                "environment_variables": dict(
                    (k, v) for k, v in os.environ.items() if k.startswith(("OPENCHRONICLE_", "PATH", "PYTHON"))
                ),
                "python_path": sys.path,
                "installed_packages": self._get_installed_packages(),
            }

        return info

    def _get_installed_packages(self) -> list[str]:
        """Get list of installed Python packages."""
        try:
            import pkg_resources

            return [f"{pkg.project_name}=={pkg.version}" for pkg in pkg_resources.working_set]
        except ImportError:
            return ["Unable to list packages - pkg_resources not available"]


def system_info(
    detailed: bool = typer.Option(
        False,
        "--detailed",
        "-d",
        help="Show detailed system information",
    ),
    output_format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format (table, json, yaml)",
    ),
    save_to: str | None = typer.Option(
        None,
        "--save",
        "-s",
        help="Save output to file",
    ),
) -> None:
    """Display comprehensive system information and OpenChronicle configuration."""
    try:
        command = SystemInfoCommand()
        info = command.execute(detailed=detailed)

        output_manager = OutputManager()

        if output_format == "json":
            output = json.dumps(info, indent=2)
        elif output_format == "yaml":
            try:
                import yaml

                output = yaml.dump(info, default_flow_style=False)
            except ImportError:
                output_manager.error("YAML output requires PyYAML package")
                raise typer.Exit(1) from None
        else:  # table format
            output = output_manager.format_system_info(info)

        if save_to:
            Path(save_to).write_text(output)
            output_manager.success(f"System information saved to {save_to}")
        else:
            typer.echo(output)

    except Exception as e:
        output_manager.error(f"Failed to get system information: {e}")
        raise typer.Exit(1) from e


def system_diagnostics(
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
        help="Save diagnostic report to file",
    ),
) -> None:
    """Run comprehensive system diagnostics and generate report."""
    try:
        output_manager = OutputManager()
        diagnostics = {
            "timestamp": datetime.now().isoformat(),
            "system_checks": _run_system_checks(),
            "openchronicle_checks": _run_openchronicle_checks(),
            "performance_metrics": _get_performance_metrics(),
        }

        if output_format == "json":
            output = json.dumps(diagnostics, indent=2)
        else:
            output = output_manager.format_diagnostics_report(diagnostics)

        if save_report:
            report_file = f"openchronicle_diagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            Path(report_file).write_text(output)
            output_manager.success(f"Diagnostic report saved to {report_file}")

        typer.echo(output)

    except Exception as e:
        output_manager.error(f"Diagnostic check failed: {e}")
        raise typer.Exit(1) from e


def _run_system_checks() -> dict[str, Any]:
    """Run basic system health checks."""
    checks = {}

    # Memory check
    memory = psutil.virtual_memory()
    checks["memory"] = {
        "status": "healthy" if memory.percent < 80 else "warning" if memory.percent < 90 else "critical",
        "usage_percent": memory.percent,
        "available_gb": round(memory.available / (1024**3), 2),
    }

    # Disk space check
    disk = psutil.disk_usage("/" if platform.system() != "Windows" else "C:\\")
    checks["disk"] = {
        "status": "healthy" if disk.percent < 80 else "warning" if disk.percent < 90 else "critical",
        "usage_percent": disk.percent,
        "free_gb": round(disk.free / (1024**3), 2),
    }

    # CPU check
    cpu_percent = psutil.cpu_percent(interval=1)
    checks["cpu"] = {
        "status": "healthy" if cpu_percent < 70 else "warning" if cpu_percent < 85 else "critical",
        "usage_percent": cpu_percent,
        "core_count": psutil.cpu_count(),
    }

    return checks


def _run_openchronicle_checks() -> dict[str, Any]:
    """Run OpenChronicle-specific health checks."""
    checks = {}

    # Configuration check
    config_path = Path.home() / ".openchronicle"
    checks["configuration"] = {
        "status": "healthy" if config_path.exists() else "warning",
        "config_directory_exists": config_path.exists(),
        "config_files": list(config_path.glob("*.json")) if config_path.exists() else [],
    }

    # Dependencies check
    required_packages = ["typer", "rich", "psutil"]
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)

    checks["dependencies"] = {
        "status": "healthy" if not missing_packages else "critical",
        "missing_packages": missing_packages,
        "checked_packages": required_packages,
    }

    return checks


def _get_performance_metrics() -> dict[str, Any]:
    """Get current performance metrics."""
    return {
        "memory_usage_mb": round(psutil.Process().memory_info().rss / (1024**2), 2),
        "cpu_usage_percent": psutil.Process().cpu_percent(interval=0.1),
        "open_files": len(psutil.Process().open_files()),
        "thread_count": psutil.Process().num_threads(),
    }
