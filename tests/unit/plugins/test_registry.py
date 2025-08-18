"""Tests for plugin registry."""

from __future__ import annotations

import threading

from openchronicle_new.plugins.registry import Registry


def test_registry_thread_safe_registration() -> None:
    registry = Registry()

    def worker(i: int) -> None:
        registry.register(f"p{i}", object())

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ids = registry.list_all()
    assert len(ids) == 10
    assert ids == sorted(ids)
