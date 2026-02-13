"""Multi-connection concurrency stress tests.

Each test creates separate SqliteStore instances pointing to the same database
file, simulating multi-process access (separate sqlite3 connections with
independent locks and WAL snapshots). Tests target specific race conditions
identified in the concurrency audit.

Gate: OC_INTEGRATION_TESTS=1
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from openchronicle.core.domain.models.conversation import Conversation, Turn
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Event, Project
from openchronicle.core.domain.services.verification import VerificationService
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

pytestmark = [
    pytest.mark.skipif(
        os.getenv("OC_INTEGRATION_TESTS") != "1",
        reason="Integration tests skipped unless OC_INTEGRATION_TESTS=1",
    ),
    pytest.mark.integration,
]


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    """Shared database file. Schema initialized, ready for multi-connection."""
    path = str(tmp_path / "stress.db")
    store = SqliteStore(path)
    store.init_schema()
    store._conn.close()
    return path


def _make_store(db_path: str, busy_timeout_ms: int = 5000) -> SqliteStore:
    """New connection to the shared database (simulates separate process)."""
    store = SqliteStore(db_path)
    if busy_timeout_ms != 5000:
        store._conn.execute(f"PRAGMA busy_timeout = {busy_timeout_ms};")
    return store


# ---------------------------------------------------------------------------
# T1: EventLogger.append() — Hash Chain Fork
# ---------------------------------------------------------------------------


def test_t1_hash_chain_fork(db_path: str) -> None:
    """Concurrent EventLogger.append() to the SAME task_id.

    Target: audit issue #2 (CRITICAL). The read-compute-write in append()
    is not transactional. Two connections can read the same prev_hash and
    create sibling events, forking the chain.
    """
    n_threads = 10
    events_per_thread = 30
    total_expected = n_threads * events_per_thread

    # Seed: project + one initial event so the chain has a root.
    setup = _make_store(db_path)
    project = Project(name="t1-project", metadata={})
    setup.add_project(project)
    task_id = str(uuid.uuid4())
    seed = Event(project_id=project.id, task_id=task_id, type="seed")
    seed.compute_hash()
    setup.append_event(seed)
    setup._conn.close()

    barrier = threading.Barrier(n_threads)
    errors: list[Exception] = []
    lock = threading.Lock()

    def _worker(thread_idx: int) -> None:
        store = _make_store(db_path)
        logger = EventLogger(store)
        barrier.wait()
        try:
            for i in range(events_per_thread):
                evt = Event(
                    project_id=project.id,
                    task_id=task_id,
                    type=f"t1.thread-{thread_idx}.event-{i}",
                )
                logger.append(evt)
        except Exception as exc:
            with lock:
                errors.append(exc)
        finally:
            store._conn.close()

    threads = [threading.Thread(target=_worker, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, f"Thread errors: {errors}"

    # Verify
    verify_store = _make_store(db_path)
    events = verify_store.list_events(task_id=task_id)
    # +1 for the seed event
    assert len(events) == total_expected + 1, f"Expected {total_expected + 1} events, got {len(events)} (lost writes)"

    # Check for prev_hash collisions (two events sharing the same prev_hash)
    prev_hashes = [e.prev_hash for e in events if e.prev_hash is not None]
    prev_hash_counts = Counter(prev_hashes)
    collisions = {ph: cnt for ph, cnt in prev_hash_counts.items() if cnt > 1}

    # Formal chain verification
    verifier = VerificationService(verify_store)
    result = verifier.verify_task_chain(task_id=task_id)
    verify_store._conn.close()

    if collisions or not result.success:
        pytest.xfail(
            f"Hash chain fork detected (expected race): "
            f"{len(collisions)} prev_hash collision(s), "
            f"verification={'OK' if result.success else result.error_message}"
        )
    # If we get here, chain is intact — race didn't trigger this run.


# ---------------------------------------------------------------------------
# T2: next_turn_index — Duplicate Turn Index
# ---------------------------------------------------------------------------


def test_t2_duplicate_turn_index(db_path: str) -> None:
    """Concurrent next_turn_index + add_turn to the same conversation.

    Target: audit issue #4 (CRITICAL). next_turn_index() reads MAX inside
    a deferred BEGIN, so the read doesn't hold a write lock. Two connections
    compute the same next index; UNIQUE constraint raises IntegrityError,
    losing the completed response.
    """
    n_threads = 10

    setup = _make_store(db_path)
    project = Project(name="t2-project", metadata={})
    setup.add_project(project)
    convo = Conversation(project_id=project.id, title="t2-convo")
    setup.add_conversation(convo)
    setup._conn.close()

    barrier = threading.Barrier(n_threads)
    successes: list[int] = []  # turn_index values that succeeded
    integrity_errors: list[Exception] = []
    locked_errors: list[Exception] = []
    other_errors: list[Exception] = []
    lock = threading.Lock()

    def _worker(thread_idx: int) -> None:
        store = _make_store(db_path)
        barrier.wait()
        try:
            with store.transaction():
                idx = store.next_turn_index(convo.id)
                turn = Turn(
                    conversation_id=convo.id,
                    turn_index=idx,
                    user_text=f"thread-{thread_idx}",
                    assistant_text=f"response-{thread_idx}",
                    provider="stub",
                    model="stress-test",
                )
                store.add_turn(turn)
            with lock:
                successes.append(idx)
        except sqlite3.IntegrityError as exc:
            with lock:
                integrity_errors.append(exc)
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower():
                with lock:
                    locked_errors.append(exc)
            else:
                with lock:
                    other_errors.append(exc)
        except Exception as exc:
            with lock:
                other_errors.append(exc)
        finally:
            store._conn.close()

    threads = [threading.Thread(target=_worker, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not other_errors, f"Unexpected errors: {other_errors}"

    # Both IntegrityError (duplicate index) and OperationalError (database
    # locked) prove the race — either way a completed LLM response is lost.
    race_errors = integrity_errors + locked_errors
    if race_errors:
        pytest.xfail(
            f"Turn index race detected (expected): "
            f"{len(integrity_errors)} IntegrityError(s), "
            f"{len(locked_errors)} locked error(s), "
            f"{len(successes)} succeeded"
        )

    # If all succeeded, verify distinct turn_index values.
    assert len(set(successes)) == len(successes), f"Duplicate turn_index values without errors: {successes}"


# ---------------------------------------------------------------------------
# T3: link_memory_to_turn — Lost Update
# ---------------------------------------------------------------------------


def test_t3_link_memory_lost_update(db_path: str) -> None:
    """Concurrent link_memory_to_turn on the same turn.

    Target: audit issue #5 (CRITICAL). Read-modify-write on a JSON column
    with no transaction protection. Two connections read the same
    memory_written_ids, each appends a different ID, second write
    silently overwrites first.
    """
    n_threads = 10

    setup = _make_store(db_path)
    project = Project(name="t3-project", metadata={})
    setup.add_project(project)
    convo = Conversation(project_id=project.id, title="t3-convo")
    setup.add_conversation(convo)
    turn = Turn(
        conversation_id=convo.id,
        turn_index=1,
        user_text="setup",
        assistant_text="setup",
        provider="stub",
        model="stress-test",
    )
    setup.add_turn(turn)

    memory_ids: list[str] = []
    for i in range(n_threads):
        mem = MemoryItem(
            content=f"memory-{i}",
            tags=["stress"],
            project_id=project.id,
        )
        setup.add_memory(mem)
        memory_ids.append(mem.id)
    setup._conn.close()

    barrier = threading.Barrier(n_threads)
    errors: list[Exception] = []
    lock = threading.Lock()

    def _worker(thread_idx: int) -> None:
        store = _make_store(db_path)
        barrier.wait()
        try:
            store.link_memory_to_turn(turn.id, memory_ids[thread_idx])
        except Exception as exc:
            with lock:
                errors.append(exc)
        finally:
            store._conn.close()

    threads = [threading.Thread(target=_worker, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, f"Thread errors: {errors}"

    # Read the final state of memory_written_ids.
    verify_store = _make_store(db_path)
    row = verify_store._conn.execute("SELECT memory_written_ids FROM turns WHERE id=?", (turn.id,)).fetchone()
    verify_store._conn.close()

    raw = row["memory_written_ids"] or "[]"
    surviving_ids: list[str] = json.loads(raw)
    survived = sum(1 for mid in memory_ids if mid in surviving_ids)

    if survived < n_threads:
        pytest.xfail(f"Lost update race detected (expected): {survived}/{n_threads} memory IDs survived")
    # If all 10 present, race didn't trigger.


# ---------------------------------------------------------------------------
# T4: Write Lock Starvation
# ---------------------------------------------------------------------------


def test_t4_write_lock_starvation(db_path: str) -> None:
    """Long transaction starves other writers.

    Target: audit issue #6 (CRITICAL). A writer holding BEGIN IMMEDIATE
    for the duration of an LLM call blocks every other writer until
    busy_timeout expires.
    """
    setup = _make_store(db_path)
    project = Project(name="t4-project", metadata={})
    setup.add_project(project)
    setup._conn.close()

    store_holder = _make_store(db_path)
    # Short timeout so the test fails fast instead of hanging.
    store_writer = _make_store(db_path, busy_timeout_ms=200)

    holder_ready = threading.Event()
    holder_done = threading.Event()
    writer_result: dict[str, Any] = {}

    def _holder() -> None:
        """Acquire write lock, hold it for 1 second (simulating LLM call)."""
        store_holder._conn.execute("BEGIN IMMEDIATE")
        store_holder._conn.execute(
            "INSERT INTO events (id, project_id, task_id, type, payload, created_at, hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), project.id, "t4-task", "t4.hold", "{}", "2024-01-01T00:00:00", "fake"),
        )
        holder_ready.set()
        time.sleep(1.0)
        store_holder._conn.execute("COMMIT")
        holder_done.set()

    def _writer() -> None:
        """Try to write while holder has the lock."""
        holder_ready.wait(timeout=5)
        # Small delay to ensure we're well within the holder's sleep window.
        time.sleep(0.1)
        try:
            evt = Event(
                project_id=project.id,
                task_id="t4-task",
                type="t4.starved",
            )
            evt.compute_hash()
            store_writer.append_event(evt)
            writer_result["error"] = None
        except sqlite3.OperationalError as exc:
            writer_result["error"] = exc
        except Exception as exc:
            writer_result["error"] = exc

    t_hold = threading.Thread(target=_holder)
    t_write = threading.Thread(target=_writer)
    t_hold.start()
    t_write.start()
    t_hold.join(timeout=10)
    t_write.join(timeout=10)

    store_holder._conn.close()
    store_writer._conn.close()

    err = writer_result.get("error")
    if isinstance(err, sqlite3.OperationalError) and "locked" in str(err).lower():
        pytest.xfail(f"Write lock starvation confirmed (expected): {err}")
    # If no error, the writer squeezed through — race didn't trigger.


# ---------------------------------------------------------------------------
# T5: Independent Task Chains — Baseline (Must Pass)
# ---------------------------------------------------------------------------


def test_t5_independent_chains_baseline(db_path: str) -> None:
    """Concurrent writes to DIFFERENT task_ids must always work.

    This is the baseline: if this fails, the database is fundamentally
    broken, not just racy. This test must always pass.
    """
    n_threads = 10
    events_per_thread = 30
    total_expected = n_threads * events_per_thread

    setup = _make_store(db_path)
    project = Project(name="t5-project", metadata={})
    setup.add_project(project)
    setup._conn.close()

    task_ids = [str(uuid.uuid4()) for _ in range(n_threads)]
    barrier = threading.Barrier(n_threads)
    errors: list[Exception] = []
    lock = threading.Lock()

    def _worker(thread_idx: int) -> None:
        store = _make_store(db_path)
        logger = EventLogger(store)
        my_task_id = task_ids[thread_idx]
        barrier.wait()
        try:
            for i in range(events_per_thread):
                evt = Event(
                    project_id=project.id,
                    task_id=my_task_id,
                    type=f"t5.thread-{thread_idx}.event-{i}",
                )
                logger.append(evt)
        except Exception as exc:
            with lock:
                errors.append(exc)
        finally:
            store._conn.close()

    threads = [threading.Thread(target=_worker, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, f"Thread errors: {errors}"

    # Verify all events persisted.
    verify_store = _make_store(db_path)

    all_events: list[Event] = []
    for tid in task_ids:
        events = verify_store.list_events(task_id=tid)
        assert len(events) == events_per_thread, f"Task {tid}: expected {events_per_thread} events, got {len(events)}"
        all_events.extend(events)

    assert len(all_events) == total_expected

    # Each task's chain must be intact.
    verifier = VerificationService(verify_store)
    for tid in task_ids:
        result = verifier.verify_task_chain(task_id=tid)
        assert result.success, f"Chain broken for task {tid}: {result.error_message}"

    # No cross-contamination.
    for tid in task_ids:
        events = verify_store.list_events(task_id=tid)
        for evt in events:
            assert evt.task_id == tid, f"Cross-contamination: event {evt.id} has task_id={evt.task_id}, expected {tid}"

    # Database integrity.
    integrity = verify_store._conn.execute("PRAGMA integrity_check").fetchone()
    verify_store._conn.close()
    assert integrity[0] == "ok", f"SQLite integrity failed: {integrity[0]}"
