"""OpenAI media generation adapter (gpt-image-1).

Uses the /v1/images/generations endpoint.  The adapter receives auth and
endpoint details from the resolved model config — it does NOT hard-code
API keys or URLs.
"""

from __future__ import annotations

import base64
import logging
import time

import httpx

from openchronicle.core.domain.errors.error_codes import PROVIDER_ERROR, TIMEOUT
from openchronicle.core.domain.models.media import MediaRequest, MediaResult
from openchronicle.core.domain.ports.llm_port import LLMProviderError
from openchronicle.core.domain.ports.media_generation_port import MediaGenerationPort

logger = logging.getLogger(__name__)

# Size mapping: (width, height) → OpenAI size string.
# gpt-image-1 supports: auto, 1024x1024, 1536x1024, 1024x1536.
_SIZE_MAP: dict[tuple[int, int], str] = {
    (1024, 1024): "1024x1024",
    (1536, 1024): "1536x1024",
    (1024, 1536): "1024x1536",
}


def _resolve_size(width: int | None, height: int | None) -> str:
    """Map width/height to a size string for OpenAI-compatible endpoints.

    Standard OpenAI sizes are returned from the lookup table.
    Non-standard sizes (e.g. for sd.cpp or other local servers) are
    passed through as ``"WxH"`` so the server can honour them directly.
    """
    if width is None and height is None:
        return "auto"
    w = width or 1024
    h = height or 1024
    key = (w, h)
    if key in _SIZE_MAP:
        return _SIZE_MAP[key]
    return f"{w}x{h}"


class OpenAIMediaAdapter(MediaGenerationPort):
    """Media generation via OpenAI image models (gpt-image-1)."""

    def __init__(
        self,
        *,
        model: str = "gpt-image-1",
        api_key: str,
        endpoint: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._endpoint = (endpoint or "https://api.openai.com/v1/images/generations").rstrip("/")
        self._timeout = timeout_seconds

    def generate(self, request: MediaRequest) -> MediaResult:
        model = request.model or self._model
        size = _resolve_size(request.width, request.height)

        payload: dict = {
            "model": model,
            "prompt": request.prompt,
            "n": 1,
            "size": size,
            "output_format": "png",
        }

        logger.info(
            "OpenAI media generation: model=%s, size=%s, prompt=%.60s...",
            model,
            size,
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
                f"OpenAI media generation failed: HTTP {exc.response.status_code}",
                error_code=PROVIDER_ERROR,
                details={"provider": "openai", "model": model},
            ) from exc
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise LLMProviderError(
                f"OpenAI connection failed: {type(exc).__name__}: {exc}",
                error_code=TIMEOUT,
                details={"provider": "openai", "endpoint": self._endpoint},
            ) from exc
        except Exception as exc:
            raise LLMProviderError(
                f"OpenAI media generation failed: {type(exc).__name__}: {exc}",
                error_code=PROVIDER_ERROR,
                details={"provider": "openai", "model": model},
            ) from exc

        elapsed_ms = (time.perf_counter() - t0) * 1000
        image_data = self._extract_image_data(data, model)

        return MediaResult(
            data=image_data,
            media_type=request.media_type,
            mime_type="image/png",
            width=request.width,
            height=request.height,
            model=model,
            provider="openai",
            seed=request.seed,
            latency_ms=elapsed_ms,
            metadata={"size": size},
        )

    def supported_media_types(self) -> list[str]:
        return ["image"]

    def model_name(self) -> str:
        return self._model

    @staticmethod
    def _extract_image_data(data: dict, model: str) -> bytes:
        """Extract base64-decoded image bytes from OpenAI response.

        Response format: ``{"data": [{"b64_json": "..."}]}``
        """
        items = data.get("data")
        if items and isinstance(items, list) and len(items) > 0:
            b64 = items[0].get("b64_json")
            if b64 and isinstance(b64, str):
                return base64.b64decode(b64)
            # Fallback: URL-based response (not used with b64_json format)
            url = items[0].get("url")
            if url:
                raise LLMProviderError(
                    f"OpenAI returned URL instead of b64_json for model '{model}'. "
                    "Ensure output_format is set correctly.",
                    error_code=PROVIDER_ERROR,
                    details={"provider": "openai", "model": model},
                )

        raise LLMProviderError(
            f"OpenAI response for model '{model}' contained no image data. Response keys: {list(data.keys())}",
            error_code=PROVIDER_ERROR,
            details={"provider": "openai", "model": model, "keys": list(data.keys())},
        )
