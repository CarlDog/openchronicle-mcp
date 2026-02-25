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


# ── Backfill resilience ────────────────────────────────────────────


def test_generate_missing_skips_failures_and_continues() -> None:
    """Individual embedding failures should not abort the entire backfill."""
    store, service = _make_store_and_service()
    for i in range(3):
        store.add_memory(_make_item(memory_id=f"m{i}", content=f"content {i}"))

    # Make the port fail on the second call only
    original_embed = service.port.embed
    call_count = 0

    def flaky_embed(text: str) -> list[float]:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("simulated API timeout")
        return original_embed(text)

    service._port.embed = flaky_embed  # type: ignore[method-assign]

    count = service.generate_missing()
    assert count == 2  # 2 succeeded, 1 failed
    # Verify the ones that succeeded are stored
    assert store.get_embedding("m0") is not None
    assert store.get_embedding("m1") is None  # this one failed
    assert store.get_embedding("m2") is not None


def test_generate_missing_returns_zero_when_all_embedded() -> None:
    """No-op backfill when all memories already have embeddings."""
    store, service = _make_store_and_service()
    item = _make_item()
    store.add_memory(item)
    service.generate_for_memory("m1", "test content")

    count = service.generate_missing()
    assert count == 0


# ── Container embedding_status_dict ────────────────────────────────


def test_embedding_status_dict_disabled() -> None:
    """Status dict when provider is 'none'."""
    from openchronicle.core.application.config.settings import EmbeddingSettings
    from openchronicle.core.infrastructure.wiring.container import CoreContainer

    container = MagicMock(spec=CoreContainer)
    container.embedding_settings = EmbeddingSettings(provider="none")
    container.embedding_service = None

    result = CoreContainer.embedding_status_dict(container)
    assert result["status"] == "disabled"
    assert result["provider"] == "none"


def test_embedding_status_dict_failed() -> None:
    """Status dict when adapter failed to initialize."""
    from openchronicle.core.application.config.settings import EmbeddingSettings
    from openchronicle.core.infrastructure.wiring.container import CoreContainer

    container = MagicMock(spec=CoreContainer)
    container.embedding_settings = EmbeddingSettings(provider="openai")
    container.embedding_service = None

    result = CoreContainer.embedding_status_dict(container)
    assert result["status"] == "failed"
    assert result["provider"] == "openai"


def test_embedding_status_dict_active() -> None:
    """Status dict when adapter is active and working."""
    from openchronicle.core.application.config.settings import EmbeddingSettings
    from openchronicle.core.infrastructure.wiring.container import CoreContainer

    store, service = _make_store_and_service()
    store.add_memory(_make_item())
    service.generate_for_memory("m1", "test content")

    container = MagicMock(spec=CoreContainer)
    container.embedding_settings = EmbeddingSettings(provider="stub")
    container.embedding_service = service

    result = CoreContainer.embedding_status_dict(container)
    assert result["status"] == "active"
    assert result["provider"] == "stub"
    assert result["model"] == "stub"
    assert result["dimensions"] == 32
    assert result["total_memories"] == 1
    assert result["embedded"] == 1
    assert result["missing"] == 0
