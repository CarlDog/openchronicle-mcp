"""Tests for infrastructure.config.env_helpers — consolidated parse helpers."""

from __future__ import annotations

import pytest

from openchronicle.core.infrastructure.config.env_helpers import (
    env_override,
    parse_bool,
    parse_float,
    parse_int,
    parse_str,
    parse_str_list,
)

# ---------- parse_bool ----------


class TestParseBool:
    def test_none_returns_default_true(self) -> None:
        assert parse_bool(None, default=True) is True

    def test_none_returns_default_false(self) -> None:
        assert parse_bool(None, default=False) is False

    def test_native_true(self) -> None:
        assert parse_bool(True, default=False) is True

    def test_native_false(self) -> None:
        assert parse_bool(False, default=True) is False

    @pytest.mark.parametrize("value", ["1", "true", "True", "TRUE", "yes", "Yes", "on", "ON"])
    def test_truthy_strings(self, value: str) -> None:
        assert parse_bool(value, default=False) is True

    @pytest.mark.parametrize("value", ["0", "false", "False", "FALSE", "no", "off", ""])
    def test_falsy_strings(self, value: str) -> None:
        assert parse_bool(value, default=True) is False

    def test_whitespace_stripped(self) -> None:
        assert parse_bool("  true  ", default=False) is True

    def test_non_string_non_bool_returns_default(self) -> None:
        assert parse_bool(42, default=True) is True


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


# ---------- parse_str_list ----------


class TestParseStrList:
    def test_none_returns_default(self) -> None:
        assert parse_str_list(None, default=["a", "b"]) == ["a", "b"]

    def test_list_passthrough(self) -> None:
        assert parse_str_list(["x", "y"], default=[]) == ["x", "y"]

    def test_list_filters_empties(self) -> None:
        assert parse_str_list(["a", "", "  ", "b"], default=[]) == ["a", "b"]

    def test_csv_string(self) -> None:
        assert parse_str_list("a, b, c", default=[]) == ["a", "b", "c"]

    def test_csv_filters_empties(self) -> None:
        assert parse_str_list("a,,b,,", default=[]) == ["a", "b"]

    def test_non_string_non_list_returns_default(self) -> None:
        assert parse_str_list(42, default=["x"]) == ["x"]

    def test_default_is_copied(self) -> None:
        default = ["orig"]
        result = parse_str_list(None, default=default)
        result.append("added")
        assert default == ["orig"]


# ---------- env_override ----------


class TestEnvOverride:
    def test_env_not_set_returns_file_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OC_TEST_VAR", raising=False)
        assert env_override("OC_TEST_VAR", "from_file") == "from_file"

    def test_env_set_overrides_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_TEST_VAR", "from_env")
        assert env_override("OC_TEST_VAR", "from_file") == "from_env"

    def test_env_empty_string_still_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # An explicitly-set empty env var should still override
        monkeypatch.setenv("OC_TEST_VAR", "")
        assert env_override("OC_TEST_VAR", "from_file") == ""

    def test_file_value_none_and_no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OC_TEST_VAR", raising=False)
        assert env_override("OC_TEST_VAR", None) is None
