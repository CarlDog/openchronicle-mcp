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
from contextlib import closing
from pathlib import Path
from secrets import token_hex
from typing import Any, Literal

from openchronicle.core.domain.time_utils import utc_now
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

_ID_RE = re.compile(r"^(auto|manual):([0-9]{8}T[0-9]{12}Z-[0-9a-f]{12})$")
_MIN_FREE_MARGIN = 1024 * 1024
# The scheduled backup waits this long for an overlapping catalog operation
# (a manual snapshot or a stage) instead of failing and losing the day: the
# loop only retries a failed daily job after its full interval.
_AUTO_LOCK_WAIT_SECONDS = 600


class BackupCatalogError(ValueError):
    """A snapshot is invalid, unavailable or unsafe to use."""


class BackupCatalog:
    """Create, inspect and stage snapshots without touching the live DB file."""

    def __init__(self, store: SqliteStore, root: Path, db_path: Path, *, require_existing_root: bool = False) -> None:
        self.store = store
        self.root = root
        self.db_path = db_path
        # An explicitly configured root (an operator mount) must already
        # exist: creating it would silently write into the container layer
        # when the mount is missing.
        self.require_existing_root = require_existing_root
        self._operation_lock = threading.Lock()

    def _check_root(self) -> None:
        if self.require_existing_root and (
            not self.root.is_absolute() or self.root.is_symlink() or not self.root.is_dir()
        ):
            raise BackupCatalogError(
                f"Configured backup directory {self.root} is missing or not a directory; "
                "nothing was written and there is no fallback location"
            )

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
    def _fsync_dir(path: Path) -> None:
        if os.name == "nt":  # Production container is Linux; Windows runs tests.
            return
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    @staticmethod
    def _inspect(path: Path) -> dict[str, int | str]:
        if path.is_symlink() or not path.is_file():
            raise BackupCatalogError("Backup artifact is not a regular file")
        if any(Path(f"{path}{suffix}").exists() for suffix in ("-wal", "-shm")):
            raise BackupCatalogError("Backup artifact must be a standalone SQLite file")
        # Published snapshots never rely on a WAL. Immutable readback does not
        # create new sidecars beside an otherwise verified artifact.
        uri = f"file:{path.as_posix()}?mode=ro&immutable=1"
        try:
            conn = sqlite3.connect(uri, uri=True)
            try:
                integrity = conn.execute("PRAGMA integrity_check").fetchone()
                if integrity is None or integrity[0] != "ok":
                    raise BackupCatalogError("Backup artifact failed SQLite integrity_check")
                if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
                    raise BackupCatalogError("Backup artifact failed SQLite foreign_key_check")
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
            BackupCatalog._fsync_dir(path.parent)
        finally:
            temp.unlink(missing_ok=True)

    def create(self, kind: Literal["auto", "manual"] = "manual") -> dict[str, Any]:
        """Create one online snapshot; a manual request never queues behind another."""
        if kind == "auto":
            acquired = self._operation_lock.acquire(timeout=_AUTO_LOCK_WAIT_SECONDS)
        else:
            acquired = self._operation_lock.acquire(blocking=False)
        if not acquired:
            raise BackupCatalogError("Another backup operation is already running")
        try:
            self._check_root()
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
            self.store.backup_to(db)
            with db.open("r+b") as snapshot:
                os.fsync(snapshot.fileno())
            self._fsync_dir(directory)
            try:
                inspected = self._inspect(db)
            except BackupCatalogError as exc:
                # The snapshot faithfully copies the live store, so a failed
                # check is evidence about the LIVE database, and possibly the
                # newest copy of it. Quarantine it outside the catalog and
                # retention names, as backup.py does for quick_check, rather
                # than deleting it. The integrity job's emergency backup
                # depends on this: it runs exactly when these checks fail.
                quarantine = db.with_name(db.name + ".failed-verify")
                os.replace(db, quarantine)
                self._fsync_dir(directory)
                raise BackupCatalogError(f"{exc}; snapshot preserved as {quarantine.name}") from exc
            metadata: dict[str, Any] = {
                "artifact_id": artifact_id,
                "created_at": utc_now().isoformat(),
                **inspected,
            }
            try:
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

    def _current_identity(self) -> dict[str, Any]:
        project_ids = sorted(project.id for project in self.store.list_projects())
        return {
            "schema_version": self.store.schema_version(),
            "project_count": len(project_ids),
            "project_identity_sha256": hashlib.sha256("\n".join(project_ids).encode("utf-8")).hexdigest(),
            "project_ids": project_ids,
            "memory_count": self.store.count_memory(),
        }

    def _artifact_project_ids(self, artifact_id: str) -> set[str]:
        db, _ = self._paths(artifact_id)
        with closing(sqlite3.connect(f"file:{db.as_posix()}?mode=ro&immutable=1", uri=True)) as conn:
            return {str(row[0]) for row in conn.execute("SELECT id FROM projects")}

    @staticmethod
    def _comparison(candidate: dict[str, Any], candidate_ids: set[str], current: dict[str, Any]) -> dict[str, Any]:
        """What makes a candidate the wrong target, and what a restore would change.

        The project fingerprint changes with every project created or deleted,
        so a mismatch is normal for an older snapshot, including the most
        common restore (undoing an accidental delete). Only a snapshot that
        shares no project with a non-empty running store is treated as another
        instance.
        """
        current_ids = set(current["project_ids"])
        reasons = []
        if int(candidate["schema_version"]) > int(current["schema_version"]):
            reasons.append("backup schema is newer than this running version")
        if candidate_ids and current_ids and candidate_ids.isdisjoint(current_ids):
            reasons.append("the snapshot shares no project with the running store: likely another instance")
        return {
            "stop_reasons": reasons,
            "memory_delta": int(candidate["memory_count"]) - int(current["memory_count"]),
            "projects_only_in_snapshot": len(candidate_ids - current_ids),
            "projects_only_in_current": len(current_ids - candidate_ids),
        }

    def restore_plan(self, artifact_id: str) -> dict[str, Any]:
        """Compare candidate with the live store; never mutate the live DB.

        `stop_reasons` lists what makes the candidate the wrong target. Row
        and project differences are reported, not refused: restoring an
        older snapshot is expected to change them, and only the operator
        can judge whether the change is the intended one.
        """
        candidate = self.verify(artifact_id)
        current = self._current_identity()
        return {
            "artifact": candidate,
            "current": {key: value for key, value in current.items() if key != "project_ids"},
            **self._comparison(candidate, self._artifact_project_ids(artifact_id), current),
            "restored": False,
            "next_step": "Stop writes and the service; activate the staged copy offline after a pre-restore backup.",
        }

    def restore_stage(self, artifact_id: str) -> dict[str, Any]:
        """Copy a verified candidate onto the DB volume, without activation."""
        if not self._operation_lock.acquire(blocking=False):
            raise BackupCatalogError("Another backup operation is already running")
        try:
            candidate = self.verify(artifact_id)
            reasons = self._comparison(candidate, self._artifact_project_ids(artifact_id), self._current_identity())[
                "stop_reasons"
            ]
            if reasons:
                raise BackupCatalogError("Refusing to stage: " + "; ".join(reasons))
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
                self._fsync_dir(stage_dir)
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
