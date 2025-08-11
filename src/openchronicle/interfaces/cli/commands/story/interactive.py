"""
Interactive story session command for OpenChronicle CLI.

Provides a rich interactive storytelling experience through the CLI framework.
"""

import asyncio

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.status import Status


from pathlib import Path

# Import the main application logic
try:
    from openchronicle.shared.logging_system import log_error
    from openchronicle.shared.logging_system import log_info
except ImportError:
    # Fallback logging if logging system not available
    def log_info(msg):
        print(f"INFO: {msg}")

    def log_error(msg):
        print(f"ERROR: {msg}")


# Import core components
try:
    from openchronicle.domain.models.model_orchestrator import ModelOrchestrator
    from openchronicle.domain.services.scenes.scene_orchestrator import (
        SceneOrchestrator,
    )
    from openchronicle.domain.services.story_loader import load_storypack
    from openchronicle.domain.services.timeline.timeline_orchestrator import (
        TimelineOrchestrator,
    )
    from openchronicle.infrastructure.content.analysis.orchestrator import (
        ContentAnalysisOrchestrator as ContentAnalyzer,
    )
    from openchronicle.infrastructure.content.context.orchestrator import (
        ContextOrchestrator,
    )
    from openchronicle.infrastructure.images.image_orchestrator import ImageType
    from openchronicle.infrastructure.memory.memory_orchestrator import (
        MemoryOrchestrator,
    )
    from openchronicle.infrastructure.persistence.database_orchestrator import (
        startup_health_check,
    )

    CORE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Core components not available for interactive mode: {e}")

    # Create placeholder functions and classes
    def load_storypack(*args, **kwargs):
        return None

    class ContextOrchestrator:
        def __init__(self):
            pass

    class MemoryOrchestrator:
        def __init__(self):
            pass

    class TimelineOrchestrator:
        def __init__(self):
            pass

    class SceneOrchestrator:
        def __init__(self):
            pass

    class ModelOrchestrator:
        def __init__(self):
            pass

    class ContentAnalyzer:
        def __init__(self):
            pass

    # No image engine factory in fallback

    class ImageType:
        pass

    def startup_health_check():
        return True

    CORE_AVAILABLE = False

# Security imports
from openchronicle.interfaces.cli.support.base_command import StoryCommand

# CLI core imports
from openchronicle.interfaces.cli.support.output_manager import OutputManager
from openchronicle.shared.security import SecurityThreatLevel
from openchronicle.shared.security import validate_user_input


class InteractiveStorySession:
    """Manages an interactive story session with professional CLI output."""

    def __init__(self, story_id: str, output_manager: OutputManager):
        self.story_id = story_id
        self.output_manager = output_manager
        self.console = Console()

        # Initialize orchestrators
        self.context_orchestrator = ContextOrchestrator()
        self.memory_orchestrator = MemoryOrchestrator()
        self.timeline_orchestrator = TimelineOrchestrator(story_id)
        self.scene_orchestrator = SceneOrchestrator(story_id)
        self.model_manager = ModelOrchestrator()

        self.story = None

    async def initialize(self):
        """Initialize the story session."""
        with Status("🚀 Initializing story session...", console=self.console):
            # Run startup health check
            try:
                await startup_health_check()
                self.output_manager.success("Database health check passed")
            except Exception as e:
                self.output_manager.warning(f"Database health check failed: {e}")

            # Load the story
            try:
                self.story = load_storypack(self.story_id)
                self.output_manager.success(
                    f"Story '{self.story_id}' loaded successfully"
                )
            except Exception as e:
                self.output_manager.error(f"Failed to load story: {e}")
                return False

            # Initialize model
            try:
                await self.model_manager.initialize_adapter(
                    self.model_manager.config["default_adapter"]
                )
                self.output_manager.success(
                    f"Model ready: {self.model_manager.default_adapter}"
                )
            except Exception as e:
                self.output_manager.warning(f"Model initialization failed: {e}")
                self.output_manager.info("System will use fallback mode")

            return True

    def secure_user_input(
        self, prompt: str, context_info: str = "user_interaction"
    ) -> str:
        """Secure wrapper for user input with validation."""
        try:
            raw_input = Prompt.ask(prompt).strip()

            # Validate the input
            validation_result = validate_user_input(raw_input, operation=context_info)

            if not validation_result.is_valid:
                if validation_result.threat_level == SecurityThreatLevel.CRITICAL:
                    self.output_manager.error("Input rejected due to security concerns")
                    log_error(
                        f"Critical security violation in user input: {validation_result.error_message}"
                    )
                    return ""
                self.output_manager.warning(
                    f"Input warning: {validation_result.error_message}"
                )
                return validation_result.sanitized_value or ""

            return validation_result.sanitized_value or raw_input

        except KeyboardInterrupt:
            raise
        except Exception as e:
            log_error(f"Error processing user input: {e}")
            return ""

    async def build_context_with_analysis(self, user_input: str, story):
        """Build context with analysis for the input."""
        # This would use the context orchestrator to build context
        # For now, return a basic context structure
        memory = await self.memory_orchestrator.load_current_memory(self.story_id)

        return {
            "full_context": f"Story: {story.get('title', 'Unknown')}\nUser: {user_input}\nMemory: {memory}",
            "memory": memory,
            "analysis": {},
            "routing": {
                "adapter": self.model_manager.default_adapter,
                "max_tokens": 1024,
                "temperature": 0.7,
            },
        }

    async def process_story_input(self, user_input: str):
        """Process a single story input."""
        with Status("🧠 Analyzing context...", console=self.console):
            context = await self.build_context_with_analysis(user_input, self.story)

        # Get routing recommendation from analysis
        routing = context.get("routing", {})
        preferred_adapter = routing.get("adapter", self.model_manager.default_adapter)
        max_tokens = routing.get("max_tokens", 1024)
        temperature = routing.get("temperature", 0.7)

        self.output_manager.info(
            f"Using {preferred_adapter} adapter (max_tokens: {max_tokens}, temp: {temperature})"
        )

        # Generate AI response
        with Status("✨ Generating response...", console=self.console):
            try:
                ai_response = await self.model_manager.generate_response(
                    context["full_context"],
                    adapter_name=preferred_adapter,
                    story_id=self.story_id,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            except Exception as e:
                self.output_manager.error(f"AI generation failed: {e}")
                ai_response = f"[Error generating response: {e}]"

        # Generate content flags from analysis and response
        analysis = context.get("analysis", {})
        if analysis:
            try:
                content_analyzer_instance = ContentAnalyzer(self.model_manager)
                content_flags = await content_analyzer_instance.generate_content_flags(
                    analysis, ai_response
                )
                for flag in content_flags:
                    await self.memory_orchestrator.add_memory_flag(
                        self.story_id, flag["name"], flag["value"]
                    )
                self.output_manager.info(
                    f"Generated {len(content_flags)} content flags"
                )
            except Exception as e:
                self.output_manager.warning(f"Flag generation failed: {e}")

        # Log the scene
        scene_id = self.scene_orchestrator.save_scene(
            user_input=user_input,
            model_output=ai_response,
            memory_snapshot=context["memory"],
            analysis_data=analysis,
        )

        # Add to recent events
        await self.memory_orchestrator.add_recent_event(
            self.story_id, f"User: {user_input}"
        )

        # Display the response
        self.output_manager.panel(ai_response, title="AI Response", style="blue")

        self.output_manager.info(f"Scene logged: {scene_id}")

    def print_memory_summary(self):
        """Print a summary of current memory state."""
        try:
            summary = asyncio.run(
                self.memory_orchestrator.get_memory_summary(self.story_id)
            )

            memory_data = [
                {"Aspect": "Characters", "Count": str(summary["character_count"])},
                {
                    "Aspect": "World State Keys",
                    "Count": str(len(summary["world_state_keys"])),
                },
                {"Aspect": "Active Flags", "Count": str(len(summary["active_flags"]))},
                {
                    "Aspect": "Recent Events",
                    "Count": str(summary["recent_events_count"]),
                },
                {"Aspect": "Last Updated", "Count": summary["last_updated"]},
            ]

            self.output_manager.table(
                memory_data, title="📚 Memory Summary", headers=["Aspect", "Count"]
            )
        except Exception as e:
            self.output_manager.error(f"Failed to get memory summary: {e}")

    def show_model_info(self):
        """Show information about available models."""
        try:
            adapters = self.model_manager.get_available_adapters()
            model_data = []

            for adapter_name in adapters:
                try:
                    info = self.model_manager.get_adapter_info(adapter_name)
                    model_data.append(
                        {
                            "Adapter": adapter_name,
                            "Provider": info["provider"],
                            "Model": info["model_name"],
                            "Status": "Ready"
                            if info["initialized"]
                            else "Not initialized",
                        }
                    )
                except Exception as e:
                    model_data.append(
                        {
                            "Adapter": adapter_name,
                            "Provider": "Unknown",
                            "Model": "Unknown",
                            "Status": f"Error: {e}",
                        }
                    )

            self.output_manager.table(
                model_data,
                title="🤖 Available Models",
                headers=["Adapter", "Provider", "Model", "Status"],
            )
        except Exception as e:
            self.output_manager.error(f"Failed to get model info: {e}")

    async def switch_model(self):
        """Switch the active model adapter."""
        try:
            adapters = self.model_manager.get_available_adapters()

            self.output_manager.info("Available Adapters:")
            for i, adapter in enumerate(adapters):
                self.console.print(f"{i+1}. {adapter}")

            choice = self.secure_user_input(
                "Select adapter number (or press Enter to cancel)", "adapter_selection"
            )
            if choice.isdigit() and 1 <= int(choice) <= len(adapters):
                adapter_name = adapters[int(choice) - 1]

                with Status(f"Initializing {adapter_name}...", console=self.console):
                    success = await self.model_manager.initialize_adapter(adapter_name)

                if success:
                    self.model_manager.default_adapter = adapter_name
                    self.output_manager.success(f"Switched to {adapter_name}")
                else:
                    self.output_manager.error(f"Failed to initialize {adapter_name}")

        except Exception as e:
            self.output_manager.error(f"Error switching model: {e}")

    async def show_rollback_options(self):
        """Show available rollback options."""
        try:
            rollback_points = await self.timeline_orchestrator.list_rollback_points()
            candidates = rollback_points.get("rollback_points", [])

            if not candidates:
                self.output_manager.info("No rollback candidates available.")
                return

            rollback_data = []
            for i, candidate in enumerate(candidates[:5]):  # Show top 5
                rollback_data.append(
                    {
                        "Option": str(i + 1),
                        "Scene": candidate.get("scene_summary", "Unknown"),
                        "Scene ID": candidate.get("scene_id", "Unknown"),
                    }
                )

            self.output_manager.table(
                rollback_data,
                title="⏪ Rollback Options",
                headers=["Option", "Scene", "Scene ID"],
            )

            choice = self.secure_user_input(
                "Enter number to rollback (or press Enter to skip)",
                "rollback_selection",
            )
            if choice.isdigit() and 1 <= int(choice) <= len(candidates):
                candidate = candidates[int(choice) - 1]
                rollback_id = candidate.get("rollback_id") or candidate.get("scene_id")

                if rollback_id:
                    with Status("⏪ Rolling back...", console=self.console):
                        result = await self.timeline_orchestrator.rollback_to_point(
                            rollback_id
                        )

                    if result.get("success"):
                        self.output_manager.success(
                            f"Rolled back to: {candidate.get('scene_summary', 'Unknown')}"
                        )
                    else:
                        self.output_manager.error(
                            f"Rollback failed: {result.get('error', 'Unknown error')}"
                        )
        except Exception as e:
            self.output_manager.error(f"Error showing rollback options: {e}")

    async def run_interactive_session(self):
        """Run the main interactive story session."""
        # Show welcome message
        self.output_manager.panel(
            f"Welcome to OpenChronicle Interactive Story: '{self.story_id}'\n\n"
            "Commands:\n"
            "• Type your story input normally\n"
            "• 'memory' - View memory summary\n"
            "• 'rollback' - See rollback options\n"
            "• 'models' - See available models\n"
            "• 'switch' - Switch model\n"
            "• 'keys' - Manage API keys\n"
            "• 'quit' - Exit session",
            title="🎭 Interactive Story Session",
            style="cyan",
        )

        while True:
            try:
                user_input = self.secure_user_input(
                    "\n[bold cyan]You:[/bold cyan] ", "story_input"
                )

                if user_input.lower() in ["quit", "exit", "q"]:
                    break
                if user_input.lower() == "memory":
                    self.print_memory_summary()
                    continue
                if user_input.lower() == "rollback":
                    await self.show_rollback_options()
                    continue
                if user_input.lower() == "models":
                    self.show_model_info()
                    continue
                if user_input.lower() == "switch":
                    await self.switch_model()
                    continue
                if user_input.lower() == "keys":
                    self.output_manager.info("API key management coming soon!")
                    continue
                if not user_input:
                    continue

                # Process story input
                await self.process_story_input(user_input)

            except KeyboardInterrupt:
                self.output_manager.info("\nSession interrupted by user")
                break
            except Exception as e:
                self.output_manager.error(f"Session error: {e}")
                log_error(f"Interactive session error: {e}")

        # Cleanup
        self.output_manager.panel(
            "Story session ended. Thank you for using OpenChronicle!",
            title="👋 Session Complete",
            style="green",
        )

        try:
            await self.model_manager.shutdown()
        except Exception as e:
            log_error(f"Error shutting down model manager: {e}")


class InteractiveCommand(StoryCommand):
    """Command for running interactive story sessions."""

    def __init__(self, output_manager: OutputManager):
        super().__init__(output_manager)

    def execute(
        self,
        story_id: str,
        non_interactive: bool = False,
        max_iterations: int = 50,
        input_text: str | None = None,
    ) -> bool:
        """Execute the interactive story command."""
        try:
            session = InteractiveStorySession(story_id, self.output_manager)

            # Run async initialization and session
            async def run_session():
                if await session.initialize():
                    if non_interactive:
                        # Run in non-interactive mode for testing
                        await self._run_non_interactive_mode(
                            session, input_text, max_iterations
                        )
                    else:
                        await session.run_interactive_session()
                    return True
                return False

            return asyncio.run(run_session())

        except Exception as e:
            self.output_manager.error(f"Failed to run interactive session: {e}")
            return False

    async def _run_non_interactive_mode(
        self,
        session: InteractiveStorySession,
        input_text: str | None,
        max_iterations: int,
    ):
        """Run in non-interactive mode for testing/automation."""
        self.output_manager.info("Running in non-interactive mode...")

        # Use provided input or default test input
        test_inputs = []
        if input_text:
            test_inputs = [input_text]
        else:
            test_inputs = [
                "Look around the forest clearing.",
                "Check my equipment.",
                "memory",
            ]

        iterations = min(len(test_inputs), max_iterations)

        for i, test_input in enumerate(test_inputs[:iterations]):
            self.output_manager.info(f"Input {i+1}: {test_input}")

            # Handle special commands
            if test_input.lower() == "memory":
                session.print_memory_summary()
                continue
            if test_input.lower() in ["models"]:
                session.show_model_info()
                continue

            # Process story input
            await session.process_story_input(test_input)

        self.output_manager.success(
            f"Non-interactive mode completed ({iterations} iterations)"
        )


# CLI command definition
interactive_app = typer.Typer(
    name="interactive", help="Interactive story session commands"
)


@interactive_app.command("start")
def start_interactive_session(
    story_id: str = typer.Argument("demo-story", help="Story ID to load"),
    non_interactive: bool = typer.Option(
        False, "--non-interactive", help="Run in non-interactive mode for testing"
    ),
    max_iterations: int = typer.Option(
        50, "--max-iterations", help="Maximum iterations in non-interactive mode"
    ),
    input_text: str
    | None = typer.Option(
        None, "--input", help="Single input to process in non-interactive mode"
    ),
):
    """
    Start an interactive story session.

    Launch a rich, interactive storytelling experience with the specified story.
    Provides full conversation mode with memory management, rollback options,
    and model switching capabilities.

    Examples:
        openchronicle story interactive start my-adventure
        openchronicle story interactive start demo-story --non-interactive --input "Hello world"
    """
    try:
        output_manager = OutputManager()
        command = InteractiveCommand(output_manager)

        success = command.execute(
            story_id=story_id,
            non_interactive=non_interactive,
            max_iterations=max_iterations,
            input_text=input_text,
        )

        if not success:
            raise typer.Exit(1)

    except Exception as e:
        OutputManager().error(f"Error starting interactive session: {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    interactive_app()
