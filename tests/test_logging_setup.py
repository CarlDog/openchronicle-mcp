"""Tests for `interfaces/logging_setup.py`.

Covers the fail-soft contract on `OC_LOG_LEVEL`: a stale or typo'd
Portainer value must degrade to a default, never crash the serve path.
"""

from __future__ import annotations

import logging

import pytest

from openchronicle.interfaces.logging_setup import uvicorn_log_level


class TestUvicornLogLevel:
    """`OC_LOG_LEVEL` must never crash the serve path.

    uvicorn indexes LOG_LEVELS directly, so a value outside its table
    raises KeyError from inside uvicorn.Config. Under
    `restart: unless-stopped` that is an indefinite crash-loop from one
    typo'd Portainer value.
    """

    def test_documented_values_pass_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Every value the repo documents (env_vars.md, .env.example, nas.yml).
        for name in ("DEBUG", "INFO", "WARNING", "ERROR"):
            monkeypatch.setenv("OC_LOG_LEVEL", name)
            assert uvicorn_log_level() == name.lower()

    def test_warn_alias_is_accepted_not_fatal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # `logging` defines WARN; uvicorn's table does not. This exact
        # value crashed `oc serve` with KeyError: 'warn'.
        monkeypatch.setenv("OC_LOG_LEVEL", "WARN")
        assert uvicorn_log_level() == "warning"

    def test_fatal_alias_maps_to_critical(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_LOG_LEVEL", "FATAL")
        assert uvicorn_log_level() == "critical"

    def test_garbage_falls_back_and_warns(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("OC_LOG_LEVEL", "WARNNG")
        with caplog.at_level(logging.WARNING):
            assert uvicorn_log_level() == "info"
        assert any("Invalid OC_LOG_LEVEL" in r.getMessage() for r in caplog.records)

    def test_empty_string_falls_back_silently(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # MCP hosts and compose inject "" for a blank field — that is
        # "unset", not "invalid", so it must not warn.
        monkeypatch.setenv("OC_LOG_LEVEL", "   ")
        assert uvicorn_log_level() == "info"

    def test_result_is_always_accepted_by_uvicorn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The contract that matters: whatever we return, uvicorn takes it."""
        from uvicorn.config import LOG_LEVELS

        for raw in ("DEBUG", "WARN", "FATAL", "WARNNG", "", "trace", "nonsense-value"):
            monkeypatch.setenv("OC_LOG_LEVEL", raw)
            assert uvicorn_log_level() in LOG_LEVELS
