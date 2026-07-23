"""Tests for memory pagination — offset parameter on list_memory and search_memory."""

from __future__ import annotations

import pytest

from openchronicle.core.domain.exceptions import NotFoundError
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


# ── count_memory ────────────────────────────────────────────────


class TestCountMemory:
    def test_empty_store_counts_zero(self, store: SqliteStore) -> None:
        assert store.count_memory() == 0

    def test_count_matches_after_inserts(self, store: SqliteStore) -> None:
        _add_items(store, 7)
        assert store.count_memory() == 7

    def test_count_scoped_by_project(self, store: SqliteStore) -> None:
        _add_items(store, 3)  # project_id="proj-1"
        store.add_project(Project(id="proj-2", name="Other", metadata={}))
        store.add_memory(MemoryItem(content="other", tags=[], pinned=False, project_id="proj-2", source="manual"))
        assert store.count_memory() == 4
        assert store.count_memory(project_id="proj-1") == 3
        assert store.count_memory(project_id="proj-2") == 1
        assert store.count_memory(project_id="missing") == 0


# ── delete_memory contract ──────────────────────────────────────


class TestDeleteMemoryContract:
    def test_delete_existing_removes_row(self, store: SqliteStore) -> None:
        items = _add_items(store, 1)
        store.delete_memory(items[0].id)
        assert store.get_memory(items[0].id) is None

    def test_delete_missing_raises_not_found(self, store: SqliteStore) -> None:
        with pytest.raises(NotFoundError, match="Memory not found"):
            store.delete_memory("no-such-id")


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


# ── list_memory project scoping ─────────────────────────────────


class TestListMemoryProjectScope:
    """`list_memory(project_id=...)` is scope-strict.

    See the MemoryStorePort docstring: enumeration answers "what is in
    project X?", so a row from outside X — including a global row with a
    NULL project_id — is a wrong answer. `pinned_items` deliberately uses
    the other rule; these tests pin the difference so neither drifts toward
    the other.
    """

    def _seed_two_projects_and_a_global(self, store: SqliteStore) -> None:
        store.add_project(Project(id="proj-2", name="Other", metadata={}))
        _add_items(store, 3)  # proj-1
        store.add_memory(MemoryItem(content="other", tags=[], pinned=False, project_id="proj-2", source="manual"))
        store.add_memory(MemoryItem(content="global rule", tags=[], pinned=True, project_id=None, source="manual"))

    def test_project_filter_is_strict_and_excludes_null_project(self, store: SqliteStore) -> None:
        self._seed_two_projects_and_a_global(store)
        results = store.list_memory(project_id="proj-1")
        assert len(results) == 3
        assert {r.project_id for r in results} == {"proj-1"}

    def test_project_filter_disagrees_with_pinned_items_by_design(self, store: SqliteStore) -> None:
        self._seed_two_projects_and_a_global(store)
        strict = store.list_memory(project_id="proj-1", pinned_only=True)
        with_global = store.pinned_items(project_id="proj-1")
        assert strict == []
        assert [i.content for i in with_global] == ["global rule"]

    def test_project_filter_composes_with_pinned_only(self, store: SqliteStore) -> None:
        _add_items(store, 2, pinned=True)
        _add_items(store, 3)
        store.add_project(Project(id="proj-2", name="Other", metadata={}))
        store.add_memory(MemoryItem(content="other", tags=[], pinned=True, project_id="proj-2", source="manual"))
        results = store.list_memory(project_id="proj-1", pinned_only=True)
        assert len(results) == 2
        assert all(r.pinned and r.project_id == "proj-1" for r in results)

    def test_project_filter_composes_with_limit_and_offset(self, store: SqliteStore) -> None:
        self._seed_two_projects_and_a_global(store)
        scoped = store.list_memory(project_id="proj-1")
        page = store.list_memory(project_id="proj-1", limit=2, offset=1)
        assert [p.id for p in page] == [s.id for s in scoped[1:3]]

    def test_no_project_id_returns_every_project(self, store: SqliteStore) -> None:
        self._seed_two_projects_and_a_global(store)
        assert len(store.list_memory()) == 5

    def test_unknown_project_returns_empty(self, store: SqliteStore) -> None:
        _add_items(store, 3)
        assert store.list_memory(project_id="no-such-project") == []


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
