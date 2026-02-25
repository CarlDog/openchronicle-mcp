"""Tests for embedding pipeline wiring — container, use cases, fallback."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from openchronicle.core.application.config.settings import load_embedding_settings
from openchronicle.core.application.services.embedding_service import EmbeddingService
from openchronicle.core.application.use_cases import add_memory, search_memory, update_memory
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.infrastructure.embedding.stub_adapter import StubEmbeddingAdapter
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


def _make_store_and_service() -> tuple[SqliteStore, EmbeddingService]:
    store = SqliteStore(db_path=":memory:")
    store.init_schema()
    store.add_project(Project(id="proj-1", name="test"))
    adapter = StubEmbeddingAdapter(dims=32)
    service = EmbeddingService(port=adapter, store=store)
    return store, service


def _make_item(memory_id: str = "m1", content: str = "test content") -> MemoryItem:
    return MemoryItem(
        id=memory_id,
        content=content,
        tags=["test"],
        created_at=datetime.now(UTC),
        pinned=False,
        source="test",
        project_id="proj-1",
    )


# ── Container wiring ────────────────────────────────────────────────


def test_container_embedding_service_none_when_provider_none() -> None:
    """When OC_EMBEDDING_PROVIDER=none (default), embedding_service is None."""
    with patch.dict("os.environ", {"OC_EMBEDDING_PROVIDER": "none"}, clear=False):
        from openchronicle.core.infrastructure.wiring.container import CoreContainer

        container = MagicMock(spec=CoreContainer)
        container.embedding_settings = load_embedding_settings()
        result = CoreContainer._build_embedding_port(container)
        assert result is None


def test_container_builds_stub_embedding() -> None:
    """When OC_EMBEDDING_PROVIDER=stub, builds StubEmbeddingAdapter."""
    with patch.dict("os.environ", {"OC_EMBEDDING_PROVIDER": "stub"}, clear=False):
        from openchronicle.core.infrastructure.wiring.container import CoreContainer

        settings = load_embedding_settings()
        container = MagicMock(spec=CoreContainer)
        container.embedding_settings = settings
        result = CoreContainer._create_embedding_adapter(container, settings)
        assert result is not None
        assert result.model_name() == "stub"


# ── Use case integration ────────────────────────────────────────────


def test_add_memory_generates_embedding_when_service_available() -> None:
    store, service = _make_store_and_service()
    emit = MagicMock()
    item = _make_item()
    add_memory.execute(store, emit, item, embedding_service=service)
    assert store.get_embedding("m1") is not None


def test_update_memory_regenerates_on_content_change() -> None:
    store, service = _make_store_and_service()
    emit = MagicMock()
    item = _make_item()
    add_memory.execute(store, emit, item, embedding_service=service)

    original_vec = store.get_embedding("m1")
    update_memory.execute(store, emit, "m1", content="new content", embedding_service=service)
    new_vec = store.get_embedding("m1")
    # Embedding should change because content changed
    # (stub deterministically produces different vectors for different text)
    assert new_vec != original_vec


def test_update_memory_skips_regeneration_tags_only() -> None:
    store, service = _make_store_and_service()
    emit = MagicMock()
    item = _make_item()
    add_memory.execute(store, emit, item, embedding_service=service)

    original_vec = store.get_embedding("m1")
    update_memory.execute(store, emit, "m1", tags=["new-tag"], embedding_service=service)
    new_vec = store.get_embedding("m1")
    # Tags-only change should NOT regenerate embedding
    assert new_vec == original_vec


def test_search_memory_uses_hybrid_when_service_available() -> None:
    store, service = _make_store_and_service()
    item = _make_item(content="python programming")
    store.add_memory(item)
    service.generate_for_memory("m1", "python programming")

    results = search_memory.execute(store, "python", embedding_service=service)
    assert any(r.id == "m1" for r in results)


def test_search_memory_falls_back_to_fts5_without_service() -> None:
    store, _ = _make_store_and_service()
    item = _make_item(content="python programming")
    store.add_memory(item)

    results = search_memory.execute(store, "python", embedding_service=None)
    assert any(r.id == "m1" for r in results)
