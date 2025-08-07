"""
OpenChronicle Unified CLI Application.

Main entry point for the comprehensive OpenChronicle command-line interface.
Provides professional tools for story management, model operations, system
administration, and development workflows.
"""

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

# Add the current directory to Python path for imports
current_dir = Path(__file__).parent.parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from cli.core.output_manager import OutputManager
from cli.core.config_manager import ConfigManager

# Import command modules
try:
    from cli.commands.story import story_app
    from cli.commands.models import models_app
    from cli.commands.system import system_app
    from cli.commands.config import config_app
    COMMANDS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Some command modules not available: {e}")
    COMMANDS_AVAILABLE = False

# Initialize Typer app
app = typer.Typer(
    name="openchronicle",
    help="OpenChronicle: Professional Narrative AI Engine CLI",
    epilog="For detailed help on any command, use: openchronicle COMMAND --help",
    no_args_is_help=True,
    pretty_exceptions_enable=False  # We handle exceptions ourselves
)

# Global options
output_format = typer.Option(
    "rich", 
    "--format", "-f",
    help="Output format: rich, json, plain, table"
)

quiet_mode = typer.Option(
    False,
    "--quiet", "-q",
    help="Suppress non-essential output"
)

config_dir = typer.Option(
    None,
    "--config-dir",
    help="Custom configuration directory"
)


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
    config_dir_path: Optional[str] = config_dir,
    version: Optional[bool] = typer.Option(
        None, 
        "--version", "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit"
    )
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
    
    # Store in app state for commands to access
    app.state = {
        "output_manager": output_manager,
        "config_manager": config_manager
    }


# Add command groups if available
if COMMANDS_AVAILABLE:
    try:
        app.add_typer(story_app, name="story")
        app.add_typer(models_app, name="models")
        app.add_typer(system_app, name="system")
        app.add_typer(config_app, name="config")
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
    output_manager = getattr(app, 'state', {}).get('output_manager', OutputManager())
    
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
        headers=["component", "status", "version"]
    )


@app.command()
def status():
    """
    Quick system status check.
    
    Displays the current state of OpenChronicle components,
    configuration, and environment.
    """
    output_manager = getattr(app, 'state', {}).get('output_manager', OutputManager())
    config_manager = getattr(app, 'state', {}).get('config_manager', ConfigManager())
    
    # Basic environment check
    output_manager.info("Checking OpenChronicle environment...")
    
    # Check core directories
    core_path = Path.cwd() / "core"
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
        {"item": "Core Path", "value": str(core_path), "status": "✅" if core_path.exists() else "❌"},
        {"item": "Config Path", "value": str(config_path), "status": "✅" if config_path.exists() else "❌"},
        {"item": "CLI Config", "value": str(config_manager.cli_config_file), "status": "✅" if config_manager.cli_config_file.exists() else "⚠️"},
        {"item": "Output Format", "value": config_manager.get_setting("output_format", "rich"), "status": "✅"},
        {"item": "Python Version", "value": sys.version.split()[0], "status": "✅"},
    ]
    
    output_manager.table(
        status_data,
        title="OpenChronicle Status",
        headers=["item", "value", "status"]
    )


if __name__ == "__main__":
    app()
