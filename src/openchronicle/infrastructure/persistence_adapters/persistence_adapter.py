"""
Persistence Adapter - Implementation of IPersistencePort

This adapter wraps the existing infrastructure persistence functions
to implement the domain interface, maintaining the dependency inversion principle.
"""

from typing import Any
from typing import Optional

from openchronicle.domain.ports.persistence_port import IPersistencePort
from openchronicle.infrastructure.persistence.database import (
    execute_query as _execute_query,
)
from openchronicle.infrastructure.persistence.database import (
    execute_update as _execute_update,
)
from openchronicle.infrastructure.persistence.database import (
    get_db_path as _get_db_path,
)
from openchronicle.infrastructure.persistence.database import (
    init_database as _init_database,
)


class PersistenceAdapter(IPersistencePort):
    """Concrete implementation of persistence operations using existing infrastructure."""

    def execute_query(
        self, story_id: str, query: str, params: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """
        Execute a database query.

        Args:
            story_id: Story identifier
            query: SQL query string
            params: Query parameters

        Returns:
            Query results as list of dictionaries
        """
        try:
            results = _execute_query(story_id, query, params)
            # Convert results to list of dictionaries if needed
            if results and isinstance(results[0], tuple):
                # Handle tuple results from raw SQL queries
                return [dict(enumerate(row)) for row in results]
            elif results and isinstance(results[0], dict):
                return results
            else:
                return []
        except Exception as e:
            # Log error but don't raise to maintain service availability
            print(f"Database query error: {e}")
            return []

    def execute_update(
        self, story_id: str, query: str, params: Optional[dict[str, Any]] = None
    ) -> bool:
        """
        Execute a database update operation.

        Args:
            story_id: Story identifier
            query: SQL update/insert/delete query
            params: Query parameters

        Returns:
            True if successful, False otherwise
        """
        try:
            result = _execute_update(story_id, query, params)
            # Return True if any rows were affected or operation succeeded
            return result is not None and result >= 0
        except Exception as e:
            print(f"Database update error: {e}")
            return False

    def init_database(self, story_id: str) -> bool:
        """
        Initialize database for a story.

        Args:
            story_id: Story identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            _init_database(story_id)
            return True
        except Exception as e:
            print(f"Database initialization error: {e}")
            return False

    def backup_database(self, story_id: str, backup_name: str) -> bool:
        """
        Create a database backup.

        Args:
            story_id: Story identifier
            backup_name: Name for the backup

        Returns:
            True if successful, False otherwise
        """
        try:
            import shutil
            from pathlib import Path

            # Get the current database path
            db_path = _get_db_path(story_id)
            if not db_path or not Path(db_path).exists():
                return False

            # Create backup path
            backup_dir = Path(db_path).parent / "backups"
            backup_dir.mkdir(exist_ok=True)
            backup_path = backup_dir / f"{backup_name}.db"

            # Copy database file
            shutil.copy2(db_path, backup_path)
            return True

        except Exception as e:
            print(f"Database backup error: {e}")
            return False

    def restore_database(self, story_id: str, backup_name: str) -> bool:
        """
        Restore database from backup.

        Args:
            story_id: Story identifier
            backup_name: Name of the backup to restore

        Returns:
            True if successful, False otherwise
        """
        try:
            import shutil
            from pathlib import Path

            # Get paths
            db_path = _get_db_path(story_id)
            if not db_path:
                return False

            backup_dir = Path(db_path).parent / "backups"
            backup_path = backup_dir / f"{backup_name}.db"

            if not backup_path.exists():
                return False

            # Restore database file
            shutil.copy2(backup_path, db_path)
            return True

        except Exception as e:
            print(f"Database restore error: {e}")
            return False
