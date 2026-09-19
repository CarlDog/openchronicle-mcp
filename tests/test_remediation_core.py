"""Tests validating Phase 1 and 2 core remediations.

Covers:
1. Ollama adapter probe failure retry cooldown and recovery.
2. Ollama adapter HTTP connection pooling and client injection.
3. SQLite store empty ID list query syntax safety.
4. SQLite store batch memory retrieval and parameter chunking.
5. Embedding service batch candidate hydration and project scope filtering.
6. API rate limit middleware periodic sweep efficiency.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest
from starlette.requests import Request
from starlette.responses import Response

from openchronicle.core.application.services.embedding_service import EmbeddingService
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.infrastructure.embedding.ollama_adapter import (
    _PROBE_RETRY_INTERVAL,
    OllamaEmbeddingAdapter,
)
from openchronicle.core.infrastructure.embedding.stub_adapter import StubEmbeddingAdapter
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.interfaces.api.middleware.rate_limit import RateLimitMiddleware
from tests.helpers.vectors import save_vec


def _make_store() -> SqliteStore:
    store = SqliteStore(db_path=":memory:")
    store.init_schema()
    store.add_project(Project(id="proj-1", name="Test Project 1"))
    store.add_project(Project(id="proj-2", name="Test Project 2"))
    return store


def _make_item(
    item_id: str,
    content: str,
    *,
    project_id: str = "proj-1",
    pinned: bool = False,
    tags: list[str] | None = None,
) -> MemoryItem:
    return MemoryItem(
        id=item_id,
        content=content,
        tags=tags or ["test"],
        created_at=datetime.now(UTC),
        pinned=pinned,
        source="unit_test",
        project_id=project_id,
    )


# ── Ollama Adapter Tests ───────────────────────────────────────────────


def test_ollama_probe_retries_after_network_failure() -> None:
    adapter = OllamaEmbeddingAdapter(
        model="nomic-embed-text",
        host="http://localhost:11434",
        timeout_seconds=5.0,
    )

    t0 = 1000.0
    with (
        patch("time.monotonic", return_value=t0),
        patch("httpx.get", side_effect=httpx.ConnectError("refused")),
    ):
        assert adapter.model_revision() is None
        assert adapter._probe_failed is True

    # Immediate subsequent call before cooldown expires should not re-query
    with (
        patch("time.monotonic", return_value=t0 + 5.0),
        patch("httpx.get") as mock_get,
    ):
        assert adapter.model_revision() is None
        mock_get.assert_not_called()

    # After cooldown expires, probe retries and succeeds
    tags_resp = httpx.Response(
        200,
        json={"models": [{"name": "nomic-embed-text:latest", "digest": "sha256:recovered"}]},
        request=httpx.Request("GET", "http://localhost:11434/api/tags"),
    )
    with (
        patch("time.monotonic", return_value=t0 + _PROBE_RETRY_INTERVAL + 1.0),
        patch("httpx.get", return_value=tags_resp) as mock_get_recovered,
    ):
        assert adapter.model_revision() == "sha256:recovered"
        assert adapter._probe_failed is False
        mock_get_recovered.assert_called_once()


def test_ollama_custom_client_and_close() -> None:
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.return_value = httpx.Response(
        200,
        json={"embeddings": [[0.1, 0.2, 0.3]]},
        request=httpx.Request("POST", "http://localhost:11434/api/embed"),
    )
    adapter = OllamaEmbeddingAdapter(
        model="nomic-embed-text",
        host="http://localhost:11434",
        client=mock_client,
    )

    vec = adapter.embed("hello")
    assert len(vec) == 3
    mock_client.post.assert_called_once()

    adapter.close()
    assert adapter._owned_client is None


# ── SQLite Store Tests ─────────────────────────────────────────────────


def test_sqlite_list_embeddings_empty_list_returns_empty_dict() -> None:
    store = _make_store()
    # Must not raise sqlite3.OperationalError (syntax error on IN ())
    result = store.list_embeddings(memory_ids=[])
    assert result == {}


def test_sqlite_get_memories_batch_and_chunking() -> None:
    store = _make_store()
    item1 = _make_item("mem-1", "first content")
    item2 = _make_item("mem-2", "second content")
    store.add_memory(item1)
    store.add_memory(item2)

    # Empty list
    assert store.get_memories([]) == {}

    # Subset and missing ID
    batch = store.get_memories(["mem-1", "mem-2", "mem-missing"])
    assert len(batch) == 2
    assert batch["mem-1"].content == "first content"
    assert batch["mem-2"].content == "second content"
    assert "mem-missing" not in batch

    # Parameter limit safety: query with 600 IDs
    bulk_ids = [f"bulk-id-{i}" for i in range(600)]
    bulk_ids.append("mem-1")
    bulk_res = store.get_memories(bulk_ids)
    assert len(bulk_res) == 1
    assert bulk_res["mem-1"].content == "first content"


def test_sqlite_list_embeddings_chunking() -> None:
    store = _make_store()
    item = _make_item("mem-1", "chunk test content")
    store.add_memory(item)
    save_vec(store, "mem-1", vec=[0.1, 0.2, 0.3])

    bulk_ids = [f"bulk-id-{i}" for i in range(600)]
    bulk_ids.append("mem-1")
    res = store.list_embeddings(memory_ids=bulk_ids)
    assert "mem-1" in res
    assert len(res["mem-1"]) == 3


# ── Embedding Service Tests ────────────────────────────────────────────


def test_embedding_service_hybrid_batch_hydration() -> None:
    store = _make_store()
    item1 = _make_item("m1", "alpha documentation", tags=["docs"])
    item2 = _make_item("m2", "completely different phrasing", tags=["other"])
    store.add_memory(item1)
    store.add_memory(item2)

    adapter = StubEmbeddingAdapter(dims=4)
    service = EmbeddingService(port=adapter, store=store)
    service.generate_for_memory("m1", item1.content)
    service.generate_for_memory("m2", item2.content)

    with patch.object(store, "get_memories", wraps=store.get_memories) as mock_get_memories:
        results = service.search_hybrid("documentation", top_k=5)
        assert len(results) > 0
        # Verify batch get_memories was called for the semantic-only item m2
        assert mock_get_memories.called
        call_ids = mock_get_memories.call_args[0][0]
        assert "m2" in call_ids


def test_embedding_service_semantic_batch_hydration_and_scoping() -> None:
    store = _make_store()
    item1 = _make_item("m1", "alpha documentation", project_id="proj-1")
    item2 = _make_item("m2", "beta documentation", project_id="proj-2")
    store.add_memory(item1)
    store.add_memory(item2)

    adapter = StubEmbeddingAdapter(dims=4)
    service = EmbeddingService(port=adapter, store=store)
    service.generate_for_memory("m1", item1.content)
    service.generate_for_memory("m2", item2.content)

    with (
        patch.object(store, "get_memories", wraps=store.get_memories) as mock_get_memories,
        patch.object(store, "list_embeddings", wraps=store.list_embeddings) as mock_list_embeddings,
    ):
        results = service.search_semantic("documentation", project_id="proj-1", top_k=5)
        assert len(results) == 1
        assert results[0].item.id == "m1"
        assert mock_get_memories.called

        # Verify that list_embeddings received memory_ids filtered to proj-1's eligible items
        call_kwargs = mock_list_embeddings.call_args.kwargs
        assert call_kwargs.get("memory_ids") == ["m1"]


# ── Rate Limit Middleware Tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_rate_limit_periodic_sweep_cleans_idle_clients() -> None:
    app_mock = MagicMock()
    middleware = RateLimitMiddleware(app_mock)
    middleware._window = 10
    middleware._sweep_interval = 20.0

    async def dummy_next(req: Request) -> Response:
        return Response("ok")

    t0 = 1000.0
    # Simulate an old client request at t0
    req_idle = MagicMock(spec=Request)
    req_idle.client.host = "192.168.1.100"
    with patch("time.monotonic", return_value=t0):
        await middleware.dispatch(req_idle, dummy_next)

    assert "192.168.1.100" in middleware._requests

    # Simulate active client request at t0 + 5s (before sweep interval)
    req_active = MagicMock(spec=Request)
    req_active.client.host = "192.168.1.200"
    with patch("time.monotonic", return_value=t0 + 5.0):
        await middleware.dispatch(req_active, dummy_next)

    assert "192.168.1.100" in middleware._requests
    assert "192.168.1.200" in middleware._requests

    # Simulate request at t0 + 25s (sweep interval elapsed, idle client window expired)
    with patch("time.monotonic", return_value=t0 + 25.0):
        await middleware.dispatch(req_active, dummy_next)

    # Idle client should be pruned by the periodic sweep
    assert "192.168.1.100" not in middleware._requests
    assert "192.168.1.200" in middleware._requests
