"""Tests for infrastructure.config.config_loader — JSON config file loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openchronicle.core.infrastructure.config.config_loader import (
    CORE_CONFIG_NAME,
    ConfigLoadError,
    load_config_files,
    load_json_config,
)


class TestLoadJsonConfig:
    def test_missing_file_returns_empty_dict(self, tmp_path: Path) -> None:
        result = load_json_config(tmp_path / "nonexistent.json")
        assert result == {}

    def test_empty_file_returns_empty_dict(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.json"
        f.write_text("", encoding="utf-8")
        assert load_json_config(f) == {}

    def test_whitespace_only_returns_empty_dict(self, tmp_path: Path) -> None:
        f = tmp_path / "ws.json"
        f.write_text("   \n  \n  ", encoding="utf-8")
        assert load_json_config(f) == {}

    def test_valid_json_object(self, tmp_path: Path) -> None:
        f = tmp_path / "good.json"
        data = {"key": "value", "num": 42}
        f.write_text(json.dumps(data), encoding="utf-8")
        assert load_json_config(f) == data

    def test_invalid_json_raises_config_load_error(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.json"
        f.write_text("{broken", encoding="utf-8")
        with pytest.raises(ConfigLoadError) as exc_info:
            load_json_config(f)
        assert str(f) in str(exc_info.value)

    def test_json_array_raises_config_load_error(self, tmp_path: Path) -> None:
        f = tmp_path / "array.json"
        f.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ConfigLoadError) as exc_info:
            load_json_config(f)
        assert "Expected JSON object" in str(exc_info.value)

    def test_nested_json_object(self, tmp_path: Path) -> None:
        f = tmp_path / "nested.json"
        data = {"outer": {"inner": [1, 2, 3]}}
        f.write_text(json.dumps(data), encoding="utf-8")
        assert load_json_config(f) == data


class TestLoadConfigFiles:
    def test_empty_dir_returns_empty_dict(self, tmp_path: Path) -> None:
        result = load_config_files(tmp_path)
        assert result == {}

    def test_core_json_loaded(self, tmp_path: Path) -> None:
        data = {"provider": "openai", "privacy": {"mode": "redact"}}
        (tmp_path / CORE_CONFIG_NAME).write_text(json.dumps(data), encoding="utf-8")

        result = load_config_files(tmp_path)
        assert result["provider"] == "openai"
        assert result["privacy"]["mode"] == "redact"

    def test_invalid_core_json_raises(self, tmp_path: Path) -> None:
        (tmp_path / CORE_CONFIG_NAME).write_text("{broken", encoding="utf-8")
        with pytest.raises(ConfigLoadError):
            load_config_files(tmp_path)

    def test_full_core_config(self, tmp_path: Path) -> None:
        """Round-trip the v3 core.json shape (embedding + api + maintenance)."""
        data = {
            "embedding": {"provider": "openai", "model": "text-embedding-3-small"},
            "api": {"host": "0.0.0.0", "port": 8000, "api_key": "secret"},
            "maintenance": {
                "jobs": [{"name": "db_vacuum", "interval_seconds": 604800, "enabled": True}],
            },
        }
        (tmp_path / CORE_CONFIG_NAME).write_text(json.dumps(data), encoding="utf-8")

        result = load_config_files(tmp_path)
        assert result["embedding"]["provider"] == "openai"
        assert result["api"]["port"] == 8000
        assert result["maintenance"]["jobs"][0]["name"] == "db_vacuum"
