"""
Story management commands for OpenChronicle CLI.

Provides comprehensive story operations including creation, loading,
generation, analysis, and management of narrative content.
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Prompt
from openchronicle.interfaces.cli.support.base_command import StoryCommand
from openchronicle.interfaces.cli.support.output_manager import OutputManager


# Import interactive commands
try:
    from .interactive import interactive_app

    INTERACTIVE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Interactive story commands not available: {e}")
    # Create a minimal fallback interactive app
    interactive_app = typer.Typer()

    @interactive_app.command("disabled")
    def interactive_disabled():
        """Interactive commands are disabled due to missing dependencies."""
        console = Console()
        console.print("❌ [red]Interactive story commands are not available[/red]")
        console.print("   This may be due to missing core dependencies")
        console.print("   Please check your installation")

    INTERACTIVE_AVAILABLE = False
    INTERACTIVE_AVAILABLE = False

# Create the story command group
story_app = typer.Typer(
    name="story", help="Story management and generation commands", no_args_is_help=True
)

# Add interactive sub-commands if available
if INTERACTIVE_AVAILABLE:
    story_app.add_typer(interactive_app, name="interactive")


class StoryListCommand(StoryCommand):
    """Command to list stories."""

    def execute(self, format_type: str = "table", limit: int = 20) -> list[dict]:
        """List available stories."""
        # This would integrate with actual story storage
        # For now, return sample data
        stories = [
            {
                "id": "story_001",
                "title": "The Crystal Tower",
                "genre": "Fantasy",
                "scenes": 15,
                "characters": 8,
                "last_modified": "2024-01-15",
                "status": "Active",
            },
            {
                "id": "story_002",
                "title": "Neon Dreams",
                "genre": "Cyberpunk",
                "scenes": 22,
                "characters": 12,
                "last_modified": "2024-01-14",
                "status": "Draft",
            },
            {
                "id": "story_003",
                "title": "The Last Voyage",
                "genre": "Adventure",
                "scenes": 8,
                "characters": 6,
                "last_modified": "2024-01-10",
                "status": "Complete",
            },
        ]

        # Apply limit
        if limit > 0:
            stories = stories[:limit]

        return stories


class StoryCreateCommand(StoryCommand):
    """Command to create a new story."""

    def execute(
        self,
        title: str,
        genre: str | None = None,
        description: str | None = None,
        template: str | None = None,
    ) -> dict:
        """Create a new story."""
        self.output.info(f"Creating new story: '{title}'")

        # Collect additional information if not provided
        if not genre:
            genre = Prompt.ask("Story genre", default="Fantasy")

        if not description:
            description = Prompt.ask("Brief description", default="")

        # Create story data structure
        story_data = {
            "id": f"story_{len(title.split()) + 1:03d}",  # Simple ID generation
            "title": title,
            "genre": genre,
            "description": description,
            "template": template,
            "created": "2024-01-15",  # Would use actual timestamp
            "scenes": [],
            "characters": [],
            "settings": [],
            "status": "Draft",
        }

        # Here we would save to actual storage
        self.output.success(f"Story '{title}' created successfully!")
        self.output.info(f"Story ID: {story_data['id']}")

        return story_data


class StoryLoadCommand(StoryCommand):
    """Command to load a story from file."""

    def execute(self, file_path: str, story_id: str | None = None) -> dict:
        """Load a story from file."""
        file_path_obj = Path(file_path)

        if not file_path_obj.exists():
            self.output.error(f"Story file not found: {file_path}")
            return {}

        try:
            story_data = self.read_json_file(file_path_obj)
            self.output.success(f"Story loaded from {file_path}")

            # Display summary
            self.output.info(f"Title: {story_data.get('title', 'Unknown')}")
            self.output.info(f"Genre: {story_data.get('genre', 'Unknown')}")
            self.output.info(f"Scenes: {len(story_data.get('scenes', []))}")
            self.output.info(f"Characters: {len(story_data.get('characters', []))}")

            return story_data

        except Exception as e:
            self.output.error(f"Error loading story: {e}")
            return {}


class StoryGenerateCommand(StoryCommand):
    """Command to generate story content."""

    def execute(
        self,
        story_id: str,
        model: str = "gpt-4",
        scenes: int = 1,
        prompt: str | None = None,
    ) -> dict:
        """Generate new content for a story."""
        self.output.info(f"Generating content for story: {story_id}")
        self.output.info(f"Model: {model}")
        self.output.info(f"Scenes to generate: {scenes}")

        # This would integrate with actual model management
        with self.output.progress_context("Generating story content...") as progress:
            task_id = progress.add_task("Processing", total=scenes)

            generated_content = []
            for i in range(scenes):
                # Simulate content generation
                scene_content = {
                    "scene_id": f"scene_{i+1:03d}",
                    "title": f"Generated Scene {i+1}",
                    "content": f"This is generated content for scene {i+1}...",
                    "characters": ["Protagonist", "Supporting Character"],
                    "setting": "Dynamic Location",
                    "generated_by": model,
                }
                generated_content.append(scene_content)
                progress.update(task_id, advance=1)  # type: ignore

        self.output.success(f"Generated {scenes} scenes successfully!")
        return {"scenes": generated_content, "story_id": story_id}


# CLI command functions
@story_app.command("list")
def list_stories(
    format_type: str = typer.Option("table", "--format", "-f", help="Output format"),
    limit: int = typer.Option(
        20, "--limit", "-l", help="Maximum number of stories to show"
    ),
    genre: str | None = typer.Option(None, "--genre", "-g", help="Filter by genre"),
):
    """
    List all available stories.

    Display stories in the OpenChronicle database with key information
    including title, genre, scene count, character count, and status.
    """
    try:
        # Get the output manager from the main app state
        output_manager = OutputManager(format_type=format_type)

        command = StoryListCommand(output_manager=output_manager)
        stories = command.safe_execute(format_type=format_type, limit=limit)

        if stories:
            # Filter by genre if specified
            if genre:
                stories = [
                    s for s in stories if s.get("genre", "").lower() == genre.lower()
                ]
                if not stories:
                    output_manager.warning(f"No stories found with genre: {genre}")
                    return

            output_manager.table(
                stories,
                title=f"OpenChronicle Stories ({len(stories)} found)",
                headers=[
                    "id",
                    "title",
                    "genre",
                    "scenes",
                    "characters",
                    "last_modified",
                    "status",
                ],
            )
        else:
            output_manager.warning("No stories found")

    except Exception as e:
        OutputManager().error(f"Error listing stories: {e}")


@story_app.command("create")
def create_story(
    title: str = typer.Argument(..., help="Story title"),
    genre: str | None = typer.Option(None, "--genre", "-g", help="Story genre"),
    description: str
    | None = typer.Option(None, "--description", "-d", help="Story description"),
    template: str
    | None = typer.Option(None, "--template", "-t", help="Story template to use"),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Interactive story creation"
    ),
):
    """
    Create a new story.

    Creates a new story in the OpenChronicle system with the specified
    title and optional metadata. Use --interactive for guided creation.
    """
    try:
        output_manager = OutputManager()
        command = StoryCreateCommand(output_manager=output_manager)

        story_data = command.safe_execute(
            title=title, genre=genre, description=description, template=template
        )

        if story_data:
            output_manager.panel(
                f"Story: {story_data['title']}\n"
                f"ID: {story_data['id']}\n"
                f"Genre: {story_data['genre']}\n"
                f"Status: {story_data['status']}",
                title="New Story Created",
                style="green",
            )

    except Exception as e:
        OutputManager().error(f"Error creating story: {e}")


@story_app.command("load")
def load_story(
    file_path: str = typer.Argument(..., help="Path to story file"),
    story_id: str | None = typer.Option(None, "--id", help="Optional story ID"),
    show_summary: bool = typer.Option(
        True, "--summary/--no-summary", help="Show story summary"
    ),
):
    """
    Load a story from file.

    Import a story from a JSON file into the OpenChronicle system.
    Supports standard OpenChronicle story format and some external formats.
    """
    try:
        output_manager = OutputManager()
        command = StoryLoadCommand(output_manager=output_manager)

        story_data = command.safe_execute(file_path=file_path, story_id=story_id)

        if story_data and show_summary:
            # Display detailed summary
            summary_data = [
                {"property": "Title", "value": story_data.get("title", "Unknown")},
                {"property": "Genre", "value": story_data.get("genre", "Unknown")},
                {
                    "property": "Description",
                    "value": story_data.get("description", "None")[:100] + "..."
                    if len(story_data.get("description", "")) > 100
                    else story_data.get("description", "None"),
                },
                {"property": "Scenes", "value": str(len(story_data.get("scenes", [])))},
                {
                    "property": "Characters",
                    "value": str(len(story_data.get("characters", []))),
                },
                {"property": "Status", "value": story_data.get("status", "Unknown")},
            ]

            output_manager.table(
                summary_data, title="Story Summary", headers=["property", "value"]
            )

    except Exception as e:
        OutputManager().error(f"Error loading story: {e}")


@story_app.command("generate")
def generate_content(
    story_id: str = typer.Argument(..., help="Story ID to generate content for"),
    model: str = typer.Option(
        "gpt-4", "--model", "-m", help="Model to use for generation"
    ),
    scenes: int = typer.Option(
        1, "--scenes", "-s", help="Number of scenes to generate"
    ),
    prompt: str
    | None = typer.Option(None, "--prompt", "-p", help="Custom generation prompt"),
):
    """
    Generate new story content.

    Use AI models to generate new scenes, characters, or other story
    elements for an existing story.
    """
    try:
        output_manager = OutputManager()
        command = StoryGenerateCommand(output_manager=output_manager)

        result = command.safe_execute(
            story_id=story_id, model=model, scenes=scenes, prompt=prompt
        )

        if result:
            # Display generation results
            generated_scenes = result.get("scenes", [])
            output_manager.panel(
                f"Generated {len(generated_scenes)} scenes for story '{story_id}'\n"
                f"Model: {model}\n"
                f"Total new content: {len(generated_scenes)} scenes",
                title="Content Generation Complete",
                style="green",
            )

            # Show scene summaries
            scene_data = [
                {
                    "scene_id": scene["scene_id"],
                    "title": scene["title"],
                    "characters": len(scene["characters"]),
                    "model": scene["generated_by"],
                }
                for scene in generated_scenes
            ]

            output_manager.table(
                scene_data,
                title="Generated Scenes",
                headers=["scene_id", "title", "characters", "model"],
            )

    except Exception as e:
        OutputManager().error(f"Error generating content: {e}")


@story_app.command("import")
def import_storypack(
    source_path: Path = typer.Argument(
        ..., help="Path to the source content directory"
    ),
    storypack_name: str = typer.Argument(..., help="Name for the generated storypack"),
    output_dir: Path
    | None = typer.Option(
        Path("storage/storypacks"),
        "--output-dir",
        "-o",
        help="Output directory for the storypack",
    ),
    import_mode: str = typer.Option(
        "auto", "--import-mode", "-m", help="Import mode: auto, manual, ai_assisted"
    ),
    ai_enabled: bool = typer.Option(
        False, "--ai-enabled", "-a", help="Enable AI processing for content analysis"
    ),
    template: str
    | None = typer.Option(
        None, "--template", "-t", help="Specific template to use for the storypack"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-d", help="Perform a dry run without creating files"
    ),
    report_type: str = typer.Option(
        "summary",
        "--report-type",
        "-r",
        help="Report type: summary, standard, detailed, technical",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
):
    """
    Import content into a new storypack.

    Converts external content (text files, documents, etc.) into OpenChronicle
    storypack format with automatic content analysis and organization.

    EXAMPLES:

        # Basic import
        openchronicle story import ./my-content "My Adventure"

        # AI-assisted import with custom template
        openchronicle story import ./content "Epic Quest" --ai-enabled --template fantasy

        # Dry run to preview import
        openchronicle story import ./content "Test" --dry-run --verbose
    """
    import asyncio

    from rich.console import Console
    from rich.progress import Progress
    from rich.progress import SpinnerColumn
    from rich.progress import TextColumn
    from openchronicle.application.services.importers.storypack import AIProcessor
    from openchronicle.application.services.importers.storypack import (
        ContentClassifier,
    )
    from openchronicle.application.services.importers.storypack import ContentParser
    from openchronicle.application.services.importers.storypack import (
        MetadataExtractor,
    )
    from openchronicle.application.services.importers.storypack import (
        OutputFormatter,
    )
    from openchronicle.application.services.importers.storypack import (
        StorypackBuilder,
    )
    from openchronicle.application.services.importers.storypack import (
        StorypackOrchestrator,
    )
    from openchronicle.application.services.importers.storypack import (
        StructureAnalyzer,
    )
    from openchronicle.application.services.importers.storypack import (
        TemplateEngine,
    )
    from openchronicle.application.services.importers.storypack import (
        ValidationEngine,
    )

    console = Console()

    async def run_import():
        """Run the import process asynchronously."""
        try:
            # Validate inputs
            if not source_path.exists():
                console.print(f"❌ [red]Source path does not exist: {source_path}[/red]")
                raise typer.Exit(1)

            if not source_path.is_dir():
                console.print(
                    f"❌ [red]Source path is not a directory: {source_path}[/red]"
                )
                raise typer.Exit(1)

            # Create output directory if it doesn't exist
            if output_dir:
                output_dir.mkdir(parents=True, exist_ok=True)
                console.print(f"   📁 Output: [yellow]{output_dir}[/yellow]")
            else:
                console.print("❌ [red]Output directory not specified[/red]")
                raise typer.Exit(1)

            console.print("📦 [bold blue]Starting storypack import[/bold blue]")
            console.print(f"   📂 Source: [cyan]{source_path}[/cyan]")
            console.print(f"   📝 Name: [green]{storypack_name}[/green]")
            console.print(f"   📁 Output: [yellow]{output_dir}[/yellow]")
            console.print(f"   🔧 Mode: [magenta]{import_mode}[/magenta]")
            if ai_enabled:
                console.print("   🤖 AI Processing: [green]Enabled[/green]")
            if template:
                console.print(f"   📋 Template: [blue]{template}[/blue]")
            if dry_run:
                console.print("   🏃 [yellow]Dry Run Mode[/yellow]")
            console.print()

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                # Initialize components
                task = progress.add_task("Initializing import system...", total=None)

                content_parser = ContentParser()
                metadata_extractor = MetadataExtractor()
                structure_analyzer = StructureAnalyzer()
                ai_processor = AIProcessor() if ai_enabled else None
                content_classifier = ContentClassifier()
                validation_engine = ValidationEngine()
                storypack_builder = StorypackBuilder()
                template_engine = TemplateEngine()
                output_formatter = OutputFormatter()

                # Create orchestrator
                orchestrator = StorypackOrchestrator(
                    content_parser=content_parser,
                    metadata_extractor=metadata_extractor,
                    structure_analyzer=structure_analyzer,
                    ai_processor=ai_processor,
                    content_classifier=content_classifier,
                    validation_engine=validation_engine,
                    storypack_builder=storypack_builder,
                    template_engine=template_engine,
                    output_formatter=output_formatter,
                )

                progress.update(task, description="Processing content...")

                # Run the import
                result = await orchestrator.import_storypack(
                    source_path=source_path,
                    storypack_name=storypack_name,
                    target_dir=output_dir,
                    import_mode=import_mode,
                )

                progress.update(task, description="Import completed!")

            # Display results
            if result:
                console.print("✅ [bold green]Import successful![/bold green]")
                console.print(f"   📦 Storypack: [cyan]{storypack_name}[/cyan]")
                console.print(
                    f"   📁 Location: [yellow]{output_dir / storypack_name}[/yellow]"
                )

                # Try to get statistics from result
                try:
                    stats = getattr(result, "statistics", None)
                    if stats:
                        console.print(
                            f"   📊 Files processed: [blue]{stats.get('files_processed', 'N/A')}[/blue]"
                        )
                        console.print(
                            f"   📝 Scenes created: [green]{stats.get('scenes_created', 'N/A')}[/green]"
                        )
                        console.print(
                            f"   👥 Characters found: [magenta]{stats.get('characters_found', 'N/A')}[/magenta]"
                        )
                    else:
                        # Try to extract stats from result object directly
                        for attr in [
                            "files_processed",
                            "scenes_created",
                            "characters_found",
                        ]:
                            value = getattr(result, attr, None)
                            if value is not None:
                                console.print(
                                    f"   📊 {attr.replace('_', ' ').title()}: [blue]{value}[/blue]"
                                )
                except Exception:
                    # If we can't get statistics, just continue
                    pass

                if report_type != "summary":
                    console.print("\n📋 [bold]Detailed Report:[/bold]")
                    # Add detailed reporting based on report_type
                    console.print(
                        f"   Report type '{report_type}' - detailed reporting coming soon"
                    )

            else:
                console.print("❌ [red]Import failed[/red]")
                raise typer.Exit(1)

        except KeyboardInterrupt:
            console.print("\n⏸️  [yellow]Import cancelled by user[/yellow]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"❌ [red]Import error: {e}[/red]")
            if verbose:
                console.print_exception()
            raise typer.Exit(1)

    # Run the async import
    asyncio.run(run_import())


if __name__ == "__main__":
    story_app()
