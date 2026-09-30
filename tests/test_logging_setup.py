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


@pytest.mark.parametrize(("level", "expected"), [("INFO", logging.WARNING), ("DEBUG", logging.NOTSET)])
def test_request_urls_stay_out_of_the_log_unless_debugging(
    monkeypatch: pytest.MonkeyPatch, level: str, expected: int
) -> None:
    """httpx logs each request URL at INFO, userinfo included, so credentials
    in OLLAMA_HOST reached the log on every embed (pre-deploy review)."""
    httpx_logger = logging.getLogger("httpx")
    monkeypatch.setattr(httpx_logger, "level", logging.NOTSET)
    monkeypatch.setenv("OC_LOG_LEVEL", level)
    monkeypatch.delenv("OC_LOG_FILE", raising=False)
    root = logging.getLogger()
    saved = root.handlers[:], root.level
    try:
        configure_root_logger()
        assert httpx_logger.level == expected
    finally:
        root.handlers[:], root.level = saved[0], saved[1]


def test_serve_logs_boot_problems_to_the_log_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Building the container logs boot problems. Before `serve` configured
    logging first, they reached only the bare stderr a Portainer recreate
    discards, not OC_LOG_FILE (ROADMAP QUAL-12)."""
    import logging

    from openchronicle.interfaces.cli import main as cli_main

    log_path = tmp_path / "logs" / "oc.log"
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setenv("OC_LOG_FILE", str(log_path))
    monkeypatch.setenv("OC_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("OC_BACKUP_DIR", "relative/backups")
    monkeypatch.setenv("OC_SEARCH_FTS5_ENABLED", "ture")
    monkeypatch.setitem(cli_main.COMMANDS, "serve", lambda _args, _container: 0)
    root = logging.getLogger()
    old_handlers = root.handlers[:]
    old_level = root.level
    try:
        assert cli_main.main(["serve"]) == 0
        for handler in root.handlers:
            handler.flush()
        text = log_path.read_text(encoding="utf-8")
        assert "OC_BACKUP_DIR relative" in text and "must be an absolute path" in text
        assert "Invalid OC_SEARCH_FTS5_ENABLED='ture'" in text
    finally:
        for handler in root.handlers[:]:
            if handler not in old_handlers:
                handler.close()
                root.removeHandler(handler)
        root.setLevel(old_level)


def _restore_root_logger(old_handlers: list[logging.Handler], old_level: int) -> None:
    root = logging.getLogger()
    for handler in root.handlers[:]:
        if handler not in old_handlers:
            handler.close()
            root.removeHandler(handler)
    root.setLevel(old_level)


def test_serve_writes_each_boot_line_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`serve` now configures logging in main() and again in cmd_serve; the
    second call must not stack a second file handler."""
    import signal

    import uvicorn

    from openchronicle.interfaces.cli import main as cli_main

    log_path = tmp_path / "logs" / "oc.log"
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setenv("OC_LOG_FILE", str(log_path))
    monkeypatch.setenv("OC_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("OC_BACKUP_DIR", "relative/backups")
    monkeypatch.setenv("OC_MAINTENANCE_DISABLED", "1")
    monkeypatch.setattr(uvicorn.Server, "run", lambda self, sockets=None: None)
    old_signals = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    root = logging.getLogger()
    old_handlers, old_level = root.handlers[:], root.level
    try:
        assert cli_main.main(["serve"]) == 0
        for handler in root.handlers:
            handler.flush()
        lines = log_path.read_text(encoding="utf-8").splitlines()
    finally:
        _restore_root_logger(old_handlers, old_level)
        for sig, saved in old_signals.items():
            signal.signal(sig, saved)
    boot = [line for line in lines if "OC_BACKUP_DIR relative" in line]
    assert len(boot) == 1, lines


def test_one_shot_commands_leave_logging_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from openchronicle.interfaces.cli import main as cli_main

    log_path = tmp_path / "logs" / "oc.log"
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setenv("OC_LOG_FILE", str(log_path))
    monkeypatch.setenv("OC_CONFIG_DIR", str(config_dir))
    root = logging.getLogger()
    old_handlers, old_level = root.handlers[:], root.level
    try:
        assert cli_main.main(["list-projects"]) == 0
        assert root.handlers == old_handlers
    finally:
        _restore_root_logger(old_handlers, old_level)
    assert not log_path.exists()


def test_a_failed_boot_reaches_the_log_file_for_serve_and_stderr_otherwise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The crash-loop case: a container that cannot start leaves its reason
    only where OC_LOG_FILE keeps it, and never on stdout."""
    from openchronicle.interfaces.cli import main as cli_main

    log_path = tmp_path / "logs" / "oc.log"
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    db = tmp_path / "oc.db"
    db.write_bytes(b"this is not a database" * 100)
    monkeypatch.setenv("OC_LOG_FILE", str(log_path))
    monkeypatch.setenv("OC_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("OC_DB_PATH", str(db))
    root = logging.getLogger()
    old_handlers, old_level = root.handlers[:], root.level
    try:
        assert cli_main.main(["serve"]) == 1
        for handler in root.handlers:
            handler.flush()
        assert "Cannot start:" in log_path.read_text(encoding="utf-8")
    finally:
        _restore_root_logger(old_handlers, old_level)
    assert capsys.readouterr().out == ""
    assert cli_main.main(["list-projects"]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "not a database" in captured.err
