"""
Storage Adapter - Implementation of IStoragePort

This adapter provides file and blob storage operations for the domain layer,
implementing the storage interface with proper dependency inversion.
"""

from pathlib import Path
from typing import Any
from typing import Optional
from typing import Union

from openchronicle.domain.ports.storage_port import IStoragePort


class StorageAdapter(IStoragePort):
    """Concrete implementation of storage operations for files and blobs."""

    def __init__(self, base_storage_path: str = "storage"):
        """
        Initialize storage adapter.

        Args:
            base_storage_path: Base directory for all storage operations
        """
        self.base_path = Path(base_storage_path)
        self.base_path.mkdir(exist_ok=True)

    def _get_story_path(self, story_id: str) -> Path:
        """Get the base path for a story's storage."""
        story_path = self.base_path / story_id
        story_path.mkdir(exist_ok=True)
        return story_path

    def save_file(
        self, story_id: str, file_path: str, content: Union[str, bytes]
    ) -> bool:
        """
        Save content to a file.

        Args:
            story_id: Story identifier
            file_path: Relative path within story storage
            content: Content to save

        Returns:
            True if successful, False otherwise
        """
        try:
            story_path = self._get_story_path(story_id)
            full_path = story_path / file_path

            # Ensure parent directory exists
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write content based on type
            if isinstance(content, str):
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
            else:
                with open(full_path, "wb") as f:
                    f.write(content)

            return True

        except Exception as e:
            print(f"File save error: {e}")
            return False

    def load_file(self, story_id: str, file_path: str) -> Optional[Union[str, bytes]]:
        """
        Load content from a file.

        Args:
            story_id: Story identifier
            file_path: Relative path within story storage

        Returns:
            File content if found, None otherwise
        """
        try:
            story_path = self._get_story_path(story_id)
            full_path = story_path / file_path

            if not full_path.exists():
                return None

            # Try to read as text first, fallback to binary
            try:
                with open(full_path, encoding="utf-8") as f:
                    return f.read()
            except UnicodeDecodeError:
                with open(full_path, "rb") as f:
                    return f.read()

        except Exception as e:
            print(f"File load error: {e}")
            return None

    def delete_file(self, story_id: str, file_path: str) -> bool:
        """
        Delete a file.

        Args:
            story_id: Story identifier
            file_path: Relative path within story storage

        Returns:
            True if successful, False otherwise
        """
        try:
            story_path = self._get_story_path(story_id)
            full_path = story_path / file_path

            if full_path.exists():
                full_path.unlink()

            return True

        except Exception as e:
            print(f"File delete error: {e}")
            return False

    def list_files(self, story_id: str, directory: str = "") -> list[str]:
        """
        List files in a directory.

        Args:
            story_id: Story identifier
            directory: Directory path within story storage

        Returns:
            List of file paths
        """
        try:
            story_path = self._get_story_path(story_id)
            target_path = story_path / directory if directory else story_path

            if not target_path.exists():
                return []

            files = []
            for item in target_path.rglob("*"):
                if item.is_file():
                    # Return relative path from story root
                    relative_path = item.relative_to(story_path)
                    files.append(str(relative_path))

            return sorted(files)

        except Exception as e:
            print(f"File listing error: {e}")
            return []

    def create_directory(self, story_id: str, directory_path: str) -> bool:
        """
        Create a directory.

        Args:
            story_id: Story identifier
            directory_path: Directory path to create

        Returns:
            True if successful, False otherwise
        """
        try:
            story_path = self._get_story_path(story_id)
            target_path = story_path / directory_path
            target_path.mkdir(parents=True, exist_ok=True)
            return True

        except Exception as e:
            print(f"Directory creation error: {e}")
            return False

    def get_file_metadata(
        self, story_id: str, file_path: str
    ) -> Optional[dict[str, Any]]:
        """
        Get file metadata.

        Args:
            story_id: Story identifier
            file_path: Relative path within story storage

        Returns:
            Metadata dictionary if found, None otherwise
        """
        try:
            story_path = self._get_story_path(story_id)
            full_path = story_path / file_path

            if not full_path.exists():
                return None

            stat = full_path.stat()

            return {
                "name": full_path.name,
                "size": stat.st_size,
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "is_file": full_path.is_file(),
                "is_directory": full_path.is_dir(),
                "extension": full_path.suffix,
            }

        except Exception as e:
            print(f"File metadata error: {e}")
            return None

    def backup_story_files(self, story_id: str, backup_name: str) -> bool:
        """
        Create a backup of all story files.

        Args:
            story_id: Story identifier
            backup_name: Name for the backup

        Returns:
            True if successful, False otherwise
        """
        try:
            import tarfile
            from datetime import datetime

            story_path = self._get_story_path(story_id)
            backup_dir = self.base_path / "backups" / story_id
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Create compressed backup
            backup_file = (
                backup_dir
                / f"{backup_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tar.gz"
            )

            with tarfile.open(backup_file, "w:gz") as tar:
                tar.add(story_path, arcname=story_id)

            return True

        except Exception as e:
            print(f"Story backup error: {e}")
            return False

    def restore_story_files(self, story_id: str, backup_name: str) -> bool:
        """
        Restore story files from backup.

        Args:
            story_id: Story identifier
            backup_name: Name of the backup to restore

        Returns:
            True if successful, False otherwise
        """
        try:
            import tarfile

            backup_dir = self.base_path / "backups" / story_id

            # Find matching backup file
            backup_files = list(backup_dir.glob(f"{backup_name}_*.tar.gz"))
            if not backup_files:
                return False

            # Use the most recent backup if multiple found
            backup_file = max(backup_files, key=lambda p: p.stat().st_mtime)

            # Extract backup
            with tarfile.open(backup_file, "r:gz") as tar:
                tar.extractall(self.base_path)

            return True

        except Exception as e:
            print(f"Story restore error: {e}")
            return False
