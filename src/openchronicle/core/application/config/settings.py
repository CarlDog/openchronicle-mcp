from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openchronicle.core.application.config.env_helpers import (
    env_override,
    parse_int,
    parse_str,
)


@dataclass(frozen=True)
class EmbeddingSettings:
    """Embedding provider configuration."""

    provider: str = "none"
    model: str = ""
    dimensions: int | None = None
    api_key: str = ""
    timeout: float = 30.0

    def __post_init__(self) -> None:
        valid = {"none", "stub", "openai", "ollama"}
        if self.provider not in valid:
            raise ValueError(f"embedding provider must be one of {valid}, got {self.provider!r}")
        if self.dimensions is not None and self.dimensions < 1:
            raise ValueError(f"embedding dimensions must be >= 1, got {self.dimensions}")
        if self.timeout <= 0:
            raise ValueError(f"embedding timeout must be > 0, got {self.timeout}")


def load_embedding_settings(
    file_config: dict[str, Any] | None = None,
) -> EmbeddingSettings:
    fc = file_config or {}
    dims_raw = env_override("OC_EMBEDDING_DIMENSIONS", fc.get("dimensions"))
    dims = parse_int(dims_raw, default=0) if dims_raw is not None else 0
    timeout_raw = env_override("OC_EMBEDDING_TIMEOUT", fc.get("timeout"))
    timeout = float(str(timeout_raw)) if timeout_raw is not None else 30.0
    return EmbeddingSettings(
        provider=parse_str(
            env_override("OC_EMBEDDING_PROVIDER", fc.get("provider")),
            default="none",
        ).lower(),
        model=parse_str(
            env_override("OC_EMBEDDING_MODEL", fc.get("model")),
            default="",
        ),
        dimensions=dims if dims != 0 else None,
        api_key=parse_str(
            env_override("OC_EMBEDDING_API_KEY", fc.get("api_key")),
            default="",
        ),
        timeout=timeout,
    )
