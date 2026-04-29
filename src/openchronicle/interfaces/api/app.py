"""FastAPI app factory — creates and configures the HTTP API server."""

from __future__ import annotations

import logging
import traceback
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request

from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.api.config import HTTPConfig

logger = logging.getLogger(__name__)


def create_app(container: CoreContainer, config: HTTPConfig) -> FastAPI:
    """Build a fully-wired FastAPI application with all OC routes registered.

    The container is stored eagerly in ``app.state`` so route handlers
    can access it immediately via dependency injection.
    """

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        logger.info("OpenChronicle HTTP API starting on %s:%d", config.host, config.port)
        yield
        logger.info("OpenChronicle HTTP API shutting down")

    app = FastAPI(
        title="OpenChronicle",
        description=(
            "Durable context engine for LLM interactions — persistent memory, "
            "explainable routing, and auditable decision trails."
        ),
        version="2.0.0",
        lifespan=lifespan,
    )

    # Eagerly set container + config on app state so route handlers can
    # access them immediately (works with both real server and TestClient).
    app.state.container = container
    app.state.http_config = config

    # Register middleware
    from openchronicle.interfaces.api.middleware import register_middleware

    register_middleware(app, config)

    # Register global exception handlers
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

    # Register route modules
    from openchronicle.interfaces.api.routes import (
        asset,
        conversation,
        hooks,
        media,
        memory,
        project,
        system,
        webhook,
    )

    app.include_router(system.router, prefix="/api/v1", tags=["system"])
    app.include_router(project.router, prefix="/api/v1", tags=["project"])
    app.include_router(memory.router, prefix="/api/v1", tags=["memory"])
    app.include_router(conversation.router, prefix="/api/v1", tags=["conversation"])
    app.include_router(asset.router, prefix="/api/v1", tags=["asset"])
    app.include_router(webhook.router, prefix="/api/v1", tags=["webhook"])
    app.include_router(hooks.router, prefix="/api/v1", tags=["hooks"])
    app.include_router(media.router, prefix="/api/v1", tags=["media"])

    return app
