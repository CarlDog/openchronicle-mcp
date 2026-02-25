"""Tests for RuntimePaths four-layer path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from openchronicle.core.application.config.paths import (
    DEFAULT_ASSETS_DIR,
    DEFAULT_CONFIG_DIR,
    DEFAULT_DB_PATH,
    DEFAULT_DISCORD_PID_PATH,
    DEFAULT_DISCORD_SESSION_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PLUGIN_DIR,
    RuntimePaths,
)

# All env vars that RuntimePaths reads (cleared in every test via autouse fixture)
_ALL_ENV_VARS = [
    "OC_DATA_DIR",
    "OC_DB_PATH",
    "OC_CONFIG_DIR",
    "OC_PLUGIN_DIR",
    "OC_OUTPUT_DIR",
    "OC_ASSETS_DIR",
    "OC_DISCORD_SESSION_STORE_PATH",
    "OC_DISCORD_PID_PATH",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all OC path env vars so each test starts clean."""
    for var in _ALL_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


class TestDefaults:
    """With no env vars and no explicit params, defaults match historical behavior."""

    def test_defaults_match_current_behavior(self) -> None:
        paths = RuntimePaths.resolve()
        assert paths.db_path == Path(DEFAULT_DB_PATH)
        assert paths.config_dir == Path(DEFAULT_CONFIG_DIR)
        assert paths.plugin_dir == Path(DEFAULT_PLUGIN_DIR)
        assert paths.output_dir == Path(DEFAULT_OUTPUT_DIR)
        assert paths.assets_dir == Path(DEFAULT_ASSETS_DIR)
        assert paths.discord_session_path == Path(DEFAULT_DISCORD_SESSION_PATH)
        assert paths.discord_pid_path == Path(DEFAULT_DISCORD_PID_PATH)


class TestExplicitParams:
    """Constructor params always win (layer 1)."""

    def test_explicit_params_override_everything(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_DATA_DIR", "/data-dir")
        monkeypatch.setenv("OC_DB_PATH", "/env-db")

        paths = RuntimePaths.resolve(db_path="/explicit/db.sqlite")
        assert paths.db_path == Path("/explicit/db.sqlite")

    def test_all_explicit_params(self) -> None:
        paths = RuntimePaths.resolve(
            db_path="/a/db",
            config_dir="/a/cfg",
            plugin_dir="/a/plug",
            output_dir="/a/out",
            assets_dir="/a/assets",
            discord_session_path="/a/sessions.json",
            discord_pid_path="/a/bot.pid",
        )
        assert paths.db_path == Path("/a/db")
        assert paths.config_dir == Path("/a/cfg")
        assert paths.plugin_dir == Path("/a/plug")
        assert paths.output_dir == Path("/a/out")
        assert paths.assets_dir == Path("/a/assets")
        assert paths.discord_session_path == Path("/a/sessions.json")
        assert paths.discord_pid_path == Path("/a/bot.pid")

    def test_explicit_path_objects(self) -> None:
        paths = RuntimePaths.resolve(db_path=Path("/x/y.db"))
        assert paths.db_path == Path("/x/y.db")


class TestPerPathEnvVars:
    """Per-path env vars override defaults (layer 2)."""

    def test_per_path_env_overrides_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_DB_PATH", "/env/my.db")
        monkeypatch.setenv("OC_ASSETS_DIR", "/env/assets")
        paths = RuntimePaths.resolve()
        assert paths.db_path == Path("/env/my.db")
        assert paths.assets_dir == Path("/env/assets")
        # Others remain default
        assert paths.config_dir == Path(DEFAULT_CONFIG_DIR)

    def test_discord_pid_path_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_DISCORD_PID_PATH", "/custom/bot.pid")
        paths = RuntimePaths.resolve()
        assert paths.discord_pid_path == Path("/custom/bot.pid")


class TestDataDir:
    """OC_DATA_DIR derives all 7 paths (layer 3)."""

    def test_data_dir_derives_all_paths(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_DATA_DIR", "/mydata")
        paths = RuntimePaths.resolve()
        assert paths.db_path == Path("/mydata/openchronicle.db")
        assert paths.config_dir == Path("/mydata/config")
        assert paths.plugin_dir == Path("/mydata/plugins")
        assert paths.output_dir == Path("/mydata/output")
        assert paths.assets_dir == Path("/mydata/assets")
        assert paths.discord_session_path == Path("/mydata/discord_sessions.json")
        assert paths.discord_pid_path == Path("/mydata/discord_bot.pid")

    def test_per_path_env_beats_data_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_DATA_DIR", "/mydata")
        monkeypatch.setenv("OC_DB_PATH", "/override/specific.db")
        paths = RuntimePaths.resolve()
        assert paths.db_path == Path("/override/specific.db")
        # Other paths still derived from OC_DATA_DIR
        assert paths.config_dir == Path("/mydata/config")


class TestMixedOverrides:
    """Combinations of layers interact correctly."""

    def test_explicit_beats_env_beats_data_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_DATA_DIR", "/data")
        monkeypatch.setenv("OC_DB_PATH", "/env/db")
        paths = RuntimePaths.resolve(db_path="/explicit/db")
        assert paths.db_path == Path("/explicit/db")

    def test_mixed_layers_across_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_DATA_DIR", "/data")
        monkeypatch.setenv("OC_ASSETS_DIR", "/env-assets")
        paths = RuntimePaths.resolve(config_dir="/explicit-config")
        # Layer 1 wins for config_dir
        assert paths.config_dir == Path("/explicit-config")
        # Layer 2 wins for assets_dir
        assert paths.assets_dir == Path("/env-assets")
        # Layer 3 wins for the rest
        assert paths.db_path == Path("/data/openchronicle.db")
        assert paths.discord_pid_path == Path("/data/discord_bot.pid")


class TestTypeGuarantees:
    """All fields are Path instances; dataclass is frozen."""

    def test_all_fields_are_paths(self) -> None:
        paths = RuntimePaths.resolve()
        for field_name in [
            "db_path",
            "config_dir",
            "plugin_dir",
            "output_dir",
            "assets_dir",
            "discord_session_path",
            "discord_pid_path",
        ]:
            assert isinstance(getattr(paths, field_name), Path), f"{field_name} is not a Path"

    def test_frozen_immutable(self) -> None:
        paths = RuntimePaths.resolve()
        with pytest.raises(AttributeError):
            paths.db_path = Path("/nope")  # type: ignore[misc]
