"""Tests for infrastructure.config.env_helpers — consolidated parse helpers."""

from __future__ import annotations

import pytest

from openchronicle.core.application.config.env_helpers import (
    env_override,
    parse_float,
    parse_int,
    parse_str,
)

# ---------- parse_int ----------


class TestParseInt:
    def test_none_returns_default(self) -> None:
        assert parse_int(None, default=10) == 10

    def test_native_int(self) -> None:
        assert parse_int(42, default=0) == 42

    def test_native_zero(self) -> None:
        assert parse_int(0, default=99) == 0

    def test_string_int(self) -> None:
        assert parse_int("123", default=0) == 123

    def test_string_negative(self) -> None:
        assert parse_int("-5", default=0) == -5

    def test_string_whitespace(self) -> None:
        assert parse_int("  42  ", default=0) == 42

    def test_invalid_string_returns_default(self) -> None:
        assert parse_int("abc", default=7) == 7

    def test_bool_rejected(self) -> None:
        # bool is subclass of int — should NOT be treated as int
        assert parse_int(True, default=99) == 99

    def test_float_returns_default(self) -> None:
        assert parse_int(3.14, default=0) == 0


# ---------- parse_float ----------


class TestParseFloat:
    def test_none_returns_default(self) -> None:
        assert parse_float(None, default=1.5) == 1.5

    def test_native_float(self) -> None:
        assert parse_float(0.7, default=0.0) == 0.7

    def test_native_int_coerced(self) -> None:
        assert parse_float(3, default=0.0) == 3.0

    def test_string_float(self) -> None:
        assert parse_float("0.45", default=0.0) == 0.45

    def test_string_int(self) -> None:
        assert parse_float("10", default=0.0) == 10.0

    def test_string_whitespace(self) -> None:
        assert parse_float("  0.5  ", default=0.0) == 0.5

    def test_invalid_string_returns_default(self) -> None:
        assert parse_float("nope", default=1.0) == 1.0

    def test_bool_rejected(self) -> None:
        assert parse_float(True, default=9.9) == 9.9


# ---------- parse_str ----------


class TestParseStr:
    def test_none_returns_default(self) -> None:
        assert parse_str(None, default="hello") == "hello"

    def test_empty_returns_default(self) -> None:
        assert parse_str("", default="fallback") == "fallback"

    def test_normal_string(self) -> None:
        assert parse_str("value", default="x") == "value"

    def test_non_string_coerced(self) -> None:
        assert parse_str(42, default="x") == "42"


# ---------- env_override ----------


class TestEnvOverride:
    def test_env_not_set_returns_file_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OC_TEST_VAR", raising=False)
        assert env_override("OC_TEST_VAR", "from_file") == "from_file"

    def test_env_set_overrides_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_TEST_VAR", "from_env")
        assert env_override("OC_TEST_VAR", "from_file") == "from_env"

    def test_env_empty_string_treated_as_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Inverted 2026-08-16 (was: empty string still overrides).

        Compose ``${VAR:-}`` lines and MCP hosts inject "" for every blank
        field, so "" winning silently shadowed core.json values — observed
        live as the NAS compose disabling core.json embedding config.
        Empty now means unset, matching every other config boundary.
        """
        monkeypatch.setenv("OC_TEST_VAR", "")
        assert env_override("OC_TEST_VAR", "from_file") == "from_file"

    def test_env_whitespace_only_treated_as_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_TEST_VAR", "   ")
        assert env_override("OC_TEST_VAR", "from_file") == "from_file"

    def test_file_value_none_and_no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OC_TEST_VAR", raising=False)
        assert env_override("OC_TEST_VAR", None) is None


# ---------- parse_int_env ----------


class TestParseIntEnv:
    """Fail-soft env parsing (2026-08-15 review): a stale Portainer stack
    value must degrade with a warning, never crash-loop the container.
    """

    def test_valid_value(self) -> None:
        from openchronicle.core.application.config.env_helpers import parse_int_env

        assert parse_int_env("1200", default=600, name="X") == 1200

    def test_invalid_value_falls_back(self) -> None:
        from openchronicle.core.application.config.env_helpers import parse_int_env

        assert parse_int_env("abc", default=600, name="X") == 600

    def test_empty_and_none_fall_back(self) -> None:
        from openchronicle.core.application.config.env_helpers import parse_int_env

        assert parse_int_env("", default=600, name="X") == 600
        assert parse_int_env("   ", default=600, name="X") == 600
        assert parse_int_env(None, default=600, name="X") == 600
