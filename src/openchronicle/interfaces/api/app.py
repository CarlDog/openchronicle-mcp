"""Unified ASGI app factory — FastAPI host with FastMCP mounted at /mcp.

v3 fold: a single ASGI process serves both the HTTP REST surface
(`/api/v1/*`) and the MCP protocol (`/mcp`). The v2 split (separate
`oc serve` and `oc mcp serve` processes on different ports) is gone.
"""

from __future__ import annotations

import logging
import traceback
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request

from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.api.config import HTTPConfig

logger = logging.getLogger(__name__)


def create_app(
    container: CoreContainer,
    config: HTTPConfig,
    *,
    mount_mcp: bool = True,
) -> FastAPI:
    """Build the unified ASGI app.

    The container is stored on ``app.state`` so route handlers reach it
    via dependency injection. When ``mount_mcp`` is True (default), a
    FastMCP server is wired up and its streamable-HTTP ASGI app is
    mounted at ``/mcp``; the FastAPI lifespan drives the FastMCP
    session manager so its background tasks join the host's startup/
    shutdown cycle.

    ``mount_mcp=False`` is for tests that exercise the HTTP surface in
    isolation without the FastMCP session-manager overhead.
    """

    mcp_server = None
    if mount_mcp:
        from openchronicle.interfaces.mcp.config import MCPConfig
        from openchronicle.interfaces.mcp.server import create_server

        mcp_config = MCPConfig.from_env(file_config=container.file_configs.get("mcp"))
        mcp_server = create_server(container, mcp_config)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("OpenChronicle ASGI starting on %s:%d", config.host, config.port)
        async with AsyncExitStack() as stack:
            if mcp_server is not None:
                # FastMCP's session manager must run inside the host's
                # lifespan so its anyio task group attaches and detaches
                # cleanly with uvicorn shutdown.
                await stack.enter_async_context(mcp_server.session_manager.run())
                logger.info("MCP mounted at /mcp")
            yield
        logger.info("OpenChronicle ASGI shutting down")

    app = FastAPI(
        title="OpenChronicle",
        description=(
            "Memory database for LLM agents — persistent semantic + keyword "
            "memory, project namespacing, git-onboard, served over HTTP REST and MCP."
        ),
        version="3.0.0-dev",
        lifespan=lifespan,
    )

    app.state.container = container
    app.state.http_config = config

    from openchronicle.interfaces.api.middleware import register_middleware

    register_middleware(app, config)

    from openchronicle.core.domain.exceptions import (
        NotFoundError,
    )
    from openchronicle.core.domain.exceptions import (
        ValidationError as DomainValidationError,
    )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc), "code": exc.code},
        )

    @app.exception_handler(DomainValidationError)
    async def validation_error_handler(_request: Request, exc: DomainValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": str(exc), "code": exc.code},
        )

    @app.exception_handler(FileNotFoundError)
    async def file_not_found_handler(_request: Request, exc: FileNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc), "code": "FILE_NOT_FOUND"},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception: %s\n%s", exc, traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "code": "INTERNAL_ERROR"},
        )

    from openchronicle.interfaces.api.routes import (
        memory,
        project,
        system,
    )

    app.include_router(system.router, prefix="/api/v1", tags=["system"])
    app.include_router(project.router, prefix="/api/v1", tags=["project"])
    app.include_router(memory.router, prefix="/api/v1", tags=["memory"])

    if mcp_server is not None:
        # FastMCP exposes a Starlette app for streamable-HTTP transport.
        # Mount it under /mcp; the inner app's `/` becomes /mcp/ on the host.
        app.mount("/mcp", mcp_server.streamable_http_app())

    @app.get("/health", include_in_schema=False)
    def liveness() -> dict[str, str]:
        return {"status": "ok"}

    return app
