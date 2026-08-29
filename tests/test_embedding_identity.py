"""ADR 0005 Phase B — composite embedding identity, CAS, and reindex.

The binding test plan from the accepted ADR: space mismatches are
search-ineligible, content mismatches stay space-eligible until
backfill replaces them, publication is compare-and-swap, staleness
buckets are disjoint, and migration sentinels are retired by one
forced reindex.
"""

from __future__ import annotations

from openchronicle.core.application.services.embedding_service import EmbeddingService
from openchronicle.core.domain.content_hash import hash_content
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from tests.helpers.vectors import save_vec


class _Port(EmbeddingPort):
    """Deterministic port with an explicit space identity."""

    def __init__(self, provider: str = "test-provider", model: str = "test-model") -> None:
        self._provider = provider
        self._model = model

    def embed(self, text: str) -> list[float]:
        return [1.0, 0.0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]

    def model_name(self) -> str:
        return self._model

    def provider_name(self) -> str:
        return self._provider

    def dimensions(self) -> int:
        return 2


def _store() -> SqliteStore:
    store = SqliteStore(db_path=":memory:")
    store.init_schema()
    store.add_project(Project(id="p", name="p"))
    return store


# ── space identity gates search eligibility ───────────────────────────


def test_same_model_different_provider_is_invisible_to_search() -> None:
    """The defining case: two providers share a model label but not a
    vector space. The wrong-provider row must never rank."""
    store = _store()
    store.add_memory(MemoryItem(id="m1", content="alpha", project_id="p"))
    save_vec(store, "m1", [1.0, 0.0], model="test-model", provider="other-provider")

    service = EmbeddingService(port=_Port(), store=store)
    ranked = service._semantic_search("alpha")  # noqa: SLF001
    assert ranked == [], "a wrong-provider vector must not rank, even with perfect similarity"


def test_wrong_dimensions_row_is_invisible_not_a_crash() -> None:
    """A different-dims row used to crash the matmul; the space filter
    now excludes it before numpy ever sees it."""
    store = _store()
    store.add_memory(MemoryItem(id="m1", content="alpha", project_id="p"))
    save_vec(store, "m1", [1.0, 0.0, 0.0], model="test-model", provider="test-provider")  # 3 dims vs port's 2

    service = EmbeddingService(port=_Port(), store=store)
    assert service._semantic_search("alpha") == []  # noqa: SLF001


# ── content identity: stale rows stay space-eligible, but are candidates ──


def test_content_mismatch_stays_rankable_until_replaced() -> None:
    """A slightly-old vector in the RIGHT space is useful; only a
    wrong-space vector is poison (ADR §2). The row ranks, and backfill
    sees it as a candidate."""
    store = _store()
    store.add_memory(MemoryItem(id="m1", content="new content", project_id="p"))
    # Vector recorded against the OLD content's hash — right space.
    published = store.save_embedding(
        "m1", [1.0, 0.0], model="test-model", provider="test-provider", content_hash=hash_content("new content")
    )
    assert published
    # Simulate the content moving on afterwards (store-level update).
    store.update_memory("m1", content="even newer content")

    service = EmbeddingService(port=_Port(), store=store)
    assert service._semantic_search("query") != []  # noqa: SLF001 — still rankable
    status = service.embedding_status()
    assert status["content_mismatch"] == 1
    assert status["space_mismatch"] == 0
    assert status["stale"] == 1

    result = service.generate_missing()
    assert result.generated == 1, "a content-stale row is a backfill candidate"
    assert service.embedding_status()["stale"] == 0


# ── compare-and-swap publication ──────────────────────────────────────


def test_cas_refuses_a_late_save_after_content_moved_on() -> None:
    """The slow-older-writer race: A embeds v1, B updates to v2 and
    publishes; A's late save must be refused, B's vector survives."""
    store = _store()
    store.add_memory(MemoryItem(id="m1", content="v1", project_id="p"))
    hash_v1 = hash_content("v1")

    store.update_memory("m1", content="v2")
    ok_b = store.save_embedding(
        "m1", [0.0, 1.0], model="test-model", provider="test-provider", content_hash=hash_content("v2")
    )
    assert ok_b

    ok_a = store.save_embedding("m1", [1.0, 0.0], model="test-model", provider="test-provider", content_hash=hash_v1)
    assert ok_a is False, "the older writer's save must be refused"
    assert store.get_embedding("m1") == [0.0, 1.0], "B's vector survives"


def test_cas_refuses_when_memory_was_deleted_mid_flight() -> None:
    """Deleted between embed and save: refuse-and-drop, never an
    IntegrityError, never a provider-failure count."""
    store = _store()
    store.add_memory(MemoryItem(id="m1", content="doomed", project_id="p"))
    h = hash_content("doomed")
    store.delete_memory("m1")

    ok = store.save_embedding("m1", [1.0, 0.0], model="test-model", provider="test-provider", content_hash=h)
    assert ok is False
    assert store.count_embeddings() == 0


def test_cas_refusal_is_not_a_provider_failure() -> None:
    """A refused publication is a normal outcome — the provider worked."""
    store = _store()
    store.add_memory(MemoryItem(id="m1", content="v1", project_id="p"))
    service = EmbeddingService(port=_Port(), store=store)

    # Make the save lose: change content between the currency check and
    # the save by pre-computing against stale content via force path.
    store.update_memory("m1", content="v2")
    service.generate_for_memory("m1", "v1", force=True)  # embeds stale content
    assert service.failure_count == 0, "a CAS refusal must not read as a dead provider"
    assert store.get_embedding("m1") is None, "the stale vector was not published"


# ── disjoint staleness buckets ────────────────────────────────────────


def test_a_row_stale_both_ways_counts_once_in_space_mismatch() -> None:
    store = _store()
    store.add_memory(MemoryItem(id="m1", content="current", project_id="p"))
    # Direct write path: wrong space AND (forged below) wrong content,
    # simulating a pre-existing row the CAS never blessed.
    save_vec(store, "m1", [1.0, 0.0], model="old-model", provider="other-provider")
    with store._lock:  # noqa: SLF001 — forge the stale hash for the both-ways case
        store._conn.execute("UPDATE memory_embeddings SET content_hash = 'stale' WHERE memory_id = 'm1'")  # noqa: SLF001

    counts = store.stale_embedding_counts("test-provider", "test-model")
    assert counts == {"space_mismatch": 1, "content_mismatch": 0}, "both-ways stale counts ONCE, in space_mismatch"


# ── migration sentinels ───────────────────────────────────────────────


def test_migration_sentinel_rows_are_stale_ineligible_and_reindexable() -> None:
    """A pre-migration row (provider='' content_hash='') is stale AND
    invisible to semantic search, FTS5 still serves the memory, and one
    forced-or-normal backfill retires the sentinel."""
    store = _store()
    store.add_memory(MemoryItem(id="m1", content="alpha content", project_id="p"))
    # Forge the post-migration shape: a row carrying the '' sentinels.
    with store._lock:  # noqa: SLF001
        import struct as _struct

        blob = _struct.pack("2f", 1.0, 0.0)
        store._conn.execute(  # noqa: SLF001
            "INSERT INTO memory_embeddings (memory_id, embedding, model, dimensions, generated_at,"
            " provider, content_hash) VALUES ('m1', ?, 'test-model', 2, '2026-01-01T00:00:00+00:00', '', '')",
            (blob,),
        )

    service = EmbeddingService(port=_Port(), store=store)
    assert service._semantic_search("alpha") == [], "sentinel rows must never rank"  # noqa: SLF001
    assert store.search_memory("alpha", project_id="p"), "FTS5 still serves the memory meanwhile"

    status = service.embedding_status()
    assert status["space_mismatch"] == 1 and status["stale"] == 1

    result = service.generate_missing()  # the normal backfill IS the reindex
    assert result.generated == 1
    assert service.embedding_status()["stale"] == 0
    assert service._semantic_search("alpha") != []  # noqa: SLF001


def test_fresh_save_is_current_and_skipped_by_backfill() -> None:
    store = _store()
    store.add_memory(MemoryItem(id="m1", content="alpha", project_id="p"))
    service = EmbeddingService(port=_Port(), store=store)
    service.generate_for_memory("m1", "alpha")

    identity = store.get_embedding_identity("m1")
    assert identity == {
        "provider": "test-provider",
        "model": "test-model",
        "dimensions": 2,
        "content_hash": hash_content("alpha"),
    }
    assert service.generate_missing().generated == 0, "a current row is not a candidate"


def test_unknown_memory_has_no_identity() -> None:
    store = _store()
    assert store.get_embedding_identity("ghost") is None
