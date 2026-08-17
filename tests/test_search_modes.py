"""Tests for the search-surface v2 mode dispatch (Q20/Q21, 2026-08-17).

Covers the `mode` parameter on search_memory.execute, the per-channel
relevance fields on ScoredMemory, and the no-silent-degradation contract
of mode="semantic".
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from openchronicle.core.application.services.embedding_service import EmbeddingService
from openchronicle.core.application.use_cases import search_memory
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort
from openchronicle.core.infrastructure.embedding.stub_adapter import StubEmbeddingAdapter
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


class _BrokenPort(EmbeddingPort):
    """Raises on embed(); lets tests prove a path never touches the provider."""

    def model_name(self) -> str:
        return "broken"

    def dimensions(self) -> int:
        return 32

    def embed(self, _text: str) -> list[float]:
        raise RuntimeError("provider must not be called")

    def embed_batch(self, _texts: list[str]) -> list[list[float]]:
        raise RuntimeError("provider must not be called")


def _make_store() -> SqliteStore:
    store = SqliteStore(db_path=":memory:")
    store.init_schema()
    store.add_project(Project(id="proj-1", name="test"))
    return store


def _add(
    store: SqliteStore,
    memory_id: str,
    content: str,
    *,
    pinned: bool = False,
    created_at: datetime | None = None,
) -> MemoryItem:
    item = MemoryItem(
        id=memory_id,
        content=content,
        tags=["test"],
        created_at=created_at or datetime.now(UTC),
        pinned=pinned,
        source="test",
        project_id="proj-1",
    )
    store.add_memory(item)
    return item


# ── mode validation ─────────────────────────────────────────────────


def test_invalid_mode_raises() -> None:
    store = _make_store()
    with pytest.raises(DomainValidationError, match="mode must be one of"):
        search_memory.execute(store, "query", mode="cosmic")


def test_semantic_without_provider_raises() -> None:
    store = _make_store()
    with pytest.raises(DomainValidationError, match="requires an embedding provider"):
        search_memory.execute(store, "query", mode="semantic", embedding_service=None)


# ── mode=keyword ────────────────────────────────────────────────────


def test_keyword_mode_never_touches_the_provider() -> None:
    """mode="keyword" must not embed anything — even with a service wired.

    The _BrokenPort raises on any embed call, so reaching the provider
    would fail this test loudly.
    """
    store = _make_store()
    _add(store, "m1", "python programming language")
    service = EmbeddingService(port=_BrokenPort(), store=store)

    results = search_memory.execute(store, "python", mode="keyword", embedding_service=service)

    assert [s.item.id for s in results] == ["m1"]
    assert results[0].channel == "keyword"
    assert results[0].keyword_rank == 1
    assert results[0].rrf_score is None
    assert results[0].semantic_similarity is None
    assert service.search_failure_count == 0, "keyword mode is a bypass, not a degradation"


def test_keyword_mode_marks_pinned_channel() -> None:
    store = _make_store()
    _add(store, "m1", "standing rule about python", pinned=True)
    _add(store, "m2", "python note")

    results = search_memory.execute(store, "python", mode="keyword")

    by_id = {s.item.id: s for s in results}
    assert by_id["m1"].channel == "pinned"
    assert by_id["m1"].keyword_rank is None, "pinned prepend is policy, not ranking"
    assert by_id["m2"].channel == "keyword"


def test_keyword_mode_phrase_requires_adjacency() -> None:
    store = _make_store()
    _add(store, "m1", "the quick brown fox jumps")
    _add(store, "m2", "brown bread and a quick snack")

    any_token = search_memory.execute(store, "quick brown", mode="keyword")
    assert {s.item.id for s in any_token} == {"m1", "m2"}

    adjacent = search_memory.execute(store, "quick brown", mode="keyword", phrase=True)
    assert {s.item.id for s in adjacent} == {"m1"}


# ── mode=semantic ───────────────────────────────────────────────────


def test_semantic_mode_returns_similarity_scored_results() -> None:
    store = _make_store()
    adapter = StubEmbeddingAdapter(dims=32)
    service = EmbeddingService(port=adapter, store=store)
    _add(store, "m1", "machine learning models")
    _add(store, "m2", "cooking recipes for pasta")
    service.generate_for_memory("m1", "machine learning models")
    service.generate_for_memory("m2", "cooking recipes for pasta")

    results = search_memory.execute(store, "machine learning models", mode="semantic", embedding_service=service)

    assert results, "exact-content query must rank its own embedding"
    top = results[0]
    assert top.item.id == "m1"
    assert top.channel == "semantic"
    assert top.semantic_similarity == pytest.approx(1.0, abs=1e-5)
    assert top.keyword_rank is None
    assert top.rrf_score is None


def test_semantic_mode_skips_unembedded_items() -> None:
    """Keyword-only matches (no embedding row) never appear in semantic mode."""
    store = _make_store()
    adapter = StubEmbeddingAdapter(dims=32)
    service = EmbeddingService(port=adapter, store=store)
    _add(store, "m1", "alpha topic")
    service.generate_for_memory("m1", "alpha topic")
    _add(store, "m2", "alpha topic no embedding")

    results = search_memory.execute(store, "alpha topic", mode="semantic", embedding_service=service)

    ids = [s.item.id for s in results]
    assert "m1" in ids
    assert "m2" not in ids


def test_semantic_mode_provider_failure_raises_not_degrades() -> None:
    """Hybrid degrades to keyword on provider failure; semantic must not —
    the caller explicitly asked for semantic results.
    """
    store = _make_store()
    _add(store, "m1", "alpha content")
    service = EmbeddingService(port=_BrokenPort(), store=store)

    with pytest.raises(RuntimeError, match="provider must not be called"):
        search_memory.execute(store, "alpha", mode="semantic", embedding_service=service)


# ── mode=hybrid relevance fields ────────────────────────────────────


def test_hybrid_mode_channel_and_score_fields() -> None:
    """An item hit by both channels reports channel="hybrid" and carries
    all three signals; the pinned prepend carries none.
    """
    store = _make_store()
    adapter = StubEmbeddingAdapter(dims=32)
    service = EmbeddingService(port=adapter, store=store)
    _add(store, "m1", "database optimization query performance")
    service.generate_for_memory("m1", "database optimization query performance")
    _add(store, "pin-1", "standing database rule", pinned=True)

    results = search_memory.execute(
        store, "database optimization query performance", mode="hybrid", embedding_service=service
    )

    by_id = {s.item.id: s for s in results}
    hit = by_id["m1"]
    assert hit.channel == "hybrid"
    assert hit.rrf_score is not None and hit.rrf_score > 0
    assert hit.semantic_similarity == pytest.approx(1.0, abs=1e-5)
    assert hit.keyword_rank == 1
    pin = by_id["pin-1"]
    assert pin.channel == "pinned"
    assert pin.rrf_score is None
    assert pin.semantic_similarity is None
    assert pin.keyword_rank is None


# ── pinned_limit (bounded prepend) ──────────────────────────────────


def _add_pins(store: SqliteStore, count: int, content: str = "standing rule") -> None:
    """Add `count` pinned items with strictly increasing created_at, so
    pin-N is the newest and the newest-first cap is deterministic."""
    for i in range(count):
        _add(
            store,
            f"pin-{i}",
            f"{content} {i}",
            pinned=True,
            created_at=datetime(2026, 8, 1, 12, 0, i, tzinfo=UTC),
        )


def test_keyword_mode_caps_pinned_prepend_to_newest() -> None:
    """Observed live (2026-08-17): a top_k=2 search against an 85-pin
    store returned 87 results. The prepend is now bounded, keeping the
    newest pins."""
    store = _make_store()
    _add_pins(store, 12, content="alpha rule")
    _add(store, "m1", "alpha note")

    results = search_memory.execute(store, "alpha", mode="keyword", top_k=2)

    pins = [s.item.id for s in results if s.channel == "pinned"]
    assert len(pins) == 10, "default pinned_limit is 10"
    assert "pin-11" in pins and "pin-2" in pins, "newest pins survive"
    assert "pin-0" not in pins and "pin-1" not in pins, "oldest pins are capped out"
    assert [s.item.id for s in results if s.channel == "keyword"] == ["m1"]


def test_pinned_limit_zero_disables_prepend() -> None:
    store = _make_store()
    _add_pins(store, 3, content="alpha rule")
    _add(store, "m1", "alpha note")

    results = search_memory.execute(store, "alpha", mode="keyword", pinned_limit=0)

    assert [s.item.id for s in results] == ["m1"]


def test_hybrid_mode_caps_prepend_and_capped_pin_does_not_reenter() -> None:
    """A capped-out pin must not sneak back in through the semantic
    channel — the exclusion set covers ALL pins, not just the shown ones.
    The capped pin here has an embedding that exactly matches the query,
    so pre-guard it would rank first semantically.
    """
    store = _make_store()
    adapter = StubEmbeddingAdapter(dims=32)
    service = EmbeddingService(port=adapter, store=store)
    _add(store, "pin-old", "gamma standing rule", pinned=True, created_at=datetime(2026, 8, 1, tzinfo=UTC))
    service.generate_for_memory("pin-old", "gamma standing rule")
    _add(store, "pin-new", "unrelated pin", pinned=True, created_at=datetime(2026, 8, 2, tzinfo=UTC))
    _add(store, "m1", "gamma note")
    service.generate_for_memory("m1", "gamma note")

    results = search_memory.execute(
        store, "gamma standing rule", mode="hybrid", embedding_service=service, pinned_limit=1
    )

    ids = [s.item.id for s in results]
    assert "pin-new" in ids, "the newest pin fills the budget"
    assert "pin-old" not in ids, "capped-out pin must not re-enter via ranking"
    assert "m1" in ids


def test_semantic_mode_caps_pinned_prepend() -> None:
    store = _make_store()
    adapter = StubEmbeddingAdapter(dims=32)
    service = EmbeddingService(port=adapter, store=store)
    _add_pins(store, 4)
    _add(store, "m1", "delta content")
    service.generate_for_memory("m1", "delta content")

    results = search_memory.execute(store, "delta content", mode="semantic", embedding_service=service, pinned_limit=2)

    pins = [s.item.id for s in results if s.channel == "pinned"]
    assert pins == ["pin-3", "pin-2"], "newest two pins, in newest-first order"
    assert "m1" in [s.item.id for s in results]


def test_negative_pinned_limit_is_treated_as_zero() -> None:
    """list[:negative] silently drops from the END — the normalization
    guard makes a negative cap mean 'no pins', never a surprise slice."""
    store = _make_store()
    _add_pins(store, 3, content="alpha rule")
    _add(store, "m1", "alpha note")

    results = search_memory.execute(store, "alpha", mode="keyword", pinned_limit=-5)

    assert [s.item.id for s in results] == ["m1"]
