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
import os
from pathlib import Path

DISTRIBUTION_NAME = "openchronicle-mcp"

BUILD_REVISION_FILE = "/app/build-revision"
"""Where the Docker build bakes the full git SHA (see Dockerfile).

A file baked into the image, not an env var: several commits can share
one ``package_version`` (every rc8 image read ``3.0.0rc8``), so health
needs a value that identifies the exact build — and a plain env var
would let any compose edit *assert* a revision the image was never
built from. ``OC_BUILD_REVISION_FILE`` overrides the path for tests;
outside an image the file simply doesn't exist and this reports
"unknown", which is the truth for an editable install.
"""


def package_version() -> str:
    """Installed version of this package, or "unknown" if not installed."""
    try:
        return importlib.metadata.version(DISTRIBUTION_NAME)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def build_revision() -> str:
    """Full git SHA the running image was built from, or "unknown"."""
    path = Path(os.getenv("OC_BUILD_REVISION_FILE") or BUILD_REVISION_FILE)
    try:
        revision = path.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"
    return revision or "unknown"
