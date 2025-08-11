"""
Timeline Orchestrator - Unified Timeline and State Management

Coordinates timeline building, navigation, and rollback operations with a clean modular
architecture. Replaces the legacy monolithic timeline_builder.py and rollback_engine.py
with orchestrated subsystems.

Features:
- Unified timeline and rollback coordination
- Lazy loading of timeline and state management components
- Graceful degradation when optional systems are unavailable
- Clean separation of timeline, navigation, and state management concerns
- Enhanced error handling and logging
"""

from datetime import UTC
from datetime import datetime
from typing import Any
from openchronicle.shared.logging_system import log_error
from openchronicle.shared.logging_system import log_info
from openchronicle.shared.logging_system import log_system_event
from openchronicle.shared.logging_system import log_warning
from openchronicle.domain.ports.persistence_inmemory import (
    InMemorySqlitePersistence,
)


class TimelineConfiguration:
    """Configuration settings for timeline operations."""

    def __init__(self):
        self.enable_auto_summaries = True
        self.enable_tone_tracking = True
        self.max_timeline_entries = 1000
        self.enable_rollback_points = True
        self.auto_rollback_interval = 10  # Create rollback every N scenes
        self.rollback_retention_days = 30


class TimelineMetrics:
    """Metrics and performance tracking for timeline operations."""

    def __init__(self):
        self.operations_count = 0
        self.timeline_builds = 0
        self.rollback_operations = 0
        self.navigation_requests = 0
        self.errors_count = 0
        self.start_time = datetime.now(UTC)

    def record_operation(self, operation_type: str, success: bool = True):
        """Record timeline operation metrics."""
        self.operations_count += 1
        if operation_type == "timeline_build":
            self.timeline_builds += 1
        elif operation_type == "rollback":
            self.rollback_operations += 1
        elif operation_type == "navigation":
            self.navigation_requests += 1

        if not success:
            self.errors_count += 1

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics summary."""
        uptime = (datetime.now(UTC) - self.start_time).total_seconds()
        return {
            "total_operations": self.operations_count,
            "timeline_builds": self.timeline_builds,
            "rollback_operations": self.rollback_operations,
            "navigation_requests": self.navigation_requests,
            "errors": self.errors_count,
            "success_rate": (self.operations_count - self.errors_count)
            / max(1, self.operations_count),
            "uptime_seconds": uptime,
        }


class TimelineOrchestrator:
    """
    Main orchestrator for timeline and state management operations.

    Provides unified interface for timeline building, navigation, and rollback operations
    for narrative AI operations. Replaces the legacy monolithic timeline and rollback engines.

    Architecture:
    - Timeline Management: Story timeline building, navigation, auto-summaries
    - State Management: Rollback points, versioning, state snapshots
    - Shared Components: Common temporal patterns and validation
    """

    def __init__(self, story_id: str):
        self.story_id = story_id
        self.config = TimelineConfiguration()
        self.metrics = TimelineMetrics()

        # Lazy-loaded components
        self._timeline_manager = None
        self._state_manager = None
        self._navigation_manager = None

        # Shared persistence for all timeline components (in-memory by default)
        self._persistence = InMemorySqlitePersistence()

        # Initialize logging
        log_system_event(
            "timeline_orchestrator_init",
            f"Initialized TimelineOrchestrator for story {self.story_id}",
        )

    def _get_timeline_manager(self):
        """Lazy load timeline management component."""
        if self._timeline_manager is None:
            try:
                from .timeline.timeline_manager import TimelineManager
                from .shared.bookmark_manager import SimpleBookmarkManager

                bookmark_mgr = SimpleBookmarkManager(self._persistence)
                self._timeline_manager = TimelineManager(
                    self.story_id,
                    persistence_port=self._persistence,
                    bookmark_manager=bookmark_mgr,
                )
                log_info(f"Timeline manager loaded for story {self.story_id}")
            except ImportError as e:
                log_warning(f"Timeline manager not available: {e}")
                self._timeline_manager = self._create_fallback_timeline_manager()
        return self._timeline_manager

    def _get_state_manager(self):
        """Lazy load state management component."""
        if self._state_manager is None:
            try:
                from .rollback.state_manager import StateManager

                self._state_manager = StateManager(
                    self.story_id, persistence_port=self._persistence
                )
                log_info(f"State manager loaded for story {self.story_id}")
            except ImportError as e:
                log_warning(f"State manager not available: {e}")
                self._state_manager = self._create_fallback_state_manager()
        return self._state_manager

    def _get_navigation_manager(self):
        """Lazy load navigation management component."""
        if self._navigation_manager is None:
            try:
                from .navigation.navigation_manager import NavigationManager

                self._navigation_manager = NavigationManager(
                    self.story_id, persistence_port=self._persistence
                )
                log_info(f"Navigation manager loaded for story {self.story_id}")
            except ImportError as e:
                log_warning(f"Navigation manager not available: {e}")
                self._navigation_manager = self._create_fallback_navigation_manager()
        return self._navigation_manager

    async def build_timeline(
        self, include_bookmarks: bool = True, include_summaries: bool = True
    ) -> dict[str, Any]:
        """
        Build complete story timeline with scenes, bookmarks, and navigation.

        This replaces the legacy get_full_timeline function from timeline_builder.py
        with enhanced modular architecture and better error handling.

        Args:
            include_bookmarks: Include bookmark entries in timeline
            include_summaries: Include auto-generated summaries

        Returns:
            Complete timeline structure with metadata
        """
        start_time = self._get_current_time_ms()

        try:
            timeline_manager = self._get_timeline_manager()

            # Build base timeline
            timeline_data = await timeline_manager.build_full_timeline(
                include_bookmarks=include_bookmarks, include_summaries=include_summaries
            )

            # Add navigation metadata
            if include_bookmarks:
                navigation_manager = self._get_navigation_manager()
                timeline_data[
                    "navigation"
                ] = await navigation_manager.build_navigation_structure(timeline_data)

            # Add metrics
            processing_time = self._get_current_time_ms() - start_time
            timeline_data["metadata"] = {
                "story_id": self.story_id,
                "generated_at": datetime.now(UTC).isoformat(),
                "processing_time_ms": processing_time,
                "entry_count": len(timeline_data.get("entries", [])),
                "includes_bookmarks": include_bookmarks,
                "includes_summaries": include_summaries,
            }

            self.metrics.record_operation("timeline_build", True)
            log_info(
                f"Timeline built successfully for {self.story_id} ({processing_time}ms)"
            )

            return timeline_data

        except Exception as e:
            self.metrics.record_operation("timeline_build", False)
            log_error(f"Timeline build failed for {self.story_id}: {e}")

            # Return minimal fallback timeline
            return self._create_fallback_timeline()

    async def create_rollback_point(
        self, scene_id: str, description: str = "Manual rollback point"
    ) -> dict[str, Any]:
        """
        Create a rollback point for state restoration.

        This replaces the legacy create_rollback_point function from rollback_engine.py
        with enhanced state management and validation.

        Args:
            scene_id: Scene ID to create rollback point for
            description: Description of the rollback point

        Returns:
            Rollback point information with metadata
        """
        try:
            state_manager = self._get_state_manager()

            rollback_data = await state_manager.create_rollback_point(
                scene_id, description
            )

            self.metrics.record_operation("rollback", True)
            log_info(
                f"Rollback point created for scene {scene_id}: {rollback_data['id']}"
            )

            return rollback_data

        except Exception as e:
            self.metrics.record_operation("rollback", False)
            log_error(f"Rollback point creation failed for scene {scene_id}: {e}")
            raise

    async def list_rollback_points(self) -> list[dict[str, Any]]:
        """
        List all available rollback points for the story.

        Returns:
            List of rollback points with metadata
        """
        try:
            state_manager = self._get_state_manager()
            return await state_manager.list_rollback_points()

        except Exception as e:
            log_error(f"Failed to list rollback points for {self.story_id}: {e}")
            return []

    async def rollback_to_point(self, rollback_id: str) -> dict[str, Any]:
        """
        Restore story state to a specific rollback point.

        Args:
            rollback_id: ID of the rollback point to restore

        Returns:
            Restoration result with metadata
        """
        try:
            state_manager = self._get_state_manager()

            restoration_result = await state_manager.rollback_to_point(rollback_id)

            self.metrics.record_operation("rollback", True)
            log_info(f"Successfully rolled back to point {rollback_id}")

            return restoration_result

        except Exception as e:
            self.metrics.record_operation("rollback", False)
            log_error(f"Rollback to {rollback_id} failed: {e}")
            raise

    async def navigate_timeline(self, navigation_type: str, **kwargs) -> dict[str, Any]:
        """
        Navigate through timeline with various options.

        Args:
            navigation_type: Type of navigation (next, previous, jump_to, search)
            **kwargs: Navigation-specific parameters

        Returns:
            Navigation result with target information
        """
        try:
            navigation_manager = self._get_navigation_manager()

            result = await navigation_manager.navigate(navigation_type, **kwargs)

            self.metrics.record_operation("navigation", True)

            return result

        except Exception as e:
            self.metrics.record_operation("navigation", False)
            log_error(f"Timeline navigation failed: {e}")
            raise

    def get_metrics(self) -> dict[str, Any]:
        """Get timeline system metrics and performance data."""
        return {
            "orchestrator_metrics": self.metrics.get_metrics(),
            "configuration": {
                "auto_summaries": self.config.enable_auto_summaries,
                "tone_tracking": self.config.enable_tone_tracking,
                "rollback_enabled": self.config.enable_rollback_points,
                "auto_rollback_interval": self.config.auto_rollback_interval,
            },
            "component_status": {
                "timeline_manager": self._timeline_manager is not None,
                "state_manager": self._state_manager is not None,
                "navigation_manager": self._navigation_manager is not None,
            },
            "story_id": self.story_id,
        }

    def _create_fallback_timeline_manager(self):
        """Create minimal fallback timeline manager."""
        from .shared.fallback_timeline import FallbackTimelineManager

        return FallbackTimelineManager(self.story_id)

    def _create_fallback_state_manager(self):
        """Create minimal fallback state manager."""
        from .shared.fallback_state import FallbackStateManager

        return FallbackStateManager(self.story_id)

    def _create_fallback_navigation_manager(self):
        """Create minimal fallback navigation manager."""
        from .shared.fallback_navigation import FallbackNavigationManager

        return FallbackNavigationManager(self.story_id)

    def _create_fallback_timeline(self) -> dict[str, Any]:
        """Create minimal fallback timeline when full generation fails."""
        fallback_data = {
            "entries": [],
            "metadata": {
                "story_id": self.story_id,
                "generated_at": datetime.now(UTC).isoformat(),
                "fallback_mode": True,
                "error": "Timeline generation failed - using fallback",
            },
            "navigation": {"total_entries": 0, "current_position": 0},
        }

        log_warning(f"Using fallback timeline for {self.story_id}")
        return fallback_data

    def _get_current_time_ms(self) -> int:
        """Get current time in milliseconds."""
        import time

        return int(time.time() * 1000)


# Direct exports for clean modular access
# No compatibility layer needed - clean breaking changes enabled by pre-public status
