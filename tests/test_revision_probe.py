"""An unknown model revision is not "no revision" (ADR 0005 §7).

Design 0014 §1.1: the Ollama adapter cached a failed `/api/tags` probe as
`None`, which ADR 0005 reads as "this provider has no revision". One
transient failure then blanked semantic search while health read
`active`, and the next backfill re-embedded the whole corpus stamped
NULL; the next healthy restart re-embedded it again.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from openchronicle.core.application.config.settings import EmbeddingSettings
from openchronicle.core.application.services import embedding_service as embedding_service_module
from openchronicle.core.application.services import maintenance_loop
from openchronicle.core.application.services.embedding_service import BackfillResult, EmbeddingService
from openchronicle.core.application.use_cases import add_memory, embed_memory, update_memory
from openchronicle.core.domain.exceptions import RevisionUnknownError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.domain.models.revision_snapshot import UNKNOWN_REVISION, RevisionSnapshot
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort
from openchronicle.core.domain.time_utils import utc_now
from openchronicle.core.infrastructure.embedding import ollama_adapter
from openchronicle.core.infrastructure.embedding.ollama_adapter import OllamaEmbeddingAdapter
from openchronicle.core.infrastructure.embedding.stub_adapter import StubEmbeddingAdapter
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.api.app import create_app
from openchronicle.interfaces.api.config import HTTPConfig
from tests.helpers.vectors import save_vec

_ADAPTER_LOGGER = "openchronicle.core.infrastructure.embedding.ollama_adapter"

_TAGS_URL = "http://localhost:11434/api/tags"


def _adapter(model: str = "nomic-embed-text") -> OllamaEmbeddingAdapter:
    return OllamaEmbeddingAdapter(model=model, host="http://localhost:11434", timeout_seconds=5.0)


def _tags(models: Any, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json={"models": models}, request=httpx.Request("GET", _TAGS_URL))


def _listed(name: str = "nomic-embed-text:latest", digest: str | None = "sha256:A") -> dict[str, Any]:
    entry: dict[str, Any] = {"name": name, "model": name}
    if digest is not None:
        entry["digest"] = digest
    return entry


def _probe(adapter: OllamaEmbeddingAdapter, outcome: object) -> RevisionSnapshot:
    """One forced probe whose `httpx.get` returns or raises ``outcome``."""
    kwargs: dict[str, Any] = (
        {"side_effect": outcome} if isinstance(outcome, BaseException) else {"return_value": outcome}
    )
    with patch("httpx.get", **kwargs):
        return adapter.refresh_revision(force=True)


# Every probe result that is not "the model is listed". Each must count as a
# FAILED probe: none of them is evidence that the model has no revision.
_FAILED_PROBES = {
    "model not listed": _tags([_listed(name="some-other-model:latest")]),
    "empty listing": _tags([]),
    "HTTP 404": httpx.Response(404, text="404 page not found", request=httpx.Request("GET", _TAGS_URL)),
    "HTTP 500": httpx.Response(500, json={"error": "boom"}, request=httpx.Request("GET", _TAGS_URL)),
    "not JSON": httpx.Response(200, text="<html>proxy</html>", request=httpx.Request("GET", _TAGS_URL)),
    "models not a list": httpx.Response(200, json={"models": "x"}, request=httpx.Request("GET", _TAGS_URL)),
    "connection refused": httpx.ConnectError("refused"),
    "timeout": httpx.ReadTimeout("slow"),
}


class TestProbeClassification:
    def test_starts_unknown_and_reads_never_probe(self) -> None:
        adapter = _adapter()
        with patch("httpx.get") as get:
            snapshot = adapter.revision_snapshot()
            assert (snapshot.known, snapshot.state) == (False, "unknown")
            with pytest.raises(RevisionUnknownError):
                adapter.model_revision()
        get.assert_not_called()

    def test_a_listed_digest_is_known(self) -> None:
        adapter = _adapter()
        snapshot = _probe(adapter, _tags([_listed()]))
        assert (snapshot.known, snapshot.value, snapshot.state) == (True, "sha256:A", "known")
        assert snapshot.verified_at is not None
        assert adapter.model_revision() == "sha256:A"
        assert adapter.revision_snapshot() is snapshot

    def test_a_model_listed_without_a_digest_genuinely_has_none(self) -> None:
        """The only real evidence of "no revision"."""
        adapter = _adapter()
        snapshot = _probe(adapter, _tags([_listed(digest=None)]))
        assert (snapshot.known, snapshot.value, snapshot.state) == (True, None, "none")
        assert adapter.model_revision() is None

    @pytest.mark.parametrize("outcome", list(_FAILED_PROBES.values()), ids=list(_FAILED_PROBES))
    def test_a_failed_probe_leaves_an_unknown_revision_unknown(self, outcome: object) -> None:
        """Replaces the old `down.model_revision() is None` assertion, which
        pinned the defect: an unreachable server read as "no revision"."""
        adapter = _adapter()
        snapshot = _probe(adapter, outcome)
        assert snapshot.known is False
        with pytest.raises(RevisionUnknownError):
            adapter.model_revision()

    @pytest.mark.parametrize("outcome", list(_FAILED_PROBES.values()), ids=list(_FAILED_PROBES))
    def test_a_failed_probe_never_changes_a_known_revision(self, outcome: object) -> None:
        """Design 0014 §1.1's HIGH variant: Ollama answers 200 without a model
        it failed to read. Taken as "none", that one probe re-embeds the
        corpus stamped NULL, and the next good probe re-embeds it again."""
        adapter = _adapter()
        known = _probe(adapter, _tags([_listed()]))
        after = _probe(adapter, outcome)
        assert after == known, "a failure must keep the value AND its verification time"

    def test_a_listed_new_digest_replaces_the_old_one_and_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        adapter = _adapter()
        _probe(adapter, _tags([_listed(digest="sha256:A")]))
        with caplog.at_level(logging.WARNING):
            snapshot = _probe(adapter, _tags([_listed(digest="sha256:B")]))
        assert snapshot.value == "sha256:B"
        changed = [r.getMessage() for r in caplog.records if "sha256:A" in r.getMessage()]
        assert len(changed) == 1 and "sha256:B" in changed[0]

    @pytest.mark.parametrize(
        ("configured", "listed"),
        [
            ("nomic-embed-text", "nomic-embed-text:latest"),
            ("nomic-embed-text:latest", "nomic-embed-text:latest"),
            ("library/nomic-embed-text", "nomic-embed-text:latest"),
            ("registry.ollama.ai/library/nomic-embed-text:latest", "nomic-embed-text:latest"),
            ("Nomic-Embed-Text", "nomic-embed-text:latest"),
            ("hf.co/someone/some-embed:Q8_0", "hf.co/someone/some-embed:Q8_0"),
        ],
    )
    def test_names_compare_the_way_ollama_resolves_them(self, configured: str, listed: str) -> None:
        snapshot = _probe(_adapter(configured), _tags([_listed(name=listed)]))
        assert snapshot.value == "sha256:A"

    def test_a_different_tag_is_a_different_model(self) -> None:
        snapshot = _probe(_adapter("nomic-embed-text:v1.5"), _tags([_listed(name="nomic-embed-text:latest")]))
        assert snapshot.known is False

    def test_the_model_field_is_matched_too(self) -> None:
        entry = {"name": "alias", "model": "nomic-embed-text:latest", "digest": "sha256:A"}
        assert _probe(_adapter(), _tags([entry])).value == "sha256:A"


# ── Adapter: probe serialization and cooldown (D3) ───────────────────


class TestProbeSerialization:
    def test_a_waiter_takes_the_in_flight_probe_result(self) -> None:
        """A write that finds a probe in flight waits for it instead of being
        refused (plan review R-ops 1), and does not probe a second time."""
        adapter = _adapter()
        entered, release = threading.Event(), threading.Event()
        calls: list[int] = []

        def slow_tags(*_args: object, **_kwargs: object) -> httpx.Response:
            calls.append(1)
            entered.set()
            release.wait(5)
            return _tags([_listed()])

        results: dict[str, RevisionSnapshot] = {}
        with patch("httpx.get", side_effect=slow_tags):
            prober = threading.Thread(target=lambda: results.update(probe=adapter.refresh_revision(force=True)))
            prober.start()
            assert entered.wait(5)
            writer = threading.Thread(target=lambda: results.update(write=adapter.refresh_revision()))
            writer.start()
            time.sleep(0.05)
            release.set()
            prober.join(5)
            writer.join(5)
        assert results["write"].value == "sha256:A", "the waiter gets the probe's result"
        assert len(calls) == 1, "and does not probe again"

    def test_a_hung_probe_holds_writers_only_for_the_wait_bound(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ollama_adapter, "_PROBE_WAIT_SECONDS", 0.2)
        adapter = _adapter()
        entered, release = threading.Event(), threading.Event()

        def hung_tags(*_args: object, **_kwargs: object) -> httpx.Response:
            entered.set()
            release.wait(5)
            return _tags([_listed()])

        with patch("httpx.get", side_effect=hung_tags):
            prober = threading.Thread(target=lambda: adapter.refresh_revision(force=True))
            prober.start()
            assert entered.wait(5)
            started = time.monotonic()
            snapshot = adapter.refresh_revision()
            waited = time.monotonic() - started
            release.set()
            prober.join(5)
        assert snapshot.known is False
        assert 0.15 <= waited < 2.0, f"waited {waited:.2f}s"

    def test_a_failed_probe_starts_a_cooldown_for_non_forced_refreshes(self) -> None:
        adapter = _adapter()
        _probe(adapter, httpx.ConnectError("refused"))
        with patch("httpx.get", return_value=_tags([_listed()])) as get:
            assert adapter.refresh_revision().known is False, "within the cooldown a write does not probe"
            get.assert_not_called()
            assert adapter.refresh_revision(force=True).known is True, "a forced refresh always probes"

    def test_a_successful_embed_ends_the_cooldown(self) -> None:
        """The server just answered, so the next write may probe at once."""
        adapter = _adapter()
        _probe(adapter, httpx.ConnectError("refused"))
        embed_ok = httpx.Response(
            200, json={"embeddings": [[1.0, 0.0]]}, request=httpx.Request("POST", "http://localhost:11434/api/embed")
        )
        with patch("httpx.post", return_value=embed_ok):
            adapter.embed("hello")
        with patch("httpx.get", return_value=_tags([_listed()])):
            assert adapter.refresh_revision().value == "sha256:A"

    def test_warnings_are_rate_limited(self, caplog: pytest.LogCaptureFixture) -> None:
        """Unknown: the first failure warns, repeats stay at DEBUG. Known: a
        run of three warns, because the value stays usable meanwhile."""
        unknown = _adapter()
        with caplog.at_level(logging.DEBUG, logger=_ADAPTER_LOGGER):
            for _ in range(3):
                _probe(unknown, httpx.ConnectError("refused"))
        warned = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warned) == 1 and "unverified" in warned[0].getMessage()

        caplog.clear()
        known = _adapter()
        _probe(known, _tags([_listed()]))
        levels = []
        with caplog.at_level(logging.DEBUG, logger=_ADAPTER_LOGGER):
            for _ in range(4):
                before = len(caplog.records)
                _probe(known, httpx.ConnectError("refused"))
                levels.append(max(r.levelno for r in caplog.records[before:]))
        assert levels == [logging.DEBUG, logging.DEBUG, logging.WARNING, logging.DEBUG]


# ── Service: one snapshot per operation, refusal, reconciliation ─────


class _RevisionPort(EmbeddingPort):
    """A revision-tracking port whose probe outcome the test controls.

    ``probe_result=None`` makes every probe fail, which leaves the snapshot
    as it is, the way the Ollama adapter behaves. ``during_embed`` runs
    inside the provider call, to change the world mid-embed.
    """

    def __init__(self, snapshot: RevisionSnapshot = UNKNOWN_REVISION) -> None:
        self.snapshot = snapshot
        self.probe_result: RevisionSnapshot | None = None
        self.probes = 0
        self.embeds = 0
        self.probe_threads: list[int] = []
        self.during_embed: Callable[[], None] | None = None

    @property
    def tracks_revision(self) -> bool:
        return True

    def revision_snapshot(self) -> RevisionSnapshot:
        return self.snapshot

    def refresh_revision(self, *, force: bool = False) -> RevisionSnapshot:
        self.probe_threads.append(threading.get_ident())
        if not force and self.snapshot.known:
            return self.snapshot
        self.probes += 1
        if self.probe_result is not None:
            self.snapshot = self.probe_result
        return self.snapshot

    def model_revision(self) -> str | None:
        if not self.snapshot.known:
            raise RevisionUnknownError("unverified")
        return self.snapshot.value

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.embeds += len(texts)
        if self.during_embed is not None:
            self.during_embed()
        return [[1.0, 0.0] for _ in texts]

    def dimensions(self) -> int:
        return 2

    def model_name(self) -> str:
        return "m"

    def provider_name(self) -> str:
        return "ollama"

    def settings_fingerprint(self) -> str:
        return "fp"


def _known(value: str | None) -> RevisionSnapshot:
    return RevisionSnapshot(known=True, value=value, verified_at=utc_now())


def _store_stamped(revision: str | None, count: int = 5) -> SqliteStore:
    """Memories whose vectors are current, stamped with ``revision``."""
    store = SqliteStore(db_path=":memory:")
    store.init_schema()
    store.add_project(Project(id="p", name="p"))
    for n in range(count):
        store.add_memory(MemoryItem(id=f"m{n}", content=f"memory number {n}", project_id="p"))
        save_vec(store, f"m{n}", [1.0, 0.0], model="m", provider="ollama", fingerprint="fp", model_revision=revision)
    return store


def _stamps(store: SqliteStore) -> set[object]:
    identities = (store.get_embedding_identity(mid) for mid in store.list_embeddings())
    return {identity["model_revision"] for identity in identities if identity is not None}


def _revision_of(store: SqliteStore, memory_id: str) -> object:
    identity = store.get_embedding_identity(memory_id)
    assert identity is not None, f"{memory_id} has no vector"
    return identity["model_revision"]


def _health(service: EmbeddingService) -> dict[str, Any]:
    container = MagicMock()
    container.embedding_settings = EmbeddingSettings(provider="ollama", model="m")
    container.embedding_service = service
    container.storage = service._store  # real values only: REST deep-copies the payload
    container.embedding_endpoint_is_remote.return_value = False
    return CoreContainer.embedding_status_dict(container)


def _save(store: SqliteStore, service: EmbeddingService, memory_id: str) -> None:
    item = MemoryItem(id=memory_id, content=f"saved as {memory_id}", project_id="p")
    add_memory.execute(store, item, embedding_service=service)


class TestTheIncident:
    def test_an_unverified_revision_re_embeds_nothing_and_keeps_search_working(self) -> None:
        """Design 0014 §1.1, end to end: rows stamped A, and every probe
        fails from startup. v3.3.0 re-embedded all of them stamped NULL,
        blanked semantic search and read `active` with stale == total."""
        store = _store_stamped("sha256:A")
        port = _RevisionPort()
        service = EmbeddingService(port=port, store=store)

        with pytest.raises(RevisionUnknownError):
            service.generate_missing()
        assert port.embeds == 0, "a refused backfill selects no candidates"
        assert _stamps(store) == {"sha256:A"}, "nothing was stamped NULL"

        hits = service.search_semantic("memory number")
        assert {s.item.id for s in hits} == {f"m{n}" for n in range(5)}, "search still matches meanwhile"

        health = _health(service)
        assert (health["status"], health["model_revision_state"], health["model_revision"]) == (
            "degraded",
            "unknown",
            None,
        )
        assert health["stale"] == 0, "stale is not inflated to the corpus size"

        embeds_before = port.embeds  # the search above embedded its query
        _save(store, service, "new")
        assert store.get_memory("new") is not None, "the save succeeds"
        assert store.get_embedding_identity("new") is None, "without a guessed stamp"
        assert port.embeds == embeds_before, "the refusal came before any embed"

        port.probe_result = _known("sha256:A")
        result = service.generate_missing()
        assert result.generated == 1, "only the refused save is embedded"
        assert port.embeds == embeds_before + 1
        assert _stamps(store) == {"sha256:A"}
        assert _health(service)["status"] == "active"

    def test_the_stamp_is_the_revision_seen_before_the_embed(self) -> None:
        """A re-pull landing mid-embed must not stamp old-weight vectors with
        the new digest, which would stay silently current forever (measured
        in the plan review). Trailing is safe: the row goes stale once B is
        verified, and the next backfill fixes it."""
        store = _store_stamped("sha256:A", count=0)
        store.add_memory(MemoryItem(id="x", content="embedded during a re-pull", project_id="p"))
        port = _RevisionPort(_known("sha256:A"))
        port.during_embed = lambda: setattr(port, "snapshot", _known("sha256:B"))
        service = EmbeddingService(port=port, store=store)

        service.generate_for_memory("x", "embedded during a re-pull")
        assert _revision_of(store, "x") == "sha256:A"

        port.during_embed = None
        port.probe_result = _known("sha256:B")
        assert service.embedding_status()["stale"] == 1, "under B the trailing row is stale"
        service.generate_missing()
        assert _stamps(store) == {"sha256:B"}

    def test_a_backfill_stamps_every_row_with_its_opening_snapshot(self) -> None:
        store = _store_stamped("sha256:OLD")
        port = _RevisionPort(_known("sha256:A"))
        port.probe_result = _known("sha256:A")
        flipped: list[bool] = []

        def flip_once() -> None:
            if not flipped:
                flipped.append(True)
                port.snapshot = _known("sha256:B")

        port.during_embed = flip_once
        EmbeddingService(port=port, store=store).generate_missing()
        assert _stamps(store) == {"sha256:A"}


class TestSingleBackfill:
    def test_a_concurrent_backfill_is_skipped_not_doubled(self) -> None:
        """The maintenance job and an automatic reindex could overlap: correct
        under CAS, but up to 1.95x the embeds (measured in the plan review)."""
        store = _store_stamped("sha256:OLD", count=3)
        port = _RevisionPort(_known("sha256:A"))
        port.probe_result = _known("sha256:A")
        inside, release = threading.Event(), threading.Event()

        def block() -> None:
            inside.set()
            release.wait(5)

        port.during_embed = block
        service = EmbeddingService(port=port, store=store)
        first: list[BackfillResult] = []
        runner = threading.Thread(target=lambda: first.append(service.generate_missing()))
        runner.start()
        assert inside.wait(5)
        assert service.backfill_running is True
        second = service.generate_missing()
        release.set()
        runner.join(5)

        assert (second.skipped, second.outcome) == (True, "skipped")
        assert first[0].generated == 3
        assert port.embeds == 3
        assert embed_memory.execute(service)["status"] == "ok", "the lock is released afterwards"

    def test_the_synchronous_embed_reports_a_running_backfill(self) -> None:
        port = _RevisionPort(_known("sha256:A"))
        service = EmbeddingService(port=port, store=_store_stamped("sha256:A", count=1))
        with service._backfill_lock:
            payload = embed_memory.execute(service)
        assert payload["status"] == "already_running"


class TestCallers:
    def test_a_refused_backfill_is_a_failed_run_not_an_exception(self) -> None:
        service = EmbeddingService(port=_RevisionPort(), store=_store_stamped("sha256:A", count=1))
        payload = embed_memory.execute(service)
        assert payload["status"] == "failed"
        assert "not verified" in payload["message"]

    def test_status_never_probes_on_the_event_loop(self) -> None:
        """R-ops 4, measured on v3.3.0: `memory_embed background=true` probed
        on the event loop and froze the server for 5 s against a hung
        endpoint. Only worker threads may probe now."""
        port = _RevisionPort()
        original = port.refresh_revision

        def slow_refresh(*, force: bool = False) -> RevisionSnapshot:
            time.sleep(0.5)
            return original(force=force)

        port.refresh_revision = slow_refresh  # type: ignore[method-assign]
        service = EmbeddingService(port=port, store=_store_stamped("sha256:A", count=1))
        loop_thread: list[int] = []

        async def scenario() -> float:
            loop_thread.append(threading.get_ident())
            started = time.monotonic()
            embed_memory.execute_background(service)
            elapsed = time.monotonic() - started
            task = service._background_backfill
            assert task is not None
            while not task.done():
                await asyncio.sleep(0.01)
            return elapsed

        elapsed = asyncio.run(scenario())
        assert elapsed < 0.25, f"execute_background blocked the loop for {elapsed:.2f}s"
        assert port.probe_threads, "premise: the backfill did probe"
        assert loop_thread[0] not in port.probe_threads, "no probe ran on the event loop's thread"

    def test_health_explains_an_unknown_revision_instead_of_failing(self) -> None:
        """F6: health called model_revision(), which now raises while the
        revision is unverified, so REST would have answered 502."""
        service = EmbeddingService(port=_RevisionPort(), store=_store_stamped("sha256:A", count=1))
        container = MagicMock()
        container.file_configs = {}
        container.storage = service._store
        container.embedding_service = None  # keeps the lifespan from starting a refresher
        container.embedding_status_dict.side_effect = lambda: _health(service)
        container.maintenance_degraded = False
        response = TestClient(create_app(container, HTTPConfig())).get("/api/v1/health")
        assert response.status_code == 200
        embedding = response.json()["embedding_status"]
        assert (embedding["status"], embedding["model_revision_state"]) == ("degraded", "unknown")

    def test_a_provider_without_revisions_reads_none_and_active(self) -> None:
        store = SqliteStore(db_path=":memory:")
        store.init_schema()
        health = _health(EmbeddingService(port=StubEmbeddingAdapter(dims=2), store=store))
        assert (health["status"], health["model_revision_state"], health["model_revision"]) == ("active", "none", None)

    def test_the_maintenance_loop_logs_a_refusal_as_one_line(self, caplog: pytest.LogCaptureFixture) -> None:
        """F5: a traceback every time reads like a dead provider."""

        async def refused(_container: object) -> None:
            raise RevisionUnknownError("the revision of embedding model 'm' is not verified yet")

        job = maintenance_loop.JobState(name="embedding_backfill", interval_seconds=60, enabled=True)
        loop = maintenance_loop.MaintenanceLoop(
            container=MagicMock(), jobs=[job], handlers={"embedding_backfill": refused}
        )
        with caplog.at_level(logging.ERROR, logger=maintenance_loop.__name__):
            asyncio.run(loop.run_once("embedding_backfill"))
        errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(errors) == 1
        assert errors[0].exc_info is None, "no traceback for a known provider condition"
        assert "not verified" in errors[0].getMessage()
        assert (job.runs_failed, job.last_success_at) == (1, None), "still a failed run"


# ── The refresher and reconciliation (D5, D6) ────────────────────────


def _run_refresher(service: EmbeddingService, until: Callable[[], bool], *, auto_backfill: bool = True) -> None:
    """Run the refresher until ``until()`` holds and no backfill is running."""

    async def scenario() -> None:
        assert service.start_revision_refresher(auto_backfill=auto_backfill) is True
        for _ in range(500):
            task = service._background_backfill
            if until() and (task is None or task.done()):
                break
            await asyncio.sleep(0.01)
        await service.stop_revision_refresher()
        task = service._background_backfill
        while task is not None and not task.done():
            await asyncio.sleep(0.01)

    asyncio.run(scenario())


class TestReconciliation:
    def test_a_boot_probe_reconciles_once_with_nothing_to_do(self) -> None:
        store = _store_stamped("sha256:A")
        port = _RevisionPort()
        port.probe_result = _known("sha256:A")
        service = EmbeddingService(port=port, store=store)

        _run_refresher(service, lambda: service.last_background_backfill is not None)

        kept = service.last_background_backfill
        assert kept is not None
        assert (kept["trigger"], kept["outcome"], kept["generated"]) == ("reconcile", "ok", 0)
        assert port.embeds == 0

        async def another_tick() -> bool:
            service._reconcile(port.snapshot)
            return service.backfill_running

        assert asyncio.run(another_tick()) is False, "reconciled once; the next tick starts nothing"

    def test_a_re_pull_seen_only_at_boot_is_re_embedded(self) -> None:
        """Unknown -> B is not "A -> B", which is why a one-shot change
        trigger missed it (plan review F1)."""
        store = _store_stamped("sha256:A")
        port = _RevisionPort()
        port.probe_result = _known("sha256:B")
        service = EmbeddingService(port=port, store=store)

        _run_refresher(service, lambda: _stamps(store) == {"sha256:B"})

        assert _stamps(store) == {"sha256:B"}
        assert port.embeds == 5

    def test_a_re_pull_while_running_is_re_embedded(self) -> None:
        store = _store_stamped("sha256:A")
        port = _RevisionPort(_known("sha256:A"))
        port.probe_result = _known("sha256:A")
        service = EmbeddingService(port=port, store=store)
        _run_refresher(service, lambda: service.last_background_backfill is not None)
        assert port.embeds == 0

        port.probe_result = _known("sha256:B")
        _run_refresher(service, lambda: _stamps(store) == {"sha256:B"})
        assert _stamps(store) == {"sha256:B"}

    def test_writes_refused_while_unverified_are_embedded_once_it_is(self) -> None:
        store = _store_stamped("sha256:A")
        port = _RevisionPort()
        service = EmbeddingService(port=port, store=store)
        _save(store, service, "late")
        assert store.get_embedding_identity("late") is None

        port.probe_result = _known("sha256:A")
        _run_refresher(service, lambda: store.get_embedding_identity("late") is not None)

        assert _revision_of(store, "late") == "sha256:A"

    def test_no_reconciliation_when_maintenance_is_disabled(self) -> None:
        store = _store_stamped("sha256:A")
        port = _RevisionPort()
        port.probe_result = _known("sha256:B")
        service = EmbeddingService(port=port, store=store)

        _run_refresher(service, lambda: port.probes >= 1, auto_backfill=False)

        assert port.snapshot.value == "sha256:B", "it still verifies"
        assert service.last_background_backfill is None
        assert port.embeds == 0

    def test_a_raising_refresh_does_not_end_the_refresher(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setattr(embedding_service_module, "_REVISION_REFRESH_UNKNOWN_SECONDS", 0.01)
        port = _RevisionPort()
        original = port.refresh_revision
        calls: list[int] = []

        def flaky(*, force: bool = False) -> RevisionSnapshot:
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("unexpected payload")
            return original(force=force)

        port.refresh_revision = flaky  # type: ignore[method-assign]
        service = EmbeddingService(port=port, store=_store_stamped("sha256:A", count=0))
        with caplog.at_level(logging.ERROR):
            _run_refresher(service, lambda: len(calls) >= 3, auto_backfill=False)
        assert len(calls) >= 3, "it kept ticking after the exception"
        assert any("refresh failed" in r.getMessage() for r in caplog.records)
        assert not any("refresher stopped" in r.getMessage() for r in caplog.records)

    def test_cadence_is_fast_while_unknown_and_slow_once_known(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(embedding_service_module, "_REVISION_REFRESH_UNKNOWN_SECONDS", 0.01)
        monkeypatch.setattr(embedding_service_module, "_REVISION_REFRESH_KNOWN_SECONDS", 60.0)
        port = _RevisionPort()
        service = EmbeddingService(port=port, store=_store_stamped("sha256:A", count=0))

        def verify_on_the_fifth_probe() -> bool:
            if port.probes >= 5:
                port.probe_result = _known("sha256:A")
            return port.snapshot.known

        _run_refresher(service, verify_on_the_fifth_probe, auto_backfill=False)
        assert port.probes >= 5, "while unknown it retried quickly"
        probes_when_known = port.probes

        async def idle() -> None:
            assert service.start_revision_refresher(auto_backfill=False) is True
            await asyncio.sleep(0.2)
            await service.stop_revision_refresher()

        asyncio.run(idle())
        assert port.probes == probes_when_known + 1, "known: one probe at start, then a long wait"

    def test_providers_without_revisions_get_no_refresher(self) -> None:
        store = SqliteStore(db_path=":memory:")
        store.init_schema()
        service = EmbeddingService(port=StubEmbeddingAdapter(dims=2), store=store)

        async def scenario() -> bool:
            return service.start_revision_refresher()

        assert asyncio.run(scenario()) is False


# ── The CLI resolves the revision itself (F4) and refuses in one line (D8) ─


def _cli(root: Path, monkeypatch: pytest.MonkeyPatch, port: _RevisionPort) -> CoreContainer:
    (root / "config").mkdir()
    monkeypatch.setenv("OC_DB_PATH", str(root / "cli.db"))
    monkeypatch.setenv("OC_CONFIG_DIR", str(root / "config"))
    monkeypatch.delenv("OC_EMBEDDING_PROVIDER", raising=False)
    container = CoreContainer()
    container.embedding_service = EmbeddingService(port=port, store=container.storage)
    return container


def _run_cli(container: CoreContainer, argv: list[str]) -> tuple[int, list[str]]:
    from openchronicle.interfaces.cli.main import main

    with (
        patch("builtins.print") as printed,
        patch("openchronicle.interfaces.cli.main._build_container", return_value=container),
    ):
        rc = main(argv)
    return rc, [str(c.args[0]) if c.args else "" for c in printed.call_args_list]


class TestCli:
    def test_embed_refusal_is_one_line_and_exit_1(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        rc, lines = _run_cli(_cli(tmp_path, monkeypatch, _RevisionPort()), ["memory", "embed"])
        assert rc == 1
        assert len(lines) == 1 and lines[0].startswith("Backfill refused:")

    def test_embed_status_verifies_the_revision_first(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        port = _RevisionPort()
        port.probe_result = _known("sha256:A")
        rc, lines = _run_cli(_cli(tmp_path, monkeypatch, port), ["memory", "embed", "--status"])
        assert rc == 0
        assert port.probes == 1
        assert "Revision:       known (sha256:A)" in lines

    def test_search_verifies_the_revision_unless_keyword_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        port = _RevisionPort()
        port.probe_result = _known("sha256:A")
        container = _cli(tmp_path, monkeypatch, port)
        _run_cli(container, ["memory", "search", "anything", "--mode", "keyword"])
        assert port.probes == 0, "keyword search needs no revision"
        _run_cli(container, ["memory", "search", "anything"])
        assert port.probes == 1


# ── Wiring: who starts the refresher, who probes once (D5, F4, D8) ────


class TestWiring:
    def test_the_asgi_lifespan_runs_the_refresher(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Started with the app and stopped with it; with maintenance
        disabled it still verifies but starts no backfills."""
        monkeypatch.setenv("OC_MAINTENANCE_DISABLED", "1")
        port = _RevisionPort()
        port.probe_result = _known("sha256:B")
        service = EmbeddingService(port=port, store=_store_stamped("sha256:A"))
        container = MagicMock()
        container.file_configs = {}
        container.embedding_service = service
        app = create_app(container, HTTPConfig(), mount_mcp=False)

        with TestClient(app):
            for _ in range(300):
                if port.probes:
                    break
                time.sleep(0.01)
            assert port.probes >= 1, "the refresher probed at startup"
            assert service._revision_refresher is not None
        assert service._revision_refresher is None, "stopped with the app"
        assert service.last_background_backfill is None, "maintenance disabled: no reconcile backfill"

    def test_the_stdio_entrypoint_verifies_before_serving(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from openchronicle.interfaces.mcp import __main__ as entry

        order: list[str] = []
        container = MagicMock()
        container.embedding_service.port.refresh_revision.side_effect = lambda: order.append("refresh")
        server = MagicMock()
        server.run.side_effect = lambda **_kwargs: order.append("run")
        monkeypatch.setattr("openchronicle.core.infrastructure.wiring.container.CoreContainer", lambda: container)
        monkeypatch.setattr("openchronicle.interfaces.mcp.server.create_server", lambda _c, _cfg: server)
        monkeypatch.delenv("OC_MCP_TRANSPORT", raising=False)

        entry.main()

        assert order == ["refresh", "run"]

    def test_a_refused_save_logs_no_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """The adapter warns once about the unverified revision. A traceback on
        every save would read like a dead provider."""
        store = _store_stamped("sha256:A", count=0)
        service = EmbeddingService(port=_RevisionPort(), store=store)
        with caplog.at_level(logging.DEBUG):
            _save(store, service, "a")
            store.update_memory("a", content="edited")
            update_memory.execute(store, "a", content="edited again", embedding_service=service)
        use_case_records = [r for r in caplog.records if r.name.startswith("openchronicle.core.application.use_cases")]
        assert use_case_records, "premise: the refusals were logged"
        assert all(r.levelno == logging.DEBUG and r.exc_info is None for r in use_case_records)
