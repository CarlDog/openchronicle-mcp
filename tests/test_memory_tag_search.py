"""Tests for tag-filtered memory search."""

from __future__ import annotations

from pathlib import Path

import pytest

from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


def _setup(tmp_path: Path) -> tuple[SqliteStore, str]:
    """Create a store with a project and several tagged memories."""
    db_path = tmp_path / "test.db"
    storage = SqliteStore(str(db_path))
    storage.init_schema()

    project = Project(name="test-project", metadata={})
    storage.add_project(project)

    items = [
        MemoryItem(
            id="m1",
            content="decided to use hexagonal architecture",
            tags=["decision", "architecture"],
            project_id=project.id,
        ),
        MemoryItem(
            id="m2", content="rejected monolith approach", tags=["rejected", "architecture"], project_id=project.id
        ),
        MemoryItem(
            id="m3", content="routing decision for LLM calls", tags=["decision", "routing"], project_id=project.id
        ),
        MemoryItem(id="m4", content="milestone: core pipeline complete", tags=["milestone"], project_id=project.id),
        MemoryItem(
            id="m5", content="pinned convention about naming", tags=["convention"], pinned=True, project_id=project.id
        ),
        MemoryItem(
            id="m6",
            content="pinned decision about config",
            tags=["decision", "convention"],
            pinned=True,
            project_id=project.id,
        ),
    ]
    for item in items:
        storage.add_memory(item)

    return storage, project.id


def test_search_without_tags_returns_all(tmp_path: Path) -> None:
    """No tag filter returns all matching (default behavior)."""
    storage, project_id = _setup(tmp_path)
    results = storage.search_memory("architecture", project_id=project_id, tags=None)
    # Should include at least m1, m2 (content match), plus pinned items
    ids = {r.id for r in results}
    assert "m1" in ids
    assert "m2" in ids


def test_search_with_single_tag(tmp_path: Path) -> None:
    storage, project_id = _setup(tmp_path)
    results = storage.search_memory("architecture", project_id=project_id, tags=["decision"])
    ids = {r.id for r in results}
    assert "m1" in ids  # decision + architecture
    assert "m2" not in ids  # rejected, not decision
    # m6 is pinned with decision tag, should be included
    assert "m6" in ids


def test_search_with_multiple_tags_and_logic(tmp_path: Path) -> None:
    """Multiple tags uses AND logic."""
    storage, project_id = _setup(tmp_path)
    results = storage.search_memory("architecture decision", project_id=project_id, tags=["decision", "architecture"])
    ids = {r.id for r in results}
    assert "m1" in ids  # has both decision + architecture
    assert "m3" not in ids  # has decision but not architecture


def test_tag_filter_with_fts5(tmp_path: Path) -> None:
    """Tag filter works with FTS5 search path."""
    storage, project_id = _setup(tmp_path)
    assert storage._fts5_active  # noqa: SLF001 — testing internals
    results = storage.search_memory("routing", project_id=project_id, tags=["decision"])
    ids = {r.id for r in results}
    assert "m3" in ids
    assert "m4" not in ids


def test_tag_filter_with_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tag filter works with fallback search path (FTS5 disabled)."""
    monkeypatch.setenv("OC_SEARCH_FTS5_ENABLED", "0")
    db_path = tmp_path / "nofts.db"
    storage = SqliteStore(str(db_path))
    storage.init_schema()
    assert not storage._fts5_active  # noqa: SLF001

    project = Project(name="p", metadata={})
    storage.add_project(project)

    storage.add_memory(MemoryItem(id="a", content="alpha decision text", tags=["decision"], project_id=project.id))
    storage.add_memory(MemoryItem(id="b", content="alpha milestone text", tags=["milestone"], project_id=project.id))

    results = storage.search_memory("alpha", project_id=project.id, tags=["decision"])
    ids = {r.id for r in results}
    assert "a" in ids
    assert "b" not in ids


def test_tag_filter_applies_to_pinned(tmp_path: Path) -> None:
    """Pinned items are also filtered by tags."""
    storage, project_id = _setup(tmp_path)
    results = storage.search_memory("convention", project_id=project_id, tags=["decision"])
    ids = {r.id for r in results}
    # m6 is pinned with tags=["decision", "convention"] — should be included
    assert "m6" in ids
    # m5 is pinned with tags=["convention"] only — should be excluded
    assert "m5" not in ids


def test_empty_tag_list_same_as_none(tmp_path: Path) -> None:
    """Empty tag list should behave like no filter."""
    storage, project_id = _setup(tmp_path)
    results_none = storage.search_memory("architecture", project_id=project_id, tags=None)
    results_empty = storage.search_memory("architecture", project_id=project_id, tags=[])
    # Empty list should not filter anything
    assert {r.id for r in results_none} == {r.id for r in results_empty}


def test_tag_filter_composes_with_scoping(tmp_path: Path) -> None:
    """Tag filter composes with project_id scoping."""
    db_path = tmp_path / "scope.db"
    storage = SqliteStore(str(db_path))
    storage.init_schema()

    p1 = Project(name="p1", metadata={})
    p2 = Project(name="p2", metadata={})
    storage.add_project(p1)
    storage.add_project(p2)

    storage.add_memory(MemoryItem(id="x1", content="something", tags=["decision"], project_id=p1.id))
    storage.add_memory(MemoryItem(id="x2", content="something", tags=["decision"], project_id=p2.id))

    results = storage.search_memory("something", project_id=p1.id, tags=["decision"])
    ids = {r.id for r in results}
    assert "x1" in ids
    assert "x2" not in ids
