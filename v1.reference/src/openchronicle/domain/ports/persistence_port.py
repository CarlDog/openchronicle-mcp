"""
Persistence Port - Interface for database operations

Defines the contract for all persistence operations that the domain layer needs.
This interface is implemented by infrastructure adapters.
"""

from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Optional


class IPersistencePort(ABC):
    """Interface for persistence operations."""

    @abstractmethod
    def execute_query(self, story_id: str, query: str, params: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
        """
        Execute a database query.

        Args:
            story_id: Story identifier
            query: SQL query string
            params: Query parameters

        Returns:
            Query results as list of dictionaries
        """

    @abstractmethod
    def execute_update(self, story_id: str, query: str, params: Optional[dict[str, Any]] = None) -> bool:
        """
        Execute a database update operation.

        Args:
            story_id: Story identifier
            query: SQL update/insert/delete query
            params: Query parameters

        Returns:
            True if successful, False otherwise
        """

    @abstractmethod
    def init_database(self, story_id: str) -> bool:
        """
        Initialize database for a story.

        Args:
            story_id: Story identifier

        Returns:
            True if successful, False otherwise
        """

    @abstractmethod
    def backup_database(self, story_id: str, backup_name: str) -> bool:
        """
        Create a database backup.

        Args:
            story_id: Story identifier
            backup_name: Name for the backup

        Returns:
            True if successful, False otherwise
        """

    @abstractmethod
    def restore_database(self, story_id: str, backup_name: str) -> bool:
        """
        Restore database from backup.

        Args:
            story_id: Story identifier
            backup_name: Name of the backup to restore

        Returns:
            True if successful, False otherwise
        """
