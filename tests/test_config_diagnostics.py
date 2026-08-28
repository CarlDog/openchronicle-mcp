"""`oc config show` must survive the config being broken.

It is the command an operator runs precisely when core.json is wrong, so
it is the one command that must never answer with a traceback.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from openchronicle.core.infrastructure.config.config_loader import ConfigLoadError, load_config_files
from openchronicle.interfaces.cli.main import main


class TestConfigLoaderWrapsReadFailures:
    def test_non_utf8_file_raises_configloaderror_naming_the_path(self, tmp_path: Path) -> None:
        """The read is inside the same try as the parse; only the parse was caught."""
        (tmp_path / "core.json").write_bytes(b'{"api": "' + bytes([0xFF, 0xFE]) + b' bad"}')
        with pytest.raises(ConfigLoadError) as exc:
            load_config_files(tmp_path)
        assert "core.json" in str(exc.value), "the filename is what ConfigLoadError exists to attach"

    def test_valid_file_still_loads(self, tmp_path: Path) -> None:
        (tmp_path / "core.json").write_text('{"api": {"port": 9001}}', encoding="utf-8")
        assert load_config_files(tmp_path)["api"]["port"] == 9001

    def test_empty_file_is_an_empty_config_not_an_error(self, tmp_path: Path) -> None:
        (tmp_path / "core.json").write_text("", encoding="utf-8")
        assert load_config_files(tmp_path) == {}


class TestConfigShowSurvivesBrokenConfig:
    def test_malformed_json_exits_cleanly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Pre-container commands skipped _build_container's error handling."""
        (tmp_path / "core.json").write_text("{ not json", encoding="utf-8")
        monkeypatch.setenv("OC_CONFIG_DIR", str(tmp_path))
        monkeypatch.setattr(sys, "argv", ["oc", "config", "show"])

        rc = main()
        out = capsys.readouterr().out

        assert rc == 1
        assert "Traceback" not in out
        assert "core.json" in out, "the operator needs to know which file"

    def test_non_utf8_exits_cleanly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / "core.json").write_bytes(b'{"api": "' + bytes([0xFF, 0xFE]) + b' bad"}')
        monkeypatch.setenv("OC_CONFIG_DIR", str(tmp_path))
        monkeypatch.setattr(sys, "argv", ["oc", "config", "show"])

        rc = main()
        assert rc == 1
        assert "Traceback" not in capsys.readouterr().out

    def test_existing_but_empty_core_json_reports_loaded_not_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Loaded-ness was inferred from the parsed dict being truthy, so a
        file the operator actually wrote reported as "not found" — sending
        them to look for a missing file instead of an empty one."""
        (tmp_path / "core.json").write_text("", encoding="utf-8")
        monkeypatch.setenv("OC_CONFIG_DIR", str(tmp_path))
        monkeypatch.setattr(sys, "argv", ["oc", "config", "show"])

        assert main() == 0
        out = capsys.readouterr().out
        assert "not found" not in out
        assert "loaded" in out.lower()

    def test_genuinely_absent_file_still_reports_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The other half — existence must still be reported honestly."""
        monkeypatch.setenv("OC_CONFIG_DIR", str(tmp_path))
        monkeypatch.setattr(sys, "argv", ["oc", "config", "show"])

        assert main() == 0
        assert "not found" in capsys.readouterr().out
