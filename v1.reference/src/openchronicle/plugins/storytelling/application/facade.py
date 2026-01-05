"""
Storytelling Facade - Public Interface for Story Processing

This facade provides a clean, simplified interface for story processing operations,
composing the underlying story processing services while maintaining clean
architecture boundaries.

The facade depends only on domain/shared/ports, not infrastructure.
"""

import logging
from typing import Any
from typing import Dict
from typing import Optional

from openchronicle.domain.entities import Story
from openchronicle.domain.ports.content_analysis_port import IContentAnalysisPort
from openchronicle.domain.ports.context_port import IContextPort
from openchronicle.domain.services import CharacterService
from openchronicle.domain.services import MemoryService
from openchronicle.domain.services import SceneService
from openchronicle.domain.services import StoryService
from openchronicle.shared.exceptions import ApplicationError

from .services import StoryProcessingConfig
from .services import StoryProcessingService


logger = logging.getLogger(__name__)


class StorytellingFacade:
    """
    Public facade for storytelling operations.

    This facade provides a simplified interface for story processing while
    composing the underlying services and maintaining clean architecture.
    """

    def __init__(
        self,
        story_service: StoryService,
        character_service: CharacterService,
        scene_service: SceneService,
        memory_service: MemoryService,
        context_port: IContextPort,
        content_analysis_port: IContentAnalysisPort,
        logging_service: Any = None,
        cache_service: Any = None,
        config: Optional[StoryProcessingConfig] = None,
    ):
        """
        Initialize the storytelling facade.

        Args:
            story_service: Domain story service
            character_service: Domain character service
            scene_service: Domain scene service
            memory_service: Domain memory service
            context_port: Context building port
            content_analysis_port: Content analysis port
            logging_service: Optional logging service
            cache_service: Optional cache service
            config: Optional processing configuration
        """
        self.story_service = story_service
        self.character_service = character_service
        self.scene_service = scene_service
        self.memory_service = memory_service
        self.logging_service = logging_service
        self.cache_service = cache_service

        # Create the internal story processing service
        self.story_processor = StoryProcessingService(
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

        # Session management
        self._sessions: Dict[str, Dict[str, Any]] = {}

    async def start_session(self, session_id: Optional[str] = None) -> str:
        """
        Start a new storytelling session.

        Args:
            session_id: Optional session identifier. If not provided, one will be generated.

        Returns:
            The session identifier

        Raises:
            ApplicationError: If session creation fails
        """
        try:
            if session_id is None:
                import uuid

                session_id = str(uuid.uuid4())

            # Initialize session state
            self._sessions[session_id] = {
                "created_at": None,  # Would use datetime.now()
                "story_id": None,
                "turn_count": 0,
                "context": {},
            }

            logger.info(f"Started storytelling session: {session_id}")
            return session_id

        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            raise ApplicationError(f"Session creation failed: {e}")

    async def process_turn(
        self, session_id: str, user_input: str, story_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """
        Process a story turn (user input and generate response).

        Args:
            session_id: Active session identifier
            user_input: User's story input
            story_id: Optional story identifier
            **kwargs: Additional processing parameters

        Returns:
            Dictionary containing the AI response and metadata

        Raises:
            ApplicationError: If processing fails
        """
        try:
            if session_id not in self._sessions:
                raise ApplicationError(f"Session {session_id} not found")

            session = self._sessions[session_id]

            # Use existing story_id from session or create/use provided one
            if story_id is None:
                story_id = session.get("story_id", "default")

            # Update session
            session["story_id"] = story_id
            session["turn_count"] += 1

            logger.info(f"Processing turn {session['turn_count']} for session {session_id}")

            # Delegate to story processing service
            result = await self.story_processor.process_user_input(user_input=user_input, story_id=story_id, **kwargs)

            return {
                "response": result,
                "session_id": session_id,
                "turn_count": session["turn_count"],
                "story_id": story_id,
            }

        except Exception as e:
            logger.error(f"Failed to process turn for session {session_id}: {e}")
            raise ApplicationError(f"Turn processing failed: {e}")

    async def generate_image(self, session_id: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Generate an image for the story.

        Args:
            session_id: Active session identifier
            prompt: Image generation prompt
            **kwargs: Additional generation parameters

        Returns:
            Dictionary containing image generation result

        Raises:
            ApplicationError: If generation fails
        """
        try:
            if session_id not in self._sessions:
                raise ApplicationError(f"Session {session_id} not found")

            logger.info(f"Generating image for session {session_id}")

            # Placeholder for image generation logic
            # This would integrate with image generation services
            result = {
                "image_url": None,
                "prompt": prompt,
                "status": "placeholder",
                "message": "Image generation not yet implemented",
            }

            return result

        except Exception as e:
            logger.error(f"Failed to generate image for session {session_id}: {e}")
            raise ApplicationError(f"Image generation failed: {e}")

    async def save_bookmark(self, session_id: str, note: str, **kwargs) -> Dict[str, Any]:
        """
        Save a bookmark/note for the current story state.

        Args:
            session_id: Active session identifier
            note: Bookmark note/description
            **kwargs: Additional bookmark parameters

        Returns:
            Dictionary containing bookmark save result

        Raises:
            ApplicationError: If saving fails
        """
        try:
            if session_id not in self._sessions:
                raise ApplicationError(f"Session {session_id} not found")

            session = self._sessions[session_id]
            story_id = session.get("story_id")

            if not story_id:
                raise ApplicationError("No active story in session")

            logger.info(f"Saving bookmark for session {session_id}")

            # Placeholder for bookmark logic
            # This would integrate with persistence services
            result = {
                "bookmark_id": f"bookmark_{session_id}_{session['turn_count']}",
                "note": note,
                "story_id": story_id,
                "turn_count": session["turn_count"],
                "status": "saved",
            }

            return result

        except Exception as e:
            logger.error(f"Failed to save bookmark for session {session_id}: {e}")
            raise ApplicationError(f"Bookmark save failed: {e}")

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a session.

        Args:
            session_id: Session identifier

        Returns:
            Session information or None if not found
        """
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[str]:
        """
        List all active session IDs.

        Returns:
            List of session identifiers
        """
        return list(self._sessions.keys())

    def close_session(self, session_id: str) -> bool:
        """
        Close and clean up a session.

        Args:
            session_id: Session identifier

        Returns:
            True if session was found and closed, False otherwise
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Closed session: {session_id}")
            return True
        return False
