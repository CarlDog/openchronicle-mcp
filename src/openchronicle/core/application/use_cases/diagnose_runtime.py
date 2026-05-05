"""Collect runtime diagnostics for the health endpoints.

v3 surface: DB reachability, config dir status, container/persistence
hints. v2's model config discovery + OC_LLM_* env summary are gone
with the LLM stack.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from openchronicle.core.application.config.paths import RuntimePaths
from openchronicle.core.application.models.diagnostics_report import DiagnosticsReport

_logger = logging.getLogger(__name__)


def execute() -> DiagnosticsReport:
    """Collect runtime diagnostics without requiring a CoreContainer."""
    paths = RuntimePaths.resolve()
    db_path = str(paths.db_path)
    config_dir = str(paths.config_dir)

    db_path_obj = paths.db_path
    config_dir_obj = paths.config_dir

    db_exists = db_path_obj.exists()
    db_size_bytes: int | None = None
    db_modified_utc: datetime | None = None

    if db_exists:
        try:
            stat_info = db_path_obj.stat()
            db_size_bytes = stat_info.st_size
            db_modified_utc = datetime.fromtimestamp(stat_info.st_mtime, UTC)
        except (OSError, ValueError):
            pass

    config_dir_exists = config_dir_obj.exists()
    running_in_container_hint = _detect_container()
    persistence_hint = _infer_persistence_hint(db_path, running_in_container_hint)

    return DiagnosticsReport(
        timestamp_utc=datetime.now(UTC),
        db_path=db_path,
        db_exists=db_exists,
        db_size_bytes=db_size_bytes,
        db_modified_utc=db_modified_utc,
        config_dir=config_dir,
        config_dir_exists=config_dir_exists,
        running_in_container_hint=running_in_container_hint,
        persistence_hint=persistence_hint,
    )


def _detect_container() -> bool:
    """Detect if running in a container (heuristic)."""
    if Path("/.dockerenv").exists():
        return True
    db_path = os.getenv("OC_DB_PATH", "data/openchronicle.db")
    return db_path.startswith("/data")


def _infer_persistence_hint(db_path: str, running_in_container_hint: bool) -> str:
    """Infer persistence mode from path + container hint."""
    db_posix = db_path.replace("\\", "/")
    if running_in_container_hint and db_posix.startswith("/data"):
        return (
            "DB configured for container volume at /data. If you expect a "
            "host file, ensure a bind-mount overlay is used."
        )
    if "\\" in db_path or db_path[1:3] == ":\\" or (len(db_path) > 2 and db_path[1] == ":"):
        return "DB appears to be on a Windows bind-mount path."
    return "Persistence mode unknown."
