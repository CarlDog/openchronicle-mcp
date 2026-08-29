"""Tests for `interfaces/logging_setup.py`.

Covers the fail-soft contract on `OC_LOG_LEVEL`: a stale or typo'd
Portainer value must degrade to a default, never crash the serve path.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from openchronicle.interfaces.logging_setup import configure_root_logger, uvicorn_log_level


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


# ── OC_LOG_FILE: logs that survive a container recreate ───────────────


def test_log_file_mirrors_records_with_rotation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A redeploy RECREATES the container and destroys its stderr history
    (observed 2026-08-29, mid-diagnosis). OC_LOG_FILE mirrors the stream
    to a rotating file on a volume; stderr stays primary."""
    import logging
    from logging.handlers import RotatingFileHandler

    log_path = tmp_path / "logs" / "oc.log"
    monkeypatch.setenv("OC_LOG_FILE", str(log_path))
    root = logging.getLogger()
    old_handlers = root.handlers[:]
    old_level = root.level
    try:
        configure_root_logger()
        file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) == 1
        logging.getLogger("oc.test").info("a line that must survive the recreate")
        file_handlers[0].flush()
        assert "survive the recreate" in log_path.read_text(encoding="utf-8")

        # Idempotent: re-configuring must not stack a second file handler.
        configure_root_logger()
        assert len([h for h in root.handlers if isinstance(h, RotatingFileHandler)]) == 1
    finally:
        # Restore the root logger EXACTLY — a leaked handler or level
        # change poisons unrelated caplog-based tests down the run.
        for handler in root.handlers[:]:
            if handler not in old_handlers:
                handler.close()
                root.removeHandler(handler)
        root.setLevel(old_level)


def test_log_file_unset_adds_no_file_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    import logging
    from logging.handlers import RotatingFileHandler

    monkeypatch.delenv("OC_LOG_FILE", raising=False)
    root = logging.getLogger()
    old_handlers = root.handlers[:]
    old_level = root.level
    try:
        before = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
        configure_root_logger()
        after = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
        assert before == after
    finally:
        for handler in root.handlers[:]:
            if handler not in old_handlers:
                handler.close()
                root.removeHandler(handler)
        root.setLevel(old_level)


def test_log_file_unusable_path_degrades_to_stderr_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """One stale Portainer value must never crash-loop the service."""
    import logging
    from logging.handlers import RotatingFileHandler

    blocker = tmp_path / "not-a-dir"
    blocker.write_text("file where a directory is needed", encoding="utf-8")
    monkeypatch.setenv("OC_LOG_FILE", str(blocker / "oc.log"))
    root = logging.getLogger()
    old_handlers = root.handlers[:]
    old_level = root.level
    try:
        with caplog.at_level(logging.WARNING):
            configure_root_logger()
        assert not [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
    finally:
        for handler in root.handlers[:]:
            if handler not in old_handlers:
                handler.close()
                root.removeHandler(handler)
        root.setLevel(old_level)
