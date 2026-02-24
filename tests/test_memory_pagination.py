"""Tests for memory pagination — offset parameter on list_memory and search_memory."""

from __future__ import annotations

import pytest

from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


@pytest.fixture
def store(tmp_path: object) -> SqliteStore:
    db_path = str(tmp_path / "test.db")  # type: ignore[operator]
    s = SqliteStore(db_path=db_path)
    s.init_schema()
    # Create a project so FK constraints are satisfied
    s.add_project(Project(id="proj-1", name="Test", metadata={}))
    return s


def _add_items(store: SqliteStore, count: int, pinned: bool = False) -> list[MemoryItem]:
    """Add count items and return them in creation order."""
    items = []
    for i in range(count):
        item = MemoryItem(
            content=f"Item {i}",
            tags=["test"],
            pinned=pinned,
            project_id="proj-1",
            source="manual",
        )
        store.add_memory(item)
        items.append(item)
    return items


# ── list_memory offset ──────────────────────────────────────────


class TestListMemoryOffset:
    def test_offset_zero_returns_from_start(self, store: SqliteStore) -> None:
        _add_items(store, 5)
        all_items = store.list_memory(limit=5, offset=0)
        assert len(all_items) == 5

    def test_offset_skips_first_n(self, store: SqliteStore) -> None:
        _add_items(store, 10)
        all_items = store.list_memory(limit=None)
        offset_items = store.list_memory(limit=5, offset=3)
        assert len(offset_items) == 5
        assert offset_items[0].id == all_items[3].id

    def test_offset_beyond_results_returns_empty(self, store: SqliteStore) -> None:
        _add_items(store, 3)
        result = store.list_memory(limit=10, offset=100)
        assert result == []

    def test_offset_without_limit(self, store: SqliteStore) -> None:
        _add_items(store, 5)
        all_items = store.list_memory(limit=None)
        result = store.list_memory(limit=None, offset=2)
        assert len(result) == 3
        assert result[0].id == all_items[2].id


# ── search_memory offset ────────────────────────────────────────


class TestSearchMemoryOffset:
    def test_offset_zero_returns_from_start(self, store: SqliteStore) -> None:
        _add_items(store, 5)
        results = store.search_memory("Item", top_k=5, include_pinned=False, offset=0)
        assert len(results) == 5

    def test_offset_skips_results(self, store: SqliteStore) -> None:
        _add_items(store, 10)
        all_results = store.search_memory("Item", top_k=10, include_pinned=False)
        offset_results = store.search_memory("Item", top_k=5, include_pinned=False, offset=3)
        assert len(offset_results) == 5
        assert offset_results[0].id == all_results[3].id

    def test_offset_beyond_results_returns_empty(self, store: SqliteStore) -> None:
        _add_items(store, 3)
        result = store.search_memory("Item", top_k=10, include_pinned=False, offset=100)
        assert result == []

    def test_offset_composes_with_top_k(self, store: SqliteStore) -> None:
        """offset + top_k together: skip offset, return top_k."""
        _add_items(store, 10)
        result = store.search_memory("Item", top_k=3, include_pinned=False, offset=2)
        assert len(result) == 3
