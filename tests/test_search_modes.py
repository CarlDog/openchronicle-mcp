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

    def provider_name(self) -> str:
        return "test-provider"

    def model_revision(self) -> str | None:
        return None

    def settings_fingerprint(self) -> str:
        return "test-fp"

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


def test_keyword_mode_pins_report_their_ranked_channel() -> None:
    """ADR 0008: no float — a pinned row surfaces through the ranking
    and reports channel="keyword" with its honest rank. The "pinned"
    channel value no longer occurs in any mode."""
    store = _make_store()
    _add(store, "m1", "standing rule about python", pinned=True)
    _add(store, "m2", "python note")

    results = search_memory.execute(store, "python", mode="keyword")

    by_id = {s.item.id: s for s in results}
    assert by_id["m1"].channel == "keyword"
    assert by_id["m1"].keyword_rank is not None, "a pin's rank is its honest ranking position"
    assert by_id["m2"].channel == "keyword"
    assert not [s for s in results if s.channel == "pinned"]


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
    all three signals; an unembedded pin reaches the page through the
    keyword channel with its real rank and score (ADR 0008 — no
    scoreless "pinned" rows).
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
    assert pin.channel == "keyword", "the pin ranked; it did not float"
    assert pin.rrf_score is not None
    assert pin.semantic_similarity is None
    assert pin.keyword_rank is not None


# ── pins rank on their merits (ADR 0008 — the float is gone) ────────


def _add_pins(store: SqliteStore, count: int, content: str = "standing rule") -> None:
    """Add `count` pinned items with strictly increasing created_at, so
    pin-N is the newest and rank tie-breaks are deterministic."""
    for i in range(count):
        _add(
            store,
            f"pin-{i}",
            f"{content} {i}",
            pinned=True,
            created_at=datetime(2026, 8, 1, 12, 0, i, tzinfo=UTC),
        )


def test_keyword_mode_top_k_bounds_the_response() -> None:
    """top_k bounds the WHOLE response. Historically a top_k=2 search
    against an 85-pin store returned 87 results (the float era); since
    ADR 0008 there is no float at all — one ranked stream, one budget.
    """
    store = _make_store()
    _add_pins(store, 12, content="alpha rule")
    _add(store, "m1", "alpha note")

    small = search_memory.execute(store, "alpha", mode="keyword", top_k=2)
    assert len(small) == 2, "top_k bounds the WHOLE response, pins included"
    assert all(s.channel == "keyword" for s in small), "everything arrives through the ranking"

    wide = search_memory.execute(store, "alpha", mode="keyword", top_k=13)
    assert len(wide) == 13, "all 12 pins and m1 rank"
    assert all(s.channel == "keyword" for s in wide)


def test_unmatched_pins_do_not_surface_in_keyword_mode() -> None:
    """The FTS5 gate (ADR 0008): no match, no candidacy — pins
    included. Under the float era ANY query could return pins; now a
    pin surfaces in keyword mode only through the ranking, which
    requires a match.
    """
    store = _make_store()
    _add_pins(store, 3, content="standing rule about deployments")
    _add(store, "m1", "alpha note")

    results = search_memory.execute(store, "alpha", mode="keyword")

    assert [s.item.id for s in results] == ["m1"]
    assert not [s for s in results if s.item.pinned]


def test_global_pin_surfaces_inside_a_project_scoped_search() -> None:
    """Scope-with-global survives the float removal: a standing rule
    belonging to no project still ranks while working inside one."""
    store = _make_store()
    store.add_memory(
        MemoryItem(
            id="global-pin",
            content="alpha standing rule",
            tags=["test"],
            created_at=datetime(2026, 8, 1, tzinfo=UTC),
            pinned=True,
            source="test",
            project_id=None,
        )
    )
    _add(store, "m1", "alpha note")

    results = search_memory.execute(store, "alpha", mode="keyword", project_id="proj-1")

    by_id = {s.item.id: s for s in results}
    assert by_id["global-pin"].channel == "keyword", "it ranked — scope-with-global, no float"
    assert "m1" in by_id


def test_hybrid_pins_rank_on_their_merits() -> None:
    """ADR 0008: every pin reaches the page through the ranking — no
    float slots, no exclusion set, no duplicates, no "pinned" channel.
    (The float-era ancestor of this test asserted one floated pin plus
    one ranked pin; both now rank.)
    """
    store = _make_store()
    adapter = StubEmbeddingAdapter(dims=32)
    service = EmbeddingService(port=adapter, store=store)
    _add(store, "pin-old", "gamma standing rule", pinned=True, created_at=datetime(2026, 8, 1, tzinfo=UTC))
    service.generate_for_memory("pin-old", "gamma standing rule")
    _add(store, "pin-new", "gamma newer rule", pinned=True, created_at=datetime(2026, 8, 2, tzinfo=UTC))
    service.generate_for_memory("pin-new", "gamma newer rule")
    _add(store, "m1", "gamma note")
    service.generate_for_memory("m1", "gamma note")

    results = search_memory.execute(store, "gamma standing rule", mode="hybrid", embedding_service=service)

    by_id = {s.item.id: s for s in results}
    assert {"pin-old", "pin-new", "m1"} <= set(by_id), "all rows reachable through ranking"
    assert all(s.channel in ("hybrid", "keyword", "semantic") for s in results)
    ids = [s.item.id for s in results]
    assert len(ids) == len(set(ids)), "no row appears twice"


def test_semantic_mode_has_no_pin_float() -> None:
    """ADR 0008: semantic mode returns the semantic ranking only — an
    unembedded pin cannot ride a keyword-matched float into the page,
    whether its content matches the query or not."""
    store = _make_store()
    adapter = StubEmbeddingAdapter(dims=32)
    service = EmbeddingService(port=adapter, store=store)
    _add_pins(store, 2, content="delta content rule")  # matching, unembedded
    _add(store, "far-pin", "unrelated standing rule", pinned=True)  # unmatching, unembedded
    _add(store, "m1", "delta content")
    service.generate_for_memory("m1", "delta content")

    results = search_memory.execute(store, "delta content", mode="semantic", embedding_service=service)

    assert [s.item.id for s in results] == ["m1"], "only embedded rows rank in semantic mode"
    assert results[0].channel == "semantic"


def test_pagination_walks_one_ranked_stream() -> None:
    """Page 2 starts exactly where page 1 ended — pins included.

    Since ADR 0008 the stream is ONE ranking (pins inside it, lifted
    by the — currently 0 — rank lift); offset indexes into it, so no
    row is duplicated or skipped across pages.
    """
    store = _make_store()
    _add_pins(store, 3, content="omega rule")
    for i in range(6):
        _add(store, f"m{i}", f"omega note {i}")

    page1 = search_memory.execute(store, "omega", mode="keyword", top_k=4, offset=0)
    page2 = search_memory.execute(store, "omega", mode="keyword", top_k=4, offset=4)
    page3 = search_memory.execute(store, "omega", mode="keyword", top_k=4, offset=8)

    ids1 = [s.item.id for s in page1]
    ids2 = [s.item.id for s in page2]
    ids3 = [s.item.id for s in page3]
    assert len(ids1) == 4
    assert not (set(ids1) & set(ids2)) and not (set(ids2) & set(ids3))
    assert len(ids1) + len(ids2) + len(ids3) == 9, "3 pins + 6 notes, no dupes, no gaps"


def test_hybrid_top_k_is_a_total_budget() -> None:
    """top_k bounds the hybrid response (stub embeddings)."""
    store = _make_store()
    adapter = StubEmbeddingAdapter(dims=16)
    service = EmbeddingService(port=adapter, store=store)
    _add_pins(store, 5, content="gamma rule")
    for i in range(5):
        _add(store, f"m{i}", f"gamma note {i}")
    service.generate_missing()

    results = search_memory.execute(store, "gamma", mode="hybrid", top_k=3, embedding_service=service)
    assert len(results) == 3, "hybrid response is bounded by top_k, pins included"


def test_semantic_top_k_is_a_total_budget() -> None:
    store = _make_store()
    adapter = StubEmbeddingAdapter(dims=16)
    service = EmbeddingService(port=adapter, store=store)
    _add_pins(store, 5, content="delta rule")
    for i in range(5):
        _add(store, f"m{i}", f"delta note {i}")
    service.generate_missing()

    results = search_memory.execute(store, "delta", mode="semantic", top_k=3, embedding_service=service)
    assert len(results) == 3


def test_include_pinned_false_hides_pins_on_every_surface_path() -> None:
    """The visibility switch (2026-08-28), orthogonal to ADR 0008's
    ranking change: false excludes pins outright — no ranking at all."""
    store = _make_store()
    _add(store, "pin-rule", "epsilon standing rule", pinned=True)
    _add(store, "m1", "epsilon note")

    visible = search_memory.execute(store, "epsilon", mode="keyword", include_pinned=True)
    hidden = search_memory.execute(store, "epsilon", mode="keyword", include_pinned=False)

    assert "pin-rule" in {s.item.id for s in visible}
    assert {s.item.id for s in hidden} == {"m1"}
