"""
Memory Adapter - Implementation of IMemoryPort

This adapter wraps the existing infrastructure memory functions
to implement the domain interface for character memory operations.
"""

from typing import Any
from typing import Optional

from openchronicle.domain.ports.memory_port import IMemoryPort


class MemoryAdapter(IMemoryPort):
    """Concrete implementation of memory operations using existing infrastructure."""

    def store_memory(
        self, story_id: str, character_name: str, memory_data: dict[str, Any]
    ) -> bool:
        """
        Store character memory data.

        Args:
            story_id: Story identifier
            character_name: Character name
            memory_data: Memory data to store

        Returns:
            True if successful, False otherwise
        """
        try:
            # Import here to avoid circular dependencies
            from openchronicle.infrastructure.memory import MemoryOrchestrator

            orchestrator = MemoryOrchestrator(story_id)
            return orchestrator.store_character_memory(character_name, memory_data)
        except Exception as e:
            print(f"Memory storage error: {e}")
            return False

    def retrieve_memory(
        self, story_id: str, character_name: str
    ) -> Optional[dict[str, Any]]:
        """
        Retrieve character memory data.

        Args:
            story_id: Story identifier
            character_name: Character name

        Returns:
            Memory data if found, None otherwise
        """
        try:
            from openchronicle.infrastructure.memory import MemoryOrchestrator

            orchestrator = MemoryOrchestrator(story_id)
            return orchestrator.get_character_memory(character_name)
        except Exception as e:
            print(f"Memory retrieval error: {e}")
            return None

    def update_memory(
        self, story_id: str, character_name: str, updates: dict[str, Any]
    ) -> bool:
        """
        Update character memory data.

        Args:
            story_id: Story identifier
            character_name: Character name
            updates: Memory updates to apply

        Returns:
            True if successful, False otherwise
        """
        try:
            from openchronicle.infrastructure.memory import MemoryOrchestrator

            orchestrator = MemoryOrchestrator(story_id)
            return orchestrator.update_character_memory(character_name, updates)
        except Exception as e:
            print(f"Memory update error: {e}")
            return False

    def delete_memory(self, story_id: str, character_name: str) -> bool:
        """
        Delete character memory data.

        Args:
            story_id: Story identifier
            character_name: Character name

        Returns:
            True if successful, False otherwise
        """
        try:
            from openchronicle.infrastructure.memory import MemoryOrchestrator

            orchestrator = MemoryOrchestrator(story_id)
            return orchestrator.delete_character_memory(character_name)
        except Exception as e:
            print(f"Memory deletion error: {e}")
            return False

    def list_character_memories(self, story_id: str) -> list[str]:
        """
        List all characters with memory data.

        Args:
            story_id: Story identifier

        Returns:
            List of character names
        """
        try:
            from openchronicle.infrastructure.memory import MemoryOrchestrator

            orchestrator = MemoryOrchestrator(story_id)
            return orchestrator.list_characters()
        except Exception as e:
            print(f"Memory listing error: {e}")
            return []

    def backup_memories(self, story_id: str, backup_name: str) -> bool:
        """
        Create a backup of all memory data.

        Args:
            story_id: Story identifier
            backup_name: Name for the backup

        Returns:
            True if successful, False otherwise
        """
        try:
            import json
            from pathlib import Path

            from openchronicle.infrastructure.memory import MemoryOrchestrator

            orchestrator = MemoryOrchestrator(story_id)

            # Get all character memories
            characters = orchestrator.list_characters()
            backup_data = {}

            for char_name in characters:
                memory = orchestrator.get_character_memory(char_name)
                if memory:
                    backup_data[char_name] = memory

            # Save backup
            backup_dir = Path(f"storage/memory/{story_id}/backups")
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / f"{backup_name}.json"

            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            print(f"Memory backup error: {e}")
            return False

    def restore_memories(self, story_id: str, backup_name: str) -> bool:
        """
        Restore memory data from backup.

        Args:
            story_id: Story identifier
            backup_name: Name of the backup to restore

        Returns:
            True if successful, False otherwise
        """
        try:
            import json
            from pathlib import Path

            from openchronicle.infrastructure.memory import MemoryOrchestrator

            # Load backup
            backup_dir = Path(f"storage/memory/{story_id}/backups")
            backup_path = backup_dir / f"{backup_name}.json"

            if not backup_path.exists():
                return False

            with open(backup_path, encoding="utf-8") as f:
                backup_data = json.load(f)

            # Restore memories
            orchestrator = MemoryOrchestrator(story_id)

            for char_name, memory_data in backup_data.items():
                orchestrator.store_character_memory(char_name, memory_data)

            return True

        except Exception as e:
            print(f"Memory restore error: {e}")
            return False
