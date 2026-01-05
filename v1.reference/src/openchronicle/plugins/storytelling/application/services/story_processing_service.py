"""
Story Processing Service - Core Business Logic for Story Interactions

This service handles the complete story processing workflow:
- Context building with analysis
- AI response generation with routing
- Content flag generation
- Scene logging
- Memory updates

Extracted from legacy main.py to fit hexagonal architecture.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any

from openchronicle.domain.entities import Story
from openchronicle.domain.services import CharacterService
from openchronicle.domain.services import MemoryService
from openchronicle.domain.services import SceneService
from openchronicle.domain.services import StoryService
from openchronicle.shared.error_handling import NarrativeError
from openchronicle.shared.exceptions import ApplicationError
from openchronicle.shared.exceptions import ModelError
from openchronicle.shared.exceptions import ValidationError
from openchronicle.shared.retry_policy import RetryPolicy


if TYPE_CHECKING:
    from openchronicle.domain.ports.content_analysis_port import IContentAnalysisPort
    from openchronicle.domain.ports.context_port import IContextPort


@dataclass
class StoryProcessingConfig:
    """Configuration for story processing workflow."""

    default_max_tokens: int = 1024
    default_temperature: float = 0.7
    enable_content_flags: bool = True
    enable_scene_logging: bool = True
    enable_memory_updates: bool = True


class StoryProcessingService:
    """
    Core story processing service that orchestrates the complete workflow
    for handling user story inputs.
    """

    def __init__(
        self,
        story_service: StoryService,
        character_service: CharacterService,
        scene_service: SceneService,
        memory_service: MemoryService,
        logging_service: Any,  # Will be proper interface later
        cache_service: Any,  # Will be proper interface later
        config: StoryProcessingConfig,
        context_port: "IContextPort | None" = None,
        content_analysis_port: "IContentAnalysisPort | None" = None,
    ):
        self.story_service = story_service
        self.character_service = character_service
        self.scene_service = scene_service
        self.memory_service = memory_service
        self.logging_service = logging_service
        self.cache_service = cache_service
        self.config = config
        self.context_port = context_port
        self.content_analysis_port = content_analysis_port

    async def process_story_input(
        self,
        story_id: str,
        user_input: str,
        preferred_adapter: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """
        Process a single story input through the complete workflow.

        Args:
            story_id: The story identifier
            user_input: User's story input
            preferred_adapter: Optional specific adapter to use
            max_tokens: Optional token limit override
            temperature: Optional temperature override

        Returns:
            Dict containing processing results with keys:
            - ai_response: Generated AI response
            - scene_id: Logged scene identifier
            - context: Built context data
            - analysis: Content analysis data
            - content_flags: Generated content flags
            - routing: Adapter routing recommendations
        """

        # 1. Load story
        story = await self.story_service.get_story(story_id)
        if not story:
            raise ValueError(f"Story not found: {story_id}")

        # 2. Build context with analysis
        await self.logging_service.log_info(f"Building context for story input: {user_input[:50]}...")
        context = await self._build_context_with_analysis(user_input, story)

        # 3. Determine routing parameters
        routing = context.get("routing", {})
        adapter_name = preferred_adapter or routing.get("adapter", "openai")
        tokens = max_tokens or routing.get("max_tokens", self.config.default_max_tokens)
        temp = temperature or routing.get("temperature", self.config.default_temperature)

        await self.logging_service.log_info(f"Using adapter: {adapter_name}, tokens: {tokens}, temperature: {temp}")

        # 4. Generate AI response
        ai_response = await self._generate_ai_response(context["full_context"], story_id, adapter_name, tokens, temp)

        # 5. Generate content flags
        content_flags = []
        if self.config.enable_content_flags and context.get("analysis"):
            content_flags = await self._generate_content_flags(story_id, context["analysis"], ai_response)

        # 6. Log the scene
        scene_id = None
        if self.config.enable_scene_logging:
            scene_id = await self._log_scene(
                story_id,
                user_input,
                ai_response,
                context.get("memory"),
                context.get("analysis"),
            )

        # 7. Update memory with recent event
        if self.config.enable_memory_updates:
            await self.memory_service.add_recent_event(story_id, f"User: {user_input}", importance=1.0)

        return {
            "ai_response": ai_response,
            "scene_id": scene_id,
            "context": context,
            "analysis": context.get("analysis", {}),
            "content_flags": content_flags,
            "routing": routing,
            "adapter_used": adapter_name,
            "tokens_used": tokens,
            "temperature_used": temp,
        }

    async def _build_context_with_analysis(self, user_input: str, story: Story) -> dict[str, Any]:
        """Build context with intelligent analysis."""
        if self.context_port is not None:
            # Use injected port
            return await self.context_port.build_context_with_analysis(user_input, story.to_dict())
        else:
            # Fallback for backward compatibility
            from openchronicle.domain.ports.context_port import IContextPort

            class MockContextPort(IContextPort):
                async def build_context_with_analysis(
                    self, user_input: str, story_data: dict[str, Any]
                ) -> dict[str, Any]:
                    return {"user_input": user_input, "story_data": story_data, "context_type": "mock"}

                async def build_basic_context(self, user_input: str, story_data: dict[str, Any]) -> dict[str, Any]:
                    return {"user_input": user_input, "story_data": story_data, "context_type": "basic_mock"}

                async def extract_context_metadata(self, context: dict[str, Any]) -> dict[str, Any]:
                    return {"mock": True}

            mock_port = MockContextPort()
            return await mock_port.build_context_with_analysis(user_input, story.to_dict())

    async def _generate_ai_response(
        self,
        full_context: str,
        story_id: str,
        adapter_name: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Generate AI response using specified adapter and parameters."""
        from openchronicle.domain.models.model_orchestrator import ModelOrchestrator

        model_manager = ModelOrchestrator()
        # TODO: narrow exception types for better error handling
        policy = RetryPolicy(max_attempts=3, base_delay=0.4, retry_exceptions=(Exception,))

        async def _attempt():
            return await model_manager.generate_response(
                full_context,
                adapter_name=adapter_name,
                story_id=story_id,
                max_tokens=max_tokens,
                temperature=temperature,
            )

        try:
            ai_response = await policy.run(_attempt)
            await self.logging_service.log_info(f"Generated AI response: {ai_response[:100]}...")
        except (ModelError, NarrativeError) as e:  # Model/narrative failures after retries
            await self.logging_service.log_error(f"Model/narrative error after retries: {e}")
            return f"[Model error after retries: {e}]"
        except Exception as e:  # Final unexpected failure after retries
            await self.logging_service.log_error(f"Unexpected AI generation failure after retries: {e}")
            return f"[Unexpected error generating response after retries: {e}]"
        else:
            return ai_response

    async def _generate_content_flags(self, story_id: str, analysis: dict[str, Any], ai_response: str) -> list:
        """Generate content flags from analysis and AI response."""
        try:
            if self.content_analysis_port is not None:
                # Use injected port
                content_flags = await self.content_analysis_port.generate_content_flags(analysis, ai_response)
            else:
                # Fallback for backward compatibility
                from openchronicle.domain.ports.content_analysis_port import IContentAnalysisPort

                class MockContentAnalysisPort(IContentAnalysisPort):
                    async def generate_content_flags(
                        self, analysis: dict[str, Any], content: str
                    ) -> list[dict[str, Any]]:
                        return [{"name": "mock_flag", "value": "test", "type": "content"}]

                    async def analyze_content_sentiment(self, content: str) -> dict[str, Any]:
                        return {"sentiment": "neutral", "confidence": 0.5}

                    async def detect_content_themes(self, content: str) -> list[str]:
                        return ["general"]

                mock_port = MockContentAnalysisPort()
                content_flags = await mock_port.generate_content_flags(analysis, ai_response)

            # Add flags to memory
            for flag in content_flags:
                await self.memory_service.add_memory_flag(story_id, flag["name"], flag["value"], flag_type="content")

            await self.logging_service.log_info(f"Generated {len(content_flags)} content flags")
        except (ApplicationError, ValidationError) as e:
            await self.logging_service.log_error(f"Service/validation error in content flag generation: {e}")
            return []
        except Exception as e:
            await self.logging_service.log_error(f"Unexpected error in content flag generation: {e}")
            return []
        else:
            return content_flags

    async def _log_scene(
        self,
        story_id: str,
        user_input: str,
        ai_response: str,
        memory_snapshot: dict[str, Any] | None = None,
        analysis_data: dict[str, Any] | None = None,
    ) -> str | None:
        """Log the scene to the story timeline."""
        try:
            # Use the legacy scene orchestrator temporarily
            # TODO: Migrate to proper domain service once available
            from openchronicle.domain.services.scenes.scene_orchestrator import SceneOrchestrator

            scene_orchestrator = SceneOrchestrator(story_id)
            scene_id = scene_orchestrator.save_scene(
                user_input=user_input,
                model_output=ai_response,
                memory_snapshot=memory_snapshot,
                analysis_data=analysis_data,
            )

            await self.logging_service.log_info(f"Scene logged with ID: {scene_id}")
        except (ApplicationError, ValidationError) as e:
            await self.logging_service.log_error(f"Service/validation error in scene logging: {e}")
            return None
        except Exception as e:
            await self.logging_service.log_error(f"Unexpected error in scene logging: {e}")
            return None
        else:
            return scene_id


class StoryProcessingServiceFactory:
    """Factory for creating story processing service with dependencies."""

    @staticmethod
    def create(
        story_service: StoryService,
        character_service: CharacterService,
        scene_service: SceneService,
        memory_service: MemoryService,
        logging_service: Any,  # Will be proper interface later
        cache_service: Any,  # Will be proper interface later
        config: StoryProcessingConfig | None = None,
    ) -> StoryProcessingService:
        """Create a story processing service with all dependencies."""
        if config is None:
            config = StoryProcessingConfig()

        return StoryProcessingService(
            story_service=story_service,
            character_service=character_service,
            scene_service=scene_service,
            memory_service=memory_service,
            logging_service=logging_service,
            cache_service=cache_service,
            config=config,
        )
