"""The content cap is enforced in ONE place and honoured by every surface.

It used to be four hardcoded literals in two driver files with nothing in
the middle: MCP hand-rolled the check twice, the REST routes declared it
twice via Pydantic, and the use cases had none — so the same store took a
200KB memory through `oc memory add` while rejecting it over MCP and HTTP.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from openchronicle.core.application.use_cases import add_memory, update_memory
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.memory_item import MAX_CONTENT_CHARS, MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqliteStore]:
    s = SqliteStore(str(tmp_path / "cap.db"))
    s.init_schema()
    s.add_project(Project(id="p", name="P"))
    yield s
    s.close()


def _item(content: str) -> MemoryItem:
    return MemoryItem(content=content, project_id="p")


class TestAddMemoryCap:
    def test_over_cap_is_rejected(self, store: SqliteStore) -> None:
        """The CLI path — previously unbounded — now enforces."""
        with pytest.raises(DomainValidationError, match="exceeds maximum length"):
            add_memory.execute(store, _item("x" * (MAX_CONTENT_CHARS + 1)))
        assert store.list_memory(limit=None) == [], "nothing may be persisted"

    def test_exactly_at_cap_is_accepted(self, store: SqliteStore) -> None:
        """Boundary: the cap is inclusive. An off-by-one here rejects valid input."""
        item = add_memory.execute(store, _item("x" * MAX_CONTENT_CHARS))
        assert len(item.content) == MAX_CONTENT_CHARS

    def test_error_names_both_the_limit_and_the_actual_size(self, store: SqliteStore) -> None:
        with pytest.raises(DomainValidationError) as exc:
            add_memory.execute(store, _item("x" * (MAX_CONTENT_CHARS + 500)))
        msg = str(exc.value)
        assert "100,000" in msg and "100,500" in msg, "an operator needs both numbers"


class TestUpdateMemoryCap:
    def test_over_cap_update_is_rejected(self, store: SqliteStore) -> None:
        existing = add_memory.execute(store, _item("small"))
        with pytest.raises(DomainValidationError, match="exceeds maximum length"):
            update_memory.execute(store, existing.id, content="x" * (MAX_CONTENT_CHARS + 1))
        unchanged = store.get_memory(existing.id)
        assert unchanged is not None, "the row must still exist"
        assert unchanged.content == "small", "the row must be untouched"

    def test_at_cap_update_is_accepted(self, store: SqliteStore) -> None:
        existing = add_memory.execute(store, _item("small"))
        updated = update_memory.execute(store, existing.id, content="x" * MAX_CONTENT_CHARS)
        assert len(updated.content) == MAX_CONTENT_CHARS

    def test_tags_only_update_is_unaffected(self, store: SqliteStore) -> None:
        existing = add_memory.execute(store, _item("small"))
        updated = update_memory.execute(store, existing.id, tags=["a"])
        assert updated.tags == ["a"]


def test_no_surface_hardcodes_the_limit() -> None:
    """One source of truth, checked structurally rather than by eyeball.

    The whole defect was the literal appearing in four places; a future
    driver copying the pattern would silently reintroduce the drift.
    """
    src = Path("src/openchronicle")
    offenders = [
        f"{path}:{n}"
        for path in src.rglob("*.py")
        if path.name != "memory_item.py"
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if "100_000" in line or "100000" in line
    ]
    assert offenders == [], f"content cap hardcoded outside the constant: {offenders}"


def test_cli_add_reports_over_cap_cleanly_instead_of_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Moving the cap into the use case must not turn the CLI into a traceback.

    `cmd_memory_add` had no try/except because nothing it called raised;
    `cmd_memory_update` has caught this class all along. An operator typing
    too much text deserves an exit code, not a stack trace.
    """
    import sys

    from openchronicle.interfaces.cli.main import main

    monkeypatch.setenv("OC_DB_PATH", str(tmp_path / "cli.db"))
    monkeypatch.setenv("OC_MAINTENANCE_DISABLED", "1")

    monkeypatch.setattr(sys, "argv", ["oc", "init-project", "CapCLI"])
    assert main() == 0
    project_id = capsys.readouterr().out.strip().splitlines()[-1]

    monkeypatch.setattr(sys, "argv", ["oc", "memory", "add", "x" * (MAX_CONTENT_CHARS + 1), "--project-id", project_id])
    rc = main()
    out = capsys.readouterr().out

    assert rc == 1, "must exit non-zero"
    assert "exceeds maximum length" in out
    assert "Traceback" not in out
