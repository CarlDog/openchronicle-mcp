"""
OpenChronicle Unified CLI Application.

Main entry point for the comprehensive OpenChronicle command-line interface.
Provides professional tools for story management, model operations, system
administration, and development workflows.
"""

import sys
from pathlib import Path

import typer
from rich.console import Console

from openchronicle.interfaces.cli.support.config_manager import ConfigManager
from openchronicle.interfaces.cli.support.output_manager import OutputManager
from openchronicle.shared.centralized_config import CentralizedConfigManager
from openchronicle.shared.logging_system import log_error
from openchronicle.shared.logging_system import log_info
from openchronicle.shared.logging_system import log_warning


# Import core system command modules (plugin-agnostic commands)
commands_imported = {}

try:
    from openchronicle.interfaces.cli.commands.models import models_app

    commands_imported["models"] = models_app
except ImportError as e:
    log_warning(f"Models commands not available: {e}", context_tags=["cli", "import", "models"])

try:
    from openchronicle.interfaces.cli.commands.system import system_app

    commands_imported["system"] = system_app
except ImportError as e:
    log_warning(f"System commands not available: {e}", context_tags=["cli", "import", "system"])

try:
    # Use unified config commands
    from openchronicle.interfaces.cli.commands.config import config_app

    commands_imported["config"] = config_app
except ImportError as e:
    log_warning(f"Config commands not available: {e}", context_tags=["cli", "import", "config"])

try:
    from openchronicle.interfaces.cli.commands.bookmarks import bookmarks_app

    commands_imported["bookmarks"] = bookmarks_app
except ImportError as e:
    log_warning(f"Bookmarks commands not available: {e}", context_tags=["cli", "import", "bookmarks"])

COMMANDS_AVAILABLE = len(commands_imported) > 0

# Initialize Typer app
app = typer.Typer(
    name="openchronicle",
    help="OpenChronicle: Professional Narrative AI Engine CLI",
    epilog="For detailed help on any command, use: openchronicle COMMAND --help",
    no_args_is_help=True,
    pretty_exceptions_enable=False,  # We handle exceptions ourselves
)

# Global options
output_format = typer.Option("rich", "--format", "-f", help="Output format: rich, json, plain, table")

quiet_mode = typer.Option(False, "--quiet", "-q", help="Suppress non-essential output")

config_dir = typer.Option(None, "--config-dir", help="Custom configuration directory")


def version_callback(value: bool):
    """Display version information."""
    if value:
        console = Console()
        console.print("🔮 [bold blue]OpenChronicle CLI[/bold blue] v1.0.0")
        console.print("Professional Narrative AI Engine")
        console.print("https://github.com/OpenChronicle/openchronicle-core")
        raise typer.Exit()


@app.callback()
def main(
    format: str = output_format,
    quiet: bool = quiet_mode,
    config_dir_path: str | None = config_dir,
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """
    OpenChronicle: Professional Narrative AI Engine CLI

    A comprehensive command-line interface for managing stories, models,
    characters, and all aspects of the OpenChronicle narrative AI system.

    QUICK START:

        # Check system status
        openchronicle system status

        # List available models
        openchronicle models list

        # Create a new story
        openchronicle story create "My Adventure"

        # Configure CLI preferences
        openchronicle config set output_format rich

    EXAMPLES:

        # Story Management
        openchronicle story list --format table
        openchronicle story load samples/fantasy-adventure.json
        openchronicle story generate --model gpt-4 --scenes 3

        # Model Operations
        openchronicle models test --provider openai
        openchronicle models benchmark --quick
        openchronicle models configure ollama --endpoint http://localhost:11434

        # System Administration
        openchronicle system backup --target ./backups/
        openchronicle system migrate --from v0.9 --to v1.0
        openchronicle system health-check --verbose
    """
    # Initialize global managers
    output_manager = OutputManager(format_type=format, quiet=quiet)
    config_manager = ConfigManager(config_dir=config_dir_path)

    # Explicit storage provisioning (replaces previous implicit side effects in config manager)
    try:
        sys_config_mgr = CentralizedConfigManager()
        sys_config_mgr.provision_storage()
        log_info(
            "Storage directories provisioned",
            context_tags=["cli", "provision", "success"],
        )
    except (OSError, RuntimeError, ValueError) as e:
        log_error(
            f"Storage provisioning failed: {e}",
            context_tags=["cli", "provision", "error"],
        )

    # Store in global variables for commands to access (simple approach)
    # Commands can import these directly or we can pass them via context


# Add command groups if available
if COMMANDS_AVAILABLE:
    try:
        if "models" in commands_imported:
            app.add_typer(commands_imported["models"], name="models")
        if "system" in commands_imported:
            app.add_typer(commands_imported["system"], name="system")
        if "config" in commands_imported:
            app.add_typer(commands_imported["config"], name="config")
        if "bookmarks" in commands_imported:
            app.add_typer(commands_imported["bookmarks"], name="bookmarks")
    except (RuntimeError, ValueError, KeyError, TypeError) as e:
        log_warning(
            f"Error adding core command groups: {e}",
            context_tags=["cli", "commands", "error"],
        )


def _wire_plugin_cli(app):
    """Hook for plugin CLI registration (no core discovery).

    Plugins should call register_cli(app) from their own bootstrap paths.
    Core does not import plugin discovery to preserve boundaries.
    """
    log_info("Plugin CLI wiring hook ready (plugins self-register if present)", context_tags=["cli", "plugin"])


def run():
    """Main entry point that builds facade and wires plugin CLIs."""
    # Build facades/containers is handled by plugin bootstrap if present
    _wire_plugin_cli(app)  # allow plugins to self-register

    # Run the CLI
    app()


# Placeholder for command groups (will be implemented next)
@app.command()
def hello(name: str = typer.Argument("World")):
    """
    Hello command for testing CLI framework.

    This is a temporary command to verify the CLI is working correctly.
    It will be removed once the main command groups are implemented.
    """
    output_manager = getattr(app, "state", {}).get("output_manager", OutputManager())

    output_manager.success(f"Hello, {name}! 🎭")
    output_manager.info("OpenChronicle CLI is working correctly.")

    # Display some sample data in different formats
    sample_data = [
        {"component": "Model Management", "status": "Ready", "version": "1.0.0"},
        {"component": "Story Systems", "status": "Ready", "version": "1.0.0"},
        {"component": "Character Engine", "status": "Ready", "version": "1.0.0"},
    ]

    output_manager.table(
        sample_data,
        title="OpenChronicle Core Components",
        headers=["component", "status", "version"],
    )


@app.command()
def status():
    """
    Quick system status check.

    Displays the current state of OpenChronicle components,
    configuration, and environment.
    """
    output_manager = getattr(app, "state", {}).get("output_manager", OutputManager())
    config_manager = getattr(app, "state", {}).get("config_manager", ConfigManager())

    # Basic environment check
    output_manager.info("Checking OpenChronicle environment...")

    # Check core directories - updated for new structure
    core_path = Path.cwd() / "src" / "openchronicle"
    config_path = Path.cwd() / "config"

    if not core_path.exists():
        output_manager.error("Core directory not found. Are you in the OpenChronicle root?")
        return

    if not config_path.exists():
        output_manager.warning("Config directory not found")
    else:
        output_manager.success("OpenChronicle environment detected")

    # Display basic status
    status_data = [
        {
            "item": "Core Path",
            "value": str(core_path),
            "status": "✅" if core_path.exists() else "❌",
        },
        {
            "item": "Config Path",
            "value": str(config_path),
            "status": "✅" if config_path.exists() else "❌",
        },
        {
            "item": "CLI Config",
            "value": str(config_manager.cli_config_file),
            "status": "✅" if config_manager.cli_config_file.exists() else "⚠️",
        },
        {
            "item": "Output Format",
            "value": config_manager.get_setting("output_format", "rich"),
            "status": "✅",
        },
        {"item": "Python Version", "value": sys.version.split()[0], "status": "✅"},
    ]

    output_manager.table(status_data, title="OpenChronicle Status", headers=["item", "value", "status"])


if __name__ == "__main__":
    run()
