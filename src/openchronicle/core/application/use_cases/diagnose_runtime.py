"""Collect runtime diagnostics for the health endpoints.

v3 surface: DB reachability, config dir status, container/persistence
hints. v2's model config discovery + OC_LLM_* env summary are gone
with the LLM stack.
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openchronicle.core.application.config.paths import RuntimePaths
from openchronicle.core.application.models.diagnostics_report import DiagnosticsReport
from openchronicle.core.domain.time_utils import utc_now
from openchronicle.version import build_revision, package_version

if TYPE_CHECKING:
    from openchronicle.core.infrastructure.wiring.container import CoreContainer

_logger = logging.getLogger(__name__)


def build_health_payload(container: CoreContainer) -> dict[str, Any]:
    """The full health payload both surfaces serve.

    Existed verbatim in the MCP tool and the REST route;
    test_health_parity pinned the copies together — sharing the builder
    makes the parity true by construction instead.
    """
    report = execute()
    report.embedding_status = container.embedding_status_dict()
    report.schema_version = container.storage.schema_version()
    report.maintenance_degraded = container.maintenance_degraded
    report.fts5_active = container.storage.fts5_active
    data = asdict(report)
    if data.get("timestamp_utc"):
        data["timestamp_utc"] = data["timestamp_utc"].isoformat()
    if data.get("db_modified_utc"):
        data["db_modified_utc"] = data["db_modified_utc"].isoformat()
    return data


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
        except OSError, ValueError:
            pass

    config_dir_exists = config_dir_obj.exists()
    running_in_container_hint = _detect_container()
    persistence_hint = _infer_persistence_hint(db_path, running_in_container_hint)

    return DiagnosticsReport(
        timestamp_utc=utc_now(),
        db_path=db_path,
        db_exists=db_exists,
        db_size_bytes=db_size_bytes,
        db_modified_utc=db_modified_utc,
        config_dir=config_dir,
        config_dir_exists=config_dir_exists,
        running_in_container_hint=running_in_container_hint,
        persistence_hint=persistence_hint,
        package_version=package_version(),
        # Distinguishes builds that share a package_version (every rc8
        # image read "3.0.0rc8") — the gap that made a same-version
        # redeploy unverifiable from health.
        build_revision=build_revision(),
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
