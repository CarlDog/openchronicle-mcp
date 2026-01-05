"""
Storage adapter implementing IStoragePort for file/blob operations.

Neutral terms are used in comments and messages. Behavior and on-disk layout
remain backward compatible.
"""

import tarfile
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Optional
from typing import Union

from openchronicle.domain.ports.storage_port import IStoragePort
from openchronicle.shared.logging_system import log_error


class StorageAdapter(IStoragePort):
    """Concrete implementation of storage operations for files and blobs."""

    def __init__(self, base_storage_path: str = "storage") -> None:
        self.base_path = Path(base_storage_path)
        self.base_path.mkdir(exist_ok=True)

    def _get_story_path(self, story_id: str) -> Path:
        story_path = self.base_path / story_id
        story_path.mkdir(exist_ok=True)
        return story_path

    def save_file(self, story_id: str, file_path: str, content: Union[str, bytes]) -> bool:
        try:
            story_path = self._get_story_path(story_id)
            full_path = story_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, str):
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
            else:
                with open(full_path, "wb") as f:
                    f.write(content)
        except OSError as e:
            log_error(f"File save error: {e}", context_tags=["storage", "file", "save", "error"])
            return False
        else:
            return True

    def load_file(self, story_id: str, file_path: str) -> Optional[Union[str, bytes]]:
        try:
            story_path = self._get_story_path(story_id)
            full_path = story_path / file_path
            if not full_path.exists():
                return None
            # Read binary first; attempt UTF-8 decode for text transparency
            with open(full_path, "rb") as f:
                raw = f.read()
            # Heuristic: treat as binary if NULL byte or high binary ratio
            if b"\x00" in raw:
                return raw
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                return raw
            # If decoded, but contains many non-printable chars, return bytes
            non_printables = sum(1 for c in text if ord(c) < 9 or (13 < ord(c) < 32))
            if non_printables > max(3, len(text) * 0.1):
                return raw
        except OSError as e:
            log_error(f"File load error: {e}", context_tags=["storage", "file", "load", "error"])
            return None
        else:
            return text

    def delete_file(self, story_id: str, file_path: str) -> bool:
        try:
            story_path = self._get_story_path(story_id)
            full_path = story_path / file_path
            if full_path.exists():
                full_path.unlink()
        except OSError as e:
            log_error(f"File delete error: {e}", context_tags=["storage", "file", "delete", "error"])
            return False
        else:
            return True

    def list_files(self, story_id: str, directory: str = "") -> list[str]:
        try:
            story_path = self._get_story_path(story_id)
            target_path = story_path / directory if directory else story_path
            if not target_path.exists():
                return []
            files: list[str] = []
            for item in target_path.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(story_path)
                    # Normalize to forward slashes for cross-platform consistency
                    files.append(str(rel).replace("\\", "/"))
            return sorted(files)
        except OSError as e:
            log_error(f"File listing error: {e}", context_tags=["storage", "file", "list", "error"])
            return []

    def create_directory(self, story_id: str, directory_path: str) -> bool:
        try:
            story_path = self._get_story_path(story_id)
            target_path = story_path / directory_path
            target_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            log_error(f"Directory creation error: {e}", context_tags=["storage", "directory", "create", "error"])
            return False
        else:
            return True

    def get_file_metadata(self, story_id: str, file_path: str) -> Optional[dict[str, Any]]:
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
        except OSError as e:
            log_error(f"File metadata error: {e}", context_tags=["storage", "file", "metadata", "error"])
            return None

    def backup_story_files(self, story_id: str, backup_name: str) -> bool:
        try:
            story_path = self._get_story_path(story_id)
            backup_dir = self.base_path / "backups" / story_id
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_file = backup_dir / f"{backup_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tar.gz"
            with tarfile.open(backup_file, "w:gz") as tar:
                tar.add(story_path, arcname=story_id)
        except (OSError, tarfile.TarError) as e:
            # Neutral phrasing while keeping context tags for compatibility
            log_error(f"Unit files backup error: {e}", context_tags=["storage", "unit", "backup", "error"])
            return False
        else:
            return True

    def restore_story_files(self, story_id: str, backup_name: str) -> bool:
        try:
            backup_dir = self.base_path / "backups" / story_id
            backup_files = list(backup_dir.glob(f"{backup_name}_*.tar.gz"))
            if not backup_files:
                return False
            backup_file = max(backup_files, key=lambda p: p.stat().st_mtime)
            with tarfile.open(backup_file, "r:gz") as tar:
                tar.extractall(self.base_path)
        except (OSError, tarfile.TarError) as e:
            # Neutral phrasing while keeping context tags for compatibility
            log_error(f"Unit files restore error: {e}", context_tags=["storage", "unit", "restore", "error"])
            return False
        else:
            return True
