"""xAI Grok Imagine media generation adapter.

Uses the ``/v1/images/generations`` endpoint — same response format as
OpenAI (``data[].b64_json``), but with ``aspect_ratio`` and
``resolution`` instead of ``size``.
"""

from __future__ import annotations

import logging
import time

import httpx

from openchronicle.core.domain.errors.error_codes import PROVIDER_ERROR, TIMEOUT
from openchronicle.core.domain.models.media import MediaRequest, MediaResult
from openchronicle.core.domain.ports.llm_port import LLMProviderError
from openchronicle.core.domain.ports.media_generation_port import MediaGenerationPort
from openchronicle.core.infrastructure.media.openai_adapter import OpenAIMediaAdapter

logger = logging.getLogger(__name__)

# Aspect ratio mapping: (width, height) → Grok aspect ratio string.
_ASPECT_RATIOS: dict[tuple[int, int], str] = {
    (1024, 1024): "1:1",
    (1536, 1024): "3:2",
    (1024, 1536): "2:3",
    (1280, 720): "16:9",
    (720, 1280): "9:16",
    (1024, 768): "4:3",
    (768, 1024): "3:4",
}


def _resolve_aspect_ratio(width: int | None, height: int | None) -> str:
    """Map width/height to the closest Grok aspect ratio string."""
    if width is None and height is None:
        return "auto"
    w = width or 1024
    h = height or 1024
    key = (w, h)
    if key in _ASPECT_RATIOS:
        return _ASPECT_RATIOS[key]
    ratio = w / h
    best = min(_ASPECT_RATIOS.items(), key=lambda kv: abs(kv[0][0] / kv[0][1] - ratio))
    return best[1]


class XAIMediaAdapter(MediaGenerationPort):
    """Media generation via xAI Grok Imagine API."""

    def __init__(
        self,
        *,
        model: str = "grok-imagine-image",
        api_key: str,
        endpoint: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._endpoint = (endpoint or "https://api.x.ai/v1/images/generations").rstrip("/")
        self._timeout = timeout_seconds

    def generate(self, request: MediaRequest) -> MediaResult:
        model = request.model or self._model
        aspect_ratio = _resolve_aspect_ratio(request.width, request.height)

        payload: dict = {
            "model": model,
            "prompt": request.prompt,
            "n": 1,
            "aspect_ratio": aspect_ratio,
            "response_format": "b64_json",
        }

        logger.info(
            "xAI media generation: model=%s, aspect_ratio=%s, prompt=%.60s...",
            model,
            aspect_ratio,
            request.prompt,
        )
        t0 = time.perf_counter()

        try:
            response = httpx.post(
                self._endpoint,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"xAI media generation failed: HTTP {exc.response.status_code}",
                error_code=PROVIDER_ERROR,
                details={"provider": "xai", "model": model},
            ) from exc
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise LLMProviderError(
                f"xAI connection failed: {type(exc).__name__}: {exc}",
                error_code=TIMEOUT,
                details={"provider": "xai", "endpoint": self._endpoint},
            ) from exc
        except Exception as exc:
            raise LLMProviderError(
                f"xAI media generation failed: {type(exc).__name__}: {exc}",
                error_code=PROVIDER_ERROR,
                details={"provider": "xai", "model": model},
            ) from exc

        elapsed_ms = (time.perf_counter() - t0) * 1000
        # Reuse OpenAI extraction — same {"data": [{"b64_json": "..."}]} format
        image_data = OpenAIMediaAdapter._extract_image_data(data, model)

        return MediaResult(
            data=image_data,
            media_type=request.media_type,
            mime_type="image/png",
            width=request.width,
            height=request.height,
            model=model,
            provider="xai",
            seed=request.seed,
            latency_ms=elapsed_ms,
            metadata={"aspect_ratio": aspect_ratio},
        )

    def supported_media_types(self) -> list[str]:
        return ["image"]

    def model_name(self) -> str:
        return self._model
