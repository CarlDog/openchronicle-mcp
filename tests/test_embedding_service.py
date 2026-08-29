"""Tests for EmbeddingService — hybrid search and embedding generation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from openchronicle.core.application.services.embedding_service import (
    EmbeddingService,
    _cosine_similarity,
)
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort
from openchronicle.core.infrastructure.embedding.stub_adapter import StubEmbeddingAdapter
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from tests.helpers.vectors import save_vec


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
) -> MemoryItem:
    item = MemoryItem(
        id=memory_id,
        content=content,
        tags=tags or ["test"],
        created_at=datetime.now(UTC),
        pinned=pinned,
        source="test",
        project_id=project_id,
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
    save_vec(store, "m1", [0.0] * 32, model="old-model", provider="stub")
    service.generate_for_memory("m1", "hello")
    assert store.get_embedding_model("m1") == "stub"


# ── generate_missing ────────────────────────────────────────────────


def test_generate_missing_backfills_all() -> None:
    service, store, _ = _make_service()
    for i in range(5):
        _add_memory(store, f"m{i}", f"content {i}")
    result = service.generate_missing()
    assert result.generated == 5
    assert result.failed == 0
    assert store.count_embeddings() == 5


def test_generate_missing_returns_count() -> None:
    service, store, _ = _make_service()
    _add_memory(store, "m1", "hello")
    service.generate_for_memory("m1", "hello")
    _add_memory(store, "m2", "world")
    result = service.generate_missing()
    assert result.generated == 1  # only m2 was missing
    assert result.failed == 0


def test_generate_missing_counts_failures() -> None:
    """Per-item exceptions must be counted, not silently swallowed.

    Regression guard for 2026-05-02: a broken embedding adapter caused all
    23 NAS-deployment items to fail, but memory_embed returned status=ok with
    generated=0 because the failure count wasn't propagated to callers.
    """
    from openchronicle.core.application.services.embedding_service import EmbeddingService
    from openchronicle.core.domain.ports.embedding_port import EmbeddingPort

    class BrokenAdapter(EmbeddingPort):
        def embed(self, text: str) -> list[float]:
            raise RuntimeError("simulated provider failure")

        def embed_batch(self, texts: list[str]) -> list[list[float]]:
            raise RuntimeError("simulated provider failure")

        def model_name(self) -> str:
            return "broken"

        def provider_name(self) -> str:
            return "test-provider"

        def model_revision(self) -> str | None:
            return None

        def settings_fingerprint(self) -> str:
            return "test-fp"

        def dimensions(self) -> int:
            return 32

    _, store, _ = _make_service()
    _add_memory(store, "m1", "hello")
    _add_memory(store, "m2", "world")
    broken_service = EmbeddingService(port=BrokenAdapter(), store=store)

    result = broken_service.generate_missing()
    assert result.generated == 0
    assert result.failed == 2
    assert result.elapsed_ms >= 0


# ── search_hybrid ───────────────────────────────────────────────────


def test_search_hybrid_returns_fts5_results_when_no_embeddings() -> None:
    service, store, _ = _make_service()
    _add_memory(store, "m1", "python programming language")
    results = service.search_hybrid("python")
    assert any(r.item.id == "m1" for r in results)


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
    ids = [r.item.id for r in results]
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


def test_search_hybrid_respects_tag_filter() -> None:
    service, store, _ = _make_service()
    _add_memory(store, "m1", "alpha beta gamma", tags=["decision"])
    _add_memory(store, "m2", "alpha beta gamma", tags=["rejected"])
    service.generate_for_memory("m1", "alpha beta gamma")
    service.generate_for_memory("m2", "alpha beta gamma")

    results = service.search_hybrid("alpha", tags=["decision"])
    ids = [r.item.id for r in results]
    assert "m1" in ids
    assert "m2" not in ids


def test_search_hybrid_respects_top_k() -> None:
    service, store, _ = _make_service()
    for i in range(10):
        _add_memory(store, f"m{i}", f"test content number {i}")
        service.generate_for_memory(f"m{i}", f"test content number {i}")

    results = service.search_hybrid("test", top_k=3)
    assert len(results) <= 3


def test_semantic_search_numpy_path_matches_python_dot_product() -> None:
    """The numpy-vectorized _semantic_search must produce the same ranking
    as a manual cosine-by-_cosine_similarity loop on every adapter that
    normalizes embeddings (which all of ours do)."""
    service, store, _ = _make_service()
    # 20 memories — enough that argpartition's k<N branch fires.
    for i in range(20):
        _add_memory(store, f"m{i}", f"unique content body number {i}")
        service.generate_for_memory(f"m{i}", f"unique content body number {i}")

    # Manual reference computation via _cosine_similarity loop.
    query = "content body"
    query_vec = service.port.embed(query)
    all_emb = store.list_embeddings()
    expected_ranking = [
        mid
        for mid, _ in sorted(
            ((mid, _cosine_similarity(query_vec, vec)) for mid, vec in all_emb.items()),
            key=lambda x: x[1],
            reverse=True,
        )[:8]
    ]

    actual = [mid for mid, _score in service._semantic_search(query, limit=8)]
    assert actual == expected_ranking


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


# ── search correctness regressions (2026-08-15 review) ──────────────


def test_search_hybrid_ignores_different_dims_stale_model_rows() -> None:
    """A model switch used to leave stale rows in the matmul. Different
    dims raised numpy's inhomogeneous-shape error, which the degradation
    handler swallowed — the whole semantic path silently fell back to
    FTS5-only until the 6-hourly backfill caught up.
    """
    service, store, _ = _make_service()
    _add_memory(store, "m1", "python programming")
    service.generate_for_memory("m1", "python programming")
    _add_memory(store, "m2", "zzz unrelated stale")
    save_vec(store, "m2", [0.5] * 8, model="old-model", provider="stub")  # 8 dims vs 32

    results = service.search_hybrid("python programming", top_k=5)

    assert service.search_failure_count == 0, "stale row must not degrade search"
    assert "m1" in [m.item.id for m in results]


def test_search_hybrid_excludes_same_dims_stale_model_rows() -> None:
    """Same dims, different model: the stale vector matmuls fine but the
    similarity is meaningless cross-space noise. Here the stale row is a
    verbatim copy of the query's own embedding, so pre-fix it ranked
    first; post-fix it is not a semantic candidate at all.
    """
    service, store, adapter = _make_service()
    _add_memory(store, "m1", "alpha topic")
    service.generate_for_memory("m1", "alpha topic")
    _add_memory(store, "m2", "zzz qqq xxx")  # no keyword overlap with query
    save_vec(store, "m2", adapter.embed("alpha topic"), model="old-model", provider="stub")

    results = service.search_hybrid("alpha topic", top_k=5)

    assert "m2" not in [m.item.id for m in results]


def test_search_hybrid_honors_include_pinned_false() -> None:
    """Regression (2026-08-15 review, verified live): with
    include_pinned=False the exclusion set was empty, so pinned items
    re-entered via the semantic channel and ranked first. The store-only
    path honored the flag; the hybrid path didn't.
    """
    service, store, _ = _make_service()
    _add_memory(store, "m1", "standing rule about deployments", pinned=True)
    service.generate_for_memory("m1", "standing rule about deployments")
    _add_memory(store, "m2", "deployments note")
    service.generate_for_memory("m2", "deployments note")

    results = service.search_hybrid("standing rule about deployments", top_k=5, include_pinned=False)

    ids = [m.item.id for m in results]
    assert "m1" not in ids
    assert "m2" in ids


def test_search_hybrid_pinned_appears_once_when_included() -> None:
    service, store, _ = _make_service()
    _add_memory(store, "m1", "pinned deployments rule", pinned=True)
    service.generate_for_memory("m1", "pinned deployments rule")

    results = service.search_hybrid("pinned deployments rule", top_k=5, include_pinned=True)

    assert [m.item.id for m in results].count("m1") == 1


def test_search_hybrid_tag_filtered_pinned_does_not_reenter() -> None:
    """A pinned item failing the tag filter must not sneak back in via
    the semantic channel — the exclusion set covers ALL pinned rows, not
    just the ones that survived the prepend's tag filter.
    """
    service, store, _ = _make_service()
    _add_memory(store, "m1", "gamma content", pinned=True, tags=["other"])
    service.generate_for_memory("m1", "gamma content")
    _add_memory(store, "m2", "gamma content two", tags=["wanted"])
    service.generate_for_memory("m2", "gamma content two")

    results = service.search_hybrid("gamma content", top_k=5, tags=["wanted"])

    ids = [m.item.id for m in results]
    assert "m1" not in ids
    assert "m2" in ids


# ── semantic eligibility precedes the top-N window (0002 batch A) ─────


class _FixedQueryPort(EmbeddingPort):
    """Port whose query embedding is a fixed unit vector; stored vectors
    are written directly to the store, so similarity is fully controlled."""

    def embed(self, text: str) -> list[float]:
        return [1.0, 0.0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]

    def model_name(self) -> str:
        return "fixed-test-model"

    def provider_name(self) -> str:
        return "test-provider"

    def model_revision(self) -> str | None:
        return None

    def settings_fingerprint(self) -> str:
        return "test-fp"

    def dimensions(self) -> int:
        return 2


def test_semantic_window_is_scope_aware() -> None:
    """Out-of-scope vectors must not consume the similarity top-N.

    Adversarial shape from the review: 20 OTHER-project memories with
    perfect similarity 1.0 outrank the single in-scope memory (0.6).
    With eligibility applied after the window (the old shape), a small
    limit filled entirely with out-of-scope ids and the in-scope match
    was missed; the window is now filtered to eligible ids first.
    """
    store = SqliteStore(db_path=":memory:")
    store.init_schema()
    store.add_project(Project(id="proj-in", name="in"))
    store.add_project(Project(id="proj-out", name="out"))
    port = _FixedQueryPort()
    service = EmbeddingService(port=port, store=store)

    for i in range(20):
        mid = f"out-{i:02d}"
        store.add_memory(MemoryItem(id=mid, content="perfect match elsewhere", project_id="proj-out"))
        save_vec(store, mid, [1.0, 0.0], model=port.model_name(), provider=port.provider_name())  # similarity 1.0
    store.add_memory(MemoryItem(id="in-scope", content="the one that counts", project_id="proj-in"))
    save_vec(store, "in-scope", [0.6, 0.8], model=port.model_name(), provider=port.provider_name())  # similarity 0.6

    ranked = service._semantic_search("query", project_id="proj-in", limit=2)  # noqa: SLF001
    assert [mid for mid, _sim in ranked] == ["in-scope"]


def test_semantic_window_is_tag_aware() -> None:
    """Same defect through the tags predicate instead of project scope."""
    store = SqliteStore(db_path=":memory:")
    store.init_schema()
    store.add_project(Project(id="proj-1", name="p"))
    port = _FixedQueryPort()
    service = EmbeddingService(port=port, store=store)

    for i in range(20):
        mid = f"untagged-{i:02d}"
        store.add_memory(MemoryItem(id=mid, content="noise", tags=[], project_id="proj-1"))
        save_vec(store, mid, [1.0, 0.0], model=port.model_name(), provider=port.provider_name())
    store.add_memory(MemoryItem(id="tagged", content="target", tags=["wanted"], project_id="proj-1"))
    save_vec(store, "tagged", [0.6, 0.8], model=port.model_name(), provider=port.provider_name())

    ranked = service._semantic_search("query", tags=["wanted"], limit=2)  # noqa: SLF001
    assert [mid for mid, _sim in ranked] == ["tagged"]


def test_eligible_ids_scope_includes_global_pins() -> None:
    """The eligibility set mirrors ranked search's include-mode scope:
    strict project plus pinned rows belonging to no project."""
    store = SqliteStore(db_path=":memory:")
    store.init_schema()
    store.add_project(Project(id="proj-1", name="p"))
    store.add_memory(MemoryItem(id="mine", content="x", project_id="proj-1"))
    store.add_memory(MemoryItem(id="global-pin", content="rule", pinned=True, project_id=None))
    store.add_memory(MemoryItem(id="global-unpinned", content="loose", project_id=None))

    eligible = store.eligible_memory_ids(project_id="proj-1")
    assert "mine" in eligible
    assert "global-pin" in eligible, "a standing rule belonging to no project applies inside one"
    assert "global-unpinned" not in eligible


# ── provider health covers every operation (0003 F4) ──────────────────


class _DeadPort(EmbeddingPort):
    def embed(self, text: str) -> list[float]:
        raise RuntimeError("provider down")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("provider down")

    def model_name(self) -> str:
        return "dead-model"

    def provider_name(self) -> str:
        return "test-provider"

    def model_revision(self) -> str | None:
        return None

    def settings_fingerprint(self) -> str:
        return "test-fp"

    def dimensions(self) -> int:
        return 2


def test_save_path_failures_are_visible_in_provider_health() -> None:
    """A dead provider used to read 'active' until someone searched —
    only search failures updated the counters, while every save failed
    silently. The boundary recorder now covers save too."""
    store = SqliteStore(db_path=":memory:")
    store.init_schema()
    store.add_memory(MemoryItem(id="m1", content="x"))
    service = EmbeddingService(port=_DeadPort(), store=store)

    with pytest.raises(RuntimeError):
        service.generate_for_memory("m1", "x", force=True)

    assert service.failure_count == 1
    assert service.last_failure_op == "save"
    assert service.last_failure_at is not None
    assert service.search_failure_count == 0, "the search-only counter keeps its meaning"


def test_backfill_failures_count_and_success_resets() -> None:
    store = SqliteStore(db_path=":memory:")
    store.init_schema()
    for i in range(3):
        store.add_memory(MemoryItem(id=f"m{i}", content=f"content {i}"))
    dead = EmbeddingService(port=_DeadPort(), store=store)

    result = dead.generate_missing()
    assert result.failed == 3 and result.generated == 0
    assert dead.failure_count == 3
    assert dead.last_failure_op == "backfill"

    # A healthy provider clears the consecutive counter on first success.
    healthy = EmbeddingService(port=StubEmbeddingAdapter(dims=8), store=store)
    healthy._failure_count = 5  # noqa: SLF001 — simulate accumulated failures
    healthy.generate_for_memory("m0", "content 0", force=True)
    assert healthy.failure_count == 0
    assert healthy.last_failure_op is None
