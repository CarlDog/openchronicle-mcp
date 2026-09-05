"""Pure ASGI request observation middleware."""

from __future__ import annotations

import logging
import time
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from openchronicle.core.domain.ports.metrics_port import MetricsRecorder

logger = logging.getLogger(__name__)


class MetricsMiddleware:
    """Measure each HTTP exchange once, including early rejection paths."""

    def __init__(self, app: ASGIApp, *, recorder: MetricsRecorder) -> None:
        self.app = app
        self.recorder = recorder

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.monotonic()
        status_code = 500
        path = str(scope.get("path", ""))
        method = str(scope.get("method", ""))
        self._safe_call(lambda: self.recorder.inflight_inc("rest"))

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                raw_status = message.get("status")
                if isinstance(raw_status, int):
                    status_code = raw_status
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # This finally runs after the last response body, and also covers
            # send failures and cancellation. The recorder itself normalizes
            # the path/method and excludes health/docs/metrics routes.
            self._safe_call(lambda: self.recorder.inflight_dec("rest"))
            self._safe_call(
                lambda: self.recorder.observe_http(
                    path=path,
                    method=method,
                    status_code=status_code,
                    duration_seconds=time.monotonic() - started,
                )
            )

    @staticmethod
    def _safe_call(callback: Any) -> None:
        try:
            callback()
        except Exception:  # metrics must never replace an HTTP result
            logger.warning("metrics recorder failed in HTTP middleware", exc_info=False)
