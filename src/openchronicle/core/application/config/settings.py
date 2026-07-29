from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from openchronicle.core.application.config.env_helpers import (
    env_override,
    parse_float,
    parse_int,
    parse_str,
)

log = logging.getLogger(__name__)

VALID_EMBEDDING_PROVIDERS = frozenset({"none", "stub", "openai", "ollama"})


@dataclass(frozen=True)
class EmbeddingSettings:
    """Embedding provider configuration."""

    provider: str = "none"
    model: str = ""
    dimensions: int | None = None
    api_key: str = ""
    timeout: float = 30.0

    def __post_init__(self) -> None:
        if self.provider not in VALID_EMBEDDING_PROVIDERS:
            raise ValueError(
                f"embedding provider must be one of {set(VALID_EMBEDDING_PROVIDERS)}, got {self.provider!r}"
            )
        if self.dimensions is not None and self.dimensions < 1:
            raise ValueError(f"embedding dimensions must be >= 1, got {self.dimensions}")
        if self.timeout <= 0:
            raise ValueError(f"embedding timeout must be > 0, got {self.timeout}")


def load_embedding_settings(
    file_config: dict[str, Any] | None = None,
) -> EmbeddingSettings:
    """Load embedding settings from file config with env var overrides.

    Invalid values fail soft: an unrecognized provider degrades to "none"
    (FTS5-only search) with a warning, and an unparseable or non-positive
    timeout/dimensions falls back to the default. One bad env var must not
    crash `oc serve` (a hard exit under `restart: unless-stopped` becomes
    a crash loop).
    """
    fc = file_config or {}
    dims_raw = env_override("OC_EMBEDDING_DIMENSIONS", fc.get("dimensions"))
    dims = parse_int(dims_raw, default=0) if dims_raw is not None else 0
    if dims < 0:
        log.warning("Invalid embedding dimensions %r; ignoring (provider default)", dims_raw)
        dims = 0
    timeout_raw = env_override("OC_EMBEDDING_TIMEOUT", fc.get("timeout"))
    timeout = parse_float(timeout_raw, default=30.0)
    if timeout <= 0:
        log.warning("Invalid embedding timeout %r; falling back to 30.0s", timeout_raw)
        timeout = 30.0
    provider = parse_str(
        env_override("OC_EMBEDDING_PROVIDER", fc.get("provider")),
        default="none",
    ).lower()
    if provider not in VALID_EMBEDDING_PROVIDERS:
        log.warning(
            "Unknown embedding provider %r; falling back to 'none' (FTS5-only search)",
            provider,
        )
        provider = "none"
    return EmbeddingSettings(
        provider=provider,
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
