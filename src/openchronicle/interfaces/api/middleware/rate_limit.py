"""Per-client rate limiting middleware using a sliding window counter."""

from __future__ import annotations

import os
import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Defaults — configurable via env vars
_DEFAULT_RPM = 600  # requests per minute per client
_DEFAULT_WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple sliding-window rate limiter keyed by client IP.

    Env vars:
        OC_API_RATE_LIMIT_RPM — max requests per minute per client (default: 600)

    Returns 429 with Retry-After header when limit is exceeded.
    """

    def __init__(self, app: object) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        rpm_env = os.environ.get("OC_API_RATE_LIMIT_RPM", "").strip()
        self._rpm = int(rpm_env) if rpm_env else _DEFAULT_RPM
        self._window = _DEFAULT_WINDOW_SECONDS
        self._lock = threading.Lock()
        # client_ip -> list of request timestamps
        self._requests: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self._rpm <= 0:
            # Rate limiting disabled
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        cutoff = now - self._window

        with self._lock:
            timestamps = self._requests.get(client_ip, [])
            # Prune expired entries
            timestamps = [t for t in timestamps if t > cutoff]

            if len(timestamps) >= self._rpm:
                # Oldest request in window determines retry-after
                retry_after = int(timestamps[0] - cutoff) + 1
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded."},
                    headers={"Retry-After": str(max(retry_after, 1))},
                )

            timestamps.append(now)
            self._requests[client_ip] = timestamps
            remaining = max(0, self._rpm - len(timestamps))

            # Evict dead keys to prevent memory leak
            dead_keys = [k for k, v in self._requests.items() if not v]
            for k in dead_keys:
                del self._requests[k]

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self._rpm)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
