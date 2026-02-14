"""Tests for oc db info|vacuum|backup|stats commands."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from openchronicle.core.application.runtime.container import CoreContainer
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
        assert "Total calls:" in output

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
        assert result["total_calls"] == 0
        assert result["total_tokens"] == 0

    def test_stats_with_usage_data(self, container: CoreContainer) -> None:
        """Insert usage rows and verify stats reflect them."""
        conn = container.storage._conn  # noqa: SLF001
        # Insert parent rows for FK constraints
        conn.execute(
            "INSERT INTO projects (id, name, metadata, created_at) VALUES (?, ?, ?, ?)",
            ("p1", "test", "{}", "2026-01-01T00:00:00"),
        )
        conn.execute(
            "INSERT INTO tasks (id, project_id, type, status, payload, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("t1", "p1", "test", "completed", "{}", "2026-01-01T00:00:00", "2026-01-01T00:00:00"),
        )
        conn.execute(
            "INSERT INTO llm_usage (id, task_id, project_id, provider, model, "
            "input_tokens, output_tokens, total_tokens, latency_ms, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("u1", "t1", "p1", "openai", "gpt-4o", 100, 50, 150, 500, "2026-01-01T00:00:00"),
        )
        conn.execute(
            "INSERT INTO llm_usage (id, task_id, project_id, provider, model, "
            "input_tokens, output_tokens, total_tokens, latency_ms, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("u2", "t1", "p1", "ollama", "llama3", 200, 100, 300, 1000, "2026-01-01T00:00:01"),
        )

        with patch("builtins.print") as mock_print:
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["db", "stats", "--json"])

        assert rc == 0
        raw = mock_print.call_args_list[0].args[0]
        payload = json.loads(raw)
        result = payload["result"]
        assert result["total_calls"] == 2
        assert result["total_tokens"] == 450
        assert len(result["breakdown"]) == 2
