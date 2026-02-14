"""Tests for oc version command."""

from __future__ import annotations

import json
from unittest.mock import patch

from openchronicle.interfaces.cli.main import main


def test_version_human_output() -> None:
    """Human output contains version and Python version."""
    with patch("builtins.print") as mock_print:
        rc = main(["version"])

    assert rc == 0
    output = " ".join(str(c.args[0]) for c in mock_print.call_args_list)
    assert "openchronicle" in output
    assert "Python" in output
    assert "Protocol" in output


def test_version_json_output() -> None:
    """--json returns valid envelope with all three fields."""
    with patch("builtins.print") as mock_print:
        rc = main(["version", "--json"])

    assert rc == 0
    raw = mock_print.call_args_list[0].args[0]
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert payload["command"] == "version"
    result = payload["result"]
    assert "package_version" in result
    assert "python_version" in result
    assert "protocol_version" in result


def test_version_with_mocked_package_version() -> None:
    """Mock importlib.metadata.version to control output."""
    with (
        patch("importlib.metadata.version", return_value="1.2.3"),
        patch("builtins.print") as mock_print,
    ):
        rc = main(["version"])

    assert rc == 0
    output = mock_print.call_args_list[0].args[0]
    assert "1.2.3" in output
