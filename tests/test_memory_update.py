"""Tests for memory_update use case and supporting infrastructure."""

from __future__ import annotations

from pathlib import Path

import pytest

from openchronicle.core.application.services.embedding_service import EmbeddingService
from openchronicle.core.application.use_cases import update_memory
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.interfaces.serializers import memory_to_dict
from tests.helpers.vectors import save_vec


def _setup(tmp_path: Path) -> tuple[SqliteStore, str]:
    """Create a store with a project and one memory item."""
    db_path = tmp_path / "test.db"
    storage = SqliteStore(str(db_path))
    storage.init_schema()

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
    return storage, project.id


def test_update_content_only(tmp_path: Path) -> None:
    storage, _ = _setup(tmp_path)
    updated = update_memory.execute(
        store=storage,
        memory_id="mem-1",
        content="new content",
    )
    assert updated.content == "new content"
    assert updated.tags == ["decision", "routing"]


def test_update_tags_only(tmp_path: Path) -> None:
    storage, _ = _setup(tmp_path)
    updated = update_memory.execute(
        store=storage,
        memory_id="mem-1",
        tags=["milestone"],
    )
    assert updated.tags == ["milestone"]
    assert updated.content == "original content"


def test_update_both(tmp_path: Path) -> None:
    storage, _ = _setup(tmp_path)
    updated = update_memory.execute(
        store=storage,
        memory_id="mem-1",
        content="new content",
        tags=["context"],
    )
    assert updated.content == "new content"
    assert updated.tags == ["context"]


def test_updated_at_set_on_update(tmp_path: Path) -> None:
    storage, _ = _setup(tmp_path)

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
    storage, _ = _setup(tmp_path)
    original = storage.get_memory("mem-1")
    assert original is not None

    updated = update_memory.execute(
        store=storage,
        memory_id="mem-1",
        content="changed",
    )
    assert updated.created_at == original.created_at


def test_update_nonexistent_raises(tmp_path: Path) -> None:
    storage, _ = _setup(tmp_path)
    with pytest.raises(NotFoundError, match="Memory not found"):
        update_memory.execute(
            store=storage,
            memory_id="nonexistent",
            content="whatever",
        )


def test_neither_content_nor_tags_raises(tmp_path: Path) -> None:
    storage, _ = _setup(tmp_path)
    with pytest.raises(DomainValidationError, match="At least one"):
        update_memory.execute(
            store=storage,
            memory_id="mem-1",
        )


def test_fts5_reindexes_after_content_update(tmp_path: Path) -> None:
    storage, project_id = _setup(tmp_path)

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
    storage, _ = _setup(tmp_path)

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


# ── content change invalidates the stored vector (0002 batch A) ────────


class _FailingPort(EmbeddingPort):
    """Provider that always fails — the scenario that used to strand a
    stale vector: content committed, re-embed raised, old vector kept."""

    def embed(self, text: str) -> list[float]:
        raise RuntimeError("provider down")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("provider down")

    def model_name(self) -> str:
        return "test-model"

    def provider_name(self) -> str:
        return "test-provider"

    def model_revision(self) -> str | None:
        return None

    def settings_fingerprint(self) -> str:
        return "test-fp"

    def dimensions(self) -> int:
        return 2


def _store_with_embedded_memory(tmp_path: Path) -> SqliteStore:
    store = SqliteStore(str(tmp_path / "inv.db"))
    store.init_schema()
    store.add_memory(MemoryItem(id="m1", content="original content"))
    save_vec(store, "m1", [1.0, 0.0], model="test-model")
    return store


def test_failed_reembed_leaves_no_stale_vector(tmp_path: Path) -> None:
    """The defect: the old vector's model still matched, so semantic
    search ranked the OLD content indefinitely and backfill (which skips
    rows whose stored model equals the current one) never repaired it.
    Invalidation now precedes regeneration, so failure leaves the row
    MISSING — visible to backfill — not stale."""
    store = _store_with_embedded_memory(tmp_path)
    service = EmbeddingService(port=_FailingPort(), store=store)

    updated = update_memory.execute(store, "m1", content="rewritten content", embedding_service=service)

    assert updated.content == "rewritten content"
    assert store.get_embedding_model("m1") is None, "a failed re-embed must not preserve the old vector"
    # And the row is a real backfill candidate again:
    assert store.list_embeddings(model="test-model") == {}
    store.close()


def test_content_update_without_provider_also_invalidates(tmp_path: Path) -> None:
    """No embedding_service configured is not an excuse to keep a vector
    of content that no longer exists — a later provider re-enable would
    find its model string current and never regenerate it."""
    store = _store_with_embedded_memory(tmp_path)
    update_memory.execute(store, "m1", content="rewritten content")
    assert store.get_embedding_model("m1") is None
    store.close()


def test_tags_only_update_keeps_the_vector(tmp_path: Path) -> None:
    """Tags don't change what the vector represents — no invalidation."""
    store = _store_with_embedded_memory(tmp_path)
    update_memory.execute(store, "m1", tags=["new-tag"])
    assert store.get_embedding_model("m1") == "test-model"
    store.close()


def test_successful_reembed_replaces_the_vector(tmp_path: Path) -> None:
    class _OkPort(_FailingPort):
        def embed(self, text: str) -> list[float]:
            return [0.0, 1.0]

    store = _store_with_embedded_memory(tmp_path)
    service = EmbeddingService(port=_OkPort(), store=store)
    update_memory.execute(store, "m1", content="rewritten content", embedding_service=service)
    assert store.get_embedding_model("m1") == "test-model"
    assert store.list_embeddings(model="test-model")["m1"] == [0.0, 1.0]
    store.close()


def test_delete_embedding_is_idempotent(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "idem.db"))
    store.init_schema()
    store.add_memory(MemoryItem(id="m1", content="x"))
    store.delete_embedding("m1")  # nothing stored — must not raise
    save_vec(store, "m1", [1.0], model="test-model")
    store.delete_embedding("m1")
    store.delete_embedding("m1")  # second call — still fine
    assert store.get_embedding_model("m1") is None
    store.close()
