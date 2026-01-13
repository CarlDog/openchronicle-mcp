"""Diagnostics report model for oc diagnose command."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class DiagnosticsReport:
    """Runtime diagnostics report collected by the diagnose use case."""

    timestamp_utc: datetime
    db_path: str
    db_exists: bool
    db_size_bytes: int | None
    db_modified_utc: datetime | None
    config_dir: str
    config_dir_exists: bool
    plugin_dir: str
    plugin_dir_exists: bool
    running_in_container_hint: bool
    persistence_hint: str
    provider_env_summary: dict[str, str]
