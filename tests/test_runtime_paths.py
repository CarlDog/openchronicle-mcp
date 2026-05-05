"""Tests for RuntimePaths four-layer path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from openchronicle.core.application.config.paths import (
    DEFAULT_CONFIG_DIR,
    DEFAULT_DB_PATH,
    DEFAULT_OUTPUT_DIR,
    RuntimePaths,
)

# Env vars that RuntimePaths reads (cleared in every test via autouse fixture).
_ALL_ENV_VARS = [
    "OC_DATA_DIR",
    "OC_DB_PATH",
    "OC_CONFIG_DIR",
    "OC_OUTPUT_DIR",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all OC path env vars so each test starts clean."""
    for var in _ALL_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


class TestDefaults:
    """With no env vars and no explicit params, defaults match historical behavior."""

    def test_defaults(self) -> None:
        paths = RuntimePaths.resolve()
        assert paths.db_path == Path(DEFAULT_DB_PATH)
        assert paths.config_dir == Path(DEFAULT_CONFIG_DIR)
        assert paths.output_dir == Path(DEFAULT_OUTPUT_DIR)


class TestExplicitParams:
    """Constructor params always win (layer 1)."""

    def test_explicit_db_path_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_DATA_DIR", "/data-dir")
        monkeypatch.setenv("OC_DB_PATH", "/env-db")
        paths = RuntimePaths.resolve(db_path="/explicit/db.sqlite")
        assert paths.db_path == Path("/explicit/db.sqlite")

    def test_all_explicit_params(self) -> None:
        paths = RuntimePaths.resolve(
            db_path="/a/db",
            config_dir="/a/cfg",
            output_dir="/a/out",
        )
        assert paths.db_path == Path("/a/db")
        assert paths.config_dir == Path("/a/cfg")
        assert paths.output_dir == Path("/a/out")

    def test_explicit_path_objects(self) -> None:
        paths = RuntimePaths.resolve(db_path=Path("/x/y.db"))
        assert paths.db_path == Path("/x/y.db")

    def test_plugin_dir_kwarg_accepted_but_ignored(self) -> None:
        """v2 callers may still pass plugin_dir; v3 silently drops it."""
        paths = RuntimePaths.resolve(plugin_dir="/legacy/plugins")
        assert not hasattr(paths, "plugin_dir")


class TestPerPathEnvVars:
    """Per-path env vars override defaults (layer 2)."""

    def test_per_path_env_overrides_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_DB_PATH", "/env/my.db")
        monkeypatch.setenv("OC_OUTPUT_DIR", "/env/out")
        paths = RuntimePaths.resolve()
        assert paths.db_path == Path("/env/my.db")
        assert paths.output_dir == Path("/env/out")
        assert paths.config_dir == Path(DEFAULT_CONFIG_DIR)


class TestDataDir:
    """OC_DATA_DIR derives all 3 paths (layer 3)."""

    def test_data_dir_derives_all_paths(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_DATA_DIR", "/mydata")
        paths = RuntimePaths.resolve()
        assert paths.db_path == Path("/mydata/openchronicle.db")
        assert paths.config_dir == Path("/mydata/config")
        assert paths.output_dir == Path("/mydata/output")

    def test_per_path_env_beats_data_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_DATA_DIR", "/mydata")
        monkeypatch.setenv("OC_DB_PATH", "/override/specific.db")
        paths = RuntimePaths.resolve()
        assert paths.db_path == Path("/override/specific.db")
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
        monkeypatch.setenv("OC_OUTPUT_DIR", "/env-out")
        paths = RuntimePaths.resolve(config_dir="/explicit-config")
        assert paths.config_dir == Path("/explicit-config")
        assert paths.output_dir == Path("/env-out")
        assert paths.db_path == Path("/data/openchronicle.db")


class TestTypeGuarantees:
    """All fields are Path instances; dataclass is frozen."""

    def test_all_fields_are_paths(self) -> None:
        paths = RuntimePaths.resolve()
        for field_name in ("db_path", "config_dir", "output_dir"):
            assert isinstance(getattr(paths, field_name), Path), f"{field_name} is not a Path"

    def test_frozen_immutable(self) -> None:
        paths = RuntimePaths.resolve()
        with pytest.raises(AttributeError):
            paths.db_path = Path("/nope")  # type: ignore[misc]
