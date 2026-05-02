"""HTTP API middleware — auth, rate limiting, CORS."""

from __future__ import annotations

import os

from fastapi import FastAPI

from openchronicle.interfaces.api.config import HTTPConfig
from openchronicle.interfaces.api.middleware.auth import APIKeyMiddleware
from openchronicle.interfaces.api.middleware.rate_limit import RateLimitMiddleware

# Paths that are always exempt from authentication.
# Kept in sync with the route prefix in app.py.
# /health is the top-level liveness probe (Synology/Docker/k8s convention);
# /api/v1/health is the full diagnostics endpoint.
_AUTH_EXEMPT_PATHS = ("/health", "/api/v1/health")


def register_middleware(app: FastAPI, config: HTTPConfig) -> None:
    """Register all middleware on the FastAPI app.

    Middleware executes in reverse registration order (last registered = outermost).
    Order: rate_limit (outermost) → CORS → auth → handler.
    """
    # Auth middleware — skipped if no API key configured
    if config.api_key:
        app.add_middleware(
            APIKeyMiddleware,
            api_key=config.api_key,
            exempt_paths=_AUTH_EXEMPT_PATHS,
        )

    # CORS — enabled via OC_API_CORS_ORIGINS env var (comma-separated origins)
    cors_origins = os.environ.get("OC_API_CORS_ORIGINS", "").strip()
    if cors_origins:
        from starlette.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=[o.strip() for o in cors_origins.split(",")],
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization", "X-Request-ID", "X-API-Key"],
        )

    # Rate limiting — simple per-client sliding window
    app.add_middleware(RateLimitMiddleware)
