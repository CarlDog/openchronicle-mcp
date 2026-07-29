"""Logging setup helper for v3 — `OC_LOG_FORMAT=human|json`.

Default is ``human`` (Python's plain formatter); set ``OC_LOG_FORMAT=json``
for one-line JSON-encoded records consumable by Loki / OpenSearch /
Datadog. Log level is inherited from ``OC_LOG_LEVEL`` (default INFO).

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
