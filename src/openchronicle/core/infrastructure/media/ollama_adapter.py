"""Ollama media generation adapter.

Uses Ollama's /api/generate endpoint with diffusion models (e.g. flux,
sdxl, stable-diffusion).  The image generation API is experimental and
may change — the port abstraction insulates callers from API drift.
"""

from __future__ import annotations

import base64
import logging
import os
import time

import httpx

from openchronicle.core.domain.errors.error_codes import PROVIDER_ERROR, TIMEOUT
from openchronicle.core.domain.models.media import MediaRequest, MediaResult
from openchronicle.core.domain.ports.llm_port import LLMProviderError
from openchronicle.core.domain.ports.media_generation_port import MediaGenerationPort

logger = logging.getLogger(__name__)


class OllamaMediaAdapter(MediaGenerationPort):
    """Media generation via Ollama diffusion models.

    Supported models include ``flux``, ``sdxl``, ``stable-diffusion``,
    and any future Ollama-hosted diffusion model.
    """

    def __init__(
        self,
        *,
        model: str = "flux",
        host: str | None = None,
        timeout_seconds: float = 120.0,
        supported_types: list[str] | None = None,
    ) -> None:
        self._model = model
        self._host: str = host or os.getenv("OLLAMA_HOST") or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"
        self._timeout = timeout_seconds
        self._supported_types = supported_types or ["image"]

    def generate(self, request: MediaRequest) -> MediaResult:
        model = request.model or self._model
        url = f"{self._host.rstrip('/')}/api/generate"

        payload: dict = {
            "model": model,
            "prompt": request.prompt,
            "stream": False,
        }
        # Optional generation parameters
        options: dict = {}
        if request.seed is not None:
            options["seed"] = request.seed
        if request.steps is not None:
            options["num_predict"] = request.steps
        if options:
            payload["options"] = options

        # Image dimensions (experimental Ollama params)
        if request.width is not None:
            payload["width"] = request.width
        if request.height is not None:
            payload["height"] = request.height

        if request.negative_prompt:
            payload["negative_prompt"] = request.negative_prompt

        logger.info(
            "Ollama media generation: model=%s, prompt=%.60s...",
            model,
            request.prompt,
        )
        t0 = time.perf_counter()

        try:
            response = httpx.post(url, json=payload, timeout=self._timeout)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"Ollama media generation failed: HTTP {exc.response.status_code}",
                error_code=PROVIDER_ERROR,
                details={"provider": "ollama", "model": model},
            ) from exc
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise LLMProviderError(
                f"Ollama connection failed: {type(exc).__name__}: {exc}",
                error_code=TIMEOUT,
                details={"provider": "ollama", "host": self._host},
            ) from exc
        except Exception as exc:
            raise LLMProviderError(
                f"Ollama media generation failed: {type(exc).__name__}: {exc}",
                error_code=PROVIDER_ERROR,
                details={"provider": "ollama", "model": model},
            ) from exc

        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Extract image data — Ollama returns base64 in "images" array
        # or possibly in "response" depending on model/version
        image_data = self._extract_image_data(data, model)

        return MediaResult(
            data=image_data,
            media_type=request.media_type,
            mime_type="image/png",
            width=request.width,
            height=request.height,
            model=model,
            provider="ollama",
            seed=request.seed,
            latency_ms=elapsed_ms,
            metadata={
                "host": self._host,
                "total_duration_ns": data.get("total_duration"),
            },
        )

    def supported_media_types(self) -> list[str]:
        return list(self._supported_types)

    def model_name(self) -> str:
        return self._model

    @staticmethod
    def _extract_image_data(data: dict, model: str) -> bytes:
        """Extract base64-decoded image bytes from Ollama response."""
        # Primary: "images" array (Ollama diffusion models)
        images = data.get("images")
        if images and isinstance(images, list) and len(images) > 0:
            return base64.b64decode(images[0])

        # Fallback: "image" field (some model versions)
        image = data.get("image")
        if image and isinstance(image, str):
            return base64.b64decode(image)

        # Fallback: raw "response" field (base64-encoded)
        response_str = data.get("response")
        if response_str and isinstance(response_str, str):
            try:
                return base64.b64decode(response_str)
            except Exception:
                pass

        raise LLMProviderError(
            f"Ollama response for model '{model}' contained no image data. Response keys: {list(data.keys())}",
            error_code=PROVIDER_ERROR,
            details={"provider": "ollama", "model": model, "keys": list(data.keys())},
        )
