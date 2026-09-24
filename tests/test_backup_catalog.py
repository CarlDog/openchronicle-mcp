"""Exposed snapshot catalog and restore preparation contracts."""

from __future__ import annotations

import asyncio
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
        assert not Path(f"{snapshot}-wal").exists()
        assert not Path(f"{snapshot}-shm").exists()
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
        assert not Path(f"{staged}-wal").exists()
        assert not Path(f"{staged}-shm").exists()
        with sqlite3.connect(staged) as candidate:
            assert candidate.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert candidate.execute("SELECT count(*) FROM memory_items").fetchone()[0] == 1
        assert store.count_memory() == 2
        with pytest.raises(BackupCatalogError, match="already staged"):
            catalog.restore_stage(created["artifact_id"])
    finally:
        store.close()


def test_verify_rejects_artifact_with_sidecars(tmp_path: Path) -> None:
    store, catalog = _catalog(tmp_path)
    try:
        created = catalog.create("manual")
        db, _ = catalog._paths(created["artifact_id"])
        Path(f"{db}-wal").write_bytes(b"unexpected")
        with pytest.raises(BackupCatalogError, match="standalone SQLite file"):
            catalog.verify(created["artifact_id"])
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


def test_create_quarantines_relationally_broken_snapshot(tmp_path: Path) -> None:
    store, catalog = _catalog(tmp_path)
    try:
        with sqlite3.connect(catalog.db_path) as conn:
            conn.execute("UPDATE memory_items SET project_id = 'missing-project'")
        with pytest.raises(BackupCatalogError, match="foreign_key_check.*preserved"):
            catalog.create()
        assert catalog.list() == []
        # The copy is evidence about the live store and may be its newest
        # copy: kept outside catalog and retention names, never deleted.
        (kept,) = (catalog.root / "manual").glob("*.db.failed-verify")
        assert list((catalog.root / "manual").glob("*.db")) == []
        assert list((catalog.root / "manual").glob("*.json")) == []
        with sqlite3.connect(f"file:{kept.as_posix()}?mode=ro&immutable=1", uri=True) as copy:
            assert copy.execute("SELECT project_id FROM memory_items").fetchone() == ("missing-project",)
    finally:
        store.close()


def _corrupt_index(db: Path) -> None:
    """Index/table mismatch that quick_check misses and integrity_check reports."""
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE corruption_probe (a INTEGER, b TEXT)")
        conn.execute("CREATE INDEX corruption_probe_a ON corruption_probe(a)")
        conn.executemany("INSERT INTO corruption_probe VALUES (?, ?)", [(i, str(i)) for i in range(50)])
        conn.commit()
        conn.execute("PRAGMA writable_schema=ON")
        conn.execute(
            "UPDATE sqlite_master SET sql='CREATE INDEX corruption_probe_a ON corruption_probe(b)' "
            "WHERE name='corruption_probe_a'"
        )
        conn.execute("PRAGMA writable_schema=OFF")
        conn.commit()
    finally:
        conn.close()


def test_integrity_failure_emergency_backup_survives_catalog_verification(tmp_path: Path) -> None:
    from openchronicle.core.infrastructure.maintenance import jobs

    db = tmp_path / "private" / "openchronicle.db"
    seed, _ = _catalog(tmp_path)
    seed.close()
    _corrupt_index(db)
    with sqlite3.connect(db) as probe:
        assert probe.execute("PRAGMA quick_check").fetchone() == ("ok",)
        assert probe.execute("PRAGMA integrity_check").fetchone() != ("ok",)
    store = SqliteStore(str(db))
    try:
        container = MagicMock()
        container.storage = store
        container.maintenance_degraded = False
        container.backup_dir = tmp_path / "exports" / "backups"
        container.backups = BackupCatalog(store, container.backup_dir, db)
        with pytest.raises(RuntimeError, match="integrity_check failed"):
            asyncio.run(jobs.db_integrity_check(container))
        assert container.maintenance_degraded is True
        (kept,) = (container.backup_dir / "auto").glob("*.db.failed-verify")
        with sqlite3.connect(f"file:{kept.as_posix()}?mode=ro&immutable=1", uri=True) as copy:
            assert copy.execute("SELECT COUNT(*) FROM memory_items").fetchone() == (1,)
            assert copy.execute("PRAGMA integrity_check").fetchone() != ("ok",)
    finally:
        store.close()


def test_published_snapshot_is_standalone_and_survives_read_only_inspection(tmp_path: Path) -> None:
    store, catalog = _catalog(tmp_path)
    try:
        created = catalog.create("manual")
        snapshot, _ = catalog._paths(created["artifact_id"])
        # Rollback-journal header (bytes 18-19 == 1), not the live DB's WAL mode.
        assert snapshot.read_bytes()[18:20] == b"\x01\x01"
        # An operator opening the export read-only must not leave sidecars
        # that make the catalog reject the artifact afterwards.
        with sqlite3.connect(f"file:{snapshot.as_posix()}?mode=ro", uri=True) as inspect:
            assert inspect.execute("SELECT COUNT(*) FROM memory_items").fetchone() == (1,)
        assert catalog.verify(created["artifact_id"])["verified"] is True
        leftovers = sorted(path.name for path in (catalog.root / "manual").iterdir())
        assert leftovers == [snapshot.name, snapshot.with_suffix(".json").name]
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
    incomplete = directory / "openchronicle-incomplete.db"
    incomplete.write_bytes(b"unpublished")
    os.utime(incomplete, (4, 4))
    _retention_prune(directory, keep=1)
    for db in directory.glob("*.db"):
        if db == incomplete:
            continue
        assert db.with_suffix(".json").exists()
    assert len([db for db in directory.glob("*.db") if db != incomplete]) == 1
    assert incomplete.exists()
