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
from src.openchronicle.interfaces.cli.support.config_manager import ConfigManager
from src.openchronicle.interfaces.cli.support.output_manager import OutputManager


# Import command modules
commands_imported = {}
try:
    from src.openchronicle.interfaces.cli.commands.story import story_app

    commands_imported["story"] = story_app
except ImportError as e:
    print(f"Warning: Story commands not available: {e}")

try:
    from src.openchronicle.interfaces.cli.commands.models import models_app

    commands_imported["models"] = models_app
except ImportError as e:
    print(f"Warning: Models commands not available: {e}")

try:
    from src.openchronicle.interfaces.cli.commands.system import system_app

    commands_imported["system"] = system_app
except ImportError as e:
    print(f"Warning: System commands not available: {e}")

try:
    # Use unified config commands
    from src.openchronicle.interfaces.cli.commands.config import config_app

    commands_imported["config"] = config_app
except ImportError as e:
    print(f"Warning: Config commands not available: {e}")

try:
    from src.openchronicle.interfaces.cli.commands.test import test_app

    commands_imported["test"] = test_app
except ImportError as e:
    print(f"Warning: Test commands not available: {e}")

try:
    from src.openchronicle.interfaces.cli.commands.bookmarks import bookmarks_app

    commands_imported["bookmarks"] = bookmarks_app
except ImportError as e:
    print(f"Warning: Bookmarks commands not available: {e}")

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
output_format = typer.Option(
    "rich", "--format", "-f", help="Output format: rich, json, plain, table"
)

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
    version: bool
    | None = typer.Option(
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

    # Store in global variables for commands to access (simple approach)
    # Commands can import these directly or we can pass them via context


# Add command groups if available
if COMMANDS_AVAILABLE:
    try:
        if "story" in commands_imported:
            app.add_typer(commands_imported["story"], name="story")
        if "models" in commands_imported:
            app.add_typer(commands_imported["models"], name="models")
        if "system" in commands_imported:
            app.add_typer(commands_imported["system"], name="system")
        if "config" in commands_imported:
            app.add_typer(commands_imported["config"], name="config")
        if "test" in commands_imported:
            app.add_typer(commands_imported["test"], name="test")
        if "bookmarks" in commands_imported:
            app.add_typer(commands_imported["bookmarks"], name="bookmarks")
    except Exception as e:
        print(f"Warning: Error adding command groups: {e}")


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
        output_manager.error(
            "Core directory not found. Are you in the OpenChronicle root?"
        )
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

    output_manager.table(
        status_data, title="OpenChronicle Status", headers=["item", "value", "status"]
    )


if __name__ == "__main__":
    app()
