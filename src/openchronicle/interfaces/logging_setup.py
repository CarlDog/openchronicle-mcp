"""Logging setup helper for v3 — `OC_LOG_FORMAT=human|json`.

Default is ``human`` (Python's plain formatter); set ``OC_LOG_FORMAT=json``
for one-line JSON-encoded records consumable by Loki / OpenSearch /
Datadog. Log level is inherited from ``OC_LOG_LEVEL`` (default INFO).
``OC_LOG_FILE`` additionally mirrors the stream to a size-rotating file
— on a mounted volume it survives the container recreate that destroys
stderr history (see ``_attach_file_handler``).

Per Q19 (locked decision): single-user / Synology Container Manager log
viewer favours readability, so default is human. Operators wanting
structured ingestion flip the env var.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

_logger = logging.getLogger(__name__)

_VALID_FORMATS = ("human", "json")


class _JsonFormatter(logging.Formatter):
    """Serialize log records as one JSON object per line.

    Includes timestamp (ISO 8601 UTC), level, logger name, message, and
    any non-builtin record attributes (e.g. ``extra={"request_id": ...}``).
    """

    _STANDARD_KEYS = {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key in self._STANDARD_KEYS or key.startswith("_"):
                continue
            try:
                json.dumps(value)
            except TypeError:
                value = repr(value)
            payload[key] = value
        return json.dumps(payload, sort_keys=True)


def configure_root_logger(*, default_level: str = "INFO") -> None:
    """Configure the root logger from `OC_LOG_FORMAT` and `OC_LOG_LEVEL`.

    Idempotent: if a stream handler is already installed on the root
    logger, this just re-applies the formatter and level. Always logs
    to stderr to keep stdout clean for tools that pipe MCP traffic.
    """
    fmt = os.getenv("OC_LOG_FORMAT", "human").strip().lower() or "human"
    if fmt not in _VALID_FORMATS:
        fmt = "human"

    level_name = os.getenv("OC_LOG_LEVEL", default_level).strip().upper()
    level = getattr(logging, level_name, logging.INFO)

    formatter: logging.Formatter
    if fmt == "json":
        formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    root = logging.getLogger()
    root.setLevel(level)
    if root.handlers:
        for handler in root.handlers:
            handler.setFormatter(formatter)
            handler.setLevel(level)
    else:
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(formatter)
        handler.setLevel(level)
        root.addHandler(handler)

    _attach_file_handler(root, formatter, level)


# Rotation bounds for OC_LOG_FILE: 5 MiB × (1 live + 3 rotated) ≈ 20 MiB
# ceiling on the volume, weeks of history at this deployment's log rate.
_LOG_FILE_MAX_BYTES = 5 * 1024 * 1024
_LOG_FILE_BACKUPS = 3


def _attach_file_handler(root: logging.Logger, formatter: logging.Formatter, level: int) -> None:
    """Mirror the log stream to ``OC_LOG_FILE`` (rotating), when set.

    Container logs die with the container: a Portainer redeploy
    RECREATES it, and the previous process's stderr — the only record of
    what it did — is gone (observed 2026-08-29: the v3.0.0 logs needed
    to diagnose a search-miss report were destroyed by the v3.1.0
    redeploy minutes later). A rotating file on a mounted volume
    survives the recreate. stderr stays the primary stream per the
    stdout/stderr contract; the file is a mirror, not a replacement.

    Fail-soft on an unwritable path: one stale Portainer value must
    degrade to stderr-only, never crash-loop the service. Idempotent by
    path: re-configuration re-applies formatter/level to an existing
    handler instead of stacking duplicates; empty-string means unset,
    per the project's env convention.
    """
    from logging.handlers import RotatingFileHandler

    log_file = os.getenv("OC_LOG_FILE", "").strip()
    if not log_file:
        return

    target = os.path.abspath(log_file)
    for existing in root.handlers:
        if isinstance(existing, RotatingFileHandler) and existing.baseFilename == target:
            existing.setFormatter(formatter)
            existing.setLevel(level)
            return

    try:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        # delay=True: the file opens on first emit, so a read-only
        # volume fails at a log call (caught by logging's own error
        # handling) rather than at startup.
        file_handler = RotatingFileHandler(
            target,
            maxBytes=_LOG_FILE_MAX_BYTES,
            backupCount=_LOG_FILE_BACKUPS,
            encoding="utf-8",
            delay=True,
        )
    except OSError as exc:
        _logger.warning("OC_LOG_FILE=%r is not usable (%s); logging to stderr only", log_file, exc)
        return
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    root.addHandler(file_handler)


# `logging` defines these aliases; uvicorn's LOG_LEVELS table does not.
# An operator typing the form every other log tool accepts should not
# take the service down for it.
_UVICORN_LEVEL_ALIASES = {"warn": "warning", "fatal": "critical"}


def uvicorn_log_level(*, default: str = "info") -> str:
    """Map ``OC_LOG_LEVEL`` onto a level ``uvicorn.Config`` will accept.

    uvicorn indexes its own ``LOG_LEVELS`` dict directly
    (``LOG_LEVELS[self.log_level.lower()]``), so an unrecognized value
    raises ``KeyError`` from inside the constructor. Under
    ``restart: unless-stopped`` that turns one typo'd Portainer value
    into an indefinite crash-loop with no service -- the trap
    ``parse_int_env`` exists to prevent everywhere else, and the one
    ``configure_root_logger`` already avoids for this very variable via
    ``getattr(logging, ..., logging.INFO)``. The serve path was the last
    place the two disagreed.

    Validates against uvicorn's real table rather than a local copy, so
    the accepted set cannot drift from what the library will take. The
    import is function-level: uvicorn is only needed by ``oc serve``, and
    every other CLI command imports this module.
    """
    from uvicorn.config import LOG_LEVELS

    raw = os.getenv("OC_LOG_LEVEL", default).strip().lower()
    if not raw:
        return default
    resolved = _UVICORN_LEVEL_ALIASES.get(raw, raw)
    if resolved not in LOG_LEVELS:
        _logger.warning(
            "Invalid OC_LOG_LEVEL=%r; using %r. Valid: %s",
            os.getenv("OC_LOG_LEVEL"),
            default,
            ", ".join(sorted(LOG_LEVELS)),
        )
        return default
    return resolved
