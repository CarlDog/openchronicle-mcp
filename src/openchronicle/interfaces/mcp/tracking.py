"""MCP tool usage tracking — decorator + dataclass."""

from __future__ import annotations

import functools
import inspect
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

_logger = logging.getLogger(__name__)


@dataclass
class MCPToolCall:
    """Record of a single MCP tool invocation."""

    tool_name: str
    started_at: str
    latency_ms: int
    success: bool
    error_type: str | None = None
    error_message: str | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


def track_tool(fn: Any) -> Any:
    """Decorator that records MCP tool call timing and success/failure.

    Applied *below* ``@mcp.tool()`` so FastMCP sees the original signature.
    Extracts ``container`` from the ``ctx`` kwarg.  If ``ctx`` is absent
    (e.g. the ``health`` tool) or telemetry is disabled, tracking is a no-op.
    Persistence failures are swallowed — tracking must never break a tool call.
    """

    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            ctx = kwargs.get("ctx")
            if ctx is None:
                return await fn(*args, **kwargs)

            start = time.monotonic()
            success = True
            error_type: str | None = None
            error_message: str | None = None
            try:
                return await fn(*args, **kwargs)
            except Exception as exc:
                success = False
                error_type = type(exc).__name__
                error_message = str(exc)[:500]
                raise
            finally:
                _persist(ctx, fn.__name__, start, success, error_type, error_message)

        return async_wrapper

    @functools.wraps(fn)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        ctx = kwargs.get("ctx")
        if ctx is None:
            return fn(*args, **kwargs)

        start = time.monotonic()
        success = True
        error_type: str | None = None
        error_message: str | None = None
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            success = False
            error_type = type(exc).__name__
            error_message = str(exc)[:500]
            raise
        finally:
            _persist(ctx, fn.__name__, start, success, error_type, error_message)

    return sync_wrapper


def _persist(
    ctx: Any,
    tool_name: str,
    start: float,
    success: bool,
    error_type: str | None,
    error_message: str | None,
) -> None:
    """Best-effort persist a tool call record. Never raises."""
    try:
        from openchronicle.core.infrastructure.wiring.container import CoreContainer

        container = cast(CoreContainer, ctx.request_context.lifespan_context["container"])

        ts = container.telemetry_settings
        if not ts.enabled or not ts.mcp_tracking_enabled:
            return

        latency_ms = int((time.monotonic() - start) * 1000)
        now = datetime.now(UTC).isoformat()

        container.storage.insert_mcp_tool_usage(
            id=uuid.uuid4().hex,
            tool_name=tool_name,
            started_at=now,
            latency_ms=latency_ms,
            success=success,
            error_type=error_type,
            error_message=error_message,
            created_at=now,
        )
    except Exception:
        _logger.debug("Failed to persist MCP tool usage for %s", tool_name, exc_info=True)
