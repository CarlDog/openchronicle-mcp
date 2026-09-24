"""Exposed snapshot catalog and restore preparation contracts."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from openchronicle.core.domain.exceptions import ConfigError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.infrastructure.persistence.backup_catalog import BackupCatalog, BackupCatalogError
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.api.app import create_app
from openchronicle.interfaces.api.config import HTTPConfig
from openchronicle.interfaces.mcp.config import MCPConfig
from openchronicle.interfaces.mcp.server import create_server


def _catalog(tmp_path: Path) -> tuple[SqliteStore, BackupCatalog]:
    db = tmp_path / "private" / "openchronicle.db"
    store = SqliteStore(str(db))
    store.init_schema()
    project = Project(name="backup-test")
    store.add_project(project)
    store.add_memory(MemoryItem(content="must survive", project_id=project.id))
    return store, BackupCatalog(store, tmp_path / "exports" / "backups", db)


def test_create_list_verify_and_stage_without_replacing_live_db(tmp_path: Path) -> None:
    store, catalog = _catalog(tmp_path)
    try:
        created = catalog.create("manual")
        assert created["artifact_id"].startswith("manual:")
        assert created["memory_count"] == 1
        assert catalog.list() == [created]
        assert catalog.verify(created["artifact_id"])["verified"] is True
        snapshot, _ = catalog._paths(created["artifact_id"])
        disposable = tmp_path / "drill" / "openchronicle.db"
        disposable.parent.mkdir()
        shutil.copy2(snapshot, disposable)
        restored = SqliteStore(str(disposable))
        try:
            assert restored.integrity_check() == "ok"
            assert restored.count_memory() == 1
            assert [project.id for project in restored.list_projects()] == [
                project.id for project in store.list_projects()
            ]
        finally:
            restored.close()
        store.add_memory(MemoryItem(content="newer", project_id=store.list_projects()[0].id))
        plan = catalog.restore_plan(created["artifact_id"])
        assert plan["artifact"]["memory_count"] == 1
        assert plan["current"]["memory_count"] == 2
        assert plan["artifact"]["project_identity_sha256"] == plan["current"]["project_identity_sha256"]
        assert plan["restored"] is False

        stage = catalog.restore_stage(created["artifact_id"])
        assert stage["restored"] is False
        staged = next((tmp_path / "private" / ".restore-stage").glob("*.db"))
        with sqlite3.connect(staged) as candidate:
            assert candidate.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert candidate.execute("SELECT count(*) FROM memory_items").fetchone()[0] == 1
        assert store.count_memory() == 2
        with pytest.raises(BackupCatalogError, match="already staged"):
            catalog.restore_stage(created["artifact_id"])
    finally:
        store.close()


def test_verify_rejects_tampering_and_list_ignores_incomplete_pair(tmp_path: Path) -> None:
    store, catalog = _catalog(tmp_path)
    try:
        created = catalog.create("auto")
        db, manifest = catalog._paths(created["artifact_id"])
        db.write_bytes(db.read_bytes() + b"changed")
        with pytest.raises(BackupCatalogError, match="differs from its manifest"):
            catalog.verify(created["artifact_id"])
        manifest.unlink()
        assert catalog.list() == []
    finally:
        store.close()


def test_create_rejects_relationally_broken_snapshot(tmp_path: Path) -> None:
    store, catalog = _catalog(tmp_path)
    try:
        with sqlite3.connect(catalog.db_path) as conn:
            conn.execute("UPDATE memory_items SET project_id = 'missing-project'")
        with pytest.raises(BackupCatalogError, match="foreign_key_check"):
            catalog.create()
        assert catalog.list() == []
    finally:
        store.close()


@pytest.mark.parametrize("artifact_id", ["../secret", "manual:../../secret", "auto:bad", "/tmp/x.db"])
def test_artifact_ids_cannot_select_paths(tmp_path: Path, artifact_id: str) -> None:
    store, catalog = _catalog(tmp_path)
    try:
        with pytest.raises(BackupCatalogError, match="Invalid backup artifact ID"):
            catalog.verify(artifact_id)
    finally:
        store.close()


def test_manifest_failure_never_offers_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, catalog = _catalog(tmp_path)
    try:

        def fail_manifest(_path: Path, _payload: dict[str, object]) -> None:
            raise OSError("manifest write failed")

        monkeypatch.setattr(catalog, "_publish_manifest", fail_manifest)
        with pytest.raises(OSError, match="manifest write failed"):
            catalog.create()
        assert catalog.list() == []
        assert list((catalog.root / "manual").glob("*.db")) == []
    finally:
        store.close()


def test_overlapping_create_is_rejected(tmp_path: Path) -> None:
    store, catalog = _catalog(tmp_path)
    try:
        assert catalog._operation_lock.acquire(blocking=False)
        with pytest.raises(BackupCatalogError, match="already running"):
            catalog.create()
    finally:
        catalog._operation_lock.release()
        store.close()


def test_configured_directory_must_exist_and_be_absolute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    for bad in ("relative/path", str(tmp_path / "missing")):
        monkeypatch.setenv("OC_BACKUP_DIR", bad)
        with pytest.raises(ConfigError, match="OC_BACKUP_DIR must be an existing absolute directory"):
            CoreContainer(db_path=str(tmp_path / "db.db"), config_dir=str(config_dir))


def test_backup_mcp_tools_require_http_auth_and_explicit_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    container = MagicMock()
    container.file_configs = {}
    container.backup_dir_explicit = True
    container.paths.db_path = tmp_path / "db.db"
    monkeypatch.setenv("OC_BACKUP_MCP_ENABLED", "true")
    with pytest.raises(ConfigError, match="require OC_API_KEY"):
        create_app(container, HTTPConfig(), mount_mcp=True)
    with pytest.raises(ConfigError, match="require OC_API_KEY"):
        create_app(container, HTTPConfig(api_key=""), mount_mcp=True)
    container.backup_dir_explicit = False
    with pytest.raises(ConfigError, match="explicit OC_BACKUP_DIR"):
        create_app(container, HTTPConfig(api_key="test-key"), mount_mcp=True)

    container.backup_dir_explicit = True
    app = create_app(container, HTTPConfig(api_key="test-key"), mount_mcp=True)
    assert app is not None
    assert "db_backup_create" not in create_server(container, MCPConfig())._tool_manager._tools
    enabled = create_server(container, MCPConfig(), backup_tools_enabled=True)
    assert {"db_backup_create", "db_backup_list", "db_backup_verify", "db_restore_plan", "db_restore_stage"} <= set(
        enabled._tool_manager._tools
    )
    monkeypatch.setenv("OC_MAINTENANCE_DISABLED", "1")
    with TestClient(app) as client:
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "backup-auth-test", "version": "1"},
            },
        }
        headers = {"Accept": "application/json, text/event-stream"}
        assert client.post("/mcp/", json=request, headers=headers).status_code == 401
        headers["Authorization"] = "Bearer test-key"
        assert client.post("/mcp/", json=request, headers=headers).status_code != 401


def test_auto_retention_prunes_manifest_with_snapshot(tmp_path: Path) -> None:
    from openchronicle.core.infrastructure.maintenance.jobs import _retention_prune

    directory = tmp_path / "auto"
    directory.mkdir()
    for index in range(3):
        db = directory / f"openchronicle-{index}.db"
        db.write_bytes(b"snapshot")
        db.with_suffix(".json").write_text(json.dumps({"index": index}), encoding="utf-8")
        db.touch()
        os.utime(db, (index, index))
    _retention_prune(directory, keep=1)
    for db in directory.glob("*.db"):
        assert db.with_suffix(".json").exists()
    assert len(list(directory.glob("*.db"))) == 1
