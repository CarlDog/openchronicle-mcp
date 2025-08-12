"""
System management commands for OpenChronicle CLI.

Provides comprehensive system administration including health checks,
diagnostics, maintenance, and configuration management.

This module coordinates all system-related CLI commands:
- System information and diagnostics
- Health monitoring and checks
- Maintenance operations  
- Database management
- Performance monitoring
"""

import typer

# Import command modules
from .system_info import system_info, system_diagnostics
from .system_health import health_check
from .system_maintenance import system_maintenance, storage_cleanup
from .database_commands import database_app


# Create the main system command group
system_app = typer.Typer(
    name="system",
    help="System administration and diagnostics commands",
    no_args_is_help=True,
)

# Add individual commands
system_app.command("info")(system_info)
system_app.command("diagnostics")(system_diagnostics)
system_app.command("health")(health_check)
system_app.command("maintenance")(system_maintenance)
system_app.command("cleanup")(storage_cleanup)

# Add database command group
system_app.add_typer(database_app, name="database")


# Performance monitoring placeholder
@system_app.command("performance")
def performance_status(
    monitoring_duration: int = typer.Option(
        30,
        "--duration",
        "-d",
        help="Monitoring duration in seconds",
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
        help="Save performance report to file",
    ),
) -> None:
    """Monitor system performance and resource usage."""
    # TODO: Implement when PerformanceOrchestrator is available
    from rich.console import Console
    console = Console()
    console.print("🚧 [yellow]Performance monitoring feature coming soon![/yellow]")
    console.print("   This will provide real-time system performance monitoring.")


# Export the main app
__all__ = ["system_app"]
