"""Tests for memory export/import use cases."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from openchronicle.core.application.use_cases import export_memory, import_memory
from openchronicle.core.domain.exceptions import ValidationError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


def _seeded(tmp_path: Path, *, project_count: int = 1, items_per_project: int = 3) -> SqliteStore:
    store = SqliteStore(str(tmp_path / "src.db"))
    store.init_schema()
    for p_i in range(project_count):
        project = Project(id=f"proj-{p_i}", name=f"Project {p_i}")
        store.add_project(project)
        for m_i in range(items_per_project):
            store.add_memory(
                MemoryItem(
                    id=f"mem-{p_i}-{m_i}",
                    content=f"memory {p_i}/{m_i}",
                    project_id=project.id,
                    tags=[f"tag-{m_i}"],
                    pinned=(m_i == 0),
                    source="test",
                )
            )
    return store


def test_export_returns_format_version_and_payload(tmp_path: Path) -> None:
    store = _seeded(tmp_path, project_count=2, items_per_project=2)
    payload = export_memory.execute(storage=store, memory_store=store)
    store.close()

    assert payload["format_version"] == 1
    assert len(payload["projects"]) == 2
    assert len(payload["memory_items"]) == 4


def test_export_filters_by_project(tmp_path: Path) -> None:
    store = _seeded(tmp_path, project_count=2, items_per_project=2)
    payload = export_memory.execute(storage=store, memory_store=store, project_id="proj-0")
    store.close()

    assert len(payload["projects"]) == 1
    assert payload["projects"][0]["id"] == "proj-0"
    assert all(m["project_id"] == "proj-0" for m in payload["memory_items"])


def test_export_excludes_embeddings(tmp_path: Path) -> None:
    """Embeddings are intentionally omitted (regenerable)."""
    store = _seeded(tmp_path)
    payload = export_memory.execute(storage=store, memory_store=store)
    store.close()
    assert "embeddings" not in payload
    for memory in payload["memory_items"]:
        assert "embedding" not in memory


def test_import_merge_into_empty_store(tmp_path: Path) -> None:
    src = _seeded(tmp_path, project_count=1, items_per_project=2)
    payload = export_memory.execute(storage=src, memory_store=src)
    src.close()

    dest = SqliteStore(str(tmp_path / "dest.db"))
    dest.init_schema()
    result = import_memory.execute(storage=dest, memory_store=dest, payload=payload)
    assert result == {
        "projects_added": 1,
        "projects_skipped": 0,
        "memory_added": 2,
        "memory_skipped": 0,
    }
    assert len(dest.list_memory()) == 2
    dest.close()


def test_import_merge_skips_existing_ids(tmp_path: Path) -> None:
    src = _seeded(tmp_path, project_count=1, items_per_project=3)
    payload = export_memory.execute(storage=src, memory_store=src)
    src.close()

    dest = SqliteStore(str(tmp_path / "dest.db"))
    dest.init_schema()
    # First pass — everything goes in.
    first = import_memory.execute(storage=dest, memory_store=dest, payload=payload)
    # Second pass — should skip everything (all IDs already exist).
    second = import_memory.execute(storage=dest, memory_store=dest, payload=payload)
    dest.close()

    assert first == {
        "projects_added": 1,
        "projects_skipped": 0,
        "memory_added": 3,
        "memory_skipped": 0,
    }
    assert second == {
        "projects_added": 0,
        "projects_skipped": 1,
        "memory_added": 0,
        "memory_skipped": 3,
    }


def test_import_replace_refuses_non_empty_destination(tmp_path: Path) -> None:
    src = _seeded(tmp_path)
    payload = export_memory.execute(storage=src, memory_store=src)
    src.close()

    dest = SqliteStore(str(tmp_path / "dest.db"))
    dest.init_schema()
    # Seed dest with one memory so 'replace' must refuse.
    dest.add_project(Project(id="dest-proj", name="Dest"))
    dest.add_memory(MemoryItem(content="existing", project_id="dest-proj"))
    with pytest.raises(ValidationError, match="non-empty"):
        import_memory.execute(storage=dest, memory_store=dest, payload=payload, mode="replace")
    dest.close()


def test_import_replace_into_empty_store_succeeds(tmp_path: Path) -> None:
    src = _seeded(tmp_path)
    payload = export_memory.execute(storage=src, memory_store=src)
    src.close()

    dest = SqliteStore(str(tmp_path / "dest.db"))
    dest.init_schema()
    result = import_memory.execute(storage=dest, memory_store=dest, payload=payload, mode="replace")
    dest.close()
    assert result["memory_added"] == 3


def test_import_rejects_unknown_mode(tmp_path: Path) -> None:
    dest = SqliteStore(str(tmp_path / "dest.db"))
    dest.init_schema()
    with pytest.raises(ValidationError, match="mode must be"):
        import_memory.execute(
            storage=dest,
            memory_store=dest,
            payload={"format_version": 1, "projects": [], "memory_items": []},
            mode="weird",
        )
    dest.close()


def test_import_rejects_payload_without_format_version(tmp_path: Path) -> None:
    dest = SqliteStore(str(tmp_path / "dest.db"))
    dest.init_schema()
    with pytest.raises(ValidationError, match="format_version"):
        import_memory.execute(storage=dest, memory_store=dest, payload={"projects": [], "memory_items": []})
    dest.close()


def test_export_then_json_roundtrip(tmp_path: Path) -> None:
    """Verify the export survives a JSON serialization roundtrip."""
    src = _seeded(tmp_path)
    payload = export_memory.execute(storage=src, memory_store=src)
    src.close()

    serialized = json.dumps(payload)
    restored = json.loads(serialized)

    dest = SqliteStore(str(tmp_path / "dest.db"))
    dest.init_schema()
    result = import_memory.execute(storage=dest, memory_store=dest, payload=restored)
    dest.close()

    assert result["memory_added"] == 3


# ── merge-hazard surface (design 0001 §11.4) ────────────────────────────
#
# `merge` is a union by id with no update branch. The semantics are
# deliberate; the silence around them was the defect. These cover the
# two things that make the silence survivable: counts a caller can act
# on, and warnings an operator can read.


_OMIT = object()
"""Sentinel: leave ``exported_at`` out of the envelope entirely.

Distinct from passing ``None``, which sets the key to JSON null. Both
reach the parser as ``None``, but only an explicit sentinel lets a test
say which shape it means.
"""


def _envelope(*, exported_at: object = _OMIT, memory_ids: tuple[str, ...]) -> dict:
    """Hand-built envelope with full control over ``exported_at``.

    Hand-built rather than round-tripped through ``export_memory`` so a
    staleness assertion turns on the stamp under test, not on whether
    two ``utc_now()`` calls happened to land microseconds apart.
    """
    payload: dict = {
        "format_version": 1,
        "projects": [{"id": "proj-0", "name": "Project 0", "metadata": {}, "created_at": "2026-01-01T00:00:00+00:00"}],
        "memory_items": [
            {
                "id": mid,
                "content": f"content for {mid}",
                "tags": [],
                "pinned": False,
                "project_id": "proj-0",
                "source": "test",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": None,
            }
            for mid in memory_ids
        ],
    }
    if exported_at is not _OMIT:
        payload["exported_at"] = exported_at
    return payload


def test_export_stamps_aware_exported_at(tmp_path: Path) -> None:
    """The stamp import's staleness check reads must exist and be aware."""
    store = _seeded(tmp_path)
    payload = export_memory.execute(storage=store, memory_store=store)
    store.close()

    stamped = datetime.fromisoformat(payload["exported_at"])
    assert stamped.tzinfo is not None
    # Not a format-version bump — old builds must still accept this envelope.
    assert payload["format_version"] == 1


def test_import_merge_counts_added_and_skipped_independently(tmp_path: Path) -> None:
    """Added and skipped must be distinct numbers, not one wired to both."""
    dest = SqliteStore(str(tmp_path / "dest.db"))
    dest.init_schema()
    dest.add_project(Project(id="proj-0", name="Project 0"))
    dest.add_memory(MemoryItem(id="mem-a", content="already here", project_id="proj-0"))

    # 1 collision, 3 inserts, 1 project collision, 0 project inserts —
    # every count a different value.
    result = import_memory.execute(
        storage=dest,
        memory_store=dest,
        payload=_envelope(memory_ids=("mem-a", "mem-b", "mem-c", "mem-d")),
    )
    dest.close()

    assert result == {
        "projects_added": 0,
        "projects_skipped": 1,
        "memory_added": 3,
        "memory_skipped": 1,
    }


def test_import_merge_warns_unconditionally(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Even a clean all-inserts merge warns: an insert can resurrect a deletion."""
    dest = SqliteStore(str(tmp_path / "dest.db"))
    dest.init_schema()
    with caplog.at_level(logging.WARNING):
        import_memory.execute(
            storage=dest,
            memory_store=dest,
            payload=_envelope(memory_ids=("mem-a",)),
        )
    dest.close()

    assert any("union by id" in r.getMessage() for r in caplog.records)


def test_import_merge_warning_reports_all_four_counts(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """The warning must carry the real numbers, projects included.

    Four distinct values (0/1/3/1) so a warning interpolating the wrong
    count — or omitting the project half — cannot read as correct.
    """
    dest = SqliteStore(str(tmp_path / "dest.db"))
    dest.init_schema()
    dest.add_project(Project(id="proj-0", name="Project 0"))
    dest.add_memory(MemoryItem(id="mem-a", content="already here", project_id="proj-0"))

    with caplog.at_level(logging.WARNING):
        import_memory.execute(
            storage=dest,
            memory_store=dest,
            payload=_envelope(memory_ids=("mem-a", "mem-b", "mem-c", "mem-d")),
        )
    dest.close()

    message = next(r.getMessage() for r in caplog.records if "union by id" in r.getMessage())
    assert "kept 1 project(s) + 1 memory item(s)" in message
    assert "inserted 0 project(s) + 3 memory item(s)" in message


def test_import_replace_does_not_warn(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """`replace` into a fresh DB is the exact-restore path — no hazard, no noise."""
    dest = SqliteStore(str(tmp_path / "dest.db"))
    dest.init_schema()
    with caplog.at_level(logging.WARNING):
        import_memory.execute(
            storage=dest,
            memory_store=dest,
            payload=_envelope(memory_ids=("mem-a",)),
            mode="replace",
        )
    dest.close()

    assert caplog.records == []


def test_import_warns_when_envelope_predates_newest_local_edit(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    dest = SqliteStore(str(tmp_path / "dest.db"))
    dest.init_schema()
    dest.add_project(Project(id="proj-0", name="Project 0"))
    dest.add_memory(MemoryItem(id="mem-a", content="original", project_id="proj-0"))
    dest.update_memory("mem-a", content="edited locally after the export")

    with caplog.at_level(logging.WARNING):
        import_memory.execute(
            storage=dest,
            memory_store=dest,
            payload=_envelope(exported_at="2020-01-01T00:00:00+00:00", memory_ids=("mem-a",)),
        )
    dest.close()

    assert any("predates" in r.getMessage() for r in caplog.records)


def test_import_no_staleness_warning_when_envelope_is_newer(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    dest = SqliteStore(str(tmp_path / "dest.db"))
    dest.init_schema()
    dest.add_project(Project(id="proj-0", name="Project 0"))
    dest.add_memory(MemoryItem(id="mem-a", content="original", project_id="proj-0"))
    dest.update_memory("mem-a", content="edited before the export")

    with caplog.at_level(logging.WARNING):
        import_memory.execute(
            storage=dest,
            memory_store=dest,
            payload=_envelope(exported_at="2099-01-01T00:00:00+00:00", memory_ids=("mem-a",)),
        )
    dest.close()

    assert not any("predates" in r.getMessage() for r in caplog.records)


def test_import_staleness_ignores_created_at(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """A future-dated `created_at` must not read as a local edit.

    `onboard_git` sets cluster `created_at` from the commit author date,
    and future-dated commits are real here — comparing against
    `max(created_at)` would make every legitimate envelope stale forever.
    """
    dest = SqliteStore(str(tmp_path / "dest.db"))
    dest.init_schema()
    dest.add_project(Project(id="proj-0", name="Project 0"))
    dest.add_memory(
        MemoryItem(
            id="mem-a",
            content="cluster from a future-dated commit",
            project_id="proj-0",
            created_at=datetime(2099, 1, 1, tzinfo=UTC),
            updated_at=None,
        )
    )

    with caplog.at_level(logging.WARNING):
        import_memory.execute(
            storage=dest,
            memory_store=dest,
            payload=_envelope(exported_at="2026-01-02T00:00:00+00:00", memory_ids=("mem-a",)),
        )
    dest.close()

    assert not any("predates" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize(
    "exported_at",
    [
        pytest.param(_OMIT, id="absent"),
        pytest.param(None, id="null"),
        pytest.param(1755980000, id="number"),
        pytest.param("not-a-timestamp", id="malformed"),
        pytest.param("2026-01-01T00:00:00", id="naive"),
    ],
)
def test_import_tolerates_absent_or_unusable_exported_at(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, exported_at: object
) -> None:
    """Every non-usable stamp shape degrades quietly — none may raise.

    ``absent`` is the pre-field envelope; ``null`` and ``number`` are why
    the parser type-checks before parsing (``fromisoformat`` raises
    ``TypeError`` on a non-string, which an ``except ValueError`` would
    not catch, turning a junk stamp into a crashed restore). None of the
    five may produce a staleness verdict — the destination here *does*
    carry a newer edit, so a parser that accepted the value would fire.
    """
    dest = SqliteStore(str(tmp_path / "dest.db"))
    dest.init_schema()
    dest.add_project(Project(id="proj-0", name="Project 0"))
    dest.add_memory(MemoryItem(id="mem-a", content="original", project_id="proj-0"))
    dest.update_memory("mem-a", content="edited locally")

    with caplog.at_level(logging.WARNING):
        result = import_memory.execute(
            storage=dest,
            memory_store=dest,
            payload=_envelope(exported_at=exported_at, memory_ids=("mem-a", "mem-b")),
        )
    dest.close()

    assert result["memory_added"] == 1
    assert result["memory_skipped"] == 1
    assert not any("predates" in r.getMessage() for r in caplog.records)
