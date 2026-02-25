"""Diagnostics report model for oc diagnose command."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


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
    # Model config discovery (v1-style configs from <OC_CONFIG_DIR>/models/*.json)
    models_dir: str
    models_dir_exists: bool
    model_config_files_count: int
    model_config_provider_summary: dict[str, dict[str, int]]
    model_config_load_errors: dict[str, str]
    # Embedding status (populated by interfaces that have access to CoreContainer)
    embedding_status: dict[str, Any] | None = field(default=None)
