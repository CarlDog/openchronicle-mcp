"""Tests for oc db info|vacuum|backup|stats commands."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.cli.main import main


@pytest.fixture()
def _stub_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OC_LLM_PROVIDER", "stub")


@pytest.fixture()
def container(tmp_path: Path, _stub_env: None) -> Iterator[CoreContainer]:
    db_path = tmp_path / "test.db"
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("OC_DB_PATH", str(db_path))
    c = CoreContainer()
    yield c
    monkeypatch.undo()


class TestDbInfo:
    def test_info_shows_size_and_row_counts(self, container: CoreContainer, tmp_path: Path) -> None:
        with patch("builtins.print") as mock_print:
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["db", "info"])

        assert rc == 0
        output = "\n".join(str(c.args[0]) if c.args else "" for c in mock_print.call_args_list)
        assert "Size:" in output
        assert "projects" in output
        assert "Integrity: ok" in output

    def test_info_json_output(self, container: CoreContainer) -> None:
        with patch("builtins.print") as mock_print:
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["db", "info", "--json"])

        assert rc == 0
        raw = mock_print.call_args_list[0].args[0]
        payload = json.loads(raw)
        assert payload["ok"] is True
        assert payload["command"] == "db.info"
        result = payload["result"]
        assert "db_size_bytes" in result
        assert "row_counts" in result
        assert "pragmas" in result
        assert "integrity" in result


class TestDbVacuum:
    def test_vacuum_runs_without_error(self, container: CoreContainer) -> None:
        with patch("builtins.print") as mock_print:
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["db", "vacuum"])

        assert rc == 0
        output = "\n".join(str(c.args[0]) for c in mock_print.call_args_list)
        assert "Before:" in output
        assert "After:" in output


class TestDbBackup:
    def test_backup_creates_readable_copy(self, container: CoreContainer, tmp_path: Path) -> None:
        dest = tmp_path / "backup.db"
        with patch(
            "openchronicle.interfaces.cli.main._build_container",
            return_value=container,
        ):
            rc = main(["db", "backup", str(dest)])

        assert rc == 0
        assert dest.exists()
        assert dest.stat().st_size > 0

    def test_backup_errors_if_exists_without_force(self, container: CoreContainer, tmp_path: Path) -> None:
        dest = tmp_path / "backup.db"
        dest.write_text("existing")

        with patch("builtins.print"):
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["db", "backup", str(dest)])

        assert rc == 1

    def test_backup_overwrites_with_force(self, container: CoreContainer, tmp_path: Path) -> None:
        dest = tmp_path / "backup.db"
        dest.write_text("existing")

        with patch(
            "openchronicle.interfaces.cli.main._build_container",
            return_value=container,
        ):
            rc = main(["db", "backup", str(dest), "--force"])

        assert rc == 0
        assert dest.stat().st_size > len("existing")


class TestDbStats:
    def test_stats_empty_db_returns_zeros(self, container: CoreContainer) -> None:
        with patch("builtins.print") as mock_print:
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["db", "stats"])

        assert rc == 0
        output = "\n".join(str(c.args[0]) for c in mock_print.call_args_list)
        assert "Memory items:" in output
        assert "Embeddings:" in output

    def test_stats_json_output(self, container: CoreContainer) -> None:
        with patch("builtins.print") as mock_print:
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["db", "stats", "--json"])

        assert rc == 0
        raw = mock_print.call_args_list[0].args[0]
        payload = json.loads(raw)
        assert payload["ok"] is True
        assert payload["command"] == "db.stats"
        result = payload["result"]
        assert result["projects"] == 0
        assert result["memory_items"] == 0
        assert result["pinned"] == 0
        assert result["embeddings"] == 0
