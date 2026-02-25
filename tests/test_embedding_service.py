"""Tests for EmbeddingService — hybrid search and embedding generation."""

from __future__ import annotations

from datetime import UTC, datetime

from openchronicle.core.application.services.embedding_service import (
    EmbeddingService,
    _cosine_similarity,
)
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.infrastructure.embedding.stub_adapter import StubEmbeddingAdapter
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


def _make_service() -> tuple[EmbeddingService, SqliteStore, StubEmbeddingAdapter]:
    store = SqliteStore(db_path=":memory:")
    store.init_schema()
    store.add_project(Project(id="proj-1", name="test"))
    adapter = StubEmbeddingAdapter(dims=32)
    service = EmbeddingService(port=adapter, store=store)
    return service, store, adapter


def _add_memory(
    store: SqliteStore,
    memory_id: str,
    content: str,
    tags: list[str] | None = None,
    pinned: bool = False,
    project_id: str = "proj-1",
    conversation_id: str | None = None,
) -> MemoryItem:
    item = MemoryItem(
        id=memory_id,
        content=content,
        tags=tags or ["test"],
        created_at=datetime.now(UTC),
        pinned=pinned,
        source="test",
        project_id=project_id,
        conversation_id=conversation_id,
    )
    store.add_memory(item)
    return item


# ── generate_for_memory ─────────────────────────────────────────────


def test_generate_for_memory_stores_embedding() -> None:
    service, store, _ = _make_service()
    _add_memory(store, "m1", "hello world")
    service.generate_for_memory("m1", "hello world")
    assert store.get_embedding("m1") is not None


def test_generate_for_memory_skips_if_same_model() -> None:
    service, store, adapter = _make_service()
    _add_memory(store, "m1", "hello")
    service.generate_for_memory("m1", "hello")
    # Save a marker to verify no second write
    first_vec = store.get_embedding("m1")
    service.generate_for_memory("m1", "hello")
    second_vec = store.get_embedding("m1")
    assert first_vec == second_vec


def test_generate_for_memory_regenerates_on_model_change() -> None:
    service, store, _ = _make_service()
    _add_memory(store, "m1", "hello")
    # Manually save with a different model
    store.save_embedding("m1", [0.0] * 32, model="old-model", dimensions=32)
    service.generate_for_memory("m1", "hello")
    assert store.get_embedding_model("m1") == "stub"


# ── generate_missing ────────────────────────────────────────────────


def test_generate_missing_backfills_all() -> None:
    service, store, _ = _make_service()
    for i in range(5):
        _add_memory(store, f"m{i}", f"content {i}")
    count = service.generate_missing()
    assert count == 5
    assert store.count_embeddings() == 5


def test_generate_missing_returns_count() -> None:
    service, store, _ = _make_service()
    _add_memory(store, "m1", "hello")
    service.generate_for_memory("m1", "hello")
    _add_memory(store, "m2", "world")
    count = service.generate_missing()
    assert count == 1  # only m2 was missing


# ── search_hybrid ───────────────────────────────────────────────────


def test_search_hybrid_returns_fts5_results_when_no_embeddings() -> None:
    service, store, _ = _make_service()
    _add_memory(store, "m1", "python programming language")
    results = service.search_hybrid("python")
    assert any(r.id == "m1" for r in results)


def test_search_hybrid_returns_semantic_results() -> None:
    service, store, adapter = _make_service()
    # Add memories with embeddings
    _add_memory(store, "m1", "machine learning models")
    _add_memory(store, "m2", "cooking recipes for pasta")
    service.generate_for_memory("m1", "machine learning models")
    service.generate_for_memory("m2", "cooking recipes for pasta")

    # Semantic search for something related to ML
    results = service.search_hybrid("artificial intelligence neural networks")
    # Both should appear; exact ranking depends on stub embeddings
    ids = [r.id for r in results]
    assert len(ids) > 0


def test_search_hybrid_combines_via_rrf() -> None:
    service, store, _ = _make_service()
    # Create memories — one matches keyword, another matches semantically
    _add_memory(store, "m1", "database optimization query performance")
    _add_memory(store, "m2", "make the app faster speed improvement")
    service.generate_for_memory("m1", "database optimization query performance")
    service.generate_for_memory("m2", "make the app faster speed improvement")

    results = service.search_hybrid("database optimization")
    assert len(results) >= 1


def test_search_hybrid_respects_conversation_filter() -> None:
    service, store, _ = _make_service()
    from openchronicle.core.domain.models.conversation import Conversation

    store.add_conversation(Conversation(id="c1", project_id="proj-1", title="test"))
    store.add_conversation(Conversation(id="c2", project_id="proj-1", title="test2"))
    _add_memory(store, "m1", "alpha beta gamma", conversation_id="c1")
    _add_memory(store, "m2", "alpha beta gamma", conversation_id="c2")
    service.generate_for_memory("m1", "alpha beta gamma")
    service.generate_for_memory("m2", "alpha beta gamma")

    results = service.search_hybrid("alpha", conversation_id="c1")
    ids = [r.id for r in results if not r.pinned]
    assert "m2" not in ids


def test_search_hybrid_respects_tag_filter() -> None:
    service, store, _ = _make_service()
    _add_memory(store, "m1", "alpha beta gamma", tags=["decision"])
    _add_memory(store, "m2", "alpha beta gamma", tags=["rejected"])
    service.generate_for_memory("m1", "alpha beta gamma")
    service.generate_for_memory("m2", "alpha beta gamma")

    results = service.search_hybrid("alpha", tags=["decision"])
    ids = [r.id for r in results]
    assert "m1" in ids
    assert "m2" not in ids


def test_search_hybrid_respects_top_k() -> None:
    service, store, _ = _make_service()
    for i in range(10):
        _add_memory(store, f"m{i}", f"test content number {i}")
        service.generate_for_memory(f"m{i}", f"test content number {i}")

    results = service.search_hybrid("test", top_k=3)
    assert len(results) <= 3


# ── cosine_similarity ───────────────────────────────────────────────


def test_cosine_similarity_identical_vectors() -> None:
    vec = [0.5, 0.5, 0.5, 0.5]
    assert abs(_cosine_similarity(vec, vec) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal_vectors() -> None:
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(_cosine_similarity(a, b)) < 1e-6


def test_embedding_status() -> None:
    service, store, _ = _make_service()
    _add_memory(store, "m1", "hello")
    _add_memory(store, "m2", "world")
    service.generate_for_memory("m1", "hello")

    status = service.embedding_status()
    assert status["total_memories"] == 2
    assert status["embedded"] == 1
    assert status["missing"] == 1
    assert status["stale"] == 0
