"""
Consistency Orchestrator

Coordinates memory consistency validation, conflict detection, and state tracking
for narrative consistency management across the OpenChronicle system.
"""

import logging
from typing import Any

from openchronicle.shared.json_utilities import JSONUtilities

from ...shared.narrative_state import NarrativeStateManager
from .memory_validator import MemoryValidator
from .state_tracker import StateTracker


logger = logging.getLogger(__name__)


class ConsistencyOrchestrator:
    """
    Main orchestrator for memory consistency operations.

    Coordinates memory validation, conflict detection, and state tracking
    to ensure narrative consistency across character memories and states.
    """

    def __init__(self, config: dict | None = None):
        """Initialize consistency orchestrator with configuration."""
        self.config = config or {}
        self.json_utils = JSONUtilities()

        # Initialize components
        self.memory_validator = MemoryValidator(config)
        self.state_tracker = StateTracker(config)
        # Initialize components
        storage_dir = self.config.get("storage_dir", "storage/narrative_consistency")
        self.narrative_state = NarrativeStateManager(storage_dir)

        # Configuration settings
        self.retention_days = self.config.get("retention_days", 30)
        self.max_memories_per_character = self.config.get(
            "max_memories_per_character", 1000
        )
        self.consistency_threshold = self.config.get("consistency_threshold", 0.8)

        logger.info("ConsistencyOrchestrator initialized")

    def add_memory(
        self, character_id: str, memory_event: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Add a new memory event with consistency validation.

        Args:
            character_id: ID of the character
            memory_event: Memory event data

        Returns:
            List of generated character memories
        """

        def _raise_invalid_memory_event_error():
            raise ValueError("Invalid memory event structure")

        try:
            # Validate memory event structure
            if not self._validate_memory_event(memory_event):
                _raise_invalid_memory_event_error()

            # Generate memories from event
            new_memories = self.memory_validator.generate_memories_from_event(
                character_id, memory_event
            )

            # Validate consistency for each new memory
            validated_memories = []
            for memory_data in new_memories:
                consistency_result = self.validate_memory_consistency(
                    character_id, memory_data
                )

                if consistency_result["is_consistent"]:
                    validated_memories.append(memory_data)
                    # Track state changes
                    self.state_tracker.update_character_state(character_id, memory_data)
                else:
                    logger.warning(
                        f"Memory consistency conflict for character {character_id}: "
                        f"{consistency_result['conflicts']}"
                    )
        except Exception as e:
            logger.exception("Error adding memory for character")
            raise
        else:
            return validated_memories

    def retrieve_relevant_memories(
        self, character_id: str, context: str, max_memories: int = 5
    ) -> list[dict[str, Any]]:
        """
        Retrieve memories relevant to current context.

        Args:
            character_id: ID of the character
            context: Current context for relevance matching
            max_memories: Maximum number of memories to return

        Returns:
            List of relevant memories sorted by relevance
        """
        return self.memory_validator.retrieve_relevant_memories(
            character_id, context, max_memories
        )

    def validate_memory_consistency(
        self, character_id: str, new_memory: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Validate consistency of new memory against existing memories.

        Args:
            character_id: ID of the character
            new_memory: Memory to validate

        Returns:
            Dictionary with consistency results
        """
        return self.memory_validator.validate_memory_consistency(
            character_id, new_memory
        )

    def get_character_memory_summary(self, character_id: str) -> dict[str, Any]:
        """
        Get summary of character's memory state.

        Args:
            character_id: ID of the character

        Returns:
            Dictionary with memory summary statistics
        """
        return self.state_tracker.get_character_memory_summary(character_id)

    def compress_old_memories(
        self, character_id: str, retention_days: int | None = None
    ) -> int:
        """
        Compress old memories to optimize storage.

        Args:
            character_id: ID of the character
            retention_days: Days to retain detailed memories

        Returns:
            Number of memories compressed
        """
        days = retention_days or self.retention_days
        return self.memory_validator.compress_old_memories(character_id, days)

    def get_memory_context_for_prompt(
        self, character_id: str, current_context: str, max_tokens: int = 500
    ) -> str:
        """
        Generate memory context for prompt generation.

        Args:
            character_id: ID of the character
            current_context: Current narrative context
            max_tokens: Maximum tokens for context

        Returns:
            Formatted memory context string
        """
        return self.memory_validator.get_memory_context_for_prompt(
            character_id, current_context, max_tokens
        )

    def export_character_memories(self, character_id: str) -> dict[str, Any]:
        """
        Export all memories for a character.

        Args:
            character_id: ID of the character

        Returns:
            Dictionary with exported memory data
        """
        return self.memory_validator.export_character_memories(character_id)

    def import_character_memories(self, data: dict[str, Any]) -> None:
        """
        Import character memories from exported data.

        Args:
            data: Exported memory data
        """
        self.memory_validator.import_character_memories(data)

    def get_consistency_metrics(
        self, character_id: str | None = None
    ) -> dict[str, Any]:
        """
        Get consistency metrics for character(s).

        Args:
            character_id: Optional specific character ID

        Returns:
            Dictionary with consistency metrics
        """
        return self.state_tracker.get_consistency_metrics(character_id)

    def _validate_memory_event(self, memory_event: dict[str, Any]) -> bool:
        """
        Validate memory event structure.

        Args:
            memory_event: Memory event to validate

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["event_type", "content", "timestamp"]
        return all(field in memory_event for field in required_fields)

    def get_status(self) -> dict[str, Any]:
        """
        Get current status of consistency orchestrator.

        Returns:
            Dictionary with status information
        """
        return {
            "consistency_orchestrator": {
                "initialized": True,
                "retention_days": self.retention_days,
                "max_memories_per_character": self.max_memories_per_character,
                "consistency_threshold": self.consistency_threshold,
                "components": {
                    "memory_validator": self.memory_validator.get_status(),
                    "state_tracker": self.state_tracker.get_status(),
                    "narrative_state": self.narrative_state.get_status(),
                },
            }
        }
