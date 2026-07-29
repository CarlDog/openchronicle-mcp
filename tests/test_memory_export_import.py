"""Tests for memory export/import use cases."""

from __future__ import annotations

import json
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
    assert result == {"projects_added": 1, "memory_added": 2}
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

    assert first == {"projects_added": 1, "memory_added": 3}
    assert second == {"projects_added": 0, "memory_added": 0}


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
