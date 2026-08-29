"""Tests for embedding storage in SqliteStore."""

from __future__ import annotations

from datetime import UTC, datetime

from openchronicle.core.domain.content_hash import hash_content
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from tests.helpers.vectors import save_tombstone, save_vec


def _make_store() -> SqliteStore:
    store = SqliteStore(db_path=":memory:")
    store.init_schema()
    return store


def _add_memory(store: SqliteStore, memory_id: str = "mem-1") -> MemoryItem:
    item = MemoryItem(
        id=memory_id,
        content="test memory content",
        tags=["test"],
        created_at=datetime.now(UTC),
        pinned=False,
        source="test",
        project_id="proj-1",
    )
    # Need project first
    from openchronicle.core.domain.models.project import Project

    store.add_project(Project(id="proj-1", name="test"))
    store.add_memory(item)
    return item


def test_save_and_retrieve_embedding() -> None:
    store = _make_store()
    _add_memory(store, "mem-1")
    vec = [0.1, 0.2, 0.3, 0.4, 0.5]
    save_vec(store, "mem-1", vec, model="test-model")

    retrieved = store.get_embedding("mem-1")
    assert retrieved is not None
    assert len(retrieved) == 5
    for a, b in zip(vec, retrieved):
        assert abs(a - b) < 1e-6


def test_get_returns_none_for_missing() -> None:
    store = _make_store()
    assert store.get_embedding("nonexistent") is None


def test_cascade_delete() -> None:
    """Deleting memory should remove its embedding via CASCADE."""
    store = _make_store()
    _add_memory(store, "mem-1")
    save_vec(store, "mem-1", [0.1, 0.2, 0.3], model="test")
    store.delete_memory("mem-1")
    assert store.get_embedding("mem-1") is None


def test_count_embeddings() -> None:
    store = _make_store()
    _add_memory(store, "mem-1")
    assert store.count_embeddings() == 0
    save_vec(store, "mem-1", [0.1, 0.2], model="test")
    assert store.count_embeddings() == 1


def test_count_stale_embeddings() -> None:
    store = _make_store()
    _add_memory(store, "mem-1")
    save_vec(store, "mem-1", [0.1], model="old-model")
    counts = store.stale_embedding_counts("test-provider", "new-model", settings_fingerprint="test-fp")
    assert counts == {"space_mismatch": 1, "content_mismatch": 0}
    same_space = store.stale_embedding_counts("test-provider", "old-model", settings_fingerprint="test-fp")
    assert same_space == {"space_mismatch": 0, "content_mismatch": 0}


def test_list_embeddings_subset() -> None:
    store = _make_store()
    from openchronicle.core.domain.models.project import Project

    store.add_project(Project(id="proj-1", name="test"))
    for i in range(3):
        mid = f"mem-{i}"
        item = MemoryItem(
            id=mid,
            content=f"content {i}",
            tags=["test"],
            created_at=datetime.now(UTC),
            pinned=False,
            source="test",
            project_id="proj-1",
        )
        store.add_memory(item)
        save_vec(store, mid, [float(i)], model="test")

    result = store.list_embeddings(["mem-0", "mem-2"])
    assert len(result) == 2
    assert "mem-0" in result
    assert "mem-2" in result
    assert "mem-1" not in result


def test_overwrite_existing_embedding() -> None:
    store = _make_store()
    _add_memory(store, "mem-1")
    save_vec(store, "mem-1", [0.1, 0.2], model="v1")
    save_vec(store, "mem-1", [0.9, 0.8], model="v2")

    retrieved = store.get_embedding("mem-1")
    assert retrieved is not None
    assert abs(retrieved[0] - 0.9) < 1e-6
    assert store.get_embedding_model("mem-1") == "v2"


def test_dimensions_column_records_actual_vector_length() -> None:
    """Regression (2026-08-15 review): the column stored the adapter's
    CONFIGURED dims while the blob stored the actual vector. Ollama can't
    control actual output length, so a mismatch wrote fine and then every
    read raised struct.error. The column now records the fact.
    """
    store = _make_store()
    _add_memory(store, "mem-1")
    save_vec(store, "mem-1", [0.1, 0.2, 0.3], model="test")
    row = store._conn.execute("SELECT dimensions FROM memory_embeddings WHERE memory_id = 'mem-1'").fetchone()
    assert row["dimensions"] == 3


def test_reads_heal_a_row_with_a_lying_dimensions_column() -> None:
    """Pre-fix rows may carry a dimensions claim that disagrees with the
    blob. Reads unpack by blob length, so those rows keep working instead
    of raising struct.error until a forced re-embed.
    """
    store = _make_store()
    _add_memory(store, "mem-1")
    save_vec(store, "mem-1", [0.1, 0.2, 0.3], model="test")
    # Poison the claim the way the old write path could (configured 768,
    # actual 3).
    store._conn.execute("UPDATE memory_embeddings SET dimensions = 768 WHERE memory_id = 'mem-1'")

    retrieved = store.get_embedding("mem-1")
    assert retrieved is not None
    assert len(retrieved) == 3
    listed = store.list_embeddings(["mem-1"])
    assert len(listed["mem-1"]) == 3


def test_list_embeddings_model_filter() -> None:
    """Regression (2026-08-15 review): semantic search loaded every model's
    vectors — a stale row after a model switch crashed the matmul
    (different dims) or silently corrupted ranking (same dims).
    """
    store = _make_store()
    from openchronicle.core.domain.models.project import Project

    store.add_project(Project(id="proj-2", name="test2"))
    for i, model in enumerate(["model-a", "model-a", "model-b"]):
        mid = f"mem-{i}"
        store.add_memory(
            MemoryItem(
                id=mid,
                content=f"content {i}",
                tags=[],
                created_at=datetime.now(UTC),
                pinned=False,
                source="test",
                project_id="proj-2",
            )
        )
        save_vec(store, mid, [float(i), 1.0], model=model)

    only_a = store.list_embeddings(model="model-a")
    assert set(only_a) == {"mem-0", "mem-1"}
    subset_and_model = store.list_embeddings(["mem-0", "mem-2"], model="model-a")
    assert set(subset_and_model) == {"mem-0"}
    unfiltered = store.list_embeddings()
    assert set(unfiltered) == {"mem-0", "mem-1", "mem-2"}


# ── ADR 0009: tombstone rows ──────────────────────────────────────────


def _store_with_memories(*memory_ids: str) -> SqliteStore:
    """One project, N memories — `_add_memory` can only be called once
    per store (it re-adds the project)."""
    store = _make_store()
    from openchronicle.core.domain.models.project import Project

    store.add_project(Project(id="proj-1", name="test"))
    for mid in memory_ids:
        store.add_memory(
            MemoryItem(
                id=mid,
                content="test memory content",
                tags=["test"],
                created_at=datetime.now(UTC),
                pinned=False,
                source="test",
                project_id="proj-1",
            )
        )
    return store


def test_tombstone_write_shape_full_identity_zero_dimensions_empty_payload() -> None:
    """A tombstone carries the full ADR 0005 identity + the failed
    content's hash, status='content_too_long', dimensions=0, and an
    empty vector payload — written through the SAME CAS as real saves."""
    store = _make_store()
    _add_memory(store, "mem-1")
    assert save_tombstone(store, "mem-1", model="m", provider="p", fingerprint="fp", model_revision="rev-1")

    identity = store.get_embedding_identity("mem-1")
    assert identity is not None
    assert identity["status"] == "content_too_long"
    assert identity["provider"] == "p"
    assert identity["model"] == "m"
    assert identity["model_revision"] == "rev-1"
    assert identity["settings_fingerprint"] == "fp"
    assert identity["dimensions"] == 0
    assert identity["content_hash"] == hash_content("test memory content")


def test_tombstone_write_is_cas_refused_when_content_moved_on() -> None:
    store = _make_store()
    _add_memory(store, "mem-1")
    # The hash of content that no longer matches the row (simulating an
    # edit between the failed embed and the tombstone write).
    published = store.save_embedding(
        "mem-1",
        [],
        model="m",
        provider="p",
        content_hash="hash-of-content-that-moved-on",
        settings_fingerprint="fp",
        status="content_too_long",
    )
    assert published is False
    assert store.get_embedding_identity("mem-1") is None, "a refused tombstone writes nothing"


def test_resurrection_round_trip_tombstone_then_successful_save() -> None:
    """The rev-1 blocker's regression test: tombstone → successful save
    → the row is 'ok', in list_embeddings, counted embedded, absent
    from unembeddable. `status = excluded.status` is what makes this
    a single-statement resurrection."""
    store = _make_store()
    _add_memory(store, "mem-1")
    assert save_tombstone(store, "mem-1")
    assert store.count_embeddings(status="ok") == 0
    assert store.count_unembeddable_embeddings("test-provider", "test-model", settings_fingerprint="test-fp") == 1

    # The larger-context-model recovery: a later save SUCCEEDS.
    assert save_vec(store, "mem-1", [0.6, 0.8])

    identity = store.get_embedding_identity("mem-1")
    assert identity is not None and identity["status"] == "ok"
    assert "mem-1" in store.list_embeddings()
    assert store.count_embeddings(status="ok") == 1
    assert store.count_unembeddable_embeddings("test-provider", "test-model", settings_fingerprint="test-fp") == 0


def test_list_embeddings_never_returns_tombstones() -> None:
    store = _store_with_memories("mem-1", "mem-2")
    save_vec(store, "mem-1", [0.6, 0.8])
    save_tombstone(store, "mem-2")

    assert set(store.list_embeddings()) == {"mem-1"}
    assert set(store.list_embeddings(["mem-1", "mem-2"])) == {"mem-1"}


def test_stored_dimensions_never_contain_a_tombstones_zero() -> None:
    """The 0003-F2 drift surface must not read [0, 2] because a
    tombstone honestly stores dimensions=0."""
    store = _store_with_memories("mem-1", "mem-2")
    save_vec(store, "mem-1", [0.6, 0.8])
    save_tombstone(store, "mem-2")

    assert store.stored_embedding_dimensions() == [2]


def test_count_unembeddable_counts_only_current_tombstones() -> None:
    """Space- or content-mismatched tombstones are backfill candidates,
    not unembeddable — they land in the stale buckets, whose SQL needs
    (and has) no status predicate."""
    store = _store_with_memories("mem-1", "mem-2", "mem-3")

    # Current tombstone: identity + hash both match the active space.
    save_tombstone(store, "mem-1")
    # Space-mismatched tombstone: wrong model.
    save_tombstone(store, "mem-2", model="old-model")
    # Content-mismatched tombstone: right space, hash goes stale after
    # a direct store-level edit (the use-case path would delete the row;
    # the hash path is the backstop this asserts).
    save_tombstone(store, "mem-3")
    store.update_memory("mem-3", content="edited content")

    assert store.count_unembeddable_embeddings("test-provider", "test-model", settings_fingerprint="test-fp") == 1

    buckets = store.stale_embedding_counts("test-provider", "test-model", settings_fingerprint="test-fp")
    assert buckets == {"space_mismatch": 1, "content_mismatch": 1}, (
        "non-current tombstones are genuine candidates and stay in the stale buckets"
    )
