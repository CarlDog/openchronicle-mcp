"""
Story management commands for OpenChronicle CLI.

Provides comprehensive story operations including creation, loading,
generation, analysis, and management of narrative content.
"""

import sys
from pathlib import Path
from typing import Optional, List

import typer
from rich.prompt import Prompt, Confirm

# Add parent directories to path for imports
current_dir = Path(__file__).parent.parent.parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from cli.core import StoryCommand, OutputManager

# Create the story command group
story_app = typer.Typer(
    name="story",
    help="Story management and generation commands",
    no_args_is_help=True
)


class StoryListCommand(StoryCommand):
    """Command to list stories."""
    
    def execute(self, format_type: str = "table", limit: int = 20) -> List[dict]:
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
                "status": "Active"
            },
            {
                "id": "story_002", 
                "title": "Neon Dreams",
                "genre": "Cyberpunk",
                "scenes": 22,
                "characters": 12,
                "last_modified": "2024-01-14",
                "status": "Draft"
            },
            {
                "id": "story_003",
                "title": "The Last Voyage",
                "genre": "Adventure",
                "scenes": 8,
                "characters": 6,
                "last_modified": "2024-01-10",
                "status": "Complete"
            }
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
        genre: Optional[str] = None,
        description: Optional[str] = None,
        template: Optional[str] = None
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
            "status": "Draft"
        }
        
        # Here we would save to actual storage
        self.output.success(f"Story '{title}' created successfully!")
        self.output.info(f"Story ID: {story_data['id']}")
        
        return story_data


class StoryLoadCommand(StoryCommand):
    """Command to load a story from file."""
    
    def execute(self, file_path: str, story_id: Optional[str] = None) -> dict:
        """Load a story from file."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            self.output.error(f"Story file not found: {file_path}")
            return {}
            
        try:
            story_data = self.read_json_file(file_path)
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
        prompt: Optional[str] = None
    ) -> dict:
        """Generate new content for a story."""
        self.output.info(f"Generating content for story: {story_id}")
        self.output.info(f"Model: {model}")
        self.output.info(f"Scenes to generate: {scenes}")
        
        # This would integrate with actual model management
        with self.output.progress_context("Generating story content...") as progress:
            task = progress.add_task("Processing", total=scenes)
            
            generated_content = []
            for i in range(scenes):
                # Simulate content generation
                scene_content = {
                    "scene_id": f"scene_{i+1:03d}",
                    "title": f"Generated Scene {i+1}",
                    "content": f"This is generated content for scene {i+1}...",
                    "characters": ["Protagonist", "Supporting Character"],
                    "setting": "Dynamic Location",
                    "generated_by": model
                }
                generated_content.append(scene_content)
                progress.update(task, advance=1)
                
        self.output.success(f"Generated {scenes} scenes successfully!")
        return {"scenes": generated_content, "story_id": story_id}


# CLI command functions
@story_app.command("list")
def list_stories(
    format_type: str = typer.Option("table", "--format", "-f", help="Output format"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of stories to show"),
    genre: Optional[str] = typer.Option(None, "--genre", "-g", help="Filter by genre")
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
                stories = [s for s in stories if s.get('genre', '').lower() == genre.lower()]
                if not stories:
                    output_manager.warning(f"No stories found with genre: {genre}")
                    return
                    
            output_manager.table(
                stories,
                title=f"OpenChronicle Stories ({len(stories)} found)",
                headers=["id", "title", "genre", "scenes", "characters", "last_modified", "status"]
            )
        else:
            output_manager.warning("No stories found")
            
    except Exception as e:
        OutputManager().error(f"Error listing stories: {e}")


@story_app.command("create")
def create_story(
    title: str = typer.Argument(..., help="Story title"),
    genre: Optional[str] = typer.Option(None, "--genre", "-g", help="Story genre"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Story description"),
    template: Optional[str] = typer.Option(None, "--template", "-t", help="Story template to use"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive story creation")
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
            title=title,
            genre=genre, 
            description=description,
            template=template
        )
        
        if story_data:
            output_manager.panel(
                f"Story: {story_data['title']}\n"
                f"ID: {story_data['id']}\n"
                f"Genre: {story_data['genre']}\n"
                f"Status: {story_data['status']}",
                title="New Story Created",
                style="green"
            )
            
    except Exception as e:
        OutputManager().error(f"Error creating story: {e}")


@story_app.command("load")
def load_story(
    file_path: str = typer.Argument(..., help="Path to story file"),
    story_id: Optional[str] = typer.Option(None, "--id", help="Optional story ID"),
    show_summary: bool = typer.Option(True, "--summary/--no-summary", help="Show story summary")
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
                {"property": "Description", "value": story_data.get("description", "None")[:100] + "..." if len(story_data.get("description", "")) > 100 else story_data.get("description", "None")},
                {"property": "Scenes", "value": str(len(story_data.get("scenes", [])))},
                {"property": "Characters", "value": str(len(story_data.get("characters", [])))},
                {"property": "Status", "value": story_data.get("status", "Unknown")}
            ]
            
            output_manager.table(
                summary_data,
                title="Story Summary",
                headers=["property", "value"]
            )
            
    except Exception as e:
        OutputManager().error(f"Error loading story: {e}")


@story_app.command("generate")
def generate_content(
    story_id: str = typer.Argument(..., help="Story ID to generate content for"),
    model: str = typer.Option("gpt-4", "--model", "-m", help="Model to use for generation"),
    scenes: int = typer.Option(1, "--scenes", "-s", help="Number of scenes to generate"),
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", help="Custom generation prompt")
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
            story_id=story_id,
            model=model,
            scenes=scenes,
            prompt=prompt
        )
        
        if result:
            # Display generation results
            generated_scenes = result.get("scenes", [])
            output_manager.panel(
                f"Generated {len(generated_scenes)} scenes for story '{story_id}'\n"
                f"Model: {model}\n"
                f"Total new content: {len(generated_scenes)} scenes",
                title="Content Generation Complete",
                style="green"
            )
            
            # Show scene summaries
            scene_data = [
                {
                    "scene_id": scene["scene_id"],
                    "title": scene["title"],
                    "characters": len(scene["characters"]),
                    "model": scene["generated_by"]
                }
                for scene in generated_scenes
            ]
            
            output_manager.table(
                scene_data,
                title="Generated Scenes",
                headers=["scene_id", "title", "characters", "model"]
            )
            
    except Exception as e:
        OutputManager().error(f"Error generating content: {e}")


if __name__ == "__main__":
    story_app()
