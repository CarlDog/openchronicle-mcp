"""
CLI interfaces for OpenChronicle.

This module provides command-line interfaces for interactive storytelling
and story management. It serves as the CLI interface layer in the hexagonal architecture.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn

from ...application import ApplicationFacade
from ...infrastructure import InfrastructureContainer, InfrastructureConfig


# ================================
# CLI Application Setup
# ================================

console = Console()


class CLIApplication:
    """Main CLI application with dependency injection."""
    
    def __init__(self):
        # Create default infrastructure configuration
        config = InfrastructureConfig(
            storage_backend="filesystem",
            storage_path="storage",
            cache_type="memory"
        )
        self.infrastructure = InfrastructureContainer(config)
        self.app_facade = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize the application facade."""
        if self._initialized:
            return
            
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Initializing OpenChronicle...", total=None)
            
            await self.infrastructure.initialize()
            self.app_facade = ApplicationFacade(
                story_orchestrator=self.infrastructure.get_story_orchestrator(),
                character_orchestrator=self.infrastructure.get_character_orchestrator(),
                scene_orchestrator=self.infrastructure.get_scene_orchestrator(),
                memory_manager=self.infrastructure.get_memory_manager()
            )
            
            progress.update(task, description="✅ Ready!")
            await asyncio.sleep(0.5)  # Brief pause to show completion
        
        self._initialized = True
    
    async def shutdown(self):
        """Clean shutdown."""
        if self._initialized:
            await self.infrastructure.shutdown()


# Global CLI application instance
cli_app = CLIApplication()


def async_command(f):
    """Decorator to handle async commands in Click."""
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


# ================================
# Main CLI Group
# ================================

@click.group()
@click.version_option(version="0.1.0", prog_name="OpenChronicle")
def cli():
    """
    🎭 OpenChronicle - Narrative AI Engine
    
    Advanced storytelling with AI-powered character consistency,
    memory management, and interactive scene generation.
    """
    pass


# ================================
# Story Commands
# ================================

@cli.group()
def story():
    """Story management commands."""
    pass


@story.command()
@click.option("--title", prompt="Story title", help="Title of the new story")
@click.option("--description", prompt="Description (optional)", default="", help="Story description")
@click.option("--genre", prompt="Genre (optional)", default="", help="Story genre")
@click.option("--interactive", "-i", is_flag=True, help="Interactive story creation")
@async_command
async def create(title: str, description: str, genre: str, interactive: bool):
    """Create a new story."""
    await cli_app.initialize()
    
    try:
        # Interactive mode for more detailed setup
        if interactive:
            console.print("\n[bold blue]📖 Interactive Story Creation[/bold blue]")
            
            # Gather additional details
            world_state = {}
            
            console.print("\n[yellow]World Building (press Enter to skip)[/yellow]")
            setting = Prompt.ask("Setting/Location", default="")
            if setting:
                world_state["setting"] = setting
                
            tech_level = Prompt.ask("Technology level", default="")
            if tech_level:
                world_state["tech_level"] = tech_level
                
            magic_level = Prompt.ask("Magic level", default="")
            if magic_level:
                world_state["magic_level"] = magic_level
        else:
            world_state = {}
        
        # Create the story
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Creating story...", total=None)
            
            result = await cli_app.app_facade.create_story(
                title=title,
                description=description if description else None,
                world_state=world_state,
                genre=genre if genre else None
            )
            
            if result.success:
                story = result.data
                progress.update(task, description="✅ Story created!")
                
                # Display success information
                console.print(f"\n[bold green]✅ Story Created Successfully![/bold green]")
                
                table = Table(show_header=False, box=None)
                table.add_row("[bold]ID:[/bold]", story.id)
                table.add_row("[bold]Title:[/bold]", story.title)
                table.add_row("[bold]Status:[/bold]", story.status.value)
                table.add_row("[bold]Created:[/bold]", story.created_at.strftime("%Y-%m-%d %H:%M:%S"))
                
                console.print(table)
                
                # Offer to create first character
                if interactive and Confirm.ask("\nWould you like to create your first character?"):
                    await create_character_interactive(story.id)
                    
            else:
                console.print(f"[bold red]❌ Failed to create story:[/bold red]")
                for error in result.errors:
                    console.print(f"  • {error}")
                
    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {str(e)}")
    finally:
        await cli_app.shutdown()


@story.command()
@click.option("--limit", "-l", default=10, help="Number of stories to show")
@async_command
async def list(limit: int):
    """List all stories."""
    await cli_app.initialize()
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Loading stories...", total=None)
            
            result = await cli_app.app_facade.list_stories(skip=0, limit=limit)
            
            if result.success:
                stories = result.data
                progress.update(task, description="✅ Stories loaded!")
                
                if not stories:
                    console.print("[yellow]No stories found. Create your first story with 'openchronicle story create'[/yellow]")
                else:
                    table = Table(title="📚 Your Stories")
                    table.add_column("Title", style="bold blue")
                    table.add_column("Status", style="green")
                    table.add_column("Created", style="dim")
                    table.add_column("ID", style="dim")
                    
                    for story in stories:
                        table.add_row(
                            story.title,
                            story.status.value,
                            story.created_at.strftime("%Y-%m-%d"),
                            story.id[:8] + "..."
                        )
                    
                    console.print(table)
            else:
                console.print(f"[bold red]❌ Failed to list stories:[/bold red]")
                for error in result.errors:
                    console.print(f"  • {error}")
                
    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {str(e)}")
    finally:
        await cli_app.shutdown()


@story.command()
@click.argument("story_id")
@async_command
async def show(story_id: str):
    """Show detailed information about a story."""
    await cli_app.initialize()
    
    try:
        result = await cli_app.app_facade.get_story(story_id)
        
        if result.success:
            story = result.data
            
            # Create a detailed panel
            content = f"""
[bold]Title:[/bold] {story.title}
[bold]Status:[/bold] {story.status.value}
[bold]Created:[/bold] {story.created_at.strftime("%Y-%m-%d %H:%M:%S")}
[bold]Updated:[/bold] {story.updated_at.strftime("%Y-%m-%d %H:%M:%S")}

[bold]Description:[/bold]
{story.description or "[dim]No description[/dim]"}

[bold]World State:[/bold]
{json.dumps(story.world_state, indent=2) if story.world_state else "[dim]No world state defined[/dim]"}
"""
            
            panel = Panel(
                content.strip(),
                title=f"📖 Story: {story.title}",
                border_style="blue"
            )
            console.print(panel)
            
        else:
            console.print(f"[bold red]❌ Story not found:[/bold red] {story_id}")
            
    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {str(e)}")
    finally:
        await cli_app.shutdown()


# ================================
# Character Commands
# ================================

@cli.group()
def character():
    """Character management commands."""
    pass


async def create_character_interactive(story_id: str) -> Optional[str]:
    """Interactive character creation helper."""
    console.print("\n[bold blue]👤 Interactive Character Creation[/bold blue]")
    
    name = Prompt.ask("Character name")
    background = Prompt.ask("Background (optional)", default="")
    appearance = Prompt.ask("Appearance (optional)", default="")
    
    # Personality traits
    console.print("\n[yellow]Personality Traits (0-10 scale, press Enter to skip)[/yellow]")
    personality_traits = {}
    
    trait_suggestions = ["courage", "wisdom", "charisma", "intelligence", "strength", "kindness"]
    for trait in trait_suggestions:
        value = Prompt.ask(f"{trait.capitalize()}", default="")
        if value and value.isdigit():
            personality_traits[trait] = float(value)
    
    # Goals
    goals = []
    console.print("\n[yellow]Character Goals (press Enter when done)[/yellow]")
    while True:
        goal = Prompt.ask("Goal", default="")
        if not goal:
            break
        goals.append(goal)
    
    # Create character
    result = await cli_app.app_facade.create_character(
        story_id=story_id,
        name=name,
        personality_traits=personality_traits,
        background=background if background else None,
        appearance=appearance if appearance else None,
        goals=goals
    )
    
    if result.success:
        character = result.data
        console.print(f"\n[bold green]✅ Character '{character.name}' created![/bold green]")
        console.print(f"[dim]Character ID: {character.id}[/dim]")
        return character.id
    else:
        console.print(f"[bold red]❌ Failed to create character:[/bold red]")
        for error in result.errors:
            console.print(f"  • {error}")
        return None


@character.command()
@click.option("--story-id", prompt="Story ID", help="ID of the story")
@click.option("--name", prompt="Character name", help="Name of the character")
@click.option("--interactive", "-i", is_flag=True, help="Interactive character creation")
@async_command
async def create(story_id: str, name: str, interactive: bool):
    """Create a new character."""
    await cli_app.initialize()
    
    try:
        if interactive:
            await create_character_interactive(story_id)
        else:
            # Simple character creation
            result = await cli_app.app_facade.create_character(
                story_id=story_id,
                name=name,
                personality_traits={},
                goals=[]
            )
            
            if result.success:
                character = result.data
                console.print(f"[bold green]✅ Character '{character.name}' created![/bold green]")
                console.print(f"[dim]Character ID: {character.id}[/dim]")
            else:
                console.print(f"[bold red]❌ Failed to create character:[/bold red]")
                for error in result.errors:
                    console.print(f"  • {error}")
                
    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {str(e)}")
    finally:
        await cli_app.shutdown()


@character.command()
@click.argument("story_id")
@async_command
async def list(story_id: str):
    """List characters in a story."""
    await cli_app.initialize()
    
    try:
        result = await cli_app.app_facade.get_story_characters(story_id)
        
        if result.success:
            characters = result.data
            
            if not characters:
                console.print("[yellow]No characters found in this story.[/yellow]")
            else:
                table = Table(title=f"👥 Characters in Story")
                table.add_column("Name", style="bold blue")
                table.add_column("Traits", style="green")
                table.add_column("Goals", style="yellow")
                table.add_column("ID", style="dim")
                
                for character in characters:
                    traits = ", ".join([f"{k}:{v}" for k, v in list(character.personality_traits.items())[:3]])
                    goals = ", ".join(character.goals[:2])
                    
                    table.add_row(
                        character.name,
                        traits[:30] + "..." if len(traits) > 30 else traits,
                        goals[:30] + "..." if len(goals) > 30 else goals,
                        character.id[:8] + "..."
                    )
                
                console.print(table)
        else:
            console.print(f"[bold red]❌ Failed to list characters:[/bold red]")
            for error in result.errors:
                console.print(f"  • {error}")
                
    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {str(e)}")
    finally:
        await cli_app.shutdown()


# ================================
# Scene Commands
# ================================

@cli.group()
def scene():
    """Scene generation and management commands."""
    pass


@scene.command()
@click.option("--story-id", prompt="Story ID", help="ID of the story")
@click.option("--interactive", "-i", is_flag=True, help="Interactive scene generation")
@async_command
async def generate(story_id: str, interactive: bool):
    """Generate a new scene."""
    await cli_app.initialize()
    
    try:
        # Get story characters for selection
        char_result = await cli_app.app_facade.get_story_characters(story_id)
        if not char_result.success or not char_result.data:
            console.print("[yellow]No characters found. Create characters first with 'openchronicle character create'[/yellow]")
            return
        
        characters = char_result.data
        
        if interactive:
            console.print("\n[bold blue]🎬 Interactive Scene Generation[/bold blue]")
            
            # Show available characters
            console.print("\n[yellow]Available Characters:[/yellow]")
            for i, char in enumerate(characters, 1):
                console.print(f"  {i}. {char.name} ({char.id[:8]}...)")
            
            # Select participants
            participant_indices = Prompt.ask(
                "Select participants (comma-separated numbers)", 
                default="1"
            ).split(",")
            
            participant_ids = []
            for idx in participant_indices:
                try:
                    char_idx = int(idx.strip()) - 1
                    if 0 <= char_idx < len(characters):
                        participant_ids.append(characters[char_idx].id)
                except ValueError:
                    continue
            
            if not participant_ids:
                participant_ids = [characters[0].id]  # Default to first character
            
            setting = Prompt.ask("Scene setting", default="A mysterious location")
            user_input = Prompt.ask("What happens in this scene?", default="The characters explore and interact")
            
        else:
            # Quick scene generation with all characters
            participant_ids = [char.id for char in characters]
            setting = "An important location in the story"
            user_input = "The characters interact and advance the story"
        
        # Generate the scene
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating scene with AI...", total=None)
            
            result = await cli_app.app_facade.generate_scene(
                story_id=story_id,
                setting=setting,
                participant_ids=participant_ids,
                user_input=user_input
            )
            
            if result.success:
                scene_data = result.data
                progress.update(task, description="✅ Scene generated!")
                
                # Display the generated scene
                participant_names = [char.name for char in characters if char.id in participant_ids]
                
                panel = Panel(
                    scene_data["content"],
                    title=f"🎭 New Scene: {setting}",
                    subtitle=f"Participants: {', '.join(participant_names)}",
                    border_style="green"
                )
                console.print(panel)
                
                # Show character updates if any
                if scene_data.get("character_updates"):
                    console.print("\n[bold yellow]Character Updates:[/bold yellow]")
                    for char_id, updates in scene_data["character_updates"].items():
                        char_name = next((c.name for c in characters if c.id == char_id), "Unknown")
                        console.print(f"  • {char_name}: {json.dumps(updates, indent=4)}")
                
            else:
                console.print(f"[bold red]❌ Failed to generate scene:[/bold red]")
                for error in result.errors:
                    console.print(f"  • {error}")
                
    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {str(e)}")
    finally:
        await cli_app.shutdown()


@scene.command()
@click.argument("story_id")
@click.option("--limit", "-l", default=5, help="Number of recent scenes to show")
@async_command
async def list(story_id: str, limit: int):
    """List recent scenes in a story."""
    await cli_app.initialize()
    
    try:
        result = await cli_app.app_facade.get_story_scenes(story_id, limit=limit)
        
        if result.success:
            scenes = result.data
            
            if not scenes:
                console.print("[yellow]No scenes found in this story.[/yellow]")
            else:
                for i, scene in enumerate(scenes, 1):
                    # Truncate content for list view
                    content_preview = scene.ai_response[:100] + "..." if len(scene.ai_response) > 100 else scene.ai_response
                    
                    panel = Panel(
                        f"[bold]Setting:[/bold] {scene.setting}\n"
                        f"[bold]Participants:[/bold] {len(scene.participants)} characters\n"
                        f"[bold]Content:[/bold] {content_preview}",
                        title=f"Scene #{i} - {scene.created_at.strftime('%Y-%m-%d %H:%M')}",
                        border_style="dim"
                    )
                    console.print(panel)
        else:
            console.print(f"[bold red]❌ Failed to list scenes:[/bold red]")
            for error in result.errors:
                console.print(f"  • {error}")
                
    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {str(e)}")
    finally:
        await cli_app.shutdown()


# ================================
# System Commands
# ================================

@cli.command()
@async_command
async def status():
    """Show system status and health."""
    await cli_app.initialize()
    
    try:
        health_status = await cli_app.infrastructure.health_check()
        
        console.print(f"\n[bold blue]🔧 OpenChronicle System Status[/bold blue]")
        console.print(f"[bold]Overall Status:[/bold] {health_status['status']}")
        console.print(f"[bold]Timestamp:[/bold] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        console.print("\n[bold]Components:[/bold]")
        for component, status in health_status["components"].items():
            status_color = "green" if status == "healthy" else "red"
            console.print(f"  • {component}: [{status_color}]{status}[/{status_color}]")
        
    except Exception as e:
        console.print(f"[bold red]❌ Error checking status:[/bold red] {str(e)}")
    finally:
        await cli_app.shutdown()


@cli.command()
def version():
    """Show version information."""
    console.print("""
[bold blue]🎭 OpenChronicle[/bold blue] v0.1.0

Narrative AI Engine with hexagonal architecture
Advanced character consistency and memory management
Interactive storytelling with multiple AI providers

[dim]Architecture: Clean/Hexagonal with CQRS pattern
Infrastructure: Async Python with dependency injection[/dim]
""")


if __name__ == "__main__":
    cli()
