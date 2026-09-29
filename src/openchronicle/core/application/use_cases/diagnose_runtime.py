"""Collect runtime diagnostics for the health endpoints.

v3 surface: DB reachability, config dir status, container/persistence
hints. v2's model config discovery + OC_LLM_* env summary are gone
with the LLM stack.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openchronicle.core.application.config.offsite import read_cloud_backup_config
from openchronicle.core.application.config.paths import RuntimePaths
from openchronicle.core.application.models.diagnostics_report import DiagnosticsReport
from openchronicle.core.application.services.maintenance_loop import (
    maintenance_state_path,
    parse_state_timestamp,
)
from openchronicle.core.domain.time_utils import utc_now
from openchronicle.version import build_revision, package_version

if TYPE_CHECKING:
    from openchronicle.core.infrastructure.wiring.container import CoreContainer

_logger = logging.getLogger(__name__)


def _integrity_failure_persisted() -> bool:
    """Did the last `db_integrity_check` run fail, per the state file?

    The in-process `maintenance_degraded` flag resets on every restart —
    and every push to main bounces the container — so a failed integrity
    check used to present a clean health surface the moment the process
    came back (the NemoClaw review's Finding 9). The persisted evidence
    survives: a `last_run_at` newer than `last_success_at` (which stamps
    only non-raising runs, from the same clock read) means the last run
    raised. Fail-soft: an absent or unreadable state file reports False,
    matching the loop's own tolerance of it.
    """
    return _last_run_failed("db_integrity_check")


def _backup_failure_persisted() -> bool:
    """Did the last scheduled `db_backup` run fail, per the state file?

    Since v3.5.0 backups go to `OC_BACKUP_DIR`, an operator-managed host
    bind on the NAS. If its ownership drifts, every nightly backup fails
    while the service stays healthy, and nothing else in health says so.
    Same evidence and fail-soft rule as the integrity check. Only the
    scheduled job stamps this state: a manual `oc maintenance run-once
    db_backup`, `oc db backup` or MCP `db_backup_create` does not clear it,
    so a fixed mount reads clean after the next scheduled run.
    """
    return _last_run_failed("db_backup")


def _read_state() -> dict[str, Any] | None:
    """The maintenance loop's persisted state, or None when absent or unreadable."""
    state_path = maintenance_state_path(RuntimePaths.resolve().db_path)
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _last_run_failed(job: str) -> bool:
    """True when `job`'s persisted last run is newer than its last success."""
    try:
        raw = _read_state() or {}
        run = parse_state_timestamp(raw.get("last_run_at", {}).get(job))
        success = parse_state_timestamp(raw.get("last_success_at", {}).get(job))
    except AttributeError:
        return False
    if run is None:
        return False
    return success is None or success < run


# Design 0001 section 6.3: two failed nights before anything can be missed offsite.
_CLOUD_STALE_AFTER = timedelta(hours=48)


def _cloud_backup_status() -> dict[str, Any]:
    """How long since a verified push landed offsite (design 0001 section 6.2).

    `misconfigured` comes from the same validator the job uses and takes
    precedence (plan review A5): the state file holds only timestamps, so it
    alone could never say "broken". Enabled with no recorded success, or a
    success older than 48 h, is `stale`: never `ok` for a deployment that
    never pushed. Never raises.
    """
    config = read_cloud_backup_config()
    if not config.enabled:
        return {"status": "disabled", "last_success_at": None, "hours_since_last_success": None}
    try:
        last = parse_state_timestamp(((_read_state() or {}).get("last_success_at") or {}).get("cloud_backup"))
    except AttributeError:
        last = None
    age = utc_now() - last if last is not None else None
    if config.problem:
        status = "misconfigured"
    elif age is None or age > _CLOUD_STALE_AFTER:
        status = "stale"
    else:
        status = "ok"
    return {
        "status": status,
        "last_success_at": last.isoformat() if last is not None else None,
        "hours_since_last_success": round(age.total_seconds() / 3600, 1) if age is not None else None,
    }


def build_health_payload(container: CoreContainer) -> dict[str, Any]:
    """The full health payload both surfaces serve.

    Existed verbatim in the MCP tool and the REST route;
    test_health_parity pinned the copies together — sharing the builder
    makes the parity true by construction instead.
    """
    report = execute()
    report.embedding_status = container.embedding_status_dict()
    report.schema_version = container.storage.schema_version()
    # In-process flag OR persisted evidence: the flag is immediate, the
    # state file survives the restart that used to clear it.
    report.maintenance_degraded = container.maintenance_degraded or _integrity_failure_persisted()
    # Its own field, never folded into maintenance_degraded: that flag means
    # "the DB may be corrupt" and sends an operator to a restore (0001 §6.2).
    report.backup_last_run_failed = _backup_failure_persisted()
    # Offsite freshness, separate from both flags above (design 0001 section 6.2).
    report.cloud_backup_status = _cloud_backup_status()
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
