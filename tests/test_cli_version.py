"""Tests for oc version command."""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from openchronicle.interfaces.cli.main import main


def test_version_human_output() -> None:
    """Human output contains a real version and the Python version.

    Asserting a version-shaped string rather than just the substring
    "openchronicle": the old check passed for years against the literal
    output "openchronicle unknown", because the distribution name being
    looked up was wrong.
    """
    with patch("builtins.print") as mock_print:
        rc = main(["version"])

    assert rc == 0
    output = " ".join(str(c.args[0]) for c in mock_print.call_args_list)
    assert "openchronicle" in output
    assert "unknown" not in output
    assert re.search(r"\d+\.\d+\.\d+", output)
    assert "Python" in output


def test_version_json_output() -> None:
    """--json returns valid envelope with package + python versions."""
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


def test_version_json_includes_build_revision() -> None:
    """The JSON envelope names the exact build, or honestly says unknown."""
    with patch("builtins.print") as mock_print:
        rc = main(["version", "--json"])

    assert rc == 0
    payload = json.loads(mock_print.call_args_list[0].args[0])
    assert "build_revision" in payload["result"]


def test_build_revision_reads_baked_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The revision comes from the file the Docker build bakes, not an env value."""
    from openchronicle.version import build_revision

    marker = tmp_path / "build-revision"
    marker.write_text("fe92114cdeadbeef\n", encoding="utf-8")
    monkeypatch.setenv("OC_BUILD_REVISION_FILE", str(marker))
    assert build_revision() == "fe92114cdeadbeef"


def test_build_revision_unknown_outside_an_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No baked file (editable install, local dev) reports 'unknown', never raises."""
    from openchronicle.version import build_revision

    monkeypatch.setenv("OC_BUILD_REVISION_FILE", str(tmp_path / "absent"))
    assert build_revision() == "unknown"

    empty = tmp_path / "empty"
    empty.write_text("\n", encoding="utf-8")
    monkeypatch.setenv("OC_BUILD_REVISION_FILE", str(empty))
    assert build_revision() == "unknown"


def test_version_human_output_shows_build_line_only_when_known(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    marker = tmp_path / "build-revision"
    marker.write_text("abc123def456\n", encoding="utf-8")
    monkeypatch.setenv("OC_BUILD_REVISION_FILE", str(marker))
    with patch("builtins.print") as mock_print:
        rc = main(["version"])
    assert rc == 0
    output = " ".join(str(c.args[0]) for c in mock_print.call_args_list)
    assert "build abc123def456" in output
