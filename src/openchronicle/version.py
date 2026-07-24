"""Single source for the running package version.

`pyproject.toml` is the only place the version is written down. Everything
that reports one — the FastAPI app, the CLI, the health payload — reads it
through here.

This exists because the alternatives had both already failed. `app.py`
carried a hardcoded literal that drifted from pyproject, and the CLI asked
`importlib.metadata` for a distribution named "openchronicle" when the
distribution is "openchronicle-mcp", so `oc version` printed "unknown"
without anyone noticing.
"""

from __future__ import annotations

import importlib.metadata

DISTRIBUTION_NAME = "openchronicle-mcp"


def package_version() -> str:
    """Installed version of this package, or "unknown" if not installed."""
    try:
        return importlib.metadata.version(DISTRIBUTION_NAME)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"
