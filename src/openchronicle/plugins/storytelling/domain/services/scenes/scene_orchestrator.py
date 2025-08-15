from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from openchronicle.domain.errors.persistence_errors import ListScenesError
from openchronicle.domain.errors.persistence_errors import LoadSceneError
from openchronicle.domain.errors.persistence_errors import RollbackSceneError
from openchronicle.domain.errors.persistence_errors import SaveSceneError
from openchronicle.domain.ports.persistence_inmemory import InMemorySqlitePersistence
from openchronicle.shared.logging_system import log_error
from openchronicle.shared.logging_system import log_info
from openchronicle.shared.logging_system import log_warning

from .management.labeling_system import LabelingSystem
from .management.scene_manager import SceneManager
from .persistence.scene_repository import SceneRepository
from .persistence.scene_serializer import SceneSerializer
from .shared.id_generator import SceneIdGenerator
from .shared.scene_models import SceneData
from .shared.scene_models import StructuredTags


# Avoid importing analysis submodules at module import time to prevent
# package-level side effects and stale import-cache issues.
if TYPE_CHECKING:
    from .analysis.mood_analyzer import MoodAnalyzer
    from .analysis.scene_statistics import SceneStatistics

"""
Scene Orchestrator - Unified Scene Management

This orchestrator coordinates between all scene subsystems:
- Scene persistence (scene_repository, scene_serializer)
- Scene analysis (scene_statistics, mood_analyzer)
- Scene management (scene_manager, labeling_system)
- Shared utilities (scene_models, id_generator)

Replaces the legacy monolithic scene_logger.py with a clean orchestration pattern.
"""


class SceneOrchestrator:
    """
    Main orchestrator for all scene operations.

    Provides a unified interface that coordinates between:
    - Persistence layer (saving, loading, storage)
    - Analysis layer (statistics, mood tracking, token analysis)
    - Management layer (labeling, rollback, organization)
    """

    def __init__(self, story_id: str, config: dict[str, Any] = None, *, persistence_port=None):
        """
        Initialize scene orchestrator for a specific story.

        Args:
            story_id: Story identifier
            config: Optional configuration dictionary
        """
        self.story_id = story_id
        self.config = config or {}

        # Initialize components with lazy loading
        self._repository = None
        self._serializer = None
        self._statistics_engine = None
        self._mood_analyzer = None
        self._scene_manager = None
        self._labeling_system = None
        self._id_generator = None

        # Performance metrics
        self.operation_count = 0
        self.last_operation_time = None

        # Dependency injection: allow caller to pass a persistence port; otherwise use in-memory default
        self._persistence_port = (
            persistence_port if persistence_port is not None else InMemorySqlitePersistence()
        )

        log_info(
            "SceneOrchestrator initialized",
            story_id=story_id,
            context_tags=["init"],
        )

    # ===== COMPONENT PROPERTIES (LAZY LOADING) =====

    @property
    def repository(self) -> SceneRepository:
        """Get scene repository (lazy loaded)."""
        if self._repository is None:
            self._repository = SceneRepository(self.story_id, self._persistence_port)
        return self._repository

    @property
    def serializer(self) -> SceneSerializer:
        """Get scene serializer (lazy loaded)."""
        if self._serializer is None:
            self._serializer = SceneSerializer()
        return self._serializer

    @property
    def statistics_engine(self) -> "SceneStatistics":
        """Get statistics engine (lazy loaded)."""
        if self._statistics_engine is None:
            from .analysis.scene_statistics import SceneStatistics

            self._statistics_engine = SceneStatistics(
                self.story_id, self._persistence_port
            )
        return self._statistics_engine

    @property
    def mood_analyzer(self) -> MoodAnalyzer:
        """Get mood analyzer (lazy loaded)."""
        if self._mood_analyzer is None:
            from .analysis.mood_analyzer import MoodAnalyzer

            self._mood_analyzer = MoodAnalyzer(
                self.story_id, self._persistence_port
            )
        return self._mood_analyzer

    @property
    def scene_manager(self) -> SceneManager:
        """Get scene manager (lazy loaded)."""
        if self._scene_manager is None:
            self._scene_manager = SceneManager(
                self.story_id, self.repository, self._persistence_port
            )
        return self._scene_manager

    @property
    def labeling_system(self) -> LabelingSystem:
        """Get labeling system (lazy loaded)."""
        if self._labeling_system is None:
            self._labeling_system = LabelingSystem(self.story_id, self.repository)
        return self._labeling_system

    @property
    def id_generator(self) -> SceneIdGenerator:
        """Get ID generator (lazy loaded)."""
        if self._id_generator is None:
            self._id_generator = SceneIdGenerator()
        return self._id_generator

    # ===== CORE SCENE OPERATIONS =====

    def save_scene(
        self,
        user_input: str,
        model_output: str,
        memory_snapshot: dict[str, Any] | None = None,
        flags: list[str] | None = None,
        context_refs: list[str] | None = None,
        analysis_data: dict[str, Any] | None = None,
        scene_label: str | None = None,
        token_manager: Any | None = None,
        model_name: str | None = None,
        structured_tags: dict[str, Any] | None = None,
    ) -> str:
        """
        Save a scene with all associated data.

        Args:
            user_input: User's input text
            model_output: Model's response text
            memory_snapshot: Memory state at scene time
            flags: Memory flags
            context_refs: Canon references used
            analysis_data: Content analysis results
            scene_label: Scene label for organization
            token_manager: Token manager instance for token tracking
            model_name: Model used for generation
            structured_tags: Additional structured metadata

        Returns:
            Generated scene identifier
        """
        try:
            # Generate scene ID
            scene_id = self.id_generator.generate_scene_id()

            # Create scene data object
            scene_data = SceneData(
                scene_id=scene_id,
                timestamp=datetime.now(UTC).isoformat(),
                user_input=user_input,
                model_output=model_output,
                memory_snapshot=memory_snapshot or {},
                flags=flags or [],
                context_refs=context_refs or [],
                analysis_data=analysis_data,
                scene_label=scene_label,
                model_name=model_name,
                structured_tags=StructuredTags(structured_tags or {}, token_manager),
            )

            # Save through repository
            try:
                success = self.repository.save_scene(scene_data)
            except SaveSceneError as e:
                log_error(
                    f"SaveSceneError: {e}",
                    story_id=self.story_id,
                    scene_id=scene_id,
                    context_tags=["save_scene"],
                )
                return ""

            if success:
                self._update_operation_metrics()
                log_info(
                    "Scene saved successfully",
                    story_id=self.story_id,
                    scene_id=scene_id,
                    context_tags=["save_scene"],
                )
                return scene_id
            log_error(
                "Failed to save scene",
                story_id=self.story_id,
                scene_id=scene_id,
                context_tags=["save_scene"],
            )

        except (ValueError, TypeError, RuntimeError, KeyError) as e:
            log_error(
                f"Error saving scene: {e}",
                story_id=self.story_id,
                context_tags=["save_scene"],
            )
            return ""
        else:
            return ""

    async def log_scene_fragment(self, story_id: str, fragment: dict[str, Any]) -> bool:
        """Log a scene fragment for interactive workflows.

        Accepts a preformatted fragment dict and persists it as a scene entry.

        Args:
            story_id: Story identifier (validated against orchestrator's story)
            fragment: Dict with keys like scene_id, user_input, ai_response, etc.

        Returns:
            True on successful persistence, False otherwise
        """
        try:
            if story_id != self.story_id:
                log_warning(
                    "log_scene_fragment called with mismatched story_id",
                    story_id=self.story_id,
                    context_tags=["log_scene_fragment", f"incoming={story_id}"],
                )

            user_input = fragment.get("user_input", "")
            model_output = fragment.get("ai_response", "")

            # Store the fragment metadata inside memory_snapshot for traceability
            memory_snapshot = {
                "fragment": {
                    k: v
                    for k, v in fragment.items()
                    if k not in {"user_input", "ai_response"}
                }
            }

            scene_label = fragment.get("action_type", "interaction_fragment")

            scene_id = self.save_scene(
                user_input=user_input,
                model_output=model_output,
                memory_snapshot=memory_snapshot,
                scene_label=scene_label,
            )

            return bool(scene_id)
        except (ValueError, TypeError, RuntimeError, KeyError) as e:
            log_error(
                f"Error logging scene fragment: {e}",
                story_id=self.story_id,
                context_tags=["log_scene_fragment"],
            )
            return False

    async def save_scene_async(
        self,
        user_input: str,
        model_output: str,
        memory_snapshot: dict[str, Any] | None = None,
        scene_label: str | None = None,
        **kwargs,
    ) -> str:
        """
        Async version of save_scene for integration tests.

        Args:
            user_input: User's input text
            model_output: Model's response text
            memory_snapshot: Memory state at scene time
            scene_label: Scene label for organization
            **kwargs: Additional parameters passed to save_scene

        Returns:
            Generated scene identifier
        """
        # Delegate to synchronous save_scene method
        scene_id = self.save_scene(
            user_input=user_input,
            model_output=model_output,
            memory_snapshot=memory_snapshot,
            scene_label=scene_label,
            **kwargs,
        )

        # If we have a memory_snapshot that contains a memory orchestrator, track the scene
        if memory_snapshot and hasattr(memory_snapshot, "get"):
            # Try to find a way to notify the memory orchestrator about the saved scene
            # For integration tests, we can use a simple approach
            try:
                # Use dependency injection instead of direct import
                # This should be injected through constructor, but for backward compatibility
                # we'll use a conditional import approach
                memory_port = getattr(self, "memory_port", None)
                if memory_port:
                    scene_data = {
                        "user_input": user_input,
                        "model_output": model_output,
                        "scene_label": scene_label,
                    }
                    # Use memory port interface instead of direct call
                    if hasattr(memory_port, "track_saved_scene"):
                        memory_port.track_saved_scene(scene_id, scene_data)
            except (RuntimeError, ValueError, KeyError, AttributeError, TypeError):
                pass  # Ignore errors for backward compatibility

        return scene_id

    def load_scene(self, scene_id: str) -> dict[str, Any] | None:
        """Load a scene by ID."""
        try:
            scene_data = self.repository.load_scene(scene_id)
            if scene_data:
                return self.serializer.serialize_scene_for_output(scene_data)
        except LoadSceneError as e:
            log_error(
                f"LoadSceneError: {e}",
                story_id=self.story_id,
                scene_id=scene_id,
                context_tags=["load_scene"],
            )
            return None
        except (ValueError, TypeError, RuntimeError, KeyError) as e:
            log_error(
                f"Unexpected error loading scene: {e}",
                story_id=self.story_id,
                scene_id=scene_id,
                context_tags=["load_scene"],
            )
            return None
        else:
            return None

    def list_scenes(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """List scenes with optional pagination."""
        try:
            scenes = self.repository.list_scenes(limit, offset)
            return [
                self.serializer.serialize_scene_for_output(scene) for scene in scenes
            ]
        except ListScenesError as e:
            log_error(
                f"ListScenesError: {e}",
                story_id=self.story_id,
                context_tags=["list_scenes"],
            )
            return []
        except (ValueError, TypeError, RuntimeError, KeyError) as e:
            log_error(
                f"Unexpected error listing scenes: {e}",
                story_id=self.story_id,
                context_tags=["list_scenes"],
            )
            return []

    # ===== SCENE ANALYSIS OPERATIONS =====

    def get_scenes_with_long_turns(self) -> list[dict[str, Any]]:
        """Get scenes with long turns using statistics engine."""
        return self.statistics_engine.get_scenes_with_long_turns()

    def get_token_usage_stats(self) -> dict[str, Any]:
        """Get token usage statistics."""
        return self.statistics_engine.get_token_usage_stats()

    def get_scene_summary_stats(self) -> dict[str, Any]:
        """Get comprehensive scene statistics."""
        return self.statistics_engine.get_scene_summary_stats()

    # ===== MOOD ANALYSIS OPERATIONS =====

    def get_scenes_by_mood(self, mood: str) -> list[dict[str, Any]]:
        """Get scenes filtered by mood."""
        return self.mood_analyzer.get_scenes_by_mood(mood)

    def get_character_mood_timeline(self, character_name: str) -> list[dict[str, Any]]:
        """Get character mood timeline."""
        return self.mood_analyzer.get_character_mood_timeline(character_name)

    def get_scenes_by_type(self, scene_type: str) -> list[dict[str, Any]]:
        """Get scenes filtered by type."""
        return self.mood_analyzer.get_scenes_by_type(scene_type)

    # ===== LABELING OPERATIONS =====

    def update_scene_label(self, scene_id: str, scene_label: str) -> bool:
        """Update scene label."""
        return self.labeling_system.update_scene_label(scene_id, scene_label)

    def get_scenes_by_label(self, scene_label: str) -> list[dict[str, Any]]:
        """Get scenes by label."""
        return self.labeling_system.get_scenes_by_label(scene_label)

    def get_labeled_scenes(self) -> list[dict[str, Any]]:
        """Get all labeled scenes."""
        return self.labeling_system.get_labeled_scenes()

    # ===== MANAGEMENT OPERATIONS =====

    def rollback_to_scene(self, scene_id: str) -> bool:
        """Rollback to specific scene."""
        try:
            return self.scene_manager.rollback_to_scene(scene_id)
        except RollbackSceneError as e:
            log_error(
                f"RollbackSceneError: {e}",
                story_id=self.story_id,
                scene_id=scene_id,
                context_tags=["rollback"],
            )
            return False

    # ===== ORCHESTRATOR STATUS =====

    def get_orchestrator_status(self) -> dict[str, Any]:
        """Get comprehensive orchestrator status."""
        return {
            "story_id": self.story_id,
            "operation_count": self.operation_count,
            "last_operation_time": self.last_operation_time,
            "components_loaded": {
                "repository": self._repository is not None,
                "statistics_engine": self._statistics_engine is not None,
                "mood_analyzer": self._mood_analyzer is not None,
                "scene_manager": self._scene_manager is not None,
                "labeling_system": self._labeling_system is not None,
            },
            "component_status": {
                "repository": (
                    self.repository.get_status() if self._repository else "not_loaded"
                ),
                "statistics": (
                    self.statistics_engine.get_status()
                    if self._statistics_engine
                    else "not_loaded"
                ),
                "mood_analysis": (
                    self.mood_analyzer.get_status()
                    if self._mood_analyzer
                    else "not_loaded"
                ),
            },
        }

    def _update_operation_metrics(self):
        """Update internal operation metrics."""
        self.operation_count += 1
        self.last_operation_time = datetime.now(UTC).isoformat()
