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
    # m1 and m2 match on content. Neither pinned item does, so neither
    # appears — pins are floated on match, not unconditionally.
    ids = {r.id for r in results}
    assert "m1" in ids
    assert "m2" in ids
    assert not ids & {"m5", "m6"}


def test_search_with_single_tag(tmp_path: Path) -> None:
    storage, project_id = _setup(tmp_path)
    results = storage.search_memory("architecture", project_id=project_id, tags=["decision"])
    ids = {r.id for r in results}
    assert "m1" in ids  # decision + architecture
    assert "m2" not in ids  # rejected, not decision
    # m6 is pinned and carries the decision tag, but its content
    # ("pinned decision about config") does not match "architecture".
    # Until 2026-08-23 it was prepended anyway — the float now requires
    # a query match, so a standing rule about something else stays out.
    assert "m6" not in ids


def test_pinned_floats_when_it_matches_the_query_and_tags(tmp_path: Path) -> None:
    """The other half of the rule above: a pin that matches both the
    query and the tag filter leads the page."""
    storage, project_id = _setup(tmp_path)
    results = storage.search_memory("config", project_id=project_id, tags=["decision"])
    assert results[0].id == "m6"
    assert results[0].pinned


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


def test_tagged_match_beyond_the_old_overfetch_window_is_found(tmp_path: Path) -> None:
    """Adversarial: the valid tagged row ranks BELOW limit*4 untagged rows.

    The old shape fetched `limit * 4` FTS matches and tag-filtered in
    Python, so with top_k=2 a tagged row ranked past position 8 was
    silently never considered. The predicate now runs in SQL before
    LIMIT, so rank among untagged rows is irrelevant.
    """
    db_path = tmp_path / "window.db"
    storage = SqliteStore(str(db_path))
    storage.init_schema()
    project = Project(name="p", metadata={})
    storage.add_project(project)

    # 40 untagged rows that match the query strongly (query term repeated),
    # ranking every one of them above the single tagged row.
    for i in range(40):
        storage.add_memory(
            MemoryItem(
                id=f"noise-{i:02d}",
                content="gadget gadget gadget gadget strong match",
                tags=[],
                project_id=project.id,
            )
        )
    storage.add_memory(
        MemoryItem(id="needle", content="one weak gadget mention", tags=["wanted"], project_id=project.id)
    )

    results = storage.search_memory("gadget", project_id=project.id, tags=["wanted"], top_k=2)
    assert [r.id for r in results] == ["needle"]


def test_fallback_tagged_match_beyond_the_scan_window_is_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same defect shape on the no-FTS5 path: the fallback scanned a fixed
    200-row recency window and tag-filtered in Python afterwards, so a
    tagged row older than 200 untagged ones was never considered."""
    monkeypatch.setenv("OC_SEARCH_FTS5_ENABLED", "0")
    db_path = tmp_path / "fallback-window.db"
    storage = SqliteStore(str(db_path))
    storage.init_schema()
    assert not storage._fts5_active  # noqa: SLF001
    project = Project(name="p", metadata={})
    storage.add_project(project)

    from datetime import UTC, datetime, timedelta

    base = datetime(2026, 1, 1, tzinfo=UTC)
    # The tagged row is the OLDEST; 210 newer untagged rows fill the window.
    storage.add_memory(
        MemoryItem(id="needle", content="widget target", tags=["wanted"], project_id=project.id, created_at=base)
    )
    for i in range(210):
        storage.add_memory(
            MemoryItem(
                id=f"noise-{i:03d}",
                content="widget filler",
                tags=[],
                project_id=project.id,
                created_at=base + timedelta(minutes=i + 1),
            )
        )

    results = storage.search_memory("widget", project_id=project.id, tags=["wanted"], top_k=5)
    assert "needle" in {r.id for r in results}
