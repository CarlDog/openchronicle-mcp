"""
Application orchestrators for OpenChronicle.

Orchestrators coordinate complex workflows that involve multiple domain services,
repositories, and external systems. They implement the application's use cases
and ensure proper transaction boundaries.
"""

import logging
from abc import ABC
from datetime import datetime
from typing import Any
from typing import Protocol

from openchronicle.domain import Character
from openchronicle.domain import CharacterAnalyzer
from openchronicle.domain import MemoryState
from openchronicle.domain import ModelResponse
from openchronicle.domain import NarrativeContext
from openchronicle.domain import Scene
from openchronicle.domain import Story
from openchronicle.domain import StoryGenerator

from ..commands import CommandResult
from ..commands import CreateCharacterCommand
from ..commands import CreateStoryCommand
from ..commands import GenerateSceneCommand
from ..commands import SaveSceneCommand
from ..commands import UpdateStoryCommand


# Repository interfaces (to be implemented in infrastructure layer)
class StoryRepository(Protocol):
    """Repository interface for story persistence."""

    async def save(self, story: Story) -> bool:
        """Save a story."""
        ...

    async def get_by_id(self, story_id: str) -> Story | None:
        """Get story by ID."""
        ...

    async def delete(self, story_id: str) -> bool:
        """Delete a story."""
        ...


class CharacterRepository(Protocol):
    """Repository interface for character persistence."""

    async def save(self, character: Character) -> bool:
        """Save a character."""
        ...

    async def get_by_id(self, character_id: str) -> Character | None:
        """Get character by ID."""
        ...

    async def get_by_story(self, story_id: str) -> list[Character]:
        """Get all characters in a story."""
        ...


class SceneRepository(Protocol):
    """Repository interface for scene persistence."""

    async def save(self, scene: Scene) -> bool:
        """Save a scene."""
        ...

    async def get_by_id(self, scene_id: str) -> Scene | None:
        """Get scene by ID."""
        ...

    async def get_by_story(
        self, story_id: str, limit: int = 50, offset: int = 0
    ) -> list[Scene]:
        """Get scenes for a story."""
        ...


class MemoryManager(Protocol):
    """Memory management interface."""

    async def get_current_state(self, story_id: str) -> MemoryState:
        """Get current memory state."""
        ...

    async def update_memory(self, story_id: str, updates: dict[str, Any]) -> bool:
        """Update memory state."""
        ...


class ModelManager(Protocol):
    """Model management interface."""

    async def generate_response(
        self, context: NarrativeContext, model_preference: str | None = None
    ) -> ModelResponse:
        """Generate AI response."""
        ...


class BaseOrchestrator(ABC):
    """Base class for all orchestrators."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)


class StoryOrchestrator(BaseOrchestrator):
    """Orchestrates story-related operations."""

    def __init__(
        self,
        story_repo: StoryRepository,
        character_repo: CharacterRepository,
        scene_repo: SceneRepository,
        memory_manager: MemoryManager,
        story_generator: StoryGenerator,
    ):
        super().__init__()
        self.story_repo = story_repo
        self.character_repo = character_repo
        self.scene_repo = scene_repo
        self.memory_manager = memory_manager
        self.story_generator = story_generator

    async def create_story(self, command: CreateStoryCommand) -> CommandResult:
        """Create a new story."""
        try:
            # Create story entity
            story = Story(
                title=command.title,
                description=command.description,
                world_state=command.initial_world_state,
            )

            # Validate with domain service
            validation_result = self.story_generator.validate_story_concept(
                title=command.title,
                description=command.description,
                world_state=command.initial_world_state,
            )

            if not validation_result.is_valid:
                return CommandResult.failure(
                    "Story concept validation failed", validation_result.errors
                )

            # Save to repository
            success = await self.story_repo.save(story)
            if not success:
                return CommandResult.failure("Failed to save story")

            # Initialize memory state
            await self.memory_manager.update_memory(
                story.id,
                {
                    "world_state": command.initial_world_state,
                    "characters": {},
                    "events": [],
                    "flags": {},
                },
            )

            self.logger.info(f"Created story: {story.id}")
            return CommandResult.success("Story created successfully", story)

        except Exception as e:
            self.logger.error(f"Error creating story: {e}")
            return CommandResult.failure(f"Error creating story: {e!s}")

    async def update_story(self, command: UpdateStoryCommand) -> CommandResult:
        """Update an existing story."""
        try:
            story = await self.story_repo.get_by_id(command.story_id)
            if not story:
                return CommandResult.failure("Story not found")

            # Update story properties
            if command.title:
                story.title = command.title
            if command.description:
                story.description = command.description
            if command.status:
                story.status = command.status
            if command.world_state_updates:
                story.world_state.update(command.world_state_updates)

            story.updated_at = datetime.now()

            # Save changes
            success = await self.story_repo.save(story)
            if not success:
                return CommandResult.failure("Failed to update story")

            # Update memory if world state changed
            if command.world_state_updates:
                await self.memory_manager.update_memory(
                    story.id, {"world_state": command.world_state_updates}
                )

            return CommandResult.success("Story updated successfully", story)

        except Exception as e:
            self.logger.error(f"Error updating story: {e}")
            return CommandResult.failure(f"Error updating story: {e!s}")


class CharacterOrchestrator(BaseOrchestrator):
    """Orchestrates character-related operations."""

    def __init__(
        self,
        character_repo: CharacterRepository,
        story_repo: StoryRepository,
        memory_manager: MemoryManager,
        character_analyzer: CharacterAnalyzer,
    ):
        super().__init__()
        self.character_repo = character_repo
        self.story_repo = story_repo
        self.memory_manager = memory_manager
        self.character_analyzer = character_analyzer

    async def create_character(self, command: CreateCharacterCommand) -> CommandResult:
        """Create a new character."""
        try:
            # Verify story exists
            story = await self.story_repo.get_by_id(command.story_id)
            if not story:
                return CommandResult.failure("Story not found")

            # Create character entity
            character = Character(
                story_id=command.story_id,
                name=command.name,
                description=command.description,
                personality_traits=command.personality_traits,
                background=command.background,
                goals=command.goals,
            )

            # Validate character concept
            validation_result = self.character_analyzer.validate_character_concept(
                name=command.name,
                personality_traits=command.personality_traits,
                background=command.background,
                story_context=story.world_state,
            )

            if not validation_result.is_valid:
                return CommandResult.failure(
                    "Character concept validation failed", validation_result.errors
                )

            # Save character
            success = await self.character_repo.save(character)
            if not success:
                return CommandResult.failure("Failed to save character")

            # Update memory
            await self.memory_manager.update_memory(
                command.story_id,
                {
                    "characters": {
                        character.id: {
                            "name": character.name,
                            "personality": character.personality_traits,
                            "emotional_state": character.emotional_state,
                            "relationships": character.relationships,
                        }
                    }
                },
            )

            self.logger.info(f"Created character: {character.id}")
            return CommandResult.success("Character created successfully", character)

        except Exception as e:
            self.logger.error(f"Error creating character: {e}")
            return CommandResult.failure(f"Error creating character: {e!s}")


class NarrativeOrchestrator(BaseOrchestrator):
    """Orchestrates narrative generation operations."""

    def __init__(
        self,
        story_repo: StoryRepository,
        character_repo: CharacterRepository,
        scene_repo: SceneRepository,
        memory_manager: MemoryManager,
        model_manager: ModelManager,
        story_generator: StoryGenerator,
        character_analyzer: CharacterAnalyzer,
    ):
        super().__init__()
        self.story_repo = story_repo
        self.character_repo = character_repo
        self.scene_repo = scene_repo
        self.memory_manager = memory_manager
        self.model_manager = model_manager
        self.story_generator = story_generator
        self.character_analyzer = character_analyzer

    async def generate_scene(self, command: GenerateSceneCommand) -> CommandResult:
        """Generate a new scene."""
        try:
            # Get story and characters
            story = await self.story_repo.get_by_id(command.story_id)
            if not story:
                return CommandResult.failure("Story not found")

            characters = await self.character_repo.get_by_story(command.story_id)
            memory_state = await self.memory_manager.get_current_state(command.story_id)

            # Build narrative context
            context = NarrativeContext(
                story_id=command.story_id,
                user_input=command.user_input,
                characters={char.id: char for char in characters},
                memory_state=memory_state,
                scene_type=command.scene_type,
                participant_ids=command.participant_ids,
                location=command.location,
                additional_context=command.context_override or {},
            )

            # Generate coherent narrative
            narrative_result = self.story_generator.generate_coherent_narrative(
                context=context,
                participant_characters=[
                    char for char in characters if char.id in command.participant_ids
                ],
            )

            if not narrative_result.is_valid:
                return CommandResult.failure(
                    "Narrative generation validation failed", narrative_result.errors
                )

            # Get AI response
            model_response = await self.model_manager.generate_response(
                context, command.model_preference
            )

            if not model_response.content or model_response.finish_reason.startswith(
                "error"
            ):
                error_msg = getattr(model_response, "finish_reason", "Unknown error")
                return CommandResult.failure("AI generation failed", [error_msg])

            # Analyze character consistency
            character_updates = {}
            for char_id in command.participant_ids:
                character = next((c for c in characters if c.id == char_id), None)
                if character:
                    consistency_result = self.character_analyzer.analyze_consistency(
                        character=character,
                        scene_content=model_response.content,
                        previous_scenes=await self.scene_repo.get_by_story(
                            command.story_id, limit=10
                        ),
                    )

                    if consistency_result.has_updates:
                        character_updates[
                            char_id
                        ] = consistency_result.suggested_updates

            return CommandResult.success(
                "Scene generated successfully",
                {
                    "content": model_response.content,
                    "model_used": model_response.model_name,
                    "tokens_used": model_response.tokens_used,
                    "generation_time": model_response.generation_time,
                    "character_updates": character_updates,
                    "memory_snapshot": memory_state,
                },
            )

        except Exception as e:
            self.logger.error(f"Error generating scene: {e}")
            return CommandResult.failure(f"Error generating scene: {e!s}")

    async def save_scene(self, command: SaveSceneCommand) -> CommandResult:
        """Save a generated scene."""
        try:
            # Create scene entity
            scene = Scene(
                story_id=command.story_id,
                user_input=command.user_input,
                ai_response=command.ai_response,
                model_used=command.model_used,
                tokens_used=command.tokens_used,
                generation_time=command.generation_time,
                scene_type=command.scene_type,
                participant_ids=command.participant_ids,
                location=command.location,
            )

            # Save scene
            success = await self.scene_repo.save(scene)
            if not success:
                return CommandResult.failure("Failed to save scene")

            # Update character states
            if command.character_updates:
                for char_id, updates in command.character_updates.items():
                    character = await self.character_repo.get_by_id(char_id)
                    if character:
                        character.apply_updates(updates)
                        await self.character_repo.save(character)

            # Update memory
            memory_updates = {
                "events": [
                    {
                        "type": "scene_created",
                        "scene_id": scene.id,
                        "timestamp": scene.created_at.isoformat(),
                        "participants": command.participant_ids,
                        "location": command.location,
                    }
                ]
            }

            if command.character_updates:
                memory_updates["characters"] = command.character_updates

            await self.memory_manager.update_memory(command.story_id, memory_updates)

            self.logger.info(f"Saved scene: {scene.id}")
            return CommandResult.success("Scene saved successfully", scene)

        except Exception as e:
            self.logger.error(f"Error saving scene: {e}")
            return CommandResult.failure(f"Error saving scene: {e!s}")


# Export all orchestrators
__all__ = [
    "BaseOrchestrator",
    "CharacterOrchestrator",
    "CharacterRepository",
    "MemoryManager",
    "ModelManager",
    "NarrativeOrchestrator",
    "SceneRepository",
    "StoryOrchestrator",
    "StoryRepository",
]
