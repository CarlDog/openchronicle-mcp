"""Root test configuration — database isolation.

Every test gets its own temporary SQLite database via OC_DB_PATH.
This prevents test runs from polluting the real database used by
the MCP server and other runtime tools.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_test_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect OC_DB_PATH to a temp directory for every test."""
    monkeypatch.setenv("OC_DB_PATH", str(tmp_path / "test.db"))
