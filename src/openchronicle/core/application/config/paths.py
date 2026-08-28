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


def _env(name: str) -> str | None:
    """Read an env var, treating empty/whitespace-only as UNSET.

    The project-wide invariant, stated at ``docs/configuration/env_vars.md``:
    "An empty-string env var counts as unset at every config boundary —
    docker-compose ``${VAR:-}`` substitutions and MCP hosts inject "" for
    blank fields, and that must fall through to core.json / defaults
    rather than silently shadowing them."

    This boundary used to be the exception. ``os.environ.get`` returns ""
    for a blank var, "" is not None, and ``Path("")`` is ``Path(".")`` —
    so ``OC_DB_PATH=`` silently relocated the SQLite store to the working
    directory, and a blank ``OC_DATA_DIR`` demoted every derived path to a
    bare relative name instead of falling through to its default. Both are
    one ``${VAR:-}`` line away in a compose file, which is precisely the
    form the fleet convention pushes operator-tunable values toward.

    Matches the ``is_disabled()`` / ``env_override()`` strip precedent.
    """
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    return raw


def _resolve(
    explicit: str | Path | None,
    env_var: str,
    data_dir: str | None,
    data_dir_suffix: str,
    fallback: str,
) -> Path:
    """Four-layer path resolution.

    1. Constructor param (``explicit``) — wins unconditionally.
    2. Per-path env var — checked next; empty/whitespace-only is unset.
    3. ``OC_DATA_DIR + suffix`` — if ``OC_DATA_DIR`` is set (same rule).
    4. Hardcoded fallback — last resort.

    ``explicit`` is deliberately NOT empty-normalized: it is a constructor
    argument from code, not operator input, so a caller passing "" has a
    bug worth surfacing rather than papering over.
    """
    if explicit is not None:
        return Path(explicit)
    env_val = _env(env_var)
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
    ) -> RuntimePaths:
        """Build ``RuntimePaths`` with four-layer precedence.

        Constructor params > per-path env vars > ``OC_DATA_DIR``-derived
        > defaults.
        """
        data_dir = _env("OC_DATA_DIR")

        return cls(
            db_path=_resolve(db_path, "OC_DB_PATH", data_dir, "openchronicle.db", DEFAULT_DB_PATH),
            config_dir=_resolve(config_dir, "OC_CONFIG_DIR", data_dir, "config", DEFAULT_CONFIG_DIR),
            output_dir=_resolve(output_dir, "OC_OUTPUT_DIR", data_dir, "output", DEFAULT_OUTPUT_DIR),
        )
