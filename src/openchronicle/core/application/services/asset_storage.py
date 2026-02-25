"""Filesystem storage for asset binary data."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from openchronicle.core.domain.models.asset import Asset


class AssetFileStorage:
    """Store and retrieve asset files on the local filesystem.

    File layout: ``{base_dir}/{project_id}/{asset_id}.{ext}``
    """

    def __init__(self, base_dir: str) -> None:
        self.base_dir = Path(base_dir)

    def store_file(self, source_path: str, asset: Asset) -> str:
        """Copy *source_path* into the asset store. Returns the relative file_path."""
        dest = self._dest_path(asset)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest)
        return str(dest.relative_to(self.base_dir))

    def store_bytes(self, data: bytes, asset: Asset) -> str:
        """Write raw bytes into the asset store. Returns the relative file_path."""
        dest = self._dest_path(asset)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return str(dest.relative_to(self.base_dir))

    def read_file(self, file_path: str) -> bytes:
        """Read file contents from the asset store."""
        return (self.base_dir / file_path).read_bytes()

    def delete_file(self, file_path: str) -> bool:
        """Delete a file from the asset store. Returns True if deleted."""
        target = self.base_dir / file_path
        if target.exists():
            target.unlink()
            return True
        return False

    @staticmethod
    def compute_hash(data: bytes) -> str:
        """Compute SHA-256 hex digest of raw bytes."""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def compute_hash_from_path(path: str) -> str:
        """Compute SHA-256 hex digest of a file on disk."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _dest_path(self, asset: Asset) -> Path:
        ext = Path(asset.filename).suffix or ""
        return self.base_dir / asset.project_id / f"{asset.id}{ext}"
