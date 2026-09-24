"""Fixed-root catalog for operator-accessible SQLite snapshots.

Artifact IDs never contain paths. The manifest is published last, so an
interrupted database copy is not offered as a restore candidate.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import threading
from pathlib import Path
from secrets import token_hex
from typing import Any, Literal

from openchronicle.core.domain.time_utils import utc_now
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

_ID_RE = re.compile(r"^(auto|manual):([0-9]{8}T[0-9]{12}Z-[0-9a-f]{12})$")
_MIN_FREE_MARGIN = 1024 * 1024


class BackupCatalogError(ValueError):
    """A snapshot is invalid, unavailable or unsafe to use."""


class BackupCatalog:
    """Create, inspect and stage snapshots without touching the live DB file."""

    def __init__(self, store: SqliteStore, root: Path, db_path: Path) -> None:
        self.store = store
        self.root = root
        self.db_path = db_path
        self._operation_lock = threading.Lock()

    @staticmethod
    def _split_id(artifact_id: str) -> tuple[str, str]:
        match = _ID_RE.fullmatch(artifact_id)
        if match is None:
            raise BackupCatalogError("Invalid backup artifact ID")
        return match.group(1), match.group(2)

    def _paths(self, artifact_id: str) -> tuple[Path, Path]:
        kind, name = self._split_id(artifact_id)
        directory = self.root / kind
        db = directory / f"openchronicle-{name}.db"
        return db, db.with_suffix(".json")

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as src:
            for block in iter(lambda: src.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _inspect(path: Path) -> dict[str, int | str]:
        if path.is_symlink() or not path.is_file():
            raise BackupCatalogError("Backup artifact is not a regular file")
        uri = f"file:{path.as_posix()}?mode=ro"
        try:
            conn = sqlite3.connect(uri, uri=True)
            try:
                integrity = conn.execute("PRAGMA integrity_check").fetchone()
                if integrity is None or integrity[0] != "ok":
                    raise BackupCatalogError("Backup artifact failed SQLite integrity_check")
                schema = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0]
                projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
                project_ids = [str(row[0]) for row in conn.execute("SELECT id FROM projects ORDER BY id")]
                memories = conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0]
                embeddings = conn.execute("SELECT COUNT(*) FROM memory_embeddings").fetchone()[0]
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise BackupCatalogError("Backup artifact is not a valid OpenChronicle database") from exc
        return {
            "schema_version": int(schema),
            "project_count": int(projects),
            "project_identity_sha256": hashlib.sha256("\n".join(project_ids).encode("utf-8")).hexdigest(),
            "memory_count": int(memories),
            "embedding_count": int(embeddings),
            "size_bytes": path.stat().st_size,
            "sha256": BackupCatalog._sha256(path),
        }

    @staticmethod
    def _publish_manifest(path: Path, payload: dict[str, Any]) -> None:
        temp = path.with_suffix(".json.tmp")
        try:
            with temp.open("x", encoding="utf-8") as out:
                json.dump(payload, out, sort_keys=True)
                out.write("\n")
                out.flush()
                os.fsync(out.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def create(self, kind: Literal["auto", "manual"] = "manual") -> dict[str, Any]:
        """Create one online snapshot; reject overlapping catalog operations."""
        if not self._operation_lock.acquire(blocking=False):
            raise BackupCatalogError("Another backup operation is already running")
        try:
            directory = self.root / kind
            directory.mkdir(parents=True, exist_ok=True)
            if directory.is_symlink():
                raise BackupCatalogError("Backup directory must not be a symlink")
            expected_bytes = max(self.db_path.stat().st_size, _MIN_FREE_MARGIN)
            if shutil.disk_usage(directory).free < expected_bytes + _MIN_FREE_MARGIN:
                raise BackupCatalogError("Insufficient free space for a backup snapshot")
            stamp = utc_now().strftime("%Y%m%dT%H%M%S%fZ")
            artifact_id = f"{kind}:{stamp}-{token_hex(6)}"
            db, manifest = self._paths(artifact_id)
            try:
                self.store.backup_to(db)
                with db.open("r+b") as snapshot:
                    os.fsync(snapshot.fileno())
                metadata: dict[str, Any] = {
                    "artifact_id": artifact_id,
                    "created_at": utc_now().isoformat(),
                    **self._inspect(db),
                }
                self._publish_manifest(manifest, metadata)
            except Exception:
                db.unlink(missing_ok=True)
                raise
            return metadata
        finally:
            self._operation_lock.release()

    def _manifest(self, artifact_id: str) -> dict[str, Any]:
        db, manifest = self._paths(artifact_id)
        if db.is_symlink() or manifest.is_symlink() or not db.is_file() or not manifest.is_file():
            raise BackupCatalogError("Completed backup artifact not found")
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BackupCatalogError("Backup manifest is unreadable") from exc
        if not isinstance(data, dict) or data.get("artifact_id") != artifact_id:
            raise BackupCatalogError("Backup manifest ID mismatch")
        return data

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """Return completed artifacts only; skip partial or malformed pairs."""
        if not 1 <= limit <= 500:
            raise BackupCatalogError("limit must be between 1 and 500")
        found: list[dict[str, Any]] = []
        for kind in ("auto", "manual"):
            directory = self.root / kind
            if not directory.is_dir() or directory.is_symlink():
                continue
            for manifest in directory.glob("openchronicle-*.json"):
                artifact_id = f"{kind}:{manifest.stem.removeprefix('openchronicle-')}"
                try:
                    found.append(self._manifest(artifact_id))
                except BackupCatalogError:
                    continue
        found.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return found[:limit]

    def verify(self, artifact_id: str) -> dict[str, Any]:
        """Check recorded digest and SQLite structure without modifying it."""
        expected = self._manifest(artifact_id)
        db, _ = self._paths(artifact_id)
        actual = self._inspect(db)
        if any(expected.get(key) != value for key, value in actual.items()):
            raise BackupCatalogError("Backup artifact differs from its manifest")
        return {**expected, "verified": True}

    def restore_plan(self, artifact_id: str) -> dict[str, Any]:
        """Compare candidate with the live store; never mutate the live DB."""
        candidate = self.verify(artifact_id)
        current_schema = self.store.schema_version()
        if int(candidate["schema_version"]) > current_schema:
            raise BackupCatalogError("Backup schema is newer than this running version")
        projects = self.store.list_projects()
        return {
            "artifact": candidate,
            "current": {
                "schema_version": current_schema,
                "project_count": len(projects),
                "project_identity_sha256": hashlib.sha256(
                    "\n".join(sorted(project.id for project in projects)).encode("utf-8")
                ).hexdigest(),
                "memory_count": self.store.count_memory(),
            },
            "restored": False,
            "next_step": "Stop writes and the service; activate the staged copy offline after a pre-restore backup.",
        }

    def restore_stage(self, artifact_id: str) -> dict[str, Any]:
        """Copy a verified candidate onto the DB volume, without activation."""
        if not self._operation_lock.acquire(blocking=False):
            raise BackupCatalogError("Another backup operation is already running")
        try:
            candidate = self.verify(artifact_id)
            if int(candidate["schema_version"]) > self.store.schema_version():
                raise BackupCatalogError("Backup schema is newer than this running version")
            stage_dir = self.db_path.parent / ".restore-stage"
            stage_dir.mkdir(mode=0o700, exist_ok=True)
            if stage_dir.is_symlink() or any(stage_dir.glob("*.db")):
                raise BackupCatalogError("A restore candidate is already staged")
            if shutil.disk_usage(stage_dir).free < int(candidate["size_bytes"]) + _MIN_FREE_MARGIN:
                raise BackupCatalogError("Insufficient free space to stage restore candidate")
            source, _ = self._paths(artifact_id)
            stage_id = token_hex(12)
            final = stage_dir / f"candidate-{stage_id}.db"
            with tempfile.NamedTemporaryFile(dir=stage_dir, prefix="candidate-", suffix=".tmp", delete=False) as out:
                temp = Path(out.name)
                try:
                    with source.open("rb") as src:
                        shutil.copyfileobj(src, out)
                    out.flush()
                    os.fsync(out.fileno())
                except BaseException:
                    temp.unlink(missing_ok=True)
                    raise
            try:
                actual = self._inspect(temp)
                if any(candidate.get(key) != value for key, value in actual.items()):
                    raise BackupCatalogError("Staged candidate differs from verified backup")
                os.replace(temp, final)
            finally:
                temp.unlink(missing_ok=True)
            return {
                "stage_id": stage_id,
                "stage_path": str(final),
                "artifact_id": artifact_id,
                "sha256": actual["sha256"],
                "restored": False,
            }
        finally:
            self._operation_lock.release()
