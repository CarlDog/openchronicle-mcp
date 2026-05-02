"""Tests for embedding backfill (CLI, MCP tool, API endpoint logic)."""

from __future__ import annotations

from datetime import UTC, datetime

from openchronicle.core.application.services.embedding_service import EmbeddingService
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.infrastructure.embedding.stub_adapter import StubEmbeddingAdapter
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


def _make_service() -> tuple[EmbeddingService, SqliteStore]:
    store = SqliteStore(db_path=":memory:")
    store.init_schema()
    store.add_project(Project(id="proj-1", name="test"))
    adapter = StubEmbeddingAdapter(dims=32)
    service = EmbeddingService(port=adapter, store=store)
    return service, store


def _add_memory(store: SqliteStore, memory_id: str, content: str) -> None:
    store.add_memory(
        MemoryItem(
            id=memory_id,
            content=content,
            tags=["test"],
            created_at=datetime.now(UTC),
            pinned=False,
            source="test",
            project_id="proj-1",
        )
    )


def test_backfill_generates_for_missing() -> None:
    service, store = _make_service()
    _add_memory(store, "m1", "hello")
    _add_memory(store, "m2", "world")
    result = service.generate_missing()
    assert result.generated == 2
    assert result.failed == 0
    assert store.count_embeddings() == 2


def test_backfill_skips_existing() -> None:
    service, store = _make_service()
    _add_memory(store, "m1", "hello")
    _add_memory(store, "m2", "world")
    service.generate_for_memory("m1", "hello")
    result = service.generate_missing()
    assert result.generated == 1  # only m2
    assert result.failed == 0


def test_force_regenerates_all() -> None:
    service, store = _make_service()
    _add_memory(store, "m1", "hello")
    service.generate_for_memory("m1", "hello")
    result = service.generate_missing(force=True)
    assert result.generated == 1  # regenerated m1
    assert result.failed == 0


def test_status_returns_coverage() -> None:
    service, store = _make_service()
    _add_memory(store, "m1", "hello")
    _add_memory(store, "m2", "world")
    service.generate_for_memory("m1", "hello")

    status = service.embedding_status()
    assert status["total_memories"] == 2
    assert status["embedded"] == 1
    assert status["missing"] == 1
    assert status["stale"] == 0


def test_empty_database_zero_counts() -> None:
    service, _store = _make_service()
    status = service.embedding_status()
    assert status["total_memories"] == 0
    assert status["embedded"] == 0
    assert status["missing"] == 0
    assert status["stale"] == 0
