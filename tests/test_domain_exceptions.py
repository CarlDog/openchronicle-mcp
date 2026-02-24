"""Tests for domain exception types — NotFoundError, ValidationError.

Also tests that infrastructure methods (sqlite_store) raise domain exceptions
with correct error codes for nonexistent entities.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError


class TestNotFoundError:
    def test_default_code(self) -> None:
        exc = NotFoundError("something missing")
        assert exc.code == "NOT_FOUND"
        assert str(exc) == "something missing"

    def test_custom_code(self) -> None:
        exc = NotFoundError("gone", code="MEMORY_NOT_FOUND")
        assert exc.code == "MEMORY_NOT_FOUND"
        assert str(exc) == "gone"

    def test_is_exception(self) -> None:
        assert issubclass(NotFoundError, Exception)


class TestValidationError:
    def test_default_code(self) -> None:
        exc = DomainValidationError("bad input")
        assert exc.code == "INVALID_ARGUMENT"
        assert str(exc) == "bad input"

    def test_custom_code(self) -> None:
        exc = DomainValidationError("oops", code="CUSTOM_CODE")
        assert exc.code == "CUSTOM_CODE"

    def test_is_exception(self) -> None:
        assert issubclass(DomainValidationError, Exception)


# ---------------------------------------------------------------------------
# Rowcount checks in SqliteStore
# ---------------------------------------------------------------------------


def _make_store(tmp_path: Path):  # type: ignore[no-untyped-def]
    from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

    store = SqliteStore(str(tmp_path / "test.db"))
    store.init_schema()
    return store


class TestStoreRowcountChecks:
    """UPDATE methods raise NotFoundError when the target entity does not exist."""

    def test_update_task_status_nonexistent(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        with pytest.raises(NotFoundError, match="Task not found"):
            store.update_task_status("nonexistent", "completed")

    def test_update_task_result_nonexistent(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        with pytest.raises(NotFoundError, match="Task not found"):
            store.update_task_result("nonexistent", "{}", "completed")

    def test_update_task_error_nonexistent(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        with pytest.raises(NotFoundError, match="Task not found"):
            store.update_task_error("nonexistent", "{}", "failed")

    def test_update_memory_nonexistent(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        with pytest.raises(NotFoundError, match="Memory not found"):
            store.update_memory("nonexistent", content="new")

    def test_set_pinned_nonexistent(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        with pytest.raises(NotFoundError, match="Memory not found"):
            store.set_pinned("nonexistent", True)

    def test_set_conversation_mode_nonexistent(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        with pytest.raises(NotFoundError, match="Conversation not found"):
            store.set_conversation_mode("nonexistent", "general")
