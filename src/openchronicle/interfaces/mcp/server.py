"""MCP server factory — creates and configures a FastMCP instance."""

from __future__ import annotations

import asyncio
import difflib
import functools
import inspect
import logging
import time
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any, cast

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.fastmcp.tools import Tool
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import AnyFunction, ContentBlock, Icon, ToolAnnotations

from openchronicle.core.application.observability.null_recorder import NullMetricsRecorder
from openchronicle.core.domain.errors.error_codes import INVALID_ARGUMENT
from openchronicle.core.domain.ports.metrics_port import MetricsRecorder
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.mcp.config import MCPConfig

logger = logging.getLogger(__name__)


def _mcp_outcome(result: object) -> str:
    if not isinstance(result, dict):
        return "ok"
    status = result.get("status")
    if status == "started":
        return "started"
    if status == "partial":
        return "partial"
    if status in {"already_running", "rejected"}:
        return "rejected"
    if status in {"error", "failed"}:
        return "error"
    return "ok"


class MetricsFastMCP(FastMCP):
    """FastMCP subclass that wraps only registered handlers, and refuses
    arguments a tool does not declare (see ``call_tool``).

    FastMCP 1.29 has no public middleware hook. Wrapping at ``add_tool``
    keeps argument validation and protocol traffic out of the execution
    metric while ``functools.wraps`` preserves the original schema, name,
    and description used by the SDK's Tool model.
    """

    def __init__(self, *args: Any, metrics: MetricsRecorder, **kwargs: Any) -> None:
        self._metrics = metrics
        super().__init__(*args, **kwargs)

    def add_tool(
        self,
        fn: AnyFunction,
        name: str | None = None,
        title: str | None = None,
        description: str | None = None,
        annotations: ToolAnnotations | None = None,
        icons: list[Icon] | None = None,
        meta: dict[str, Any] | None = None,
        structured_output: bool | None = None,
    ) -> None:
        tool_name = name if name is not None else str(getattr(fn, "__name__", "__unknown__"))
        wrapped = self._wrap_handler(fn, tool_name)
        super().add_tool(
            wrapped,
            name=name,
            title=title,
            description=description,
            annotations=annotations,
            icons=icons,
            meta=meta,
            structured_output=structured_output,
        )

    def _wrap_handler(self, fn: AnyFunction, tool_name: str) -> AnyFunction:
        if not self._metrics.enabled:
            return fn

        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_handler(*args: Any, **kwargs: Any) -> Any:
                started = time.monotonic()
                outcome = "error"
                self._safe_metric(lambda: self._metrics.inflight_inc("mcp"))
                try:
                    result = await fn(*args, **kwargs)
                    outcome = _mcp_outcome(result)
                    return result
                except asyncio.CancelledError:
                    outcome = "cancelled"
                    raise
                except Exception:
                    outcome = "error"
                    raise
                finally:
                    self._safe_metric(
                        lambda: self._metrics.observe_mcp(
                            tool=tool_name,
                            outcome=outcome,
                            duration_seconds=time.monotonic() - started,
                        )
                    )
                    self._safe_metric(lambda: self._metrics.inflight_dec("mcp"))

            return cast(AnyFunction, async_handler)

        @functools.wraps(fn)
        def sync_handler(*args: Any, **kwargs: Any) -> Any:
            started = time.monotonic()
            outcome = "error"
            self._safe_metric(lambda: self._metrics.inflight_inc("mcp"))
            try:
                result = fn(*args, **kwargs)
                outcome = _mcp_outcome(result)
                return result
            except Exception:
                outcome = "error"
                raise
            finally:
                self._safe_metric(
                    lambda: self._metrics.observe_mcp(
                        tool=tool_name,
                        outcome=outcome,
                        duration_seconds=time.monotonic() - started,
                    )
                )
                self._safe_metric(lambda: self._metrics.inflight_dec("mcp"))

        return cast(AnyFunction, sync_handler)

    @staticmethod
    def _safe_metric(callback: Any) -> None:
        try:
            callback()
        except Exception:  # metrics must never replace an MCP result
            logger.warning("metrics recorder failed in MCP handler", exc_info=False)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Sequence[ContentBlock] | dict[str, Any]:
        """Refuse arguments a tool does not declare, then dispatch.

        FastMCP's generated argument model ignores extra keys, so a caller
        who sends ``limit`` to ``memory_search`` (whose count is ``top_k``)
        silently got the default of 8 (QUAL-11). The check runs before
        dispatch, so a refused call never reaches the handler or its
        execution metric. Classified MINOR under a narrow STABILITY.md
        exception (operator, 2026-10-03).
        """
        tool = self._tool_manager.get_tool(name)
        if tool is not None:
            _reject_unknown_arguments(tool, arguments)
        return await super().call_tool(name, arguments)


#: Parameter names that mean the same thing on sibling tools. A caller who
#: uses one where the tool takes the other is pointed at the right name.
_SYNONYMS: dict[str, tuple[str, ...]] = {
    "limit": ("top_k",),
    "top_k": ("limit",),
}


def _reject_unknown_arguments(tool: Tool, arguments: dict[str, Any]) -> None:
    """Raise INVALID_ARGUMENT naming each undeclared key and the valid ones.

    The text follows FastMCP's own "Error executing tool {name}: " prefix,
    so a refused argument reads like any other argument failure. The code
    is spelled out in the message because MCP drops an exception's
    structured ``code`` (the GATE-04 gap).
    """
    fields = tool.fn_metadata.arg_model.model_fields
    accepted = [info.alias or field_name for field_name, info in fields.items()]
    known = set(accepted) | set(fields)
    unknown = sorted(key for key in arguments if key not in known)
    if not unknown:
        return
    named: list[str] = []
    for key in unknown:
        candidates = [s for s in _SYNONYMS.get(key, ()) if s in known]
        candidates += difflib.get_close_matches(key, accepted, n=1)
        named.append(f"'{key}' (did you mean '{candidates[0]}'?)" if candidates else f"'{key}'")
    message = (
        f"Error executing tool {tool.name}: {INVALID_ARGUMENT}: unknown argument"
        f"{'s' if len(unknown) > 1 else ''} {', '.join(named)}"
    )
    message += f". Valid arguments: {', '.join(accepted) if accepted else '(none)'}."
    raise ToolError(message)


def create_server(container: CoreContainer, config: MCPConfig, *, backup_tools_enabled: bool = False) -> FastMCP:
    """Build a fully-wired FastMCP server with all OC tools registered.

    The container is injected into tool handlers via the lifespan context.
    Tools access it as ``ctx.request_context.lifespan_context["container"]``.
    """

    @asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        # DEBUG: in stateless streamable-HTTP this runs once per REQUEST, and
        # at INFO it wrote two lines to OC_LOG_FILE for every MCP call. The
        # once-per-process startup lines are in the ASGI lifespan and the
        # stdio entrypoint.
        logger.debug("OpenChronicle MCP server starting")
        yield {"container": container}
        logger.debug("OpenChronicle MCP server shutting down")

    metrics_candidate = getattr(container, "metrics", None)
    metrics: MetricsRecorder
    if isinstance(getattr(metrics_candidate, "enabled", None), bool):
        metrics = cast(MetricsRecorder, metrics_candidate)
    else:
        metrics = NullMetricsRecorder()

    mcp = MetricsFastMCP(
        config.server_name,
        metrics=metrics,
        instructions=(
            "OpenChronicle is a memory database for LLM agents. Use memory_save "
            "to persist decisions, milestones, and context that should outlive "
            "the current session; memory_search for hybrid semantic + keyword "
            "retrieval scoped to a project; memory_pin for standing rules; "
            "onboard_git to seed memory from a repo's commit history."
        ),
        lifespan=lifespan,
        host=config.host,
        port=config.port,
        # FastMCP's streamable-HTTP transport defaults to handling `/mcp`
        # internally. When the FastAPI host mounts that ASGI app at /mcp,
        # the result is path-doubling: requests must hit /mcp/mcp instead
        # of the documented /mcp. Setting this to "/" makes the inner app
        # handle its own root, so the host's mount path is the full URL.
        # Discovered post-cutover 2026-05-06 — see triage doc.
        streamable_http_path="/",
        # Defense against DNS rebinding: FastMCP rejects any Host header
        # not on this allowlist with a 421. Defaults are localhost-only;
        # operators binding to a LAN-reachable interface configure the
        # allowlist via OC_MCP_ALLOWED_HOSTS. See MCPConfig docstring.
        transport_security=TransportSecuritySettings(
            allowed_hosts=list(config.allowed_hosts),
        ),
        # Stateless streamable-HTTP: OC tools keep nothing per session
        # (the container comes from the lifespan), while the SDK's
        # stateful mode keeps a live task + transport per session that is
        # only released when the client sends DELETE — which killed
        # sessions, sleeping laptops, and dropped networks never do. On a
        # container that runs for weeks that leak is unbounded.
        stateless_http=True,
    )

    # Register tool modules
    from openchronicle.interfaces.mcp.tools import (
        context,
        memory,
        onboard,
        project,
        system,
    )

    system.register(mcp)
    project.register(mcp)
    memory.register(mcp)
    context.register(mcp)
    onboard.register(mcp)
    if backup_tools_enabled:
        from openchronicle.interfaces.mcp.tools import backup

        backup.register(mcp)

    return mcp
