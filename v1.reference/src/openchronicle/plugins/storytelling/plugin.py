from typing import Any
from typing import Dict
from typing import cast

from openchronicle.domain.ports.content_analysis_port import IContentAnalysisPort
from openchronicle.domain.services import CharacterService
from openchronicle.domain.services import MemoryService
from openchronicle.domain.services import SceneService
from openchronicle.domain.services import StoryService

from .application import StoryProcessingConfig
from .application import StorytellingFacade
from .infrastructure.adapters.content_adapter import StorytellingContentAdapter
from .infrastructure.adapters.context_adapter import StorytellingContextAdapter
from .infrastructure.adapters.memory_adapter import StorytellingMemoryAdapter
from .infrastructure.adapters.persistence_adapter import StorytellingPersistenceAdapter


def metadata() -> dict:
    return {"name": "storytelling", "version": "0.1.0"}


def register(container: Dict[str, Any]) -> None:
    """
    Register storytelling services and facade with the container.

    This function wires together the storytelling facade using services
    and ports from the container bootstrap, then overrides with storytelling-specific adapters.
    """
    # Create storytelling-specific adapters
    storytelling_persistence = StorytellingPersistenceAdapter()
    storytelling_memory = StorytellingMemoryAdapter()
    storytelling_content = StorytellingContentAdapter()
    # Bind storytelling adapters to domain ports in container
    container["persistence_port"] = storytelling_persistence
    container["memory_port"] = storytelling_memory
    container["content_analysis_port"] = storytelling_content

    # Get domain services from container (should be set by bootstrap)
    story_service = container.get("story_service")
    character_service = container.get("character_service")
    scene_service = container.get("scene_service")
    memory_service = container.get("memory_service")

    # Get optional services
    logging_service = container.get("logging_service")
    cache_service = container.get("cache_service")

    # Create infrastructure adapters (plugin-local)
    context_port = StorytellingContextAdapter()

    # Use the storytelling content adapter we just created
    content_analysis_port = storytelling_content

    # Create configuration
    config = StoryProcessingConfig()

    # Only create facade if we have the required dependencies
    if all([story_service, character_service, scene_service, memory_service, content_analysis_port]):
        # Create and register the storytelling facade
        story_facade = StorytellingFacade(
            story_service=cast(StoryService, story_service),
            character_service=cast(CharacterService, character_service),
            scene_service=cast(SceneService, scene_service),
            memory_service=cast(MemoryService, memory_service),
            context_port=context_port,
            content_analysis_port=cast(IContentAnalysisPort, content_analysis_port),
            logging_service=logging_service,
            cache_service=cache_service,
            config=config,
        )

        # Register facade in container
        container["story_facade"] = story_facade
    else:
        # Log missing dependencies (if logging is available)
        missing = []
        if not story_service:
            missing.append("story_service")
        if not character_service:
            missing.append("character_service")
        if not scene_service:
            missing.append("scene_service")
        if not memory_service:
            missing.append("memory_service")
        if not content_analysis_port:
            missing.append("content_analysis_port/model_orchestrator")

        if logging_service:
            logging_service.warning(f"Storytelling plugin: Missing dependencies: {missing}")


def register_cli(app: Any) -> None:
    """
    Register storytelling CLI commands with the root CLI application.

    Args:
        app: The root CLI application (typically a Typer app)
    """
    try:
        from .interfaces.cli.cli import register_cli as _register_cli

        _register_cli(app)
    except Exception as e:
        # Don't crash the app if CLI wiring fails
        print(f"[warn] storytelling CLI registration failed: {e}")
