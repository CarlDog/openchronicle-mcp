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
    # Embedding subsystem status — populated by interfaces with a
    # CoreContainer in hand (the container injects its own
    # `embedding_status_dict` here).
    embedding_status: dict[str, Any] | None = field(default=None)
