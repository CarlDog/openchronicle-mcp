"""Bootstrap the runtime directory tree.

Creates parent dirs for the SQLite DB, the config dir, and the output
dir based on resolved ``RuntimePaths``. v2's model/router_assist
templates are gone with the LLM stack — Phase 5's
``config/core.json.example`` is the only template now.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openchronicle.core.application.config.paths import RuntimePaths


def resolve_runtime_paths() -> RuntimePaths:
    """Convenience wrapper — delegates to ``RuntimePaths.resolve()``."""
    return RuntimePaths.resolve()


def execute(
    paths: RuntimePaths,
    *,
    write_templates: bool = True,  # noqa: ARG001 - kept for kwarg stability
    force: bool = False,  # noqa: ARG001 - kept for kwarg stability
) -> dict[str, Any]:
    """Ensure the v3 path tree exists. Returns a status dict.

    ``write_templates`` and ``force`` are accepted for caller stability
    but no longer write anything — v3 has no templates beyond the
    `core.json.example` baked into the image.
    """
    paths_result = {
        "db_path": _ensure_parent(paths.db_path),
        "config_dir": _ensure_dir(paths.config_dir),
        "output_dir": _ensure_dir(paths.output_dir),
    }

    return {
        "status": "ok",
        "paths": paths_result,
    }


def _ensure_parent(path: Path) -> dict[str, str]:
    parent = path.parent
    status = "exists" if parent.exists() else "created"
    parent.mkdir(parents=True, exist_ok=True)
    return {
        "path": str(path),
        "parent": str(parent),
        "status": status,
    }


def _ensure_dir(path: Path) -> dict[str, str]:
    status = "exists" if path.exists() else "created"
    path.mkdir(parents=True, exist_ok=True)
    return {"path": str(path), "status": status}
