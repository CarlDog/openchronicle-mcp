"""Tests for infrastructure.config.env_helpers — consolidated parse helpers."""

from __future__ import annotations

import logging

import pytest

from openchronicle.core.application.config.env_helpers import (
    env_override,
    parse_bool_env,
    parse_float,
    parse_int,
    parse_str,
    resolve_port,
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

    @pytest.mark.parametrize("raw", ["true", "1.0", "8080.5"])
    def test_words_and_decimals_are_not_integers(self, raw: str, caplog: pytest.LogCaptureFixture) -> None:
        """An env var is text: "true" is not 1 and "1.0" is not 1 (QUAL-23)."""
        from openchronicle.core.application.config.env_helpers import parse_int_env

        with caplog.at_level(logging.WARNING):
            assert parse_int_env(raw, default=600, name="X") == 600
        assert f"Invalid X={raw!r}" in caplog.text


# ---------- resolve_port ----------


class TestResolvePort:
    """Env var, else core.json "port", else the default; each source must be
    1-65535, and a bad one falls back with a warning naming that source and
    the port actually used (QUAL-23)."""

    def test_precedence_env_then_file_then_default(self) -> None:
        assert resolve_port(env_name="P", env_raw="9002", file_value=9001, default=8000) == 9002
        assert resolve_port(env_name="P", env_raw=None, file_value=9001, default=8000) == 9001
        assert resolve_port(env_name="P", env_raw=None, file_value=None, default=8000) == 8000

    def test_range_edges_are_valid(self) -> None:
        assert resolve_port(env_name="P", env_raw=None, file_value=1, default=8000) == 1
        assert resolve_port(env_name="P", env_raw=None, file_value=65535, default=8000) == 65535
        assert resolve_port(env_name="P", env_raw="1", file_value=None, default=8000) == 1
        assert resolve_port(env_name="P", env_raw="65535", file_value=None, default=8000) == 65535

    @pytest.mark.parametrize("raw", ["0", "65536", "99999", "-1"])
    def test_out_of_range_env_falls_back_to_the_file_port(self, raw: str, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING):
            assert resolve_port(env_name="P", env_raw=raw, file_value=7777, default=8000) == 7777
        assert f"P={raw} is outside 1-65535; using 7777" in caplog.text

    @pytest.mark.parametrize("value", [0, 65536, -1, True, False, "9001", 8080.0])
    def test_invalid_file_port_falls_back_to_the_default_naming_core_json(
        self, value: object, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            assert resolve_port(env_name="P", env_raw=None, file_value=value, default=8000) == 8000
        assert f"Invalid core.json port {value!r} (must be 1-65535); using 8000" in caplog.text
        # The old warning blamed the env var for a bad file value.
        assert "P=" not in caplog.text


# ---------- parse_bool_env ----------


@pytest.mark.parametrize(
    ("raw", "default", "expected"),
    [
        (None, True, True),
        ("", False, False),
        ("   ", True, True),
        ("1", False, True),
        ("TRUE", False, True),
        (" yes ", False, True),
        ("on", False, True),
        ("0", True, False),
        ("False", True, False),
        ("no", True, False),
        ("OFF", True, False),
    ],
)
def test_parse_bool_env_recognized(raw: str | None, default: bool, expected: bool) -> None:
    assert parse_bool_env(raw, default=default, name="OC_X") is expected


@pytest.mark.parametrize("default", [True, False])
def test_parse_bool_env_unrecognized_logs_and_keeps_the_default(
    default: bool, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        assert parse_bool_env("maybe", default=default, name="OC_X") is default
    assert "Invalid OC_X='maybe'" in caplog.text


def test_parse_bool_env_logs_at_the_callers_level(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        parse_bool_env("maybe", default=False, name="OC_X", level=logging.ERROR)
    assert [r.levelno for r in caplog.records] == [logging.ERROR]
