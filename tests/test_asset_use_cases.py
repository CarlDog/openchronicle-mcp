"""Tests for upload_asset and link_asset use cases."""

from __future__ import annotations

from pathlib import Path

from openchronicle.core.application.services.asset_storage import AssetFileStorage
from openchronicle.core.application.use_cases import link_asset, upload_asset
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.models.project import Event, Project
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


def _setup(tmp_path: Path) -> tuple[SqliteStore, AssetFileStorage, list[Event]]:
    store = SqliteStore(str(tmp_path / "test.db"))
    store.init_schema()
    project = Project(id="proj-1", name="test-project")
    store.add_project(project)
    file_storage = AssetFileStorage(base_dir=str(tmp_path / "assets"))
    events: list[Event] = []
    return store, file_storage, events


class TestUploadAsset:
    def test_new_upload(self, tmp_path: Path) -> None:
        store, file_storage, events = _setup(tmp_path)
        source = tmp_path / "photo.png"
        source.write_bytes(b"PNG CONTENT")

        asset, is_new = upload_asset.execute(
            store=store,
            file_storage=file_storage,
            emit_event=events.append,
            project_id="proj-1",
            source_path=str(source),
        )

        assert is_new is True
        assert asset.filename == "photo.png"
        assert asset.mime_type == "image/png"
        assert asset.size_bytes == 11
        assert asset.content_hash  # non-empty
        assert store.get_asset(asset.id) is not None

        # Check event
        assert len(events) == 1
        assert events[0].type == "asset.created"
        assert events[0].payload["asset_id"] == asset.id

    def test_dedup_returns_existing(self, tmp_path: Path) -> None:
        store, file_storage, events = _setup(tmp_path)
        source = tmp_path / "photo.png"
        source.write_bytes(b"SAME CONTENT")

        asset1, is_new1 = upload_asset.execute(
            store=store,
            file_storage=file_storage,
            emit_event=events.append,
            project_id="proj-1",
            source_path=str(source),
        )
        events.clear()

        asset2, is_new2 = upload_asset.execute(
            store=store,
            file_storage=file_storage,
            emit_event=events.append,
            project_id="proj-1",
            source_path=str(source),
        )

        assert is_new1 is True
        assert is_new2 is False
        assert asset1.id == asset2.id
        assert len(events) == 0  # no link requested, no events

    def test_dedup_with_link(self, tmp_path: Path) -> None:
        store, file_storage, events = _setup(tmp_path)
        source = tmp_path / "photo.png"
        source.write_bytes(b"SAME CONTENT")

        upload_asset.execute(
            store=store,
            file_storage=file_storage,
            emit_event=events.append,
            project_id="proj-1",
            source_path=str(source),
        )
        events.clear()

        asset, is_new = upload_asset.execute(
            store=store,
            file_storage=file_storage,
            emit_event=events.append,
            project_id="proj-1",
            source_path=str(source),
            link_target_type="conversation",
            link_target_id="convo-1",
            link_role="input",
        )

        assert is_new is False
        assert len(events) == 1
        assert events[0].type == "asset.linked"
        assert events[0].payload["dedup"] is True

    def test_upload_with_immediate_link(self, tmp_path: Path) -> None:
        store, file_storage, events = _setup(tmp_path)
        source = tmp_path / "doc.pdf"
        source.write_bytes(b"PDF DATA")

        asset, is_new = upload_asset.execute(
            store=store,
            file_storage=file_storage,
            emit_event=events.append,
            project_id="proj-1",
            source_path=str(source),
            link_target_type="turn",
            link_target_id="turn-1",
            link_role="reference",
        )

        assert is_new is True
        assert len(events) == 2  # asset.created + asset.linked
        assert events[0].type == "asset.created"
        assert events[1].type == "asset.linked"
        links = store.list_asset_links(asset_id=asset.id)
        assert len(links) == 1
        assert links[0].target_id == "turn-1"

    def test_custom_filename_and_mime_type(self, tmp_path: Path) -> None:
        store, file_storage, events = _setup(tmp_path)
        source = tmp_path / "blob"
        source.write_bytes(b"DATA")

        asset, _ = upload_asset.execute(
            store=store,
            file_storage=file_storage,
            emit_event=events.append,
            project_id="proj-1",
            source_path=str(source),
            filename="custom.dat",
            mime_type="application/x-custom",
        )

        assert asset.filename == "custom.dat"
        assert asset.mime_type == "application/x-custom"


class TestLinkAsset:
    def test_creates_link(self, tmp_path: Path) -> None:
        store, file_storage, events = _setup(tmp_path)
        source = tmp_path / "img.jpg"
        source.write_bytes(b"JPEG")

        asset, _ = upload_asset.execute(
            store=store,
            file_storage=file_storage,
            emit_event=events.append,
            project_id="proj-1",
            source_path=str(source),
        )
        events.clear()

        link = link_asset.execute(
            store=store,
            emit_event=events.append,
            asset_id=asset.id,
            target_type="memory_item",
            target_id="mem-1",
            role="avatar",
        )

        assert link.asset_id == asset.id
        assert link.target_type == "memory_item"
        assert link.role == "avatar"
        assert len(events) == 1
        assert events[0].type == "asset.linked"

    def test_raises_for_missing_asset(self, tmp_path: Path) -> None:
        import pytest

        store, _, events = _setup(tmp_path)

        with pytest.raises(NotFoundError, match="Asset not found"):
            link_asset.execute(
                store=store,
                emit_event=events.append,
                asset_id="nonexistent",
                target_type="project",
                target_id="proj-1",
            )
