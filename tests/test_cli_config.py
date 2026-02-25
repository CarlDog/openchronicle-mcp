"""Tests for oc config show command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from openchronicle.interfaces.cli.main import main


def test_config_show_default_values() -> None:
    """Default config shows expected defaults (stub provider, budget off, privacy off)."""
    with patch("builtins.print") as mock_print:
        rc = main(["config", "show"])

    assert rc == 0
    output = "\n".join(str(c.args[0]) if c.args else "" for c in mock_print.call_args_list)
    assert "stub" in output
    assert "Paths:" in output
    assert "Provider:" in output
    assert "Budget:" in output
    assert "Privacy:" in output


def test_config_show_custom_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Custom env vars reflected in output."""
    monkeypatch.setenv("OC_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OC_DB_PATH", "/custom/db.sqlite")

    with patch("builtins.print") as mock_print:
        rc = main(["config", "show"])

    assert rc == 0
    output = "\n".join(str(c.args[0]) if c.args else "" for c in mock_print.call_args_list)
    assert "openai" in output
    assert str(Path("/custom/db.sqlite")) in output


def test_config_show_json_output() -> None:
    """--json returns valid envelope with all sections."""
    with patch("builtins.print") as mock_print:
        rc = main(["config", "show", "--json"])

    assert rc == 0
    raw = mock_print.call_args_list[0].args[0]
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert payload["command"] == "config.show"
    result = payload["result"]
    assert "paths" in result
    assert "provider" in result
    assert "pools" in result
    assert "budget" in result
    assert "privacy" in result
    assert "telemetry" in result
    assert "router_assist" in result


def test_config_show_masks_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """API keys are masked in output."""
    monkeypatch.setenv("OC_OPENAI_API_KEY", "test-key")

    with patch("builtins.print") as mock_print:
        rc = main(["config", "show", "--json"])

    assert rc == 0
    raw = mock_print.call_args_list[0].args[0]
    payload = json.loads(raw)
    masked = payload["result"]["masked_secrets"]
    assert "OC_OPENAI_API_KEY" in masked
    # Should be masked, not the full key
    assert masked["OC_OPENAI_API_KEY"] == "****"
    assert "test-key" not in masked["OC_OPENAI_API_KEY"]
