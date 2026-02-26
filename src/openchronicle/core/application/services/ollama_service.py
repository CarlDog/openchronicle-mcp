"""Ollama model discovery and config generation service.

Talks to the Ollama HTTP API to list/show models, infers capabilities,
and generates model config JSON files compatible with ModelConfigLoader.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Families/formats that indicate diffusion (image generation) models.
_DIFFUSION_FAMILIES = {"flux", "stable-diffusion", "sdxl"}
_DIFFUSION_FORMAT = "safetensors"

# Families that indicate vision (multimodal) capability.
_VISION_FAMILIES = {"clip"}

# Template fragments that indicate function-calling support.
_TOOL_TEMPLATE_MARKERS = ("TOOL_CALLS", "AVAILABLE_TOOLS", "<tool_call>", "<|tool_start|>")


def _default_base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_HOST") or "http://localhost:11434"


def _sanitize_filename(model_name: str) -> str:
    """Convert a model name to a safe config filename.

    ``deepseek-r1:32b`` → ``ollama_deepseek-r1_32b.json``
    ``HammerAI/mythomax-l2:latest`` → ``ollama_hammerai_mythomax-l2_latest.json``
    """
    slug = model_name.lower().replace("/", "_").replace(":", "_")
    slug = re.sub(r"[^a-z0-9_\-]", "", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return f"ollama_{slug}.json"


@dataclass
class OllamaModelInfo:
    """Parsed model information from the Ollama API."""

    name: str
    size_bytes: int
    parameter_size: str
    quantization_level: str
    family: str
    families: list[str]
    fmt: str  # "gguf", "safetensors", etc.
    context_length: int | None = None
    has_tools: bool = False

    @property
    def is_diffusion(self) -> bool:
        if self.fmt == _DIFFUSION_FORMAT:
            return True
        family_lower = self.family.lower().removesuffix("pipeline")
        return bool(family_lower and any(kw in family_lower for kw in _DIFFUSION_FAMILIES))

    @property
    def is_vision(self) -> bool:
        return bool(_VISION_FAMILIES & {f.lower() for f in self.families})

    def inferred_capabilities(self) -> dict[str, bool]:
        if self.is_diffusion:
            return {"image_generation": True}
        caps: dict[str, bool] = {
            "text_generation": True,
            "streaming": True,
        }
        if self.is_vision:
            caps["vision"] = True
        caps["function_calling"] = self.has_tools
        if not self.is_vision and not self.has_tools:
            caps["vision"] = False
            caps["function_calling"] = False
        return caps

    def inferred_type(self) -> str:
        return "media" if self.is_diffusion else "llm"

    def display_name(self) -> str:
        base = self.name.split(":")[0].split("/")[-1].replace("-", " ").title()
        tag = self.name.split(":")[-1] if ":" in self.name else ""
        suffix = f" {tag}" if tag and tag != "latest" else ""
        return f"Ollama - {base}{suffix}"

    def description(self) -> str:
        parts = [f"Local {self.name} via Ollama"]
        if self.parameter_size:
            parts.append(f"({self.parameter_size})")
        if self.quantization_level:
            parts.append(f"[{self.quantization_level}]")
        return " ".join(parts)


@dataclass
class ConfigDiff:
    """Result of comparing installed models against existing configs."""

    installed: list[OllamaModelInfo]
    configured: list[str]  # model names that have configs
    unconfigured: list[OllamaModelInfo] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)  # configs with no installed model


class OllamaService:
    """Ollama model discovery and config management."""

    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        self._base_url = (base_url or _default_base_url()).rstrip("/")
        self._timeout = timeout

    def list_models(self) -> list[OllamaModelInfo]:
        """List all models installed in Ollama."""
        resp = httpx.get(f"{self._base_url}/api/tags", timeout=self._timeout)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        models: list[OllamaModelInfo] = []
        for entry in data.get("models", []):
            details = entry.get("details", {})
            models.append(
                OllamaModelInfo(
                    name=entry["name"],
                    size_bytes=entry.get("size", 0),
                    parameter_size=details.get("parameter_size", ""),
                    quantization_level=details.get("quantization_level", ""),
                    family=details.get("family", ""),
                    families=details.get("families") or [],
                    fmt=details.get("format", ""),
                )
            )
        return models

    def show_model(self, name: str) -> OllamaModelInfo:
        """Get detailed info for a specific model."""
        resp = httpx.post(
            f"{self._base_url}/api/show",
            json={"name": name},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        details = data.get("details", {})
        model_info = data.get("model_info", {})
        template = data.get("template", "")

        context_length = (
            model_info.get("llama.context_length")
            or model_info.get("gemma.context_length")
            or model_info.get("qwen2.context_length")
        )

        has_tools = any(marker in template for marker in _TOOL_TEMPLATE_MARKERS)

        return OllamaModelInfo(
            name=name,
            size_bytes=0,  # not in /api/show
            parameter_size=details.get("parameter_size", ""),
            quantization_level=details.get("quantization_level", ""),
            family=details.get("family", ""),
            families=details.get("families") or [],
            fmt=details.get("format", ""),
            context_length=context_length,
            has_tools=has_tools,
        )

    def diff(self, models_dir: Path) -> ConfigDiff:
        """Compare installed models against config files in *models_dir*."""
        installed = self.list_models()

        # Find existing ollama configs and extract their model names.
        configured_models: dict[str, str] = {}  # model_name -> filename
        if models_dir.exists():
            for path in models_dir.glob("ollama*.json"):
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    model_name = raw.get("model", "")
                    if model_name:
                        configured_models[model_name] = path.name
                except (json.JSONDecodeError, OSError):
                    continue

        installed_names = {m.name for m in installed}
        unconfigured = [m for m in installed if m.name not in configured_models]
        stale = [name for name in configured_models if name not in installed_names]

        return ConfigDiff(
            installed=installed,
            configured=list(configured_models.keys()),
            unconfigured=unconfigured,
            stale=stale,
        )

    def generate_config(self, info: OllamaModelInfo) -> dict[str, Any]:
        """Generate a model config dict for an Ollama model."""
        caps = info.inferred_capabilities()
        model_type = info.inferred_type()

        endpoint = f"{self._base_url}/api/generate" if model_type == "media" else f"{self._base_url}/api/chat"

        config: dict[str, Any] = {
            "provider": "ollama",
            "model": info.name,
            "type": model_type,
            "display_name": info.display_name(),
            "description": info.description(),
            "capabilities": caps,
            "api_config": {
                "endpoint": endpoint,
                "default_base_url": self._base_url,
                "timeout": 120,
            },
        }

        # Add limits for LLMs if we have context length.
        if model_type == "llm" and info.context_length:
            config["limits"] = {
                "max_tokens": 4096,
                "context_window": info.context_length,
                "rate_limit_rpm": None,
                "rate_limit_tpm": None,
            }

        # Local models are always free.
        if model_type == "llm":
            config["cost_tracking"] = {
                "input_cost_per_1k": 0.0,
                "output_cost_per_1k": 0.0,
                "currency": "USD",
            }
            config["performance"] = {
                "priority": "local_privacy",
                "recommended_for": ["local_development", "privacy_sensitive"],
            }

        return config

    def write_config(self, info: OllamaModelInfo, models_dir: Path) -> Path:
        """Generate and write a config file. Returns the path written."""
        config = self.generate_config(info)
        filename = _sanitize_filename(info.name)
        path = models_dir / filename
        path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        logger.info("Wrote config: %s", path)
        return path

    def remove_config(self, model_name: str, models_dir: Path) -> Path | None:
        """Remove config file for *model_name*. Returns path removed, or None."""
        if not models_dir.exists():
            return None
        for path in models_dir.glob("ollama*.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if raw.get("model") == model_name:
                    path.unlink()
                    logger.info("Removed config: %s", path)
                    return path
            except (json.JSONDecodeError, OSError):
                continue
        return None
