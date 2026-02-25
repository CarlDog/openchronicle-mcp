"""Tests for embedding storage in SqliteStore."""

from __future__ import annotations

from datetime import UTC, datetime

from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


def _make_store() -> SqliteStore:
    store = SqliteStore(db_path=":memory:")
    store.init_schema()
    return store


def _add_memory(store: SqliteStore, memory_id: str = "mem-1") -> MemoryItem:
    item = MemoryItem(
        id=memory_id,
        content="test memory content",
        tags=["test"],
        created_at=datetime.now(UTC),
        pinned=False,
        source="test",
        project_id="proj-1",
    )
    # Need project first
    from openchronicle.core.domain.models.project import Project

    store.add_project(Project(id="proj-1", name="test"))
    store.add_memory(item)
    return item


def test_save_and_retrieve_embedding() -> None:
    store = _make_store()
    _add_memory(store, "mem-1")
    vec = [0.1, 0.2, 0.3, 0.4, 0.5]
    store.save_embedding("mem-1", vec, model="test-model", dimensions=5)

    retrieved = store.get_embedding("mem-1")
    assert retrieved is not None
    assert len(retrieved) == 5
    for a, b in zip(vec, retrieved):
        assert abs(a - b) < 1e-6


def test_get_returns_none_for_missing() -> None:
    store = _make_store()
    assert store.get_embedding("nonexistent") is None


def test_delete_embedding() -> None:
    store = _make_store()
    _add_memory(store, "mem-1")
    store.save_embedding("mem-1", [0.1, 0.2], model="test", dimensions=2)
    store.delete_embedding("mem-1")
    assert store.get_embedding("mem-1") is None


def test_cascade_delete() -> None:
    """Deleting memory should remove its embedding via CASCADE."""
    store = _make_store()
    _add_memory(store, "mem-1")
    store.save_embedding("mem-1", [0.1, 0.2, 0.3], model="test", dimensions=3)
    store.delete_memory("mem-1")
    assert store.get_embedding("mem-1") is None


def test_count_embeddings() -> None:
    store = _make_store()
    _add_memory(store, "mem-1")
    assert store.count_embeddings() == 0
    store.save_embedding("mem-1", [0.1, 0.2], model="test", dimensions=2)
    assert store.count_embeddings() == 1


def test_count_stale_embeddings() -> None:
    store = _make_store()
    _add_memory(store, "mem-1")
    store.save_embedding("mem-1", [0.1], model="old-model", dimensions=1)
    assert store.count_stale_embeddings("new-model") == 1
    assert store.count_stale_embeddings("old-model") == 0


def test_list_embeddings_subset() -> None:
    store = _make_store()
    from openchronicle.core.domain.models.project import Project

    store.add_project(Project(id="proj-1", name="test"))
    for i in range(3):
        mid = f"mem-{i}"
        item = MemoryItem(
            id=mid,
            content=f"content {i}",
            tags=["test"],
            created_at=datetime.now(UTC),
            pinned=False,
            source="test",
            project_id="proj-1",
        )
        store.add_memory(item)
        store.save_embedding(mid, [float(i)], model="test", dimensions=1)

    result = store.list_embeddings(["mem-0", "mem-2"])
    assert len(result) == 2
    assert "mem-0" in result
    assert "mem-2" in result
    assert "mem-1" not in result


def test_overwrite_existing_embedding() -> None:
    store = _make_store()
    _add_memory(store, "mem-1")
    store.save_embedding("mem-1", [0.1, 0.2], model="v1", dimensions=2)
    store.save_embedding("mem-1", [0.9, 0.8], model="v2", dimensions=2)

    retrieved = store.get_embedding("mem-1")
    assert retrieved is not None
    assert abs(retrieved[0] - 0.9) < 1e-6
    assert store.get_embedding_model("mem-1") == "v2"
