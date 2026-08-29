"""ADR 0009 behavior: classified CONTENT_TOO_LONG outcomes park, not poison.

The service-and-consumers half of the test plan (adapter classification
lives in test_embedding_adapters.py; tombstone storage semantics in
test_embedding_storage.py): the three `_record_failure` exemptions, the
save-path park-and-return contract, the batch isolation mechanism,
emergent candidacy, the row-class PARTITION, and the `tombstoned`
accounting through the maintenance job / `embed_memory` / CLI.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from openchronicle.core.application.services.embedding_service import BackfillResult, EmbeddingService
from openchronicle.core.application.use_cases import add_memory, embed_memory, update_memory
from openchronicle.core.domain.content_hash import hash_content
from openchronicle.core.domain.errors.error_codes import CONTENT_TOO_LONG, PROVIDER_ERROR
from openchronicle.core.domain.exceptions import ProviderError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort
from openchronicle.core.infrastructure.maintenance import jobs as maintenance_jobs
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

_OVERLENGTH = "x" * 100  # anything past _LimitedContextPort's max_chars


class _LimitedContextPort(EmbeddingPort):
    """A provider with a small context: over-length content classifies.

    Mirrors the real Ollama contract — the WHOLE batch fails when any
    item is over-length (classification at the adapter is batch-blind),
    and the per-item call classifies the specific item.
    """

    def __init__(
        self,
        *,
        max_chars: int = 50,
        fingerprint: str = "test-fp",
        revision: str | None = None,
    ) -> None:
        self.max_chars = max_chars
        self._fingerprint = fingerprint
        self._revision = revision
        self.batch_calls: list[int] = []
        self.item_calls: list[str] = []

    def _check(self, text: str) -> None:
        if len(text) > self.max_chars:
            raise ProviderError(
                "Ollama embedding failed: HTTP 400: input exceeds maximum context length",
                error_code=CONTENT_TOO_LONG,
                details={"provider": "test-provider", "model": "test-model"},
            )

    def embed(self, text: str) -> list[float]:
        self.item_calls.append(text)
        self._check(text)
        return [1.0, 0.0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.batch_calls.append(len(texts))
        for t in texts:
            self._check(t)
        return [[1.0, 0.0] for _ in texts]

    def dimensions(self) -> int:
        return 2

    def model_name(self) -> str:
        return "test-model"

    def provider_name(self) -> str:
        return "test-provider"

    def model_revision(self) -> str | None:
        return self._revision

    def settings_fingerprint(self) -> str:
        return self._fingerprint


class _TransientFailPort(_LimitedContextPort):
    """Every call fails with a NON-classified provider error."""

    def _check(self, text: str) -> None:
        raise ProviderError(
            "Ollama connection failed: refused",
            error_code=PROVIDER_ERROR,
            details={"provider": "test-provider", "model": "test-model"},
        )


def _make_store() -> SqliteStore:
    store = SqliteStore(db_path=":memory:")
    store.init_schema()
    store.add_project(Project(id="p", name="test"))
    return store


def _add(store: SqliteStore, memory_id: str, content: str) -> None:
    store.add_memory(
        MemoryItem(
            id=memory_id,
            content=content,
            tags=["t"],
            created_at=datetime.now(UTC),
            pinned=False,
            source="test",
            project_id="p",
        )
    )


def _row_status(store: SqliteStore, memory_id: str) -> str | None:
    identity = store.get_embedding_identity(memory_id)
    return None if identity is None else identity["status"]


# ── Save path: park and return normally ───────────────────────────────


def test_overlength_save_parks_and_returns_normally() -> None:
    store = _make_store()
    service = EmbeddingService(port=_LimitedContextPort(), store=store)
    _add(store, "m1", _OVERLENGTH)

    service.generate_for_memory("m1", _OVERLENGTH)  # must NOT raise

    assert _row_status(store, "m1") == "content_too_long"
    assert service.failure_count == 0, "a classified outcome records no failure"
    assert service.last_failure_op is None


def test_transient_save_failure_still_raises_and_records() -> None:
    store = _make_store()
    service = EmbeddingService(port=_TransientFailPort(), store=store)
    _add(store, "m1", "short")

    with pytest.raises(ProviderError):
        service.generate_for_memory("m1", "short")
    assert service.failure_count == 1
    assert service.last_failure_op == "save"
    assert _row_status(store, "m1") is None, "a transient failure writes no tombstone"


def test_add_memory_caller_emits_no_warning_for_a_parked_save(caplog: pytest.LogCaptureFixture) -> None:
    """The caller's warning block is for GENUINE failures; a parked
    outcome must not read as one (the rev-144 log-noise class)."""
    store = _make_store()
    service = EmbeddingService(port=_LimitedContextPort(), store=store)
    item = MemoryItem(content="findme " + _OVERLENGTH, tags=[], pinned=False, source="test", project_id="p")

    with caplog.at_level(logging.INFO):
        returned = add_memory.execute(store=store, item=item, embedding_service=service)

    assert returned.id == item.id, "the save itself succeeded — response unchanged"
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings == [], "no traceback, no warning for a designed outcome"
    info_lines = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert any("parked as unembeddable" in line and item.id in line for line in info_lines), (
        "the one INFO line carries the memory id and the remedy"
    )
    assert _row_status(store, item.id) == "content_too_long"
    assert store.search_memory("findme"), "the memory stays FTS5-searchable"


def test_add_memory_caller_still_warns_for_transient_failures(caplog: pytest.LogCaptureFixture) -> None:
    store = _make_store()
    service = EmbeddingService(port=_TransientFailPort(), store=store)
    item = MemoryItem(content="short", tags=[], pinned=False, source="test", project_id="p")

    with caplog.at_level(logging.WARNING):
        add_memory.execute(store=store, item=item, embedding_service=service)

    assert any("Failed to generate embedding" in r.getMessage() for r in caplog.records)


def test_update_to_still_overlength_content_reparks_immediately(caplog: pytest.LogCaptureFixture) -> None:
    """An edit that stays over-length re-parks at save time instead of
    poisoning health until the next 6-hourly backfill. Covers the
    update path's delete-then-force-regenerate flow."""
    store = _make_store()
    service = EmbeddingService(port=_LimitedContextPort(), store=store)
    _add(store, "m1", _OVERLENGTH)
    service.generate_for_memory("m1", _OVERLENGTH)
    assert _row_status(store, "m1") == "content_too_long"

    with caplog.at_level(logging.WARNING):
        update_memory.execute(store=store, memory_id="m1", content=_OVERLENGTH + "y", embedding_service=service)

    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
    identity = store.get_embedding_identity("m1")
    assert identity is not None and identity["status"] == "content_too_long"
    assert identity["content_hash"] == hash_content(_OVERLENGTH + "y"), "the tombstone tracks the NEW content"
    assert service.failure_count == 0


def test_tombstone_cas_refused_when_content_moves_mid_save() -> None:
    """The failed content's hash is what the tombstone carries; content
    that moved on mid-run refuses cleanly and stays a candidate."""
    store = _make_store()
    service = EmbeddingService(port=_LimitedContextPort(), store=store)
    _add(store, "m1", _OVERLENGTH)
    # The edit happens between the failed embed and the tombstone write:
    # generate_for_memory embeds the OLD content while the store already
    # holds new content.
    store.update_memory("m1", content="edited meanwhile")

    service.generate_for_memory("m1", _OVERLENGTH)  # parks against the OLD hash → CAS refuses

    assert store.get_embedding_identity("m1") is None, "refused tombstone writes nothing"
    assert service.failure_count == 0


# ── Search path: an over-length query is caller content ───────────────


def test_overlength_query_degrades_without_recording_failure() -> None:
    store = _make_store()
    service = EmbeddingService(port=_LimitedContextPort(), store=store)
    _add(store, "m1", "alpha beta")
    service.generate_for_memory("m1", "alpha beta")

    results = service.search_hybrid("alpha " + _OVERLENGTH)

    assert [s.item.id for s in results] == ["m1"], "keyword-only results still serve"
    assert service.failure_count == 0
    assert service.search_failure_count == 0, "an over-length query is not provider degradation"


def test_transient_search_failure_still_records() -> None:
    store = _make_store()
    service = EmbeddingService(port=_TransientFailPort(), store=store)
    _add(store, "m1", "alpha beta")

    service.search_hybrid("alpha")

    assert service.search_failure_count == 1
    assert service.failure_count == 1


# ── Backfill: per-item classification, batch isolation, counters ──────


def test_backfill_parks_overlength_rows_and_counts_them_separately() -> None:
    store = _make_store()
    port = _LimitedContextPort()
    service = EmbeddingService(port=port, store=store)
    _add(store, "m-short", "short one")
    _add(store, "m-long", _OVERLENGTH)

    result = service.generate_missing()

    assert result.generated == 1
    assert result.failed == 0
    assert result.tombstoned == 1
    assert _row_status(store, "m-short") == "ok"
    assert _row_status(store, "m-long") == "content_too_long"
    assert service.failure_count == 0, "classified outcomes never touch the counters"


def test_batch_level_classification_is_never_trusted_for_attribution() -> None:
    """A batch containing one over-length row raises CONTENT_TOO_LONG at
    the BATCH level (Ollama fails the whole HTTP batch). The service
    must fall to per-item isolation and tombstone ONLY the long row."""
    store = _make_store()
    port = _LimitedContextPort()
    service = EmbeddingService(port=port, store=store)
    for i in range(3):
        _add(store, f"m-{i}", f"short {i}")
    _add(store, "m-long", _OVERLENGTH)

    result = service.generate_missing()

    assert port.batch_calls == [4], "one chunk attempt"
    assert len(port.item_calls) == 4, "the failed chunk retries item by item"
    assert result.generated == 3
    assert result.tombstoned == 1
    assert result.failed == 0
    for i in range(3):
        assert _row_status(store, f"m-{i}") == "ok", "chunk-mates must not be tombstoned"
    assert _row_status(store, "m-long") == "content_too_long"


# ── Candidacy: emergent exclusion, force, space/content expiry ────────


def test_current_tombstone_is_not_a_backfill_candidate() -> None:
    store = _make_store()
    port = _LimitedContextPort()
    service = EmbeddingService(port=port, store=store)
    _add(store, "m1", _OVERLENGTH)
    assert service.generate_missing().tombstoned == 1

    port.item_calls.clear()
    port.batch_calls.clear()
    rerun = service.generate_missing()

    assert rerun == BackfillResult(generated=0, failed=0, tombstoned=0, elapsed_ms=0)
    assert port.batch_calls == [] and port.item_calls == [], "no provider call for a parked row"


def test_tombstone_pins_the_ports_model_revision() -> None:
    """A tombstone carries the PORT's `model_revision` — pinned under a
    non-None revision, the shape the live Ollama adapter reports.

    Every other port stub reports revision None, so `_write_tombstone`
    hardcoding/omitting `model_revision` (→ None) is indistinguishable
    from correct there (None == None reads current). Under a revisioned
    port that slip makes every tombstone instantly space-stale —
    `unembeddable: 0`, `space_mismatch: 1`, re-parked every backfill
    forever, the exact infinite-retry loop ADR 0009 exists to stop.
    """
    store = _make_store()
    port = _LimitedContextPort(revision="sha256:abc123")
    service = EmbeddingService(port=port, store=store)
    _add(store, "m1", _OVERLENGTH)

    assert service.generate_missing().tombstoned == 1

    identity = store.get_embedding_identity("m1")
    assert identity is not None
    assert identity["model_revision"] == "sha256:abc123", "tombstone must carry the port's revision"

    # Pins `embedding_status`'s own model_revision pass-through too:
    # `count_unembeddable_embeddings` matches `model_revision IS ?`.
    status = service.embedding_status()
    assert status["unembeddable"] == 1, "a right-revision tombstone is CURRENT"
    assert status["space_mismatch"] == 0, "…not space-stale (the None-slip symptom)"

    port.item_calls.clear()
    port.batch_calls.clear()
    rerun = service.generate_missing()
    assert rerun == BackfillResult(generated=0, failed=0, tombstoned=0, elapsed_ms=0)
    assert port.batch_calls == [] and port.item_calls == [], "no provider call for a parked row"


def test_force_retries_tombstones() -> None:
    store = _make_store()
    port = _LimitedContextPort()
    service = EmbeddingService(port=port, store=store)
    _add(store, "m1", _OVERLENGTH)
    service.generate_missing()

    # Same still-too-small model: the row re-parks, still not a failure.
    assert service.generate_missing(force=True).tombstoned == 1

    # The provider's limit grew (same space): force now succeeds and
    # the resurrection clause flips the row back to 'ok'.
    port.max_chars = 10_000
    result = service.generate_missing(force=True)
    assert result.generated == 1 and result.tombstoned == 0
    assert _row_status(store, "m1") == "ok"


def test_space_change_recandidates_a_tombstone() -> None:
    store = _make_store()
    service = EmbeddingService(port=_LimitedContextPort(), store=store)
    _add(store, "m1", _OVERLENGTH)
    service.generate_missing()

    # A larger-context model in a NEW space: the tombstone is
    # space-stale, so a PLAIN backfill picks it up.
    bigger = _LimitedContextPort(max_chars=10_000, fingerprint="bigger-model-fp")
    service2 = EmbeddingService(port=bigger, store=store)
    status = service2.embedding_status()
    assert status["unembeddable"] == 0, "a non-current tombstone is not unembeddable"
    assert status["space_mismatch"] == 1, "…it is a stale-bucket candidate"

    result = service2.generate_missing()
    assert result.generated == 1
    assert _row_status(store, "m1") == "ok"


def test_content_edit_recandidates_via_the_deletion_path() -> None:
    store = _make_store()
    service = EmbeddingService(port=_LimitedContextPort(), store=store)
    _add(store, "m1", _OVERLENGTH)
    service.generate_missing()
    assert _row_status(store, "m1") == "content_too_long"

    # Shortening the content through the use case deletes the row and
    # regenerates: the park expires with the content that earned it.
    update_memory.execute(store=store, memory_id="m1", content="now short", embedding_service=service)

    assert _row_status(store, "m1") == "ok"
    assert service.embedding_status()["unembeddable"] == 0


# ── Health: the row-class partition and the additive field ────────────


def test_row_classes_partition_and_health_invariants() -> None:
    """Every memory_embeddings row is exactly one of {status='ok',
    current tombstone, non-current tombstone}; the class counts sum to
    the row count. Asserted over ROW CLASSES, not health fields — the
    fields legitimately overlay (an ok-but-stale row is in `embedded`
    AND a stale bucket)."""
    store = _make_store()
    port = _LimitedContextPort()
    service = EmbeddingService(port=port, store=store)

    _add(store, "m-ok", "current ok row")
    _add(store, "m-ok-stale", "ok but edited later")
    _add(store, "m-park", _OVERLENGTH)
    _add(store, "m-park-stale", "x" * 90)
    _add(store, "m-missing", "never embedded")

    service.generate_for_memory("m-ok", "current ok row")
    service.generate_for_memory("m-ok-stale", "ok but edited later")
    service.generate_for_memory("m-park", _OVERLENGTH)
    service.generate_for_memory("m-park-stale", "x" * 90)
    # Direct store edits keep the embedding rows in place (the use-case
    # path would delete them): the rows go hash-stale.
    store.update_memory("m-ok-stale", content="edited after embedding")
    store.update_memory("m-park-stale", content="edited after parking")

    embedded_ids = {"m-ok", "m-ok-stale", "m-park", "m-park-stale"}
    classes: dict[str, str] = {}
    for mid in embedded_ids:
        identity = store.get_embedding_identity(mid)
        assert identity is not None
        item = store.get_memory(mid)
        assert item is not None
        current = bool(
            identity["provider"] == port.provider_name()
            and identity["model"] == port.model_name()
            and identity["settings_fingerprint"] == port.settings_fingerprint()
            and identity["model_revision"] == port.model_revision()
            and identity["content_hash"] == hash_content(item.content)
        )
        if identity["status"] == "ok":
            classes[mid] = "ok"
        elif current:
            classes[mid] = "current_tombstone"
        else:
            classes[mid] = "non_current_tombstone"

    assert classes == {
        "m-ok": "ok",
        "m-ok-stale": "ok",
        "m-park": "current_tombstone",
        "m-park-stale": "non_current_tombstone",
    }
    counts = {c: sum(1 for v in classes.values() if v == c) for c in set(classes.values())}
    assert sum(counts.values()) == store.count_embeddings(), "class counts sum to the row count"

    status = service.embedding_status()
    assert status["embedded"] == 2, "embedded = count(status='ok'), stale or not"
    assert status["unembeddable"] == 1, "only the CURRENT tombstone"
    assert status["missing"] == 1, "missing = total memories − ALL rows (a tombstone is known)"
    assert status["embedded"] + 2 == store.count_embeddings(), "embedded + tombstones = total rows"
    # The non-current tombstone is a stale-bucket candidate; the
    # ok-but-stale row is too — `stale ⊆ embedded` no longer holds.
    assert status["content_mismatch"] == 2
    assert status["stale"] == 2


# ── Consumers: maintenance job, embed_memory, CLI ─────────────────────


def test_maintenance_job_succeeds_on_a_tombstoned_only_run() -> None:
    container = MagicMock()
    container.embedding_service.generate_missing.return_value = BackfillResult(
        generated=0, failed=0, tombstoned=9, elapsed_ms=1
    )
    asyncio.run(maintenance_jobs.embedding_backfill(container))  # must not raise


def test_embed_memory_maps_a_tombstoned_only_run_to_ok() -> None:
    store = _make_store()
    service = EmbeddingService(port=_LimitedContextPort(), store=store)
    _add(store, "m1", _OVERLENGTH)

    payload = embed_memory.execute(service)

    assert payload["status"] == "ok"
    assert payload["tombstoned"] == 1
    assert payload["generated"] == 0
    assert payload["failed"] == 0
    assert payload["unembeddable"] == 1


def test_cli_embed_prints_tombstoned_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    store = _make_store()
    service = EmbeddingService(port=_LimitedContextPort(), store=store)
    _add(store, "m1", _OVERLENGTH)
    container = MagicMock()
    container.embedding_service = service

    from openchronicle.interfaces.cli.commands.memory import cmd_memory_embed

    args = argparse.Namespace(status=False, force=False, json=False)
    exit_code = cmd_memory_embed(args, container)

    assert exit_code == 0, "a tombstoned-only run is a success"
    out = capsys.readouterr().out
    assert "1 tombstoned" in out


def test_cli_embed_status_prints_the_unembeddable_line(capsys: pytest.CaptureFixture[str]) -> None:
    store = _make_store()
    service = EmbeddingService(port=_LimitedContextPort(), store=store)
    _add(store, "m1", _OVERLENGTH)
    service.generate_missing()
    container = MagicMock()
    container.embedding_service = service

    from openchronicle.interfaces.cli.commands.memory import cmd_memory_embed

    args = argparse.Namespace(status=True, json=False)
    assert cmd_memory_embed(args, container) == 0
    out = capsys.readouterr().out
    assert "Unembeddable:   1" in out, "parked rows must be visible in a printed field"
