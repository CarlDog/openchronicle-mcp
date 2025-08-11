"""
Storage Port - Interface for file and blob storage operations

Defines the contract for all storage operations that the domain layer needs.
This interface is implemented by infrastructure adapters.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class IStoragePort(ABC):
    """Interface for storage operations."""

    @abstractmethod
    def save_file(self, story_id: str, file_path: str, content: Union[str, bytes]) -> bool:
        """
        Save content to a file.
        
        Args:
            story_id: Story identifier
            file_path: Relative path within story storage
            content: Content to save
            
        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def load_file(self, story_id: str, file_path: str) -> Optional[Union[str, bytes]]:
        """
        Load content from a file.
        
        Args:
            story_id: Story identifier
            file_path: Relative path within story storage
            
        Returns:
            File content if found, None otherwise
        """
        pass

    @abstractmethod
    def delete_file(self, story_id: str, file_path: str) -> bool:
        """
        Delete a file.
        
        Args:
            story_id: Story identifier
            file_path: Relative path within story storage
            
        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def list_files(self, story_id: str, directory: str = "") -> List[str]:
        """
        List files in a directory.
        
        Args:
            story_id: Story identifier
            directory: Directory path within story storage
            
        Returns:
            List of file paths
        """
        pass

    @abstractmethod
    def create_directory(self, story_id: str, directory_path: str) -> bool:
        """
        Create a directory.
        
        Args:
            story_id: Story identifier
            directory_path: Directory path to create
            
        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_file_metadata(self, story_id: str, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get file metadata.
        
        Args:
            story_id: Story identifier
            file_path: Relative path within story storage
            
        Returns:
            Metadata dictionary if found, None otherwise
        """
        pass

    @abstractmethod
    def backup_story_files(self, story_id: str, backup_name: str) -> bool:
        """
        Create a backup of all story files.
        
        Args:
            story_id: Story identifier
            backup_name: Name for the backup
            
        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def restore_story_files(self, story_id: str, backup_name: str) -> bool:
        """
        Restore story files from backup.
        
        Args:
            story_id: Story identifier
            backup_name: Name of the backup to restore
            
        Returns:
            True if successful, False otherwise
        """
        pass
