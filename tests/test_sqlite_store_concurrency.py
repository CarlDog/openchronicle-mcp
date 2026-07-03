"""Thread-safety of the shared SqliteStore connection.

One SqliteStore holds one sqlite3.Connection shared across Starlette's
sync-handler threadpool and the maintenance loop's asyncio.to_thread
workers. These tests pin the serialization contract: concurrent
transactions never nest a BEGIN on the shared connection, statements
from one thread never land inside another thread's open transaction,
and VACUUM/backup never interleave an open transaction.

Before the store lock existed, the concurrent-writer tests here
reliably raised ``sqlite3.OperationalError: cannot start a transaction
within a transaction`` (the BEGIN retry only covers "locked") and the
vacuum test raised ``cannot VACUUM from within a transaction``.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

_THREADS = 8
_OPS_PER_THREAD = 10


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqliteStore]:
    s = SqliteStore(db_path=str(tmp_path / "concurrency.db"))
    s.init_schema()
    yield s
    s.close()


def _run_threads(workers: list[threading.Thread], errors: list[BaseException]) -> None:
    for t in workers:
        t.start()
    for t in workers:
        t.join(timeout=30)
    assert not any(t.is_alive() for t in workers), "worker thread hung"
    assert errors == [], f"worker raised: {errors!r}"


def test_concurrent_transactional_writers_do_not_nest_begin(store: SqliteStore) -> None:
    """N threads doing add+delete inside explicit transactions, no errors."""
    errors: list[BaseException] = []
    barrier = threading.Barrier(_THREADS)

    def writer(worker_id: int) -> None:
        try:
            barrier.wait(timeout=10)
            for i in range(_OPS_PER_THREAD):
                item = MemoryItem(content=f"w{worker_id}-{i}", source="test")
                with store.transaction():
                    store.add_memory(item)
                with store.transaction():
                    store.delete_memory(item.id)
        except BaseException as exc:
            errors.append(exc)

    _run_threads([threading.Thread(target=writer, args=(n,)) for n in range(_THREADS)], errors)
    assert store.count_memory() == 0


def test_plain_writes_do_not_land_inside_open_transaction(store: SqliteStore) -> None:
    """A non-transactional write from thread B must not join thread A's
    open transaction — if it did, A's ROLLBACK would eat B's committed row."""
    errors: list[BaseException] = []
    a_in_transaction = threading.Event()
    b_done = threading.Event()
    b_item = MemoryItem(content="from-b", source="test")

    def thread_a() -> None:
        try:
            with pytest.raises(RuntimeError, match="induced rollback"), store.transaction():
                store.add_memory(MemoryItem(content="from-a", source="test"))
                a_in_transaction.set()
                # Give B a real window to attempt its write mid-transaction.
                b_done.wait(timeout=0.5)
                raise RuntimeError("induced rollback")
        except BaseException as exc:
            errors.append(exc)

    def thread_b() -> None:
        try:
            a_in_transaction.wait(timeout=10)
            store.add_memory(b_item)  # blocks on the store lock until A rolls back
            b_done.set()
        except BaseException as exc:
            errors.append(exc)

    _run_threads([threading.Thread(target=thread_a), threading.Thread(target=thread_b)], errors)
    # A rolled back; B's independent write must have survived.
    assert store.get_memory(b_item.id) is not None
    assert store.count_memory() == 1


def test_second_thread_waits_for_open_transaction(store: SqliteStore) -> None:
    """transaction() from thread B blocks until thread A commits."""
    errors: list[BaseException] = []
    order: list[str] = []
    a_in = threading.Event()

    def thread_a() -> None:
        try:
            with store.transaction():
                order.append("a-enter")
                a_in.set()
                time.sleep(0.3)
                order.append("a-exit")
        except BaseException as exc:
            errors.append(exc)

    def thread_b() -> None:
        try:
            a_in.wait(timeout=10)
            with store.transaction():
                order.append("b-enter")
        except BaseException as exc:
            errors.append(exc)

    _run_threads([threading.Thread(target=thread_a), threading.Thread(target=thread_b)], errors)
    assert order == ["a-enter", "a-exit", "b-enter"]


def test_vacuum_concurrent_with_transactions(store: SqliteStore) -> None:
    """VACUUM serializes against open transactions instead of raising
    'cannot VACUUM from within a transaction'."""
    errors: list[BaseException] = []
    stop = threading.Event()

    def writer() -> None:
        try:
            while not stop.is_set():
                item = MemoryItem(content="vacuum-race", source="test")
                with store.transaction():
                    store.add_memory(item)
                store.delete_memory(item.id)
        except BaseException as exc:
            errors.append(exc)

    def vacuumer() -> None:
        try:
            for _ in range(5):
                store.vacuum()
        except BaseException as exc:
            errors.append(exc)
        finally:
            stop.set()

    _run_threads([threading.Thread(target=writer), threading.Thread(target=vacuumer)], errors)


def test_backup_concurrent_with_transactions(store: SqliteStore, tmp_path: Path) -> None:
    """backup_to never interleaves an open transaction's page writes."""
    errors: list[BaseException] = []
    stop = threading.Event()

    def writer() -> None:
        try:
            while not stop.is_set():
                item = MemoryItem(content="backup-race", source="test")
                with store.transaction():
                    store.add_memory(item)
        except BaseException as exc:
            errors.append(exc)

    def backupper() -> None:
        try:
            for i in range(3):
                store.backup_to(tmp_path / f"snap-{i}.db")
        except BaseException as exc:
            errors.append(exc)
        finally:
            stop.set()

    _run_threads([threading.Thread(target=writer), threading.Thread(target=backupper)], errors)
    for i in range(3):
        assert (tmp_path / f"snap-{i}.db").exists()


def test_nested_transaction_same_thread_uses_savepoints(store: SqliteStore) -> None:
    """The RLock keeps same-thread nesting on the savepoint path."""
    outer = MemoryItem(content="outer", source="test")
    inner = MemoryItem(content="inner", source="test")
    with store.transaction():
        store.add_memory(outer)
        with pytest.raises(RuntimeError, match="inner rollback"), store.transaction():
            store.add_memory(inner)
            raise RuntimeError("inner rollback")
        # Inner savepoint rolled back; outer transaction still intact.
        assert store.get_memory(inner.id) is None
    assert store.get_memory(outer.id) is not None
