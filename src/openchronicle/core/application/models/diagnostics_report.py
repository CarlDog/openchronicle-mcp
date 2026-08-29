"""Diagnostics report model.

Returned by ``diagnose_runtime.execute()`` and surfaced by the v3
health endpoints (``/health``, ``/api/v1/health``, MCP ``health`` tool).
v2's plugin_dir / model config discovery / OC_LLM_* env summary fields
are gone with the LLM stack.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DiagnosticsReport:
    """Runtime diagnostics report."""

    timestamp_utc: datetime
    db_path: str
    db_exists: bool
    db_size_bytes: int | None
    db_modified_utc: datetime | None
    config_dir: str
    config_dir_exists: bool
    running_in_container_hint: bool
    persistence_hint: str
    package_version: str
    build_revision: str
    # Fields below are populated by interfaces with a CoreContainer in
    # hand. They can't be filled by `diagnose_runtime.execute()`, which
    # deliberately takes no container and (per the hexagonal boundary
    # tests) can't import from infrastructure to reach the store.
    embedding_status: dict[str, Any] | None = field(default=None)
    schema_version: int | None = field(default=None)
    maintenance_degraded: bool | None = field(default=None)
    fts5_active: bool | None = field(default=None)
