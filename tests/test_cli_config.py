"""Tests for oc config show command (v3 surface)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from openchronicle.interfaces.cli.main import main


def test_config_show_human_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Human output prints paths and core.json status."""
    monkeypatch.delenv("OC_CONFIG_DIR", raising=False)
    with patch("builtins.print") as mock_print:
        rc = main(["config", "show"])

    assert rc == 0
    output = "\n".join(str(c.args[0]) if c.args else "" for c in mock_print.call_args_list)
    assert "Paths:" in output
    assert "Config file:" in output


def test_config_show_custom_db_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Custom OC_DB_PATH appears in output."""
    monkeypatch.setenv("OC_DB_PATH", "/custom/db.sqlite")

    with patch("builtins.print") as mock_print:
        rc = main(["config", "show"])

    assert rc == 0
    output = "\n".join(str(c.args[0]) if c.args else "" for c in mock_print.call_args_list)
    assert str(Path("/custom/db.sqlite")) in output


def test_config_show_json_envelope() -> None:
    """--json returns a valid envelope with paths and core_config sections."""
    with patch("builtins.print") as mock_print:
        rc = main(["config", "show", "--json"])

    assert rc == 0
    raw = mock_print.call_args_list[0].args[0]
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert payload["command"] == "config.show"
    result = payload["result"]
    assert "paths" in result
    assert "core_config_loaded" in result
    assert "core_config" in result
    assert "masked_secrets" in result


def test_config_show_masks_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """API key env vars are masked."""
    monkeypatch.setenv("OC_OPENAI_API_KEY", "test-key")

    with patch("builtins.print") as mock_print:
        rc = main(["config", "show", "--json"])

    assert rc == 0
    raw = mock_print.call_args_list[0].args[0]
    payload = json.loads(raw)
    masked = payload["result"]["masked_secrets"]
    assert "OC_OPENAI_API_KEY" in masked
    assert masked["OC_OPENAI_API_KEY"] == "****"
    assert "test-key" not in masked["OC_OPENAI_API_KEY"]
