"""Tests for the embedding-failure degradation policy."""

from __future__ import annotations

from pathlib import Path

from openchronicle.core.application.services.embedding_service import EmbeddingService
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort
from openchronicle.core.infrastructure.embedding.stub_adapter import StubEmbeddingAdapter
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


class _BrokenEmbeddingPort(EmbeddingPort):
    """Always raises on embed(); pretends to be a 4-dim model."""

    def model_name(self) -> str:
        return "broken"

    def dimensions(self) -> int:
        return 4

    def embed(self, _text: str) -> list[float]:
        raise RuntimeError("simulated provider down")

    def embed_batch(self, _texts: list[str]) -> list[list[float]]:
        raise RuntimeError("simulated provider down")


def _seeded_store(tmp_path: Path) -> SqliteStore:
    store = SqliteStore(str(tmp_path / "test.db"))
    store.init_schema()
    project = Project(id="proj-1", name="test")
    store.add_project(project)
    for i in range(3):
        store.add_memory(
            MemoryItem(
                id=f"mem-{i}",
                content=f"alpha beta document {i}",
                project_id=project.id,
                source="test",
            )
        )
    return store


def test_search_falls_back_to_fts5_when_provider_raises(tmp_path: Path) -> None:
    """When the embedding port raises, search returns FTS5-only results."""
    store = _seeded_store(tmp_path)
    service = EmbeddingService(port=_BrokenEmbeddingPort(), store=store)

    results = service.search_hybrid("alpha")
    # FTS5 alone still finds the matching items.
    assert len(results) >= 1
    assert all("alpha" in r.content for r in results)
    # Counter is bumped, status is degraded.
    assert service.search_failure_count == 1
    assert service.last_failure_at is not None
    store.close()


def test_search_recovery_clears_failure_counter(tmp_path: Path) -> None:
    """A successful semantic search resets the degraded marker."""
    store = _seeded_store(tmp_path)
    broken = EmbeddingService(port=_BrokenEmbeddingPort(), store=store)
    broken.search_hybrid("alpha")
    assert broken.search_failure_count == 1

    # Swap in a working port (simulates the provider coming back).
    broken._port = StubEmbeddingAdapter(dims=4)
    # First success path needs at least one embedded item; backfill them.
    broken.generate_missing(force=True)
    broken.search_hybrid("alpha")
    assert broken.search_failure_count == 0
    store.close()


def test_container_status_reports_degraded_after_failure(tmp_path: Path) -> None:
    """container.embedding_status_dict surfaces the degraded state."""
    store = _seeded_store(tmp_path)
    service = EmbeddingService(port=_BrokenEmbeddingPort(), store=store)

    # Build a minimal stub container with the slim dict-builder logic
    # under test. We can't construct CoreContainer here because it would
    # try to load real config; the key shape is what we assert.
    from unittest.mock import MagicMock

    from openchronicle.core.application.config.settings import EmbeddingSettings

    container = MagicMock()
    container.embedding_settings = EmbeddingSettings(provider="stub", model="broken")
    container.embedding_service = service
    container.maintenance_degraded = False

    # Trigger a degraded path
    service.search_hybrid("alpha")

    # Re-bind the real method onto the mock so we can call it
    from openchronicle.core.infrastructure.wiring.container import CoreContainer

    status = CoreContainer.embedding_status_dict(container)
    assert status["status"] == "degraded"
    assert status["search_failure_count"] >= 1
    assert status["last_search_failure_at"] is not None
    store.close()
