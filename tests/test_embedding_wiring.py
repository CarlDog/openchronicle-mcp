"""Tests for embedding pipeline wiring — container, use cases, fallback."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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
    item = _make_item()
    add_memory.execute(store, item, embedding_service=service)
    assert store.get_embedding("m1") is not None


def test_update_memory_regenerates_on_content_change() -> None:
    store, service = _make_store_and_service()
    item = _make_item()
    add_memory.execute(store, item, embedding_service=service)

    original_vec = store.get_embedding("m1")
    update_memory.execute(store, "m1", content="new content", embedding_service=service)
    new_vec = store.get_embedding("m1")
    # Embedding should change because content changed
    # (stub deterministically produces different vectors for different text)
    assert new_vec != original_vec


def test_update_memory_skips_regeneration_tags_only() -> None:
    store, service = _make_store_and_service()
    item = _make_item()
    add_memory.execute(store, item, embedding_service=service)

    original_vec = store.get_embedding("m1")
    update_memory.execute(store, "m1", tags=["new-tag"], embedding_service=service)
    new_vec = store.get_embedding("m1")
    # Tags-only change should NOT regenerate embedding
    assert new_vec == original_vec


def test_search_memory_uses_hybrid_when_service_available() -> None:
    store, service = _make_store_and_service()
    item = _make_item(content="python programming")
    store.add_memory(item)
    service.generate_for_memory("m1", "python programming")

    results = search_memory.execute(store, "python", embedding_service=service)
    assert any(r.item.id == "m1" for r in results)


def test_search_memory_falls_back_to_fts5_without_service() -> None:
    store, _ = _make_store_and_service()
    item = _make_item(content="python programming")
    store.add_memory(item)

    results = search_memory.execute(store, "python", embedding_service=None)
    assert any(r.item.id == "m1" for r in results)


# ── Backfill resilience ────────────────────────────────────────────


def test_generate_missing_skips_failures_and_continues() -> None:
    """A persistently-bad item must not abort the backfill.

    Failure is keyed to the ITEM, not the call count: since Phase D the
    backfill goes batch-first with a per-item fallback, so a one-call
    transient blip now heals on the retry (deliberately). What this
    test pins is the per-item resilience contract — the bad item fails,
    its neighbours land.
    """
    store, service = _make_store_and_service()
    for i in range(3):
        store.add_memory(_make_item(memory_id=f"m{i}", content=f"content {i}"))

    original_embed = service.port.embed
    original_batch = service.port.embed_batch

    def bad_item_embed(text: str) -> list[float]:
        if text == "content 1":
            raise RuntimeError("simulated API failure for this item")
        return original_embed(text)

    def bad_item_batch(texts: list[str]) -> list[list[float]]:
        if "content 1" in texts:
            raise RuntimeError("simulated API failure in the batch")
        return original_batch(texts)

    service._port.embed = bad_item_embed  # type: ignore[method-assign]
    service._port.embed_batch = bad_item_batch  # type: ignore[method-assign]

    result = service.generate_missing()
    assert result.generated == 2  # 2 succeeded
    assert result.failed == 1  # 1 failed
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

    result = service.generate_missing()
    assert result.generated == 0
    assert result.failed == 0


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
    container.storage = store

    result = CoreContainer.embedding_status_dict(container)
    assert result["status"] == "active"
    assert result["provider"] == "stub"
    assert result["model"] == "stub"
    assert result["dimensions"] == 32
    # The dimensions-truth trio (0003 F2): request, claim, measured fact.
    assert result["configured_dimensions"] is None
    assert result["stored_dimensions"] == [32]
    assert result["model_revision"] is None
    assert result["total_memories"] == 1
    assert result["embedded"] == 1
    assert result["missing"] == 0


# ── content-egress notice (operator-directed 2026-08-29) ──────────────


class TestContentEgressNotice:
    """A cloud embedding provider must be a MADE choice, never a silent
    default: the container warns at startup and health carries the fact."""

    def test_private_host_classification(self) -> None:
        from openchronicle.core.infrastructure.wiring.container import _looks_private_host

        local = [
            "http://localhost:11434",
            "http://127.0.0.1:11434",
            "http://[::1]:11434",
            "http://host.docker.internal:11434",
            "http://192.168.1.50:11434",
            "http://10.0.0.5:11434",
            "http://carldog-nas:11434",  # single-label LAN name
            "http://nas.local:11434",
            "http://ollama.internal:11434",
        ]
        remote = [
            "https://api.openai.com/v1",
            "https://api.voyageai.com/v1",
            "https://ollama.com",
            "https://nas.example.com:11434",  # public-looking FQDN: fail-safe -> warn
        ]
        for url in local:
            assert _looks_private_host(url), f"{url} should classify local"
        for url in remote:
            assert not _looks_private_host(url), f"{url} should classify remote"

    def _container_with(self, monkeypatch: pytest.MonkeyPatch, provider: str, **env: str) -> MagicMock:
        from openchronicle.core.application.config.settings import EmbeddingSettings
        from openchronicle.core.infrastructure.wiring.container import CoreContainer

        for key in ("OPENAI_BASE_URL", "OLLAMA_HOST", "OLLAMA_BASE_URL"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        container = MagicMock(spec=CoreContainer)
        container.embedding_settings = EmbeddingSettings(provider=provider)
        container._embedding_endpoint = lambda: CoreContainer._embedding_endpoint(container)
        container.embedding_endpoint_is_remote = lambda: CoreContainer.embedding_endpoint_is_remote(container)
        return container

    def test_default_openai_is_remote(self, monkeypatch: pytest.MonkeyPatch) -> None:
        c = self._container_with(monkeypatch, "openai")
        assert c.embedding_endpoint_is_remote() is True

    def test_lan_ollama_is_local_but_cloud_ollama_is_remote(self, monkeypatch: pytest.MonkeyPatch) -> None:
        c = self._container_with(monkeypatch, "ollama", OLLAMA_HOST="http://host.docker.internal:11434")
        assert c.embedding_endpoint_is_remote() is False
        c2 = self._container_with(monkeypatch, "ollama", OLLAMA_HOST="https://ollama.com")
        assert c2.embedding_endpoint_is_remote() is True, "ollama pointed at a cloud host is still egress"

    def test_stub_and_none_are_never_remote(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._container_with(monkeypatch, "stub").embedding_endpoint_is_remote() is False
        assert self._container_with(monkeypatch, "none").embedding_endpoint_is_remote() is False

    def test_health_carries_the_egress_fact(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from openchronicle.core.application.config.settings import EmbeddingSettings
        from openchronicle.core.infrastructure.wiring.container import CoreContainer

        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        store, service = _make_store_and_service()
        container = MagicMock(spec=CoreContainer)
        container.embedding_settings = EmbeddingSettings(provider="stub")
        container.embedding_service = service
        container.storage = store
        container._embedding_endpoint = lambda: CoreContainer._embedding_endpoint(container)
        container.embedding_endpoint_is_remote = lambda: CoreContainer.embedding_endpoint_is_remote(container)

        result = CoreContainer.embedding_status_dict(container)
        assert result["content_egress"] == "local"

    def test_startup_warning_fires_for_remote_endpoint(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
    ) -> None:
        import logging

        from openchronicle.core.infrastructure.wiring.container import CoreContainer

        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        (tmp_path / "config").mkdir()
        monkeypatch.setenv("OC_DB_PATH", str(tmp_path / "egress.db"))
        monkeypatch.setenv("OC_CONFIG_DIR", str(tmp_path / "config"))
        monkeypatch.setenv("OC_EMBEDDING_PROVIDER", "stub")
        with caplog.at_level(logging.WARNING):
            container = CoreContainer()
            try:
                # stub is local — no warning
                assert not [r for r in caplog.records if "content leaves this host" in r.getMessage()]
            finally:
                container.close()

        monkeypatch.setenv("OC_EMBEDDING_PROVIDER", "ollama")
        monkeypatch.setenv("OLLAMA_HOST", "https://ollama.com")
        with caplog.at_level(logging.WARNING):
            container = CoreContainer()
            try:
                warnings = [r for r in caplog.records if "content leaves this host" in r.getMessage()]
                assert warnings, "a remote embedding endpoint must warn at startup"
                assert "ollama.com" in warnings[0].getMessage()
            finally:
                container.close()
