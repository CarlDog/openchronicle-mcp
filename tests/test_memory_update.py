"""Tests for memory_update use case and supporting infrastructure."""

from __future__ import annotations

from pathlib import Path

import pytest

from openchronicle.core.application.use_cases import update_memory
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.interfaces.serializers import memory_to_dict


def _setup(tmp_path: Path) -> tuple[SqliteStore, EventLogger, str]:
    """Create a store with a project and one memory item."""
    db_path = tmp_path / "test.db"
    storage = SqliteStore(str(db_path))
    storage.init_schema()
    event_logger = EventLogger(storage)

    project = Project(name="test-project", metadata={})
    storage.add_project(project)

    item = MemoryItem(
        id="mem-1",
        content="original content",
        tags=["decision", "routing"],
        pinned=False,
        project_id=project.id,
        source="manual",
    )
    storage.add_memory(item)
    return storage, event_logger, project.id


def test_update_content_only(tmp_path: Path) -> None:
    storage, event_logger, _ = _setup(tmp_path)
    updated = update_memory.execute(
        store=storage,
        memory_id="mem-1",
        content="new content",
    )
    assert updated.content == "new content"
    assert updated.tags == ["decision", "routing"]


def test_update_tags_only(tmp_path: Path) -> None:
    storage, event_logger, _ = _setup(tmp_path)
    updated = update_memory.execute(
        store=storage,
        memory_id="mem-1",
        tags=["milestone"],
    )
    assert updated.tags == ["milestone"]
    assert updated.content == "original content"


def test_update_both(tmp_path: Path) -> None:
    storage, event_logger, _ = _setup(tmp_path)
    updated = update_memory.execute(
        store=storage,
        memory_id="mem-1",
        content="new content",
        tags=["context"],
    )
    assert updated.content == "new content"
    assert updated.tags == ["context"]


def test_updated_at_set_on_update(tmp_path: Path) -> None:
    storage, event_logger, _ = _setup(tmp_path)

    # Fresh memory has no updated_at
    original = storage.get_memory("mem-1")
    assert original is not None
    assert original.updated_at is None

    updated = update_memory.execute(
        store=storage,
        memory_id="mem-1",
        content="changed",
    )
    assert updated.updated_at is not None


def test_created_at_unchanged_on_update(tmp_path: Path) -> None:
    storage, event_logger, _ = _setup(tmp_path)
    original = storage.get_memory("mem-1")
    assert original is not None

    updated = update_memory.execute(
        store=storage,
        memory_id="mem-1",
        content="changed",
    )
    assert updated.created_at == original.created_at


def test_update_nonexistent_raises(tmp_path: Path) -> None:
    storage, event_logger, _ = _setup(tmp_path)
    with pytest.raises(NotFoundError, match="Memory not found"):
        update_memory.execute(
            store=storage,
            memory_id="nonexistent",
            content="whatever",
        )


def test_neither_content_nor_tags_raises(tmp_path: Path) -> None:
    storage, event_logger, _ = _setup(tmp_path)
    with pytest.raises(DomainValidationError, match="At least one"):
        update_memory.execute(
            store=storage,
            memory_id="mem-1",
        )


def test_fts5_reindexes_after_content_update(tmp_path: Path) -> None:
    storage, event_logger, project_id = _setup(tmp_path)

    # Original content should match
    results = storage.search_memory("original", project_id=project_id)
    assert any(r.id == "mem-1" for r in results)

    # Update content
    update_memory.execute(
        store=storage,
        memory_id="mem-1",
        content="completely different text",
    )

    # New content should match
    results = storage.search_memory("completely different", project_id=project_id)
    assert any(r.id == "mem-1" for r in results)


def test_serializer_includes_updated_at(tmp_path: Path) -> None:
    storage, event_logger, _ = _setup(tmp_path)

    # Before update
    original = storage.get_memory("mem-1")
    assert original is not None
    d = memory_to_dict(original)
    assert d["updated_at"] is None

    # After update
    updated = update_memory.execute(
        store=storage,
        memory_id="mem-1",
        content="changed",
    )
    d = memory_to_dict(updated)
    assert d["updated_at"] is not None
    assert isinstance(d["updated_at"], str)


def test_fresh_memory_has_no_updated_at(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    storage = SqliteStore(str(db_path))
    storage.init_schema()

    project = Project(name="p", metadata={})
    storage.add_project(project)

    item = MemoryItem(content="test", project_id=project.id)
    storage.add_memory(item)

    loaded = storage.get_memory(item.id)
    assert loaded is not None
    assert loaded.updated_at is None
