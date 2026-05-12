"""Project CRUD integration tests against a real SqliteStore.

Covers the v3.0.x project surface completion (get / update / delete) using
a temp-dir DB. Mirrors the shape of `test_memory_crud_parity.py` for the
memory side. Exercises:

- `delete_project` cascade: memories AND their embeddings go away.
- `update_project`: rename, metadata replacement, validation, NotFoundError.
- `get_project` round-trips through the live row mapper.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from openchronicle.core.application.use_cases import (
    create_project,
    delete_project,
    update_project,
)
from openchronicle.core.domain.errors.error_codes import PROJECT_NOT_FOUND
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


@pytest.fixture()
def store(tmp_path: Path) -> Iterator[SqliteStore]:
    db_path = tmp_path / "oc.db"
    s = SqliteStore(str(db_path))
    s.init_schema()
    yield s
    s.close()


# ── delete_project ───────────────────────────────────────────────


class TestDeleteProject:
    def test_cascades_memories_and_embeddings(self, store: SqliteStore) -> None:
        project = create_project.execute(store=store, name="cascade-target")
        store.add_memory(
            MemoryItem(
                id="mem-A",
                content="first",
                tags=["t"],
                pinned=False,
                project_id=project.id,
                source="manual",
            )
        )
        store.add_memory(
            MemoryItem(
                id="mem-B",
                content="second",
                tags=[],
                pinned=False,
                project_id=project.id,
                source="manual",
            )
        )
        store.save_embedding("mem-A", embedding=[0.1, 0.2, 0.3], model="m", dimensions=3)

        result = delete_project.execute(
            store=store,
            memory_store=store,
            project_id=project.id,
            confirm=True,
        )

        assert result["status"] == "ok"
        assert result["deleted_memories"] == 2
        assert store.get_project(project.id) is None
        assert store.get_memory("mem-A") is None
        assert store.get_memory("mem-B") is None
        # Embeddings cascade via FK ON DELETE CASCADE
        cur = store._conn.execute("SELECT COUNT(*) FROM memory_embeddings WHERE memory_id = ?", ("mem-A",))
        assert cur.fetchone()[0] == 0

    def test_preview_does_not_touch_db(self, store: SqliteStore) -> None:
        project = create_project.execute(store=store, name="preview")
        store.add_memory(
            MemoryItem(
                id="mem-1",
                content="x",
                tags=[],
                pinned=False,
                project_id=project.id,
                source="manual",
            )
        )

        result = delete_project.execute(
            store=store,
            memory_store=store,
            project_id=project.id,
            confirm=False,
        )

        assert result["status"] == "preview"
        assert result["memory_count"] == 1
        assert result["name"] == "preview"
        assert store.get_project(project.id) is not None
        assert store.get_memory("mem-1") is not None

    def test_missing_project_raises(self, store: SqliteStore) -> None:
        with pytest.raises(NotFoundError) as excinfo:
            delete_project.execute(
                store=store,
                memory_store=store,
                project_id="no-such-id",
                confirm=True,
            )
        assert excinfo.value.code == PROJECT_NOT_FOUND

    def test_other_projects_untouched(self, store: SqliteStore) -> None:
        keep = create_project.execute(store=store, name="keep")
        drop = create_project.execute(store=store, name="drop")
        store.add_memory(
            MemoryItem(
                id="keep-mem",
                content="x",
                tags=[],
                pinned=False,
                project_id=keep.id,
                source="manual",
            )
        )
        store.add_memory(
            MemoryItem(
                id="drop-mem",
                content="y",
                tags=[],
                pinned=False,
                project_id=drop.id,
                source="manual",
            )
        )

        delete_project.execute(
            store=store,
            memory_store=store,
            project_id=drop.id,
            confirm=True,
        )

        assert store.get_project(keep.id) is not None
        assert store.get_memory("keep-mem") is not None


# ── update_project ───────────────────────────────────────────────


class TestUpdateProject:
    def test_rename(self, store: SqliteStore) -> None:
        project = create_project.execute(store=store, name="old-name", metadata={"team": "a"})
        updated = update_project.execute(store=store, project_id=project.id, name="new-name")
        assert updated.name == "new-name"
        assert updated.metadata == {"team": "a"}  # untouched

    def test_metadata_replacement_leaves_name(self, store: SqliteStore) -> None:
        project = create_project.execute(store=store, name="keep", metadata={"team": "a"})
        updated = update_project.execute(store=store, project_id=project.id, metadata={"team": "b", "k": "v"})
        assert updated.name == "keep"
        assert updated.metadata == {"team": "b", "k": "v"}

    def test_clear_metadata(self, store: SqliteStore) -> None:
        project = create_project.execute(store=store, name="x", metadata={"team": "a"})
        updated = update_project.execute(store=store, project_id=project.id, metadata={})
        assert updated.metadata == {}

    def test_missing_raises(self, store: SqliteStore) -> None:
        with pytest.raises(NotFoundError) as excinfo:
            update_project.execute(store=store, project_id="nope", name="x")
        assert excinfo.value.code == PROJECT_NOT_FOUND

    def test_requires_one_field(self, store: SqliteStore) -> None:
        project = create_project.execute(store=store, name="x")
        with pytest.raises(ValueError, match="at least one"):
            update_project.execute(store=store, project_id=project.id)
