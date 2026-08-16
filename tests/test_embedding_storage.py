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
    store.save_embedding("mem-1", vec, model="test-model")

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
    store.save_embedding("mem-1", [0.1, 0.2], model="test")
    store.delete_embedding("mem-1")
    assert store.get_embedding("mem-1") is None


def test_cascade_delete() -> None:
    """Deleting memory should remove its embedding via CASCADE."""
    store = _make_store()
    _add_memory(store, "mem-1")
    store.save_embedding("mem-1", [0.1, 0.2, 0.3], model="test")
    store.delete_memory("mem-1")
    assert store.get_embedding("mem-1") is None


def test_count_embeddings() -> None:
    store = _make_store()
    _add_memory(store, "mem-1")
    assert store.count_embeddings() == 0
    store.save_embedding("mem-1", [0.1, 0.2], model="test")
    assert store.count_embeddings() == 1


def test_count_stale_embeddings() -> None:
    store = _make_store()
    _add_memory(store, "mem-1")
    store.save_embedding("mem-1", [0.1], model="old-model")
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
        store.save_embedding(mid, [float(i)], model="test")

    result = store.list_embeddings(["mem-0", "mem-2"])
    assert len(result) == 2
    assert "mem-0" in result
    assert "mem-2" in result
    assert "mem-1" not in result


def test_overwrite_existing_embedding() -> None:
    store = _make_store()
    _add_memory(store, "mem-1")
    store.save_embedding("mem-1", [0.1, 0.2], model="v1")
    store.save_embedding("mem-1", [0.9, 0.8], model="v2")

    retrieved = store.get_embedding("mem-1")
    assert retrieved is not None
    assert abs(retrieved[0] - 0.9) < 1e-6
    assert store.get_embedding_model("mem-1") == "v2"


def test_dimensions_column_records_actual_vector_length() -> None:
    """Regression (2026-08-15 review): the column stored the adapter's
    CONFIGURED dims while the blob stored the actual vector. Ollama can't
    control actual output length, so a mismatch wrote fine and then every
    read raised struct.error. The column now records the fact.
    """
    store = _make_store()
    _add_memory(store, "mem-1")
    store.save_embedding("mem-1", [0.1, 0.2, 0.3], model="test")
    row = store._conn.execute("SELECT dimensions FROM memory_embeddings WHERE memory_id = 'mem-1'").fetchone()
    assert row["dimensions"] == 3


def test_reads_heal_a_row_with_a_lying_dimensions_column() -> None:
    """Pre-fix rows may carry a dimensions claim that disagrees with the
    blob. Reads unpack by blob length, so those rows keep working instead
    of raising struct.error until a forced re-embed.
    """
    store = _make_store()
    _add_memory(store, "mem-1")
    store.save_embedding("mem-1", [0.1, 0.2, 0.3], model="test")
    # Poison the claim the way the old write path could (configured 768,
    # actual 3).
    store._conn.execute("UPDATE memory_embeddings SET dimensions = 768 WHERE memory_id = 'mem-1'")

    retrieved = store.get_embedding("mem-1")
    assert retrieved is not None
    assert len(retrieved) == 3
    listed = store.list_embeddings(["mem-1"])
    assert len(listed["mem-1"]) == 3


def test_list_embeddings_model_filter() -> None:
    """Regression (2026-08-15 review): semantic search loaded every model's
    vectors — a stale row after a model switch crashed the matmul
    (different dims) or silently corrupted ranking (same dims).
    """
    store = _make_store()
    from openchronicle.core.domain.models.project import Project

    store.add_project(Project(id="proj-2", name="test2"))
    for i, model in enumerate(["model-a", "model-a", "model-b"]):
        mid = f"mem-{i}"
        store.add_memory(
            MemoryItem(
                id=mid,
                content=f"content {i}",
                tags=[],
                created_at=datetime.now(UTC),
                pinned=False,
                source="test",
                project_id="proj-2",
            )
        )
        store.save_embedding(mid, [float(i), 1.0], model=model)

    only_a = store.list_embeddings(model="model-a")
    assert set(only_a) == {"mem-0", "mem-1"}
    subset_and_model = store.list_embeddings(["mem-0", "mem-2"], model="model-a")
    assert set(subset_and_model) == {"mem-0"}
    unfiltered = store.list_embeddings()
    assert set(unfiltered) == {"mem-0", "mem-1", "mem-2"}
