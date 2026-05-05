"""Canonical runtime path resolution for the entire project.

All data-directory paths flow through ``RuntimePaths.resolve()``.
Four-layer precedence: constructor param > per-path env var >
``OC_DATA_DIR``-derived > hardcoded default.

v3 manages three paths: the SQLite file, the config dir, and an
output dir. v2's plugin/assets/discord paths are gone with their
subsystems.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# ── Default constants ────────────────────────────────────────────────

DEFAULT_DB_PATH = "data/openchronicle.db"
DEFAULT_CONFIG_DIR = "config"
DEFAULT_OUTPUT_DIR = "output"


def _resolve(
    explicit: str | Path | None,
    env_var: str,
    data_dir: str | None,
    data_dir_suffix: str,
    fallback: str,
) -> Path:
    """Four-layer path resolution.

    1. Constructor param (``explicit``) — wins unconditionally.
    2. Per-path env var — checked next.
    3. ``OC_DATA_DIR + suffix`` — if ``OC_DATA_DIR`` is set.
    4. Hardcoded fallback — last resort.
    """
    if explicit is not None:
        return Path(explicit)
    env_val = os.environ.get(env_var)
    if env_val is not None:
        return Path(env_val)
    if data_dir is not None:
        return Path(data_dir) / data_dir_suffix
    return Path(fallback)


@dataclass(frozen=True)
class RuntimePaths:
    """Resolved runtime paths for v3 data artifacts."""

    db_path: Path
    config_dir: Path
    output_dir: Path

    @classmethod
    def resolve(
        cls,
        *,
        db_path: str | Path | None = None,
        config_dir: str | Path | None = None,
        output_dir: str | Path | None = None,
        # Accepted but ignored for backwards-compatible callers (e.g.
        # CLI flags / kwargs that haven't been pruned in lock step).
        plugin_dir: str | Path | None = None,  # noqa: ARG003 - accepted for kwarg stability
    ) -> RuntimePaths:
        """Build ``RuntimePaths`` with four-layer precedence.

        Constructor params > per-path env vars > ``OC_DATA_DIR``-derived
        > defaults.
        """
        data_dir = os.environ.get("OC_DATA_DIR")

        return cls(
            db_path=_resolve(db_path, "OC_DB_PATH", data_dir, "openchronicle.db", DEFAULT_DB_PATH),
            config_dir=_resolve(config_dir, "OC_CONFIG_DIR", data_dir, "config", DEFAULT_CONFIG_DIR),
            output_dir=_resolve(output_dir, "OC_OUTPUT_DIR", data_dir, "output", DEFAULT_OUTPUT_DIR),
        )
