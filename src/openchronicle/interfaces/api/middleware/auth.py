"""API key authentication middleware."""

from __future__ import annotations

import hmac
from collections.abc import Sequence

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# OpenAPI docs paths that are always exempt
_DOCS_PATHS = frozenset({"/docs", "/redoc", "/openapi.json"})


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validate API key from Authorization header or X-API-Key header.

    Accepts either:
        Authorization: Bearer <key>
        X-API-Key: <key>

    Unauthenticated requests receive 401. Exempt paths are always public.
    """

    def __init__(
        self,
        app: object,
        api_key: str,
        exempt_paths: Sequence[str] = (),
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._api_key = api_key
        self._exempt: frozenset[str] = _DOCS_PATHS | frozenset(exempt_paths)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self._exempt:
            return await call_next(request)

        key = _extract_key(request)
        if key is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing API key. Provide via Authorization: Bearer <key> or X-API-Key header."},
            )

        if not _key_matches(key, self._api_key):
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid API key."},
            )

        return await call_next(request)


def request_has_key(request: Request, api_key: str) -> bool:
    """Whether `request` carries `api_key`, compared as the middleware does.

    For auth-exempt routes that still show more to a caller holding the key.
    """
    key = _extract_key(request)
    return key is not None and _key_matches(key, api_key)


def _key_matches(key: str, api_key: str) -> bool:
    """Timing-safe comparison of a header key with the configured key.

    `hmac.compare_digest` refuses str with non-ASCII characters (TypeError,
    so a 500 on any route), so compare bytes. Starlette decodes header
    values as latin-1, which makes `encode("latin-1")` recover the bytes the
    client sent; the configured key is compared as its UTF-8 bytes.
    """
    try:
        sent = key.encode("latin-1")
    except UnicodeEncodeError:
        return False
    return hmac.compare_digest(sent, api_key.encode("utf-8"))


def _extract_key(request: Request) -> str | None:
    """Extract API key from request headers."""
    # Try Authorization: Bearer <key>
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()

    # Try X-API-Key header
    return request.headers.get("x-api-key") or None
