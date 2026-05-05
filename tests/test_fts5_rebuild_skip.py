"""Tests for FTS5 rebuild-skip optimization.

Verifies that _ensure_fts5() only rebuilds indexes when they are empty,
not on every startup.
"""

from __future__ import annotations

import logging
import pathlib

import pytest

from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


@pytest.fixture()
def store(tmp_path: pathlib.Path) -> SqliteStore:
    """Create a fresh SqliteStore with FTS5 enabled."""
    db_path = tmp_path / "test.db"
    s = SqliteStore(db_path=str(db_path))
    s.init_schema()
    return s


def test_first_init_rebuilds_empty_fts(store: SqliteStore) -> None:
    """First init should rebuild because FTS tables are empty."""
    assert store._fts5_active  # noqa: SLF001


def test_second_init_skips_rebuild_when_populated(
    tmp_path: pathlib.Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Second init should skip rebuild because FTS tables are already populated."""
    db_path = tmp_path / "test.db"

    # First init — seeds data and builds FTS
    s1 = SqliteStore(db_path=str(db_path))
    s1.init_schema()
    s1.add_memory(MemoryItem(content="hello world", tags=["test"]))
    s1.close()

    # Second init — FTS should already be populated, rebuild skipped
    with caplog.at_level(logging.INFO, logger="openchronicle.core.infrastructure.persistence.sqlite_store"):
        s2 = SqliteStore(db_path=str(db_path))
        s2.init_schema()

    # memory_fts should NOT rebuild (already populated); turns_fts may
    # rebuild because no turns were inserted — that's correct behavior.
    memory_rebuilds = [r for r in caplog.records if "memory_fts" in r.message and "rebuilding" in r.message.lower()]
    assert len(memory_rebuilds) == 0, f"Unexpected memory_fts rebuild: {[r.message for r in memory_rebuilds]}"
    assert s2._fts5_active  # noqa: SLF001
    s2.close()


# NOTE: a v2 test that simulated FTS clearing via `DELETE FROM memory_fts`
# was removed in v3 — that DELETE is a no-op on FTS5 contentless tables
# whose `content_rowid` is bound to memory_items, so the rebuild branch
# under test never fired. The "FTS empty on first create" path is already
# covered by `test_first_init_rebuilds_empty_fts`.
