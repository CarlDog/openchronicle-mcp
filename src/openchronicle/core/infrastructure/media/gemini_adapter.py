"""Google Gemini media generation adapter.

Supports two API surfaces:

1. **Imagen models** (``imagen-4.0-*``) — ``:predict`` endpoint with
   ``instances``/``parameters`` request format.  Auth via ``x-goog-api-key``
   header.  Response: ``predictions[].bytesBase64Encoded``.

2. **Gemini native image models** (``gemini-*-image*``) —
   ``:generateContent`` endpoint with ``responseModalities: ["TEXT", "IMAGE"]``.
   Response: ``candidates[].content.parts[].inlineData``.

The adapter auto-detects the surface from the model name.
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

# Aspect ratio mapping: (width, height) → string.
_ASPECT_RATIOS: dict[tuple[int, int], str] = {
    (1024, 1024): "1:1",
    (1536, 1024): "3:2",
    (1024, 1536): "2:3",
    (1280, 720): "16:9",
    (720, 1280): "9:16",
    (1024, 768): "4:3",
    (768, 1024): "3:4",
}


def _resolve_aspect_ratio(width: int | None, height: int | None) -> str | None:
    """Map width/height to the closest supported aspect ratio."""
    if width is None and height is None:
        return None
    w = width or 1024
    h = height or 1024
    key = (w, h)
    if key in _ASPECT_RATIOS:
        return _ASPECT_RATIOS[key]
    ratio = w / h
    best = min(_ASPECT_RATIOS.items(), key=lambda kv: abs(kv[0][0] / kv[0][1] - ratio))
    return best[1]


def _is_imagen_model(model: str) -> bool:
    """True if the model uses the Imagen :predict API surface."""
    return model.startswith("imagen-")


class GeminiMediaAdapter(MediaGenerationPort):
    """Media generation via Google Gemini API (Imagen or native image models)."""

    def __init__(
        self,
        *,
        model: str = "gemini-2.0-flash-exp-image-generation",
        api_key: str,
        endpoint: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._base_endpoint = (endpoint or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        self._timeout = timeout_seconds

    def generate(self, request: MediaRequest) -> MediaResult:
        model = request.model or self._model

        if _is_imagen_model(model):
            return self._generate_imagen(model, request)
        return self._generate_native(model, request)

    def supported_media_types(self) -> list[str]:
        return ["image"]

    def model_name(self) -> str:
        return self._model

    # ── Imagen :predict surface ───────────────────────────────────

    def _generate_imagen(self, model: str, request: MediaRequest) -> MediaResult:
        url = f"{self._base_endpoint}/models/{model}:predict"

        parameters: dict = {"sampleCount": 1}
        aspect_ratio = _resolve_aspect_ratio(request.width, request.height)
        if aspect_ratio:
            parameters["aspectRatio"] = aspect_ratio

        payload: dict = {
            "instances": [{"prompt": request.prompt}],
            "parameters": parameters,
        }

        logger.info("Gemini Imagen generation: model=%s, prompt=%.60s...", model, request.prompt)
        data = self._post(url, payload, model)

        image_data, mime_type = self._extract_imagen_data(data, model)
        return MediaResult(
            data=image_data,
            media_type=request.media_type,
            mime_type=mime_type,
            width=request.width,
            height=request.height,
            model=model,
            provider="gemini",
            seed=request.seed,
            latency_ms=data["_elapsed_ms"],
            metadata={"aspect_ratio": aspect_ratio, "surface": "predict"} if aspect_ratio else {"surface": "predict"},
        )

    # ── Gemini native :generateContent surface ────────────────────

    def _generate_native(self, model: str, request: MediaRequest) -> MediaResult:
        url = f"{self._base_endpoint}/models/{model}:generateContent"

        payload: dict = {
            "contents": [{"parts": [{"text": request.prompt}]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        }

        logger.info("Gemini native image generation: model=%s, prompt=%.60s...", model, request.prompt)
        data = self._post(url, payload, model)

        image_data, mime_type = self._extract_native_data(data, model)
        return MediaResult(
            data=image_data,
            media_type=request.media_type,
            mime_type=mime_type,
            width=request.width,
            height=request.height,
            model=model,
            provider="gemini",
            seed=request.seed,
            latency_ms=data["_elapsed_ms"],
            metadata={"surface": "generateContent"},
        )

    # ── Shared HTTP ───────────────────────────────────────────────

    def _post(self, url: str, payload: dict, model: str) -> dict:
        """POST to Gemini API with standard error handling.

        Returns the response JSON with ``_elapsed_ms`` injected.
        """
        t0 = time.perf_counter()
        try:
            response = httpx.post(
                url,
                json=payload,
                headers={
                    "x-goog-api-key": self._api_key,
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            data: dict = response.json()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"Gemini media generation failed: HTTP {exc.response.status_code}",
                error_code=PROVIDER_ERROR,
                details={"provider": "gemini", "model": model},
            ) from exc
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise LLMProviderError(
                f"Gemini connection failed: {type(exc).__name__}: {exc}",
                error_code=TIMEOUT,
                details={"provider": "gemini", "endpoint": url},
            ) from exc
        except Exception as exc:
            raise LLMProviderError(
                f"Gemini media generation failed: {type(exc).__name__}: {exc}",
                error_code=PROVIDER_ERROR,
                details={"provider": "gemini", "model": model},
            ) from exc

        data["_elapsed_ms"] = (time.perf_counter() - t0) * 1000
        return data

    # ── Response extraction ───────────────────────────────────────

    @staticmethod
    def _extract_imagen_data(data: dict, model: str) -> tuple[bytes, str]:
        """Extract from Imagen :predict response.

        Format: ``{"predictions": [{"bytesBase64Encoded": "...", "mimeType": "..."}]}``
        """
        predictions = data.get("predictions")
        if predictions and isinstance(predictions, list) and len(predictions) > 0:
            pred = predictions[0]
            b64 = pred.get("bytesBase64Encoded")
            if b64 and isinstance(b64, str):
                mime = pred.get("mimeType", "image/png")
                return base64.b64decode(b64), str(mime)

        # Also try "generatedImages" (seen in some API versions)
        generated = data.get("generatedImages")
        if generated and isinstance(generated, list) and len(generated) > 0:
            item = generated[0]
            b64 = item.get("image", {}).get("imageBytes") or item.get("bytesBase64Encoded")
            if b64 and isinstance(b64, str):
                mime = item.get("mimeType", "image/png")
                return base64.b64decode(b64), str(mime)

        raise LLMProviderError(
            f"Gemini response for model '{model}' contained no image data. Response keys: {list(data.keys())}",
            error_code=PROVIDER_ERROR,
            details={"provider": "gemini", "model": model, "keys": list(data.keys())},
        )

    @staticmethod
    def _extract_native_data(data: dict, model: str) -> tuple[bytes, str]:
        """Extract from Gemini :generateContent response.

        Format: ``{"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "...", "data": "..."}}]}}]}``
        """
        candidates = data.get("candidates")
        if candidates and isinstance(candidates, list) and len(candidates) > 0:
            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                inline = part.get("inlineData")
                if inline and isinstance(inline, dict):
                    b64 = inline.get("data")
                    if b64 and isinstance(b64, str):
                        mime = inline.get("mimeType", "image/png")
                        return base64.b64decode(b64), str(mime)

        raise LLMProviderError(
            f"Gemini response for model '{model}' contained no image data. Response keys: {list(data.keys())}",
            error_code=PROVIDER_ERROR,
            details={"provider": "gemini", "model": model, "keys": list(data.keys())},
        )
