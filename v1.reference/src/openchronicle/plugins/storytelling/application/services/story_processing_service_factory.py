"""
Story Processing Service Factory - Application Layer

Provides factory methods for creating properly configured StoryProcessingService
instances with correct dependency injection for different environments.
"""

from typing import Any

from openchronicle.domain.services import CharacterService
from openchronicle.domain.services import MemoryService
from openchronicle.domain.services import SceneService
from openchronicle.domain.services import StoryService

from .story_processing_service import StoryProcessingConfig
from .story_processing_service import StoryProcessingService


class StoryProcessingServiceFactory:
    """
    Factory for creating StoryProcessingService instances with proper dependency injection.

    This factory handles the wiring of infrastructure dependencies to application services,
    maintaining clean hexagonal architecture boundaries.
    """

    @staticmethod
    def create_production_service(
        story_service: StoryService,
        character_service: CharacterService,
        scene_service: SceneService,
        memory_service: MemoryService,
        logging_service: Any,
        cache_service: Any,
        config: StoryProcessingConfig | None = None,
    ) -> StoryProcessingService:
        """
        Create a StoryProcessingService for production use.

        Args:
            story_service: Story domain service
            character_service: Character domain service
            scene_service: Scene domain service
            memory_service: Memory domain service
            logging_service: Logging service
            cache_service: Cache service
            config: Optional configuration

        Returns:
            Configured StoryProcessingService with production adapters
        """
        from ...infrastructure.adapters.content_adapter import StorytellingContentAdapter
        from ...infrastructure.adapters.context_adapter import StorytellingContextAdapter

        # Create production adapters using plugin-local implementations
        context_port = StorytellingContextAdapter()
        content_analysis_port = StorytellingContentAdapter()

        return StoryProcessingService(
            story_service=story_service,
            character_service=character_service,
            scene_service=scene_service,
            memory_service=memory_service,
            logging_service=logging_service,
            cache_service=cache_service,
            config=config or StoryProcessingConfig(),
            context_port=context_port,
            content_analysis_port=content_analysis_port,
        )

    @staticmethod
    def create_test_service(
        story_service: StoryService,
        character_service: CharacterService,
        scene_service: SceneService,
        memory_service: MemoryService,
        logging_service: Any,
        cache_service: Any,
        config: StoryProcessingConfig | None = None,
    ) -> StoryProcessingService:
        """
        Create a StoryProcessingService for testing.

        Args:
            story_service: Story domain service
            character_service: Character domain service
            scene_service: Scene domain service
            memory_service: Memory domain service
            logging_service: Logging service
            cache_service: Cache service
            config: Optional configuration

        Returns:
            Configured StoryProcessingService with mock adapters
        """
        # For testing, we can use the fallback mocks built into the service
        # or inject specific test doubles as needed
        return StoryProcessingService(
            story_service=story_service,
            character_service=character_service,
            scene_service=scene_service,
            memory_service=memory_service,
            logging_service=logging_service,
            cache_service=cache_service,
            config=config or StoryProcessingConfig(),
            context_port=None,  # Will use mock fallback
            content_analysis_port=None,  # Will use mock fallback
        )
