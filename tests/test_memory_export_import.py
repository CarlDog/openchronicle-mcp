"""Tests for memory export/import use cases."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from openchronicle.core.application.services import git_onboard
from openchronicle.core.application.use_cases import export_memory, import_memory
from openchronicle.core.domain.exceptions import ValidationError
from openchronicle.core.domain.models.memory_item import MAX_CONTENT_CHARS, MemoryItem
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
        "watermark_dropped": 0,
        "oversized_content": 0,
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
        "watermark_dropped": 0,
        "oversized_content": 0,
    }
    assert second == {
        "projects_added": 0,
        "projects_skipped": 1,
        "memory_added": 0,
        "memory_skipped": 3,
        "watermark_dropped": 0,
        "oversized_content": 0,
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
        "watermark_dropped": 0,
        "oversized_content": 0,
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


# ── git-onboard watermark leak (design 0001 §11.3) ──────────────────────
#
# The watermark is one device's git resume point, written as an ordinary
# memory row. Carried across devices it corrupts incremental onboarding:
# a hash unreachable in the destination clone forces a full re-walk and
# duplicate cluster memories, one *ahead* of the destination silently
# skips commits. Filtered on export (stop producing it) AND on import
# (every envelope written before the export fix still carries one).


def test_save_watermark_writes_the_source_the_filters_read(tmp_path: Path) -> None:
    """The producer and the filters must agree on one literal.

    This is the whole point of sharing `WATERMARK_SOURCE` as a constant:
    renaming it in `git_onboard` must not silently turn both filters into
    no-ops. Asserting against the constant on both sides would pass under
    exactly that rename, so this reads the row back and compares its
    stored `source` to what the export filter uses.
    """
    store = SqliteStore(str(tmp_path / "wm.db"))
    store.init_schema()
    store.add_project(Project(id="proj-0", name="Project 0"))
    git_onboard.save_watermark(store, "proj-0", "abc1234")

    rows = [m for m in store.list_memory(limit=None) if m.content == "abc1234"]
    store.close()

    assert len(rows) == 1
    assert rows[0].source == git_onboard.WATERMARK_SOURCE


def test_export_omits_the_watermark(tmp_path: Path) -> None:
    store = _seeded(tmp_path, project_count=1, items_per_project=2)
    git_onboard.save_watermark(store, "proj-0", "abc1234")
    payload = export_memory.execute(storage=store, memory_store=store)
    store.close()

    assert not any(m["source"] == git_onboard.WATERMARK_SOURCE for m in payload["memory_items"])
    # The real content is untouched — this filters one row, not the export.
    assert len(payload["memory_items"]) == 2


@pytest.mark.parametrize("mode", ["merge", "replace"])
def test_import_drops_a_watermark_carried_by_an_old_envelope(tmp_path: Path, mode: str) -> None:
    """A pre-fix envelope must not re-anchor this device's onboarding.

    Hand-built because `export_memory` will never produce one again —
    and those pre-fix envelopes are exactly what a first cross-device
    restore reads. Both modes: a fresh-DB `replace` restore is the most
    likely path and must not resurrect it either.
    """
    payload = _envelope(memory_ids=("mem-a",))
    payload["memory_items"].append(
        {
            "id": "mem-watermark",
            "content": "deadbee",
            "tags": [git_onboard.WATERMARK_SOURCE],
            "pinned": False,
            "project_id": "proj-0",
            "source": git_onboard.WATERMARK_SOURCE,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": None,
        }
    )

    dest = SqliteStore(str(tmp_path / "dest.db"))
    dest.init_schema()
    result = import_memory.execute(storage=dest, memory_store=dest, payload=payload, mode=mode)
    survivors = dest.list_memory_by_source(git_onboard.WATERMARK_SOURCE, "proj-0")
    dest.close()

    assert survivors == []
    assert result["watermark_dropped"] == 1
    # Counted apart from collisions — folding it into memory_skipped would
    # undo what that count exists to report.
    assert result["memory_skipped"] == 0
    assert result["memory_added"] == 1


def test_watermark_survives_a_local_export_import_round_trip_as_absent(tmp_path: Path) -> None:
    """End-to-end: onboarded state exports and restores without the resume point.

    The property, not the comprehension: a store holding a watermark
    exports clean, and importing that export into a fresh store leaves
    the destination with no watermark to resume from.
    """
    src = _seeded(tmp_path, project_count=1, items_per_project=2)
    git_onboard.save_watermark(src, "proj-0", "abc1234")
    payload = json.loads(json.dumps(export_memory.execute(storage=src, memory_store=src)))
    src.close()

    dest = SqliteStore(str(tmp_path / "dest.db"))
    dest.init_schema()
    result = import_memory.execute(storage=dest, memory_store=dest, payload=payload)
    survivors = dest.list_memory_by_source(git_onboard.WATERMARK_SOURCE, "proj-0")
    dest.close()

    assert survivors == []
    assert result["memory_added"] == 2
    # Nothing to drop on import — the export already omitted it.
    assert result["watermark_dropped"] == 0


# ── content cap (design audit: driver-only enforcement) ─────────────────
#
# The 100k cap lived as four hardcoded literals in two driver files and
# nowhere in between, so the same store rejected a 200KB memory over MCP
# and HTTP while `oc memory add` accepted it. Enforcement moved into the
# use cases; import REPORTS rather than enforces, because it is a restore
# of data the store may already hold.


def test_import_accepts_oversized_content_but_counts_it(tmp_path: Path) -> None:
    """A restore must not fail on data the operator already owns."""
    payload = _envelope(memory_ids=("mem-a",))
    payload["memory_items"][0]["content"] = "x" * (MAX_CONTENT_CHARS + 1)

    dest = SqliteStore(str(tmp_path / "dest.db"))
    dest.init_schema()
    result = import_memory.execute(storage=dest, memory_store=dest, payload=payload)
    stored = dest.list_memory(limit=None)
    dest.close()

    assert result["memory_added"] == 1, "the row must actually be imported"
    assert result["oversized_content"] == 1
    assert len(stored[0].content) == MAX_CONTENT_CHARS + 1, "content must survive intact"


def test_import_warns_about_oversized_content(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    payload = _envelope(memory_ids=("mem-a",))
    payload["memory_items"][0]["content"] = "x" * (MAX_CONTENT_CHARS + 1)

    dest = SqliteStore(str(tmp_path / "dest.db"))
    dest.init_schema()
    with caplog.at_level(logging.WARNING):
        import_memory.execute(storage=dest, memory_store=dest, payload=payload)
    dest.close()

    msg = next((r.getMessage() for r in caplog.records if "exceeds" in r.getMessage()), "")
    assert "mem-a" in msg, "the warning must name the offending id"


def test_import_does_not_warn_when_all_content_is_within_cap(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """No false alarm on an ordinary restore."""
    payload = _envelope(memory_ids=("mem-a",))
    payload["memory_items"][0]["content"] = "x" * MAX_CONTENT_CHARS  # exactly at the cap

    dest = SqliteStore(str(tmp_path / "dest.db"))
    dest.init_schema()
    with caplog.at_level(logging.WARNING):
        result = import_memory.execute(storage=dest, memory_store=dest, payload=payload)
    dest.close()

    assert result["oversized_content"] == 0, "at the cap is not over it"
    assert not any("exceeds" in r.getMessage() for r in caplog.records)


# --- Envelope contract (strict validation before any write) ---------------


def _empty_store(tmp_path: Path) -> SqliteStore:
    store = SqliteStore(str(tmp_path / "dest.db"))
    store.init_schema()
    return store


def _assert_untouched(store: SqliteStore) -> None:
    """A rejected envelope must leave the store byte-for-byte empty."""
    assert store.list_projects() == []
    assert store.list_memory() == []


def test_import_rejects_unsupported_format_version(tmp_path: Path) -> None:
    """format_version: 999 used to import 'successfully' as an empty restore."""
    dest = _empty_store(tmp_path)
    with pytest.raises(ValidationError, match=r"unsupported format_version 999.*version 1"):
        import_memory.execute(
            storage=dest, memory_store=dest, payload={"format_version": 999, "projects": [], "memory_items": []}
        )
    _assert_untouched(dest)
    dest.close()


@pytest.mark.parametrize("bad_version", ["1", True, 1.0, None])
def test_import_rejects_non_integer_format_version(tmp_path: Path, bad_version: object) -> None:
    dest = _empty_store(tmp_path)
    with pytest.raises(ValidationError, match="unsupported format_version"):
        import_memory.execute(
            storage=dest,
            memory_store=dest,
            payload={"format_version": bad_version, "projects": [], "memory_items": []},
        )
    dest.close()


@pytest.mark.parametrize("missing_key", ["projects", "memory_items"])
def test_import_rejects_missing_arrays(tmp_path: Path, missing_key: str) -> None:
    """A truncated envelope must not masquerade as a legitimate empty restore."""
    payload = _envelope(memory_ids=("mem-a",))
    del payload[missing_key]
    dest = _empty_store(tmp_path)
    with pytest.raises(ValidationError, match=f"missing required '{missing_key}'"):
        import_memory.execute(storage=dest, memory_store=dest, payload=payload)
    _assert_untouched(dest)
    dest.close()


@pytest.mark.parametrize("bad_value", [{"a": 1}, "not-a-list", 7])
def test_import_rejects_non_list_arrays(tmp_path: Path, bad_value: object) -> None:
    payload = _envelope(memory_ids=())
    payload["memory_items"] = bad_value
    dest = _empty_store(tmp_path)
    with pytest.raises(ValidationError, match="'memory_items' must be an array"):
        import_memory.execute(storage=dest, memory_store=dest, payload=payload)
    dest.close()


def test_import_rejects_non_object_payload(tmp_path: Path) -> None:
    """json.loads can yield a list; that must be a ValidationError, not a TypeError."""
    dest = _empty_store(tmp_path)
    with pytest.raises(ValidationError, match="payload must be a JSON object"):
        import_memory.execute(storage=dest, memory_store=dest, payload=[1, 2, 3])  # type: ignore[arg-type]
    dest.close()


def test_import_row_missing_id_is_validation_error_not_keyerror(tmp_path: Path) -> None:
    """The old shape read row['id'] before its try block and leaked KeyError."""
    payload = _envelope(memory_ids=("mem-a",))
    del payload["memory_items"][0]["id"]
    dest = _empty_store(tmp_path)
    with pytest.raises(ValidationError, match=r"memory_items\[0\].*'id'"):
        import_memory.execute(storage=dest, memory_store=dest, payload=payload)
    _assert_untouched(dest)
    dest.close()


def test_import_row_error_names_collection_index_and_id(tmp_path: Path) -> None:
    payload = _envelope(memory_ids=("mem-a", "mem-b"))
    payload["memory_items"][1]["created_at"] = "not-a-date"
    dest = _empty_store(tmp_path)
    with pytest.raises(ValidationError, match=r"memory_items\[1\] \(id='mem-b'\).*created_at"):
        import_memory.execute(storage=dest, memory_store=dest, payload=payload)
    _assert_untouched(dest)
    dest.close()


def test_import_rejects_unknown_project_reference_before_any_write(tmp_path: Path) -> None:
    """Used to surface as a raw sqlite3.IntegrityError from the FK constraint."""
    payload = _envelope(memory_ids=("mem-a",))
    payload["memory_items"][0]["project_id"] = "no-such-project"
    dest = _empty_store(tmp_path)
    with pytest.raises(ValidationError, match=r"references project 'no-such-project'"):
        import_memory.execute(storage=dest, memory_store=dest, payload=payload)
    _assert_untouched(dest)
    dest.close()


def test_import_accepts_project_reference_satisfied_by_the_store(tmp_path: Path) -> None:
    """The reference check must union store + envelope, not envelope alone."""
    dest = _empty_store(tmp_path)
    dest.add_project(Project(id="already-here", name="Existing"))
    payload = _envelope(memory_ids=("mem-a",))
    payload["projects"] = []
    payload["memory_items"][0]["project_id"] = "already-here"
    result = import_memory.execute(storage=dest, memory_store=dest, payload=payload)
    assert result["memory_added"] == 1
    dest.close()


def test_import_rejects_duplicate_memory_id_within_envelope(tmp_path: Path) -> None:
    """Used to surface as a raw sqlite3.IntegrityError on the second insert."""
    payload = _envelope(memory_ids=("mem-a", "mem-a"))
    dest = _empty_store(tmp_path)
    with pytest.raises(ValidationError, match=r"memory_items\[1\].*duplicate memory id"):
        import_memory.execute(storage=dest, memory_store=dest, payload=payload)
    _assert_untouched(dest)
    dest.close()


def test_import_rejects_bad_tags_shape(tmp_path: Path) -> None:
    payload = _envelope(memory_ids=("mem-a",))
    payload["memory_items"][0]["tags"] = ["ok", 42]
    dest = _empty_store(tmp_path)
    with pytest.raises(ValidationError, match="'tags' must be an array of strings"):
        import_memory.execute(storage=dest, memory_store=dest, payload=payload)
    dest.close()


def test_import_validates_every_row_before_the_first_write(tmp_path: Path) -> None:
    """A bad LAST row must reject the envelope with zero rows written.

    The transaction already guaranteed rollback; this pins the stronger
    contract that validation completes before mutation begins at all.
    """
    payload = _envelope(memory_ids=("mem-a", "mem-b", "mem-c"))
    del payload["memory_items"][2]["created_at"]
    dest = _empty_store(tmp_path)
    with pytest.raises(ValidationError, match=r"memory_items\[2\]"):
        import_memory.execute(storage=dest, memory_store=dest, payload=payload)
    _assert_untouched(dest)
    dest.close()


# --- Atomic export publication (CLI) --------------------------------------


def _export_args(out: Path) -> object:
    import argparse

    return argparse.Namespace(project_id=None, out=str(out), json=False)


def _cli_container(store: SqliteStore) -> object:
    from types import SimpleNamespace

    # cmd_memory_export touches only container.storage.
    return SimpleNamespace(storage=store)


def test_cli_export_writes_atomically_and_cleans_temp(tmp_path: Path) -> None:
    from openchronicle.interfaces.cli.commands.memory import cmd_memory_export

    store = _seeded(tmp_path)
    out = tmp_path / "backup" / "envelope.json"
    rc = cmd_memory_export(_export_args(out), _cli_container(store))  # type: ignore[arg-type]
    store.close()

    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["format_version"] == 1
    leftovers = [p for p in out.parent.iterdir() if p.name != out.name]
    assert leftovers == [], f"temp files left beside the export: {leftovers}"


def test_cli_export_failure_preserves_previous_backup(tmp_path: Path) -> None:
    """An interrupted export must not truncate the operator's last good envelope.

    The old shape was Path.write_text straight onto the destination —
    truncate-in-place, so a failure left a partial file where the backup
    had been. Publication is now temp + os.replace; a failure at the
    rename leaves the previous file byte-identical and no temp behind.
    """
    from unittest.mock import patch

    from openchronicle.interfaces.cli.commands.memory import cmd_memory_export

    store = _seeded(tmp_path)
    out = tmp_path / "envelope.json"
    previous = '{"format_version": 1, "the previous good backup": true}'
    out.write_text(previous, encoding="utf-8")

    with patch("os.replace", side_effect=OSError("disk full")), pytest.raises(OSError, match="disk full"):
        cmd_memory_export(_export_args(out), _cli_container(store))  # type: ignore[arg-type]
    store.close()

    assert out.read_text(encoding="utf-8") == previous, "previous backup must survive a failed export"
    leftovers = [p for p in out.parent.iterdir() if p.suffix == ".tmp"]
    assert leftovers == [], f"temp files left behind: {leftovers}"
