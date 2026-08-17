"""Host-header allowlist middleware — DNS-rebinding defense for the REST surface.

A containerized HTTP service cannot be secured by its bind address: to be
reachable at all it binds 0.0.0.0, and a malicious web page can then reach
it via DNS rebinding (the page resolves its own hostname to this host's IP,
making the request same-origin in the browser's eyes, so CORS never
applies). The defense is validating the Host header against an allowlist —
the same control FastMCP applies to /mcp via TransportSecuritySettings.
This middleware extends it to everything else (/api/v1/*, /health).

Entry format matches OC_MCP_ALLOWED_HOSTS: exact ``host:port`` / ``host``,
or ``host:*`` for any port. One deliberate divergence from the MCP SDK
matcher: a ``:*`` entry here also matches a bare ``host`` with no port,
because browsers omit default ports (``:80``/``:443``) from Host.

Loopback hosts — and Starlette's TestClient identity ``testserver``, which
is not publicly resolvable — are always allowed: a rebinding attack cannot
present a loopback Host, and the Docker HEALTHCHECK probes /health as
localhost from inside the container regardless of operator config.

Requests under /mcp pass through untouched — FastMCP's transport security
owns that surface (and answers with its own 421 semantics).
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from openchronicle.core.domain.errors.error_codes import INVALID_HOST

_logger = logging.getLogger(__name__)

_ALWAYS_ALLOWED: tuple[str, ...] = (
    "127.0.0.1",
    "127.0.0.1:*",
    "localhost",
    "localhost:*",
    "[::1]",
    "[::1]:*",
    "testserver",
)

_SKIP_PREFIX = "/mcp"


def host_allowed(host: str | None, allowed: tuple[str, ...]) -> bool:
    """True when the Host header value matches an allowlist entry."""
    if not host:
        return False
    for entry in allowed:
        if host == entry:
            return True
        if entry.endswith(":*"):
            base = entry[:-2]
            if host == base or host.startswith(base + ":"):
                return True
    return False


class HostAllowlistMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Host header is not on the allowlist with 421."""

    def __init__(self, app: object, allowed_hosts: tuple[str, ...] = ()) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._allowed = _ALWAYS_ALLOWED + tuple(allowed_hosts)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path == _SKIP_PREFIX or path.startswith(_SKIP_PREFIX + "/"):
            return await call_next(request)

        host = request.headers.get("host")
        if not host_allowed(host, self._allowed):
            _logger.warning("Rejected request with invalid Host header: %r", host)
            return JSONResponse(
                status_code=421,
                content={"detail": "Invalid Host header.", "code": INVALID_HOST},
            )
        return await call_next(request)
