"""ADR 0008 — pins as a bounded ranking prior (PIN_RANK_LIFT).

Deterministic property tests with INJECTED lift constants (the module
default stays 0 until the rollout-step-4 tuning sweep): bounded lift +
tie-break ordering, the offset-invariant clamp, the FTS5 keyword gate,
mode parity including the degraded-hybrid fallback, per-mode fetch
reach, include_pinned=False in every mode, single-channel pagination
stability, the lift's application to the effective ranks RRF consumes
in the fused stream (per channel and combined — mutation-verified: each
of these fails if the fusion lift is dropped wholesale, per channel, or
loses its rank-1 floor), the fused-stream id tie-break, and the inert
deprecated `pinned_limit` on the CLI. Equality-of-score assertions stay banned —
these tests assert order, rank, channel, and membership.

Keyword ranks are crafted, not assumed: identical token-shape contents
tie on bm25, and FTS5's `ORDER BY fts.rank, created_at DESC, id ASC`
then makes creation time the rank. Semantic ranks are crafted with a
fixed [1, 0] query embedding and manually stored vectors whose first
components are strictly distinct (no argpartition tie ambiguity).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from openchronicle.core.application.services import embedding_service as es
from openchronicle.core.application.services.embedding_service import (
    EmbeddingService,
    effective_pin_lift,
    lift_single_channel,
)
from openchronicle.core.application.use_cases import search_memory
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort
from openchronicle.core.infrastructure.embedding.stub_adapter import StubEmbeddingAdapter
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from tests.helpers.vectors import save_vec


class _FixedQueryPort(EmbeddingPort):
    """Query embedding is always [1, 0]; stored vectors are written
    directly, so semantic similarity (the first component) is fully
    controlled by each test."""

    def embed(self, _text: str) -> list[float]:
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


class _BrokenPort(EmbeddingPort):
    """Raises on embed() — drives search_hybrid down the degraded path."""

    def embed(self, _text: str) -> list[float]:
        raise RuntimeError("provider down")

    def embed_batch(self, _texts: list[str]) -> list[list[float]]:
        raise RuntimeError("provider down")

    def model_name(self) -> str:
        return "broken"

    def provider_name(self) -> str:
        return "test-provider"

    def model_revision(self) -> str | None:
        return None

    def settings_fingerprint(self) -> str:
        return "test-fp"

    def dimensions(self) -> int:
        return 2


def _make_store() -> SqliteStore:
    store = SqliteStore(db_path=":memory:")
    store.init_schema()
    store.add_project(Project(id="proj-1", name="test"))
    return store


def _mem(memory_id: str, content: str, *, pinned: bool = False, created_at: datetime | None = None) -> MemoryItem:
    return MemoryItem(
        id=memory_id,
        content=content,
        tags=["test"],
        created_at=created_at or datetime(2026, 8, 1, tzinfo=UTC),
        pinned=pinned,
        source="test",
        project_id="proj-1",
    )


def _seed_keyword_ranked(store: SqliteStore, spec: list[tuple[str, bool]]) -> None:
    """Seed rows whose FTS5 ranks for the query "omega" equal their
    1-based position in ``spec``: identical token shape ties bm25, and
    strictly decreasing created_at down the list makes recency the
    tie-break."""
    base = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
    for i, (memory_id, pinned) in enumerate(spec):
        store.add_memory(
            _mem(memory_id, f"omega note {memory_id}", pinned=pinned, created_at=base - timedelta(seconds=i))
        )


def _seed_semantic_ranked(store: SqliteStore, port: _FixedQueryPort, spec: list[tuple[str, bool, float]]) -> None:
    """Seed embedded rows whose semantic ranks follow ``spec`` order
    (first components must be strictly descending). Contents carry no
    query tokens, so the keyword channel never sees them."""
    for memory_id, pinned, first in spec:
        store.add_memory(_mem(memory_id, f"filler body {memory_id}", pinned=pinned))
        save_vec(store, memory_id, [first, 0.0], model=port.model_name(), provider=port.provider_name())


# ── the pure helpers ────────────────────────────────────────────────


def test_effective_pin_lift_clamps_on_top_k() -> None:
    assert effective_pin_lift(8, 0) == 0
    assert effective_pin_lift(8, 4) == 4
    assert effective_pin_lift(2, 8) == 2, "clamped on top_k"
    assert effective_pin_lift(1, 8) == 1
    assert effective_pin_lift(8, -3) == 0, "a negative constant is a disabled lift, not a demotion"


def test_lift_single_channel_total_order() -> None:
    """The ADR §1 tuple order: a lifted pin ties the holder of its
    target rank and sorts AFTER it; floor pile-ups keep original
    order; lift 0 is the identity."""
    items = [
        _mem("u1", "x"),
        _mem("u2", "x"),
        _mem("u3", "x"),
        _mem("u4", "x"),
        _mem("u5", "x"),
        _mem("p6", "x", pinned=True),
    ]
    ranked = list(enumerate(items, start=1))

    identity = [item.id for _r, item in lift_single_channel(ranked, 0)]
    assert identity == ["u1", "u2", "u3", "u4", "u5", "p6"]

    # lift 2: p6's effective rank is 4 — it ties u4, sorts after it,
    # and passes only the rows between (u5).
    lifted = [item.id for _r, item in lift_single_channel(ranked, 2)]
    assert lifted == ["u1", "u2", "u3", "u4", "p6", "u5"]

    # Floor pile-up: everything collides at rank 1 → original order.
    pile = [
        _mem("u1", "x"),
        _mem("p2", "x", pinned=True),
        _mem("p3", "x", pinned=True),
    ]
    floored = [item.id for _r, item in lift_single_channel(list(enumerate(pile, start=1)), 8)]
    assert floored == ["u1", "p2", "p3"], "rank-1 collisions order by original rank"


# ── keyword mode (module constant read directly) ────────────────────


def test_keyword_mode_pin_gains_at_most_effective_lift(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end through FTS5: a pin at rank 7 under lift 3 lands
    after the rank-4 holder — bounded, tie-after-holder, raw rank
    reported."""
    monkeypatch.setattr(es, "PIN_RANK_LIFT", 3)
    store = _make_store()
    _seed_keyword_ranked(
        store, [("u1", False), ("u2", False), ("u3", False), ("u4", False), ("u5", False), ("u6", False), ("p7", True)]
    )

    results = search_memory.execute(store, "omega", mode="keyword", top_k=7)

    assert [s.item.id for s in results] == ["u1", "u2", "u3", "u4", "p7", "u5", "u6"]
    pin = next(s for s in results if s.item.id == "p7")
    assert pin.keyword_rank == 7, "the reported rank stays the honest pre-lift rank"
    assert pin.channel == "keyword"


def test_keyword_mode_clamp_is_offset_invariant(monkeypatch: pytest.MonkeyPatch) -> None:
    """The rev-3 defect's regression test: every page of one logical
    query uses effective_lift = min(LIFT, top_k) — never top_k+offset —
    so consecutive pages neither duplicate nor drop rows."""
    monkeypatch.setattr(es, "PIN_RANK_LIFT", 8)
    store = _make_store()
    _seed_keyword_ranked(
        store,
        [
            ("u1", False),
            ("u2", False),
            ("u3", False),
            ("u4", False),
            ("p5", True),
            ("u6", False),
            ("u7", False),
            ("u8", False),
            ("p9", True),
        ],
    )

    # Hand-computed stream at effective_lift = min(8, 3) = 3:
    # p5 (eff 2) ties u2 and follows it; p9 (eff 6) ties u6 and
    # follows it.
    expected = ["u1", "u2", "p5", "u3", "u4", "u6", "p9", "u7", "u8"]

    pages = [
        [s.item.id for s in search_memory.execute(store, "omega", mode="keyword", top_k=3, offset=off)]
        for off in (0, 3, 6)
    ]
    assert pages[0] + pages[1] + pages[2] == expected
    assert not (set(pages[0]) & set(pages[1])) and not (set(pages[1]) & set(pages[2]))

    # Tiny top_k values clamp the lift and succeed.
    assert len(search_memory.execute(store, "omega", mode="keyword", top_k=1)) == 1
    assert len(search_memory.execute(store, "omega", mode="keyword", top_k=2)) == 2


def test_keyword_gate_unmatched_pin_never_surfaces(monkeypatch: pytest.MonkeyPatch) -> None:
    """FTS5 relevance gate: no match, no candidacy — a large lift
    cannot conjure a pin the query never matched (scoped to FTS5; the
    non-FTS5 fallback scorer is depth-gated and exempt, ADR 0008 §1)."""
    monkeypatch.setattr(es, "PIN_RANK_LIFT", 8)
    store = _make_store()
    store.add_memory(_mem("far-pin", "zebra unrelated rule", pinned=True))
    store.add_memory(_mem("m1", "alpha note"))

    results = search_memory.execute(store, "alpha", mode="keyword")

    assert [s.item.id for s in results] == ["m1"]


def test_keyword_mode_fetch_reach_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR 0008 §2 single-channel reach: a pin at unlifted rank
    top_k + effective_lift − 1 can surface on the page; one deeper
    cannot."""
    monkeypatch.setattr(es, "PIN_RANK_LIFT", 2)

    # Case A: pin at rank 5 = 4 + 2 − 1 → effective rank 3 → on page.
    store_a = _make_store()
    _seed_keyword_ranked(
        store_a, [("u1", False), ("u2", False), ("u3", False), ("u4", False), ("p5", True), ("u6", False)]
    )
    page_a = [s.item.id for s in search_memory.execute(store_a, "omega", mode="keyword", top_k=4)]
    assert page_a == ["u1", "u2", "u3", "p5"]

    # Case B: pin at rank 6 = 4 + 2 → lifts to 4, sorts after the
    # rank-4 holder → position 5 → off the page.
    store_b = _make_store()
    _seed_keyword_ranked(
        store_b, [("u1", False), ("u2", False), ("u3", False), ("u4", False), ("u5", False), ("p6", True)]
    )
    page_b = [s.item.id for s in search_memory.execute(store_b, "omega", mode="keyword", top_k=4)]
    assert page_b == ["u1", "u2", "u3", "u4"]
    assert "p6" not in page_b


# ── mode parity ─────────────────────────────────────────────────────


def test_degraded_hybrid_matches_keyword_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR 0008 mode parity: the degraded-hybrid fallback applies the
    SAME lift and single-channel ordering as keyword mode."""
    spec = [("u1", False), ("u2", False), ("u3", False), ("u4", False), ("u5", False), ("u6", False), ("p7", True)]
    store = _make_store()
    _seed_keyword_ranked(store, spec)

    monkeypatch.setattr(es, "PIN_RANK_LIFT", 3)
    keyword = search_memory.execute(store, "omega", mode="keyword", top_k=7)

    broken = EmbeddingService(port=_BrokenPort(), store=store, pin_rank_lift=3)
    degraded = search_memory.execute(store, "omega", mode="hybrid", embedding_service=broken, top_k=7)

    assert [s.item.id for s in degraded] == [s.item.id for s in keyword]
    assert [s.keyword_rank for s in degraded] == [s.keyword_rank for s in keyword]
    assert all(s.channel == "keyword" for s in degraded)
    assert broken.search_failure_count == 1, "the fallback really was the degraded path"


def test_semantic_mode_applies_the_same_lift() -> None:
    """Semantic-mode parity: the same tuple order over similarity
    ranks, with the reported similarities staying raw."""
    port = _FixedQueryPort()
    store = _make_store()
    _seed_semantic_ranked(
        store,
        port,
        [("r1", False, 0.9), ("r2", False, 0.8), ("r3", False, 0.7), ("p4", True, 0.6), ("r5", False, 0.5)],
    )
    service = EmbeddingService(port=port, store=store, pin_rank_lift=2)

    results = service.search_semantic("anything", top_k=5)

    assert [s.item.id for s in results] == ["r1", "r2", "p4", "r3", "r5"]
    pin = next(s for s in results if s.item.id == "p4")
    assert pin.channel == "semantic"
    assert pin.semantic_similarity == pytest.approx(0.6, abs=1e-6), "the raw similarity is reported, not rewritten"


def test_semantic_mode_fetch_reach_boundary() -> None:
    """Same §2 reach property through the semantic ranking."""
    port = _FixedQueryPort()

    # Case A: pin at semantic rank 3 = 2 + 2 − 1 → effective rank 1 →
    # ties r1, follows it → position 2 → on the top_k=2 page.
    store_a = _make_store()
    _seed_semantic_ranked(
        store_a, port, [("r1", False, 0.9), ("r2", False, 0.8), ("p3", True, 0.7), ("r4", False, 0.6)]
    )
    service_a = EmbeddingService(port=port, store=store_a, pin_rank_lift=2)
    page_a = [s.item.id for s in service_a.search_semantic("anything", top_k=2)]
    assert page_a == ["r1", "p3"]

    # Case B: pin at semantic rank 4 = 2 + 2 → effective rank 2 →
    # follows r2 → position 3 → off the page.
    store_b = _make_store()
    _seed_semantic_ranked(
        store_b,
        port,
        [("r1", False, 0.9), ("r2", False, 0.8), ("r3", False, 0.7), ("p4", True, 0.6), ("r5", False, 0.5)],
    )
    service_b = EmbeddingService(port=port, store=store_b, pin_rank_lift=2)
    page_b = [s.item.id for s in service_b.search_semantic("anything", top_k=2)]
    assert page_b == ["r1", "r2"]


def test_semantic_pagination_is_stable_under_lift() -> None:
    """Test-plan pagination property with a lift > 0: consecutive
    semantic pages neither duplicate nor drop rows, and concatenate to
    the lifted stream."""
    port = _FixedQueryPort()
    store = _make_store()
    _seed_semantic_ranked(
        store,
        port,
        [
            ("r1", False, 0.9),
            ("p2", True, 0.8),
            ("r3", False, 0.7),
            ("r4", False, 0.6),
            ("p5", True, 0.5),
            ("r6", False, 0.4),
        ],
    )
    service = EmbeddingService(port=port, store=store, pin_rank_lift=2)

    # Hand-computed stream at effective_lift = 2: p2 (eff 1) follows
    # r1; p5 (eff 3) follows r3.
    expected = ["r1", "p2", "r3", "p5", "r4", "r6"]

    pages = [[s.item.id for s in service.search_semantic("anything", top_k=2, offset=off)] for off in (0, 2, 4)]
    assert pages[0] + pages[1] + pages[2] == expected
    assert not (set(pages[0]) & set(pages[1])) and not (set(pages[1]) & set(pages[2]))


# ── hybrid fusion ───────────────────────────────────────────────────


def test_hybrid_pin_at_widened_semantic_fetch_boundary_enters_fusion() -> None:
    """ADR 0008 §2 hybrid reach (membership, not position): a pin at
    the widened semantic fetch boundary gains a semantic fusion term —
    its channel flips keyword → hybrid. One rank deeper it stays
    keyword-only."""
    port = _FixedQueryPort()

    # top_k=2, lift=2 → per-channel fetch = 2·2 + 2 = 6.
    # Case A: pin is semantic rank 6 (the boundary) AND the only
    # keyword match → it enters fusion from both channels.
    store_a = _make_store()
    _seed_semantic_ranked(
        store_a,
        port,
        [("r1", False, 0.9), ("r2", False, 0.8), ("r3", False, 0.7), ("r4", False, 0.6), ("r5", False, 0.5)],
    )
    store_a.add_memory(_mem("aaa-pin", "zulu findme rule", pinned=True))
    save_vec(store_a, "aaa-pin", [0.4, 0.0], model=port.model_name(), provider=port.provider_name())
    service_a = EmbeddingService(port=port, store=store_a, pin_rank_lift=2)
    hits_a = {s.item.id: s for s in service_a.search_hybrid("zulu findme", top_k=2)}
    assert "aaa-pin" in hits_a
    assert hits_a["aaa-pin"].channel == "hybrid", "fetched at the boundary → fused from both channels"
    assert hits_a["aaa-pin"].semantic_similarity is not None

    # Case B: one more (stronger) semantic row pushes the pin to
    # semantic rank 7 — past the fetch — so it fuses keyword-only.
    store_b = _make_store()
    _seed_semantic_ranked(
        store_b,
        port,
        [
            ("r1", False, 0.9),
            ("r2", False, 0.8),
            ("r3", False, 0.7),
            ("r4", False, 0.6),
            ("r5", False, 0.5),
            ("r6", False, 0.45),
        ],
    )
    store_b.add_memory(_mem("aaa-pin", "zulu findme rule", pinned=True))
    save_vec(store_b, "aaa-pin", [0.4, 0.0], model=port.model_name(), provider=port.provider_name())
    service_b = EmbeddingService(port=port, store=store_b, pin_rank_lift=2)
    hits_b = {s.item.id: s for s in service_b.search_hybrid("zulu findme", top_k=2)}
    assert "aaa-pin" in hits_b
    assert hits_b["aaa-pin"].channel == "keyword", "one past the boundary → keyword term only"
    assert hits_b["aaa-pin"].semantic_similarity is None


def test_hybrid_fusion_lift_moves_pin_in_fused_order() -> None:
    """ADR 0008 §1 in the DEFAULT production mode: RRF consumes the
    COLLIDED effective ranks, so a pin present in both channels gains
    fused positions versus the lift-0 stream (test-plan clause "a pin
    gains at most effective_lift positions per channel", applied where
    it was previously untested — the fused path).

    Both channels rank the same five rows. Keyword ranks (recency
    tie-break): u1..u3 = 1..3, p4 = 4, u5 = 5. Semantic ranks (first
    components): u1 = 1, p4 = 2, u2 = 3, u3 = 4, u5 = 5.

    Hand-computed fused scores (K = 60), lift 0:
    u1 2/61 ≈ .03279 · u2 1/62+1/63 ≈ .03200 · p4 1/64+1/62 ≈ .03175 ·
    u3 1/63+1/64 ≈ .03150 · u5 2/65 ≈ .03077.

    Lift 2 changes only p4: keyword 4→2, semantic 2→max(1, 0)=1 (the
    rank-1 floor, inside fusion) → 1/62+1/61 ≈ .03252 — the pin passes
    u2 in the fused stream. No ties anywhere in either run.
    """
    port = _FixedQueryPort()
    store = _make_store()
    _seed_keyword_ranked(store, [("u1", False), ("u2", False), ("u3", False), ("p4", True), ("u5", False)])
    for memory_id, first in (("u1", 0.9), ("p4", 0.8), ("u2", 0.7), ("u3", 0.6), ("u5", 0.5)):
        save_vec(store, memory_id, [first, 0.0], model=port.model_name(), provider=port.provider_name())

    lift0 = EmbeddingService(port=port, store=store, pin_rank_lift=0)
    lift2 = EmbeddingService(port=port, store=store, pin_rank_lift=2)

    assert [s.item.id for s in lift0.search_hybrid("omega", top_k=5)] == ["u1", "u2", "p4", "u3", "u5"]

    lifted = lift2.search_hybrid("omega", top_k=5)
    assert [s.item.id for s in lifted] == ["u1", "p4", "u2", "u3", "u5"], "the reorder is lift-caused"
    pin = next(s for s in lifted if s.item.id == "p4")
    assert pin.channel == "hybrid"
    assert pin.keyword_rank == 4, "the raw keyword rank is reported, not the lifted one"
    assert pin.semantic_similarity == pytest.approx(0.8, abs=1e-6), "the raw similarity is reported, not rewritten"


def test_hybrid_fusion_applies_keyword_channel_lift() -> None:
    """Keyword-side lift inside fusion, isolated: the pin has no
    vector, so its only fusion term is keyword — dropping the lift on
    the keyword term alone is caught here and nowhere else. The lifted
    pin (5 → 3, 1/63) COLLIDES with u3 (1/63) and the fused tie breaks
    by memory id ascending (u3 < zzpin) — NOT by the single-channel
    after-the-holder rule (ADR 0008 §1: RRF consumes collided effective
    ranks as numbers; fused order is score desc, id asc).

    The pin id is deliberately unhyphenated: FTS5's tokenizer splits on
    "-", and a fourth token would break the fixture's identical
    token-shape bm25 tie.
    """
    port = _FixedQueryPort()
    store = _make_store()
    _seed_keyword_ranked(store, [("u1", False), ("u2", False), ("u3", False), ("u4", False), ("zzpin", True)])
    store.add_memory(_mem("s-filler", "unrelated filler body"))
    save_vec(store, "s-filler", [0.9, 0.0], model=port.model_name(), provider=port.provider_name())
    service = EmbeddingService(port=port, store=store, pin_rank_lift=2)

    results = service.search_hybrid("omega", top_k=6)

    # s-filler (semantic rank 1, 1/61) ties u1 (keyword rank 1, 1/61)
    # and precedes it on id; zzpin lifts 5 → 3 (1/63), ties u3 and
    # follows it on id — passing exactly u4.
    assert [s.item.id for s in results] == ["s-filler", "u1", "u2", "u3", "zzpin", "u4"]
    pin = next(s for s in results if s.item.id == "zzpin")
    assert pin.channel == "keyword"
    assert pin.keyword_rank == 5, "the raw keyword rank is reported, not the lifted one"


def test_hybrid_fusion_applies_semantic_channel_lift() -> None:
    """Semantic-side lift inside fusion, isolated: the pin never
    keyword-matches, so its only fusion term is semantic — dropping the
    lift on the semantic term alone is caught here and nowhere else.
    The lifted pin (5 → 3, 1/63) ties r3 and the fused tie again breaks
    by id — this time the pin sorts FIRST (aa-pin < r3): the id leg
    decides, not pin status or original rank (the mirror of the
    keyword-channel test's tie direction)."""
    port = _FixedQueryPort()
    store = _make_store()
    _seed_semantic_ranked(
        store,
        port,
        [("r1", False, 0.9), ("r2", False, 0.8), ("r3", False, 0.7), ("r4", False, 0.6), ("aa-pin", True, 0.5)],
    )
    store.add_memory(_mem("k-filler", "omega note k-filler"))
    service = EmbeddingService(port=port, store=store, pin_rank_lift=2)

    results = service.search_hybrid("omega", top_k=6)

    # k-filler (keyword rank 1, 1/61) ties r1 (semantic rank 1) and
    # precedes it on id; aa-pin lifts 5 → 3 (1/63), ties r3 and
    # precedes it on id — passing r3 and r4.
    assert [s.item.id for s in results] == ["k-filler", "r1", "r2", "aa-pin", "r3", "r4"]
    pin = next(s for s in results if s.item.id == "aa-pin")
    assert pin.channel == "semantic"
    assert pin.semantic_similarity == pytest.approx(0.5, abs=1e-6), "the raw similarity is reported, not rewritten"


def test_fused_score_tie_orders_by_memory_id() -> None:
    """ADR 0008 §1 fused order: a keyword-only row and a semantic-only
    row at the same effective rank score identically — the memory-id
    leg decides, deterministically, regardless of which channel
    produced which row."""

    def _run(keyword_id: str, semantic_id: str) -> list[str]:
        store = _make_store()
        adapter = StubEmbeddingAdapter(dims=8)
        service = EmbeddingService(port=adapter, store=store)
        store.add_memory(_mem(keyword_id, "kilo match"))  # keyword rank 1, no vector
        store.add_memory(_mem(semantic_id, "unrelated body"))  # semantic rank 1, no keyword match
        service.generate_for_memory(semantic_id, "unrelated body")
        return [s.item.id for s in service.search_hybrid("kilo", top_k=4)]

    assert _run(keyword_id="b-key", semantic_id="a-sem") == ["a-sem", "b-key"]
    assert _run(keyword_id="a-key", semantic_id="b-sem") == ["a-key", "b-sem"]


# ── visibility ──────────────────────────────────────────────────────


def test_include_pinned_false_hides_pins_in_all_three_modes() -> None:
    """Visibility stays orthogonal to the lift: False hides pins in
    keyword, semantic, and hybrid mode alike."""
    store = _make_store()
    adapter = StubEmbeddingAdapter(dims=8)
    service = EmbeddingService(port=adapter, store=store, pin_rank_lift=4)
    store.add_memory(_mem("pin-rule", "epsilon standing rule", pinned=True))
    service.generate_for_memory("pin-rule", "epsilon standing rule")
    store.add_memory(_mem("m1", "epsilon note"))
    service.generate_for_memory("m1", "epsilon note")

    for mode in ("keyword", "semantic", "hybrid"):
        visible = search_memory.execute(store, "epsilon", mode=mode, embedding_service=service, include_pinned=True)
        hidden = search_memory.execute(store, "epsilon", mode=mode, embedding_service=service, include_pinned=False)
        assert "pin-rule" in {s.item.id for s in visible}, f"mode={mode}"
        assert "pin-rule" not in {s.item.id for s in hidden}, f"mode={mode}"
        assert "m1" in {s.item.id for s in hidden}, f"mode={mode}"


# ── constant wiring ─────────────────────────────────────────────────


def test_constructor_injection_and_module_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """The sweep injects the constant; production wiring passes nothing
    and gets the module default, read at construction time."""
    store = _make_store()
    port = _FixedQueryPort()

    assert EmbeddingService(port=port, store=store)._pin_rank_lift == es.PIN_RANK_LIFT
    assert EmbeddingService(port=port, store=store, pin_rank_lift=4)._pin_rank_lift == 4
    monkeypatch.setattr(es, "PIN_RANK_LIFT", 5)
    assert EmbeddingService(port=port, store=store)._pin_rank_lift == 5


def test_fetch_extension_widens_the_window_without_lifting() -> None:
    """ADR 0008 §3's window-only ablation knob: with ``pin_rank_lift=0``
    and ``fetch_extension`` set, the candidate fetch widens exactly as
    if the paired lift were active — fusion MEMBERSHIP extends — while
    no rank moves, and the extension clamps on top_k like the lift."""
    port = _FixedQueryPort()

    def _boundary_store(unpinned_semantic: int) -> SqliteStore:
        """N unpinned semantic rows, then a keyword-matching pin at
        semantic rank N+1 (first components strictly descending)."""
        store = _make_store()
        _seed_semantic_ranked(
            store,
            port,
            [(f"r{i}", False, 0.9 - 0.05 * i) for i in range(1, unpinned_semantic + 1)],
        )
        store.add_memory(_mem("aaa-pin", "zulu findme rule", pinned=True))
        save_vec(
            store,
            "aaa-pin",
            [0.9 - 0.05 * (unpinned_semantic + 1), 0.0],
            model=port.model_name(),
            provider=port.provider_name(),
        )
        return store

    def _pin_channel(service: EmbeddingService) -> str:
        hits = {s.item.id: s for s in service.search_hybrid("zulu findme", top_k=2)}
        return str(hits["aaa-pin"].channel)

    # Membership: top_k=2, extension 2 → semantic fetch 2·2+2 = 6; the
    # pin at semantic rank 6 gains a semantic fusion term ONLY under
    # the extension (without it the fetch stops at 4).
    store_a = _boundary_store(unpinned_semantic=5)
    assert _pin_channel(EmbeddingService(port=port, store=store_a, pin_rank_lift=0)) == "keyword"
    assert _pin_channel(EmbeddingService(port=port, store=store_a, pin_rank_lift=0, fetch_extension=2)) == "hybrid"

    # Clamp mirror: at top_k=2 an extension of 8 clamps to 2 (fetch 6,
    # not 12) — a pin at semantic rank 7 stays out of the fusion.
    store_b = _boundary_store(unpinned_semantic=6)
    assert _pin_channel(EmbeddingService(port=port, store=store_b, pin_rank_lift=0, fetch_extension=8)) == "keyword"

    # No lift: the semantic-mode order is the raw ranking — contrast
    # test_semantic_mode_applies_the_same_lift, where lift 2 over the
    # same seeding moves p4 ahead of r3.
    store_c = _make_store()
    _seed_semantic_ranked(
        store_c,
        port,
        [("r1", False, 0.9), ("r2", False, 0.8), ("r3", False, 0.7), ("p4", True, 0.6), ("r5", False, 0.5)],
    )
    ablated = EmbeddingService(port=port, store=store_c, pin_rank_lift=0, fetch_extension=2)
    assert [s.item.id for s in ablated.search_semantic("anything", top_k=5)] == ["r1", "r2", "r3", "p4", "r5"]


def test_cli_pinned_limit_flag_is_accepted_and_inert(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The inert --pinned-limit flag still parses and changes nothing
    (ADR 0008 §4 deprecation window; removal no earlier than
    v5.0.0)."""
    from openchronicle.core.infrastructure.wiring.container import CoreContainer
    from openchronicle.interfaces.cli.main import main

    (tmp_path / "config").mkdir()
    monkeypatch.setenv("OC_DB_PATH", str(tmp_path / "cli.db"))
    monkeypatch.setenv("OC_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.delenv("OC_EMBEDDING_PROVIDER", raising=False)
    container = CoreContainer()
    try:
        container.storage.add_project(Project(id="proj-1", name="test"))
        container.storage.add_memory(_mem("pin-1", "alpha standing rule", pinned=True))
        container.storage.add_memory(_mem("m1", "alpha note"))

        def _run(argv: list[str]) -> tuple[int, str]:
            with (
                patch("builtins.print") as mock_print,
                patch("openchronicle.interfaces.cli.main._build_container", return_value=container),
            ):
                rc = main(argv)
            out = "\n".join(str(c.args[0]) if c.args else "" for c in mock_print.call_args_list)
            return rc, out

        rc_flag, out_flag = _run(["memory", "search", "alpha", "--pinned-limit", "3"])
        rc_bare, out_bare = _run(["memory", "search", "alpha"])
    finally:
        container.close()

    assert rc_flag == rc_bare == 0
    assert out_flag == out_bare, "the flag must not change the output in any way"
