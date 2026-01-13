"""Tests for diagnose_runtime use case."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

from openchronicle.core.application.use_cases import diagnose_runtime


def test_diagnose_runtime_does_not_leak_secrets(monkeypatch) -> None:  # type: ignore
    """Verify that OPENAI_API_KEY is never revealed in diagnostics report."""
    real_key = "sk-svcacct-6-bRj9w_hCJoz-SpIWU5IVW3ZtMf9_Mwl90wnONU67_WF11YOJg08EvHq-Kg5adQ9"
    monkeypatch.setenv("OPENAI_API_KEY", real_key)

    report = diagnose_runtime.execute()

    # Verify that the key is never revealed
    assert report.provider_env_summary["OPENAI_API_KEY"] == "set"
    assert real_key not in str(report.provider_env_summary)
    assert real_key not in report.persistence_hint
    assert real_key not in report.db_path
    assert real_key not in report.config_dir
    assert real_key not in report.plugin_dir


def test_diagnose_runtime_missing_api_key(monkeypatch) -> None:  # type: ignore
    """Verify that missing OPENAI_API_KEY is reported correctly."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    report = diagnose_runtime.execute()

    assert report.provider_env_summary["OPENAI_API_KEY"] == "missing"


def test_diagnose_runtime_db_file_stats() -> None:
    """Verify that DB file size and mtime are correctly captured."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        test_content = b"x" * 1024  # 1 KB
        Path(db_path).write_bytes(test_content)

        with mock.patch.dict(os.environ, {"OC_DB_PATH": db_path}):
            report = diagnose_runtime.execute()

            assert report.db_exists is True
            assert report.db_size_bytes == 1024
            assert report.db_modified_utc is not None


def test_diagnose_runtime_missing_db_file() -> None:
    """Verify that missing DB file is reported correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        nonexistent_db = os.path.join(tmpdir, "nonexistent.db")

        with mock.patch.dict(os.environ, {"OC_DB_PATH": nonexistent_db}):
            report = diagnose_runtime.execute()

            assert report.db_exists is False
            assert report.db_size_bytes is None
            assert report.db_modified_utc is None


def test_diagnose_runtime_paths_resolved_from_env() -> None:
    """Verify that paths are resolved from environment variables."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "db")
        config_dir = os.path.join(tmpdir, "cfg")
        plugin_dir = os.path.join(tmpdir, "plugins")

        Path(config_dir).mkdir()
        Path(plugin_dir).mkdir()

        with mock.patch.dict(
            os.environ,
            {"OC_DB_PATH": db_path, "OC_CONFIG_DIR": config_dir, "OC_PLUGIN_DIR": plugin_dir},
        ):
            report = diagnose_runtime.execute()

            assert report.db_path == db_path
            assert report.config_dir == config_dir
            assert report.plugin_dir == plugin_dir
            assert report.config_dir_exists is True
            assert report.plugin_dir_exists is True


def test_diagnose_runtime_container_hint_dockerenv() -> None:
    """Verify container detection via /.dockerenv file."""
    with mock.patch("openchronicle.core.application.use_cases.diagnose_runtime.Path.exists") as mock_exists:
        # Mock /.dockerenv exists
        def exists_side_effect() -> bool:
            return True

        mock_exists.side_effect = exists_side_effect

        report = diagnose_runtime.execute()

        assert report.running_in_container_hint is True


def test_diagnose_runtime_container_hint_db_path() -> None:
    """Verify container detection via /data DB path."""
    with mock.patch.dict(os.environ, {"OC_DB_PATH": "/data/openchronicle.db"}):
        report = diagnose_runtime.execute()

        assert report.running_in_container_hint is True


def test_diagnose_runtime_persistence_hint_container_volume() -> None:
    """Verify persistence hint for container volume configuration."""
    with mock.patch.dict(os.environ, {"OC_DB_PATH": "/data/openchronicle.db"}):
        with mock.patch("pathlib.Path.exists", return_value=False):
            report = diagnose_runtime.execute()

            assert "container volume at /data" in report.persistence_hint
            assert "bind-mount overlay" in report.persistence_hint


def test_diagnose_runtime_persistence_hint_windows_path() -> None:
    """Verify persistence hint for Windows bind-mount paths."""
    with mock.patch.dict(os.environ, {"OC_DB_PATH": "C:\\Docker\\openchronicle\\data\\openchronicle.db"}):
        report = diagnose_runtime.execute()

        assert "Windows bind-mount" in report.persistence_hint


def test_diagnose_runtime_provider_env_summary() -> None:
    """Verify that provider env summary includes safe config values."""
    with mock.patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "sk-secret-key",
            "OLLAMA_HOST": "http://localhost:11434",
            "OC_LLM_PROVIDER": "openai",
            "OC_LLM_MODEL_FAST": "gpt-4o-mini",
            "OC_LLM_RPM_LIMIT": "3000",
        },
    ):
        report = diagnose_runtime.execute()

        # Secrets should not appear, only status
        assert report.provider_env_summary["OPENAI_API_KEY"] == "set"
        assert "sk-secret-key" not in str(report.provider_env_summary)

        # Safe values should be present
        assert report.provider_env_summary.get("OLLAMA_HOST") == "http://localhost:11434"
        assert report.provider_env_summary.get("OC_LLM_PROVIDER") == "openai"
        assert report.provider_env_summary.get("OC_LLM_MODEL_FAST") == "gpt-4o-mini"
        assert report.provider_env_summary.get("OC_LLM_RPM_LIMIT") == "3000"


def test_diagnose_runtime_cli_human_readable(monkeypatch) -> None:  # type: ignore
    """Verify that CLI human-readable output does not leak secrets."""
    import sys
    from io import StringIO

    monkeypatch.setenv("OPENAI_API_KEY", "sk-super-secret-key")
    monkeypatch.setenv("OC_LLM_PROVIDER", "openai")

    # Capture output
    from openchronicle.interfaces.cli.main import main

    captured_output = StringIO()
    monkeypatch.setattr(sys, "stdout", captured_output)

    # Run diagnose command
    exit_code = main(["diagnose"])

    output = captured_output.getvalue()

    # Verify exit code
    assert exit_code == 0

    # Verify secret is never in output
    assert "sk-super-secret-key" not in output

    # Verify that status is reported
    assert "set" in output or "OPENAI_API_KEY" in output


def test_diagnose_runtime_cli_json_output(monkeypatch) -> None:  # type: ignore
    """Verify that CLI JSON output is valid and does not leak secrets."""
    import sys
    from io import StringIO

    monkeypatch.setenv("OPENAI_API_KEY", "sk-super-secret-json-key")
    monkeypatch.setenv("OC_LLM_PROVIDER", "openai")

    from openchronicle.interfaces.cli.main import main

    captured_output = StringIO()
    monkeypatch.setattr(sys, "stdout", captured_output)

    # Run diagnose command with --json
    exit_code = main(["diagnose", "--json"])

    output = captured_output.getvalue()

    # Verify exit code
    assert exit_code == 0

    # Verify JSON is valid
    result = json.loads(output)
    assert isinstance(result, dict)

    # Verify secret is never in JSON output
    assert "sk-super-secret-json-key" not in output

    # Verify that status is reported in JSON
    assert result["provider_env_summary"]["OPENAI_API_KEY"] == "set"
