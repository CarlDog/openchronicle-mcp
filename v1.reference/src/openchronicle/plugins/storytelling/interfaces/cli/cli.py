"""
Storytelling Plugin CLI Commands

This module provides CLI commands for storytelling functionality through the plugin system.
Provides minimal story commands demonstrating plugin CLI integration.
"""

import typer
from rich.console import Console


# Create storytelling command group
story_app = typer.Typer(help="Storytelling commands from plugin")
console = Console()


@story_app.command("status")
def story_status():
    """Show storytelling plugin status."""
    console.print("[green]✅ Storytelling plugin is active[/green]")
    console.print("Story commands are now provided by the storytelling plugin.")
    console.print("[dim]This demonstrates successful CLI command migration from core to plugin.[/dim]")


@story_app.command("info")
def story_info():
    """Show information about storytelling functionality."""
    console.print("[bold blue]🎭 OpenChronicle Storytelling Plugin[/bold blue]")
    console.print("")
    console.print("The storytelling plugin provides:")
    console.print("• Story creation and management")
    console.print("• Interactive narrative sessions")
    console.print("• Character and scene orchestration")
    console.print("• Memory-aware story generation")
    console.print("")
    console.print("[dim]Full story commands will be implemented in the plugin.[/dim]")


def register_cli(app: typer.Typer) -> None:
    """Register story CLI commands with the main app."""
    try:
        # Add the story command group
        app.add_typer(story_app, name="story")
        console.print("[green]✅ Registered storytelling CLI commands[/green]", style="dim")
    except Exception as e:
        console.print(f"[red]❌ Failed to register story CLI commands: {e}[/red]")
        raise
