"""
Memory Port - Interface for memory operations

Defines the contract for all memory operations that the domain layer needs.
This interface is implemented by infrastructure adapters.
"""

from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Optional


class IMemoryPort(ABC):
    """Interface for memory operations."""

    @abstractmethod
    def store_memory(self, story_id: str, character_name: str, memory_data: dict[str, Any]) -> bool:
        """
        Store character memory data.

        Args:
            story_id: Story identifier
            character_name: Character name
            memory_data: Memory data to store

        Returns:
            True if successful, False otherwise
        """

    @abstractmethod
    def retrieve_memory(self, story_id: str, character_name: str) -> Optional[dict[str, Any]]:
        """
        Retrieve character memory data.

        Args:
            story_id: Story identifier
            character_name: Character name

        Returns:
            Memory data if found, None otherwise
        """

    @abstractmethod
    def update_memory(self, story_id: str, character_name: str, updates: dict[str, Any]) -> bool:
        """
        Update character memory data.

        Args:
            story_id: Story identifier
            character_name: Character name
            updates: Memory updates to apply

        Returns:
            True if successful, False otherwise
        """

    @abstractmethod
    def delete_memory(self, story_id: str, character_name: str) -> bool:
        """
        Delete character memory data.

        Args:
            story_id: Story identifier
            character_name: Character name

        Returns:
            True if successful, False otherwise
        """

    @abstractmethod
    def list_character_memories(self, story_id: str) -> list[str]:
        """
        List all characters with memory data.

        Args:
            story_id: Story identifier

        Returns:
            List of character names
        """

    @abstractmethod
    def backup_memories(self, story_id: str, backup_name: str) -> bool:
        """
        Create a backup of all memory data.

        Args:
            story_id: Story identifier
            backup_name: Name for the backup

        Returns:
            True if successful, False otherwise
        """

    @abstractmethod
    def restore_memories(self, story_id: str, backup_name: str) -> bool:
        """
        Restore memory data from backup.

        Args:
            story_id: Story identifier
            backup_name: Name of the backup to restore

        Returns:
            True if successful, False otherwise
        """

    @abstractmethod
    def load_memory(self, story_id: str) -> Any:
        """
        Load full memory state for story validation.

        Args:
            story_id: Story identifier

        Returns:
            Memory state object
        """

    @abstractmethod
    def save_memory(self, story_id: str, memory_state: Any) -> bool:
        """
        Save full memory state for story validation.

        Args:
            story_id: Story identifier
            memory_state: Memory state object to save

        Returns:
            True if successful, False otherwise
        """
