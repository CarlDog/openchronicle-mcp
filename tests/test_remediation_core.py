"""Tests validating Phase 1 to 6 and Batch 4/5 core remediations.

Covers:
1. Ollama adapter probe failure retry cooldown and recovery.
2. Ollama adapter HTTP connection pooling and client injection.
3. SQLite store empty ID list query syntax safety.
4. SQLite store batch memory retrieval and parameter chunking.
5. Embedding service batch candidate hydration and project scope filtering.
6. API rate limit middleware periodic sweep efficiency.
7. SQLite WAL concurrent reads during active write transactions.
8. SQLite read-your-own-writes consistency in open transactions.
9. SQLite thread-local reader connection cleanup on close.
10. Background vector embedding scheduling and asynchronous execution.
11. Background embed parameter support on API routes and MCP tools.
12. Context budget enforcement and omission reporting (max_chars).
13. Identity-scoped query LRU embedding cache.
14. In-flight singleflight request coalescing and failure isolation.
15. OpenAI adapter optional-send dimensions and empty batch handling.
16. Write idempotency and replay safety in add_memory.
17. Optimistic concurrency control (OCC) and expected revisions on memory updates.
18. Bounded write-transaction chunking for batch memory insertions (add_memories).
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from starlette.requests import Request
from starlette.responses import Response

from openchronicle.core.application.services.embedding_service import EmbeddingService
from openchronicle.core.application.use_cases import add_memory
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


# ── Phase 3: SQLite Concurrency & Background Embedding Tests ─────────


def test_sqlite_wal_concurrent_reads_during_write_transaction(tmp_path: Path) -> None:
    db_file = tmp_path / "concurrent.db"
    store = SqliteStore(db_path=str(db_file))
    store.init_schema()
    store.add_project(Project(id="p1", name="Project 1"))
    store.add_memory(_make_item("m1", "initial content", project_id="p1"))

    write_started = threading.Event()
    read_finished = threading.Event()
    read_result: dict[str, str | None] = {"content": None}

    def writer_worker() -> None:
        with store.transaction():
            store.add_memory(_make_item("m2", "uncommitted content", project_id="p1"))
            write_started.set()
            # Hold write transaction open until reader completes
            assert read_finished.wait(timeout=5.0)

    def reader_worker() -> None:
        assert write_started.wait(timeout=5.0)
        # In WAL mode, readers do not block on writers and read committed snapshot
        item = store.get_memory("m1")
        if item:
            read_result["content"] = item.content
        read_finished.set()

    t_writer = threading.Thread(target=writer_worker)
    t_reader = threading.Thread(target=reader_worker)

    t_writer.start()
    t_reader.start()

    t_reader.join(timeout=6.0)
    t_writer.join(timeout=6.0)

    assert read_result["content"] == "initial content"
    assert store.get_memory("m2") is not None
    store.close()


def test_sqlite_read_your_own_writes_in_transaction(tmp_path: Path) -> None:
    db_file = tmp_path / "read_own.db"
    store = SqliteStore(db_path=str(db_file))
    store.init_schema()
    store.add_project(Project(id="p1", name="Project 1"))

    with store.transaction():
        item = _make_item("tx-1", "in transaction content", project_id="p1")
        store.add_memory(item)
        # Read-your-own-writes: must be visible within the transaction
        read_back = store.get_memory("tx-1")
        assert read_back is not None
        assert read_back.content == "in transaction content"

    store.close()


def test_sqlite_reader_connections_cleaned_up_on_close(tmp_path: Path) -> None:
    db_file = tmp_path / "readers.db"
    store = SqliteStore(db_path=str(db_file))
    store.init_schema()
    store.add_project(Project(id="p1", name="Project 1"))
    store.add_memory(_make_item("m1", "content", project_id="p1"))

    def read_op() -> None:
        _ = store.get_memory("m1")

    threads = [threading.Thread(target=read_op) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(store._reader_conns) > 0
    store.close()
    assert len(store._reader_conns) == 0


def test_background_embedding_scheduling_and_execution() -> None:
    store = _make_store()
    adapter = StubEmbeddingAdapter(dims=4)
    service = EmbeddingService(port=adapter, store=store)

    item = _make_item("bg-mem-1", "background content to embed")
    saved = add_memory.execute(store, item, embedding_service=service, background_embed=True)

    # Item is persisted in store immediately
    assert store.get_memory(saved.id) is not None

    # Wait for the background worker thread to generate vector
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        emb = store.get_embedding("bg-mem-1")
        if emb is not None:
            break
        time.sleep(0.05)

    emb = store.get_embedding("bg-mem-1")
    assert emb is not None
    assert len(emb) == 4


def test_background_embed_api_schema() -> None:
    from openchronicle.interfaces.api.routes.memory import MemorySaveRequest

    req = MemorySaveRequest(
        content="test content",
        project_id="proj-1",
        background_embed=True,
    )
    assert req.background_embed is True


def test_context_budget_enforcement() -> None:
    from openchronicle.core.domain.context_budget import apply_char_budget

    items = ["short", "a much longer string", "tail"]
    # 1. None or 0 max_chars retains everything
    retained, total, truncated, omitted = apply_char_budget(items, lambda s: s, None)
    assert retained == items
    assert total == sum(len(s) for s in items)
    assert not truncated
    assert omitted == 0

    # 2. Budget limits items
    # "short" (5) + "a much longer string" (20) = 25
    retained, total, truncated, omitted = apply_char_budget(items, lambda s: s, 10)
    assert retained == ["short"]
    assert total == 5
    assert truncated is True
    assert omitted == 2

    # 3. Oversized first item is retained to prevent empty context
    retained, total, truncated, omitted = apply_char_budget(items, lambda s: s, 3)
    assert retained == ["short"]
    assert total == 5
    assert truncated is True
    assert omitted == 2


def test_search_memory_max_chars_budget() -> None:
    from openchronicle.core.application.use_cases import search_memory

    store = _make_store()
    item1 = _make_item("mem-budget-1", "alpha keyword text " + "x" * 100)
    item2 = _make_item("mem-budget-2", "alpha second entry " + "y" * 100)
    store.add_memory(item1)
    store.add_memory(item2)

    # Without max_chars, both match keyword search
    results = search_memory.execute(store, "alpha", mode="keyword")
    assert len(results) == 2

    # With tight max_chars, results are truncated to 1 item
    budgeted = search_memory.execute(store, "alpha", mode="keyword", max_chars=130)
    assert len(budgeted) == 1
    assert budgeted[0].item.id in ("mem-budget-1", "mem-budget-2")


def test_query_embedding_lru_cache() -> None:
    store = _make_store()
    adapter = StubEmbeddingAdapter(dims=4)
    call_count = 0
    orig_embed = adapter.embed

    def counting_embed(text: str) -> list[float]:
        nonlocal call_count
        call_count += 1
        return orig_embed(text)

    adapter.embed = counting_embed  # type: ignore[method-assign]
    service = EmbeddingService(port=adapter, store=store)

    assert service.query_cache_size == 0

    # First search: query embedding generated and cached
    vec1 = service._embed_query("test query")
    assert service.query_cache_size == 1
    assert call_count == 1

    # Second search with same query: cache hit, adapter not called again
    vec2 = service._embed_query("test query")
    assert vec1 == vec2
    assert service.query_cache_size == 1
    assert call_count == 1

    # Search with different query: cache miss
    service._embed_query("another query")
    assert service.query_cache_size == 2
    assert call_count == 2

    # Clear cache
    service.clear_query_cache()
    assert service.query_cache_size == 0


def test_query_embedding_singleflight_concurrency() -> None:
    store = _make_store()
    adapter = StubEmbeddingAdapter(dims=4)

    # Slow down embed to ensure concurrent calls overlap
    original_embed = adapter.embed
    call_count = 0
    lock = threading.Lock()

    def slow_embed(text: str) -> list[float]:
        nonlocal call_count
        with lock:
            call_count += 1
        time.sleep(0.05)
        return original_embed(text)

    adapter.embed = slow_embed  # type: ignore[method-assign]
    service = EmbeddingService(port=adapter, store=store)

    results: list[list[float]] = []
    threads = []

    def worker() -> None:
        v = service._embed_query("concurrent query")
        results.append(v)

    for _ in range(5):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert len(results) == 5
    # All threads got identical vectors
    assert all(r == results[0] for r in results)
    # But only a single provider call was dispatched!
    assert call_count == 1


def test_query_embedding_singleflight_failure_isolation() -> None:
    store = _make_store()
    adapter = StubEmbeddingAdapter(dims=4)

    def failing_embed(text: str) -> list[float]:
        time.sleep(0.02)
        raise RuntimeError("simulated provider crash")

    adapter.embed = failing_embed  # type: ignore[method-assign]
    service = EmbeddingService(port=adapter, store=store)

    exceptions: list[Exception] = []
    threads = []

    def worker() -> None:
        try:
            service._embed_query("failing query")
        except Exception as e:
            exceptions.append(e)

    for _ in range(3):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert len(exceptions) == 3
    assert all("simulated provider crash" in str(e) for e in exceptions)
    # Cache was not poisoned with failed result
    assert service.query_cache_size == 0


def test_query_embedding_singleflight_waiter_timeout_fallback() -> None:
    store = _make_store()
    adapter = StubEmbeddingAdapter(dims=4)
    setattr(adapter, "_timeout", -4.95)  # wait timeout becomes 0.05s

    service = EmbeddingService(port=adapter, store=store)

    leader_started = threading.Event()
    follower_done = threading.Event()
    results: dict[str, list[float]] = {}

    def slow_leader_embed(text: str) -> list[float]:
        leader_started.set()
        time.sleep(0.2)
        return [0.1, 0.2, 0.3, 0.4]

    def follower_worker() -> None:
        leader_started.wait()
        res = service._embed_query("timeout query")
        results["follower"] = res
        follower_done.set()

    adapter.embed = slow_leader_embed  # type: ignore[method-assign]
    t_follower = threading.Thread(target=follower_worker)

    # Leader starts and holds flight
    def leader_worker() -> None:
        res = service._embed_query("timeout query")
        results["leader"] = res

    t_leader = threading.Thread(target=leader_worker)
    t_leader.start()
    t_follower.start()

    t_follower.join(timeout=1.0)
    t_leader.join(timeout=1.0)

    assert "follower" in results
    assert "leader" in results
    assert len(results["follower"]) == 4


def test_add_memory_idempotency_identical_replay() -> None:
    store = _make_store()
    item = _make_item("idemp-1", "idempotent content", tags=["alpha", "beta"])

    saved1 = add_memory.execute(store, item)
    assert saved1.id == "idemp-1"

    # Replaying identical memory (same project, content, tags) succeeds cleanly
    saved2 = add_memory.execute(store, item)
    assert saved2.id == "idemp-1"
    assert saved2.content == "idempotent content"

    # Replay with same tags in different order succeeds cleanly
    item_reordered_tags = _make_item("idemp-1", "idempotent content", tags=["beta", "alpha"])
    saved3 = add_memory.execute(store, item_reordered_tags)
    assert saved3.id == "idemp-1"


def test_add_memory_idempotency_conflict_raises() -> None:
    from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError

    store = _make_store()
    item1 = _make_item("idemp-conflict-1", "initial content", tags=["t1"])
    add_memory.execute(store, item1)

    # Replaying same ID with different content fails fast
    item2 = _make_item("idemp-conflict-1", "different content", tags=["t1"])
    with pytest.raises(
        DomainValidationError, match="Memory already exists with id 'idemp-conflict-1' and different content"
    ):
        add_memory.execute(store, item2)

    # Replaying same ID with different project fails fast
    item3 = _make_item("idemp-conflict-1", "initial content", project_id="proj-2", tags=["t1"])
    with pytest.raises(
        DomainValidationError, match="Memory already exists with id 'idemp-conflict-1' and different content"
    ):
        add_memory.execute(store, item3)

    # Replaying same ID with different tags fails fast
    item4 = _make_item("idemp-conflict-1", "initial content", tags=["different-tag"])
    with pytest.raises(
        DomainValidationError, match="Memory already exists with id 'idemp-conflict-1' and different content"
    ):
        add_memory.execute(store, item4)


def test_update_memory_background_embed() -> None:
    from openchronicle.core.application.use_cases import update_memory

    store = _make_store()
    adapter = StubEmbeddingAdapter(dims=4)
    service = EmbeddingService(port=adapter, store=store)

    item = _make_item("update-bg-1", "initial text")
    add_memory.execute(store, item, embedding_service=service, background_embed=False)

    # Initial embedding exists
    assert store.get_embedding("update-bg-1") is not None

    # Update with background_embed=True schedules async embedding
    updated = update_memory.execute(
        store,
        memory_id="update-bg-1",
        content="updated background text",
        embedding_service=service,
        background_embed=True,
    )
    assert updated.content == "updated background text"

    # Background embedding worker processes the scheduled update
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        emb = store.get_embedding("update-bg-1")
        if emb is not None:
            break
        time.sleep(0.05)

    assert store.get_embedding("update-bg-1") is not None


def test_memory_save_and_update_api_schema() -> None:
    from openchronicle.interfaces.api.routes.memory import (
        MemorySaveRequest,
        MemoryUpdateRequest,
    )

    save_req = MemorySaveRequest(
        content="save text",
        project_id="proj-1",
        id="custom-uuid-1",
        background_embed=True,
    )
    assert save_req.id == "custom-uuid-1"
    assert save_req.background_embed is True

    update_req = MemoryUpdateRequest(
        content="update text",
        background_embed=True,
    )
    assert update_req.content == "update text"
    assert update_req.background_embed is True


def test_update_memory_occ_success_and_advances_revision() -> None:
    from openchronicle.core.application.use_cases import update_memory

    store = _make_store()
    item = _make_item("occ-test-1", "initial content")
    add_memory.execute(store, item)

    initial_rev = item.created_at.isoformat()

    # Successful update with initial created_at revision
    up1 = update_memory.execute(
        store,
        memory_id="occ-test-1",
        content="content revision 2",
        expected_updated_at=initial_rev,
    )
    assert up1.content == "content revision 2"
    assert up1.updated_at is not None
    rev2 = up1.updated_at.isoformat()

    # Subsequent update with rev2
    up2 = update_memory.execute(
        store,
        memory_id="occ-test-1",
        content="content revision 3",
        expected_updated_at=rev2,
    )
    assert up2.content == "content revision 3"
    assert up2.updated_at is not None
    assert up2.updated_at != up1.updated_at


def test_update_memory_occ_conflict_rejection() -> None:
    from openchronicle.core.application.use_cases import update_memory
    from openchronicle.core.domain.exceptions import ConflictError

    store = _make_store()
    item = _make_item("occ-conflict-1", "base content")
    add_memory.execute(store, item)

    initial_rev = item.created_at.isoformat()

    # First update succeeds and moves revision forward
    update_memory.execute(
        store,
        memory_id="occ-conflict-1",
        content="stolen content",
        expected_updated_at=initial_rev,
    )

    # Stale second editor using initial_rev must fail with ConflictError
    with pytest.raises(ConflictError, match="update conflict: expected revision"):
        update_memory.execute(
            store,
            memory_id="occ-conflict-1",
            content="stale overwrite attempt",
            expected_updated_at=initial_rev,
        )


def test_update_memory_occ_initial_tokens_and_unconditional() -> None:
    from openchronicle.core.application.use_cases import update_memory

    store = _make_store()
    item1 = _make_item("occ-token-1", "raw content 1")
    item2 = _make_item("occ-token-2", "raw content 2")
    add_memory.execute(store, item1)
    add_memory.execute(store, item2)

    # "null", "none", or "initial" matches an un-updated memory
    up1 = update_memory.execute(
        store,
        memory_id="occ-token-1",
        content="updated via initial token",
        expected_updated_at="initial",
    )
    assert up1.content == "updated via initial token"

    # Unconditional update when expected_updated_at is None
    up2 = update_memory.execute(
        store,
        memory_id="occ-token-2",
        content="updated unconditionally",
        expected_updated_at=None,
    )
    assert up2.content == "updated unconditionally"


def test_update_memory_occ_not_found() -> None:
    from openchronicle.core.application.use_cases import update_memory
    from openchronicle.core.domain.exceptions import NotFoundError

    store = _make_store()
    with pytest.raises(NotFoundError, match="Memory not found"):
        update_memory.execute(
            store,
            memory_id="nonexistent-mem",
            content="text",
            expected_updated_at="2026-01-01T00:00:00Z",
        )


def test_add_memories_chunked_batch() -> None:
    store = _make_store()
    items = [_make_item(f"batch-item-{i}", f"content {i}") for i in range(25)]

    # Slices into 5 chunks of 5 items
    store.add_memories(items, chunk_size=5)

    assert store.count_memory("proj-1") == 25
    fetched = store.get_memories([f"batch-item-{i}" for i in range(25)])
    assert len(fetched) == 25
    assert fetched["batch-item-0"].content == "content 0"
    assert fetched["batch-item-24"].content == "content 24"


def test_add_memories_empty_and_foreign_key_guard() -> None:
    from openchronicle.core.domain.exceptions import NotFoundError

    store = _make_store()
    # Empty batch is no-op
    store.add_memories([], chunk_size=10)

    # Invalid project ID raises NotFoundError
    bad_item = _make_item("bad-proj-item", "text", project_id="unknown-project")
    with pytest.raises(NotFoundError, match="Foreign key constraint failed"):
        store.add_memories([bad_item], chunk_size=10)


def test_memory_update_request_expected_updated_at() -> None:
    from openchronicle.interfaces.api.routes.memory import MemoryUpdateRequest

    req = MemoryUpdateRequest(
        content="occ payload",
        expected_updated_at="2026-09-19T06:00:00+00:00",
    )
    assert req.content == "occ payload"
    assert req.expected_updated_at == "2026-09-19T06:00:00+00:00"


def test_concurrent_idempotent_add_memory(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    from openchronicle.core.application.use_cases import add_memory
    from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
    from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

    db_path = tmp_path / "concurrent_idempotent.db"
    store = SqliteStore(str(db_path))
    store.init_schema()
    store.add_project(Project(id="proj-1", name="Project 1"))

    item = _make_item("shared-concurrent-id", "idempotent content", tags=["a", "b"])

    def _insert() -> MemoryItem:
        return add_memory.execute(store, item)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(_insert) for _ in range(4)]
        results = [f.result() for f in futures]

    assert len(results) == 4
    for res in results:
        assert res.id == "shared-concurrent-id"
        assert res.content == "idempotent content"

    # Conflicting insert on existing id raises DomainValidationError
    conflicting = _make_item("shared-concurrent-id", "different content", tags=["a", "b"])
    with pytest.raises(DomainValidationError, match="different content"):
        add_memory.execute(store, conflicting)
