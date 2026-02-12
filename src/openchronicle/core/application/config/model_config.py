"""Model configuration loading for v1-style configs (no secret files)."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(Exception):
    """Configuration error with secret-safe messaging."""


@dataclass
class ModelConfigEntry:
    """Raw model config entry loaded from disk (may not be fully resolved)."""

    provider: str
    model: str
    enabled: bool
    filename: str
    display_name: str | None
    api_config: dict[str, Any]


@dataclass
class ResolvedModelConfig:
    """Model config with resolved runtime values (api key resolved)."""

    provider: str
    model: str
    endpoint: str | None = None
    base_url: str | None = None
    timeout: int | float | None = None
    auth_header: str | None = None
    auth_format: str | None = None
    api_key: str | None = None
    filename: str | None = None
    display_name: str | None = None

    def __repr__(self) -> str:  # pragma: no cover - defensive, but keep secret-safe
        return (
            f"ResolvedModelConfig(provider={self.provider!r}, model={self.model!r}, "
            f"endpoint={self.endpoint!r}, base_url={self.base_url!r}, timeout={self.timeout!r}, "
            f"auth_header={self.auth_header!r}, auth_format={self.auth_format!r}, "
            f"api_key={'<set>' if self.api_key else 'None'})"
        )


class ModelConfigLoader:
    """Load v1-style model configs from <OC_CONFIG_DIR>/models/*.json."""

    def __init__(self, config_dir: str) -> None:
        self.config_dir = Path(config_dir)
        self.models_dir = self.config_dir / "models"
        self._configs: list[ModelConfigEntry] = self._load_all()

    def list_all(self) -> list[ModelConfigEntry]:
        """Return all parsed model configs (including disabled)."""
        return list(self._configs)

    def list_enabled(self) -> list[ModelConfigEntry]:
        """Return enabled model configs only."""
        return [cfg for cfg in self._configs if cfg.enabled]

    def providers(self) -> set[str]:
        """Providers present in enabled configs (deterministic order not required)."""
        return {cfg.provider for cfg in self.list_enabled()}

    def resolve(self, provider: str, model: str) -> ResolvedModelConfig:
        """
        Resolve a specific provider/model combination.

        Raises ConfigError if not found, disabled, or missing api key when required.
        """
        for cfg in self.list_enabled():
            if cfg.provider == provider and cfg.model == model:
                return self._to_resolved(cfg)
        raise ConfigError(f"Model config not found or disabled for provider={provider!r}, model={model!r}")

    # Internal helpers -------------------------------------------------

    def _load_all(self) -> list[ModelConfigEntry]:
        if not self.models_dir.exists():
            return []

        entries: list[ModelConfigEntry] = []
        for path in sorted(self.models_dir.glob("*.json"), key=lambda p: p.name.lower()):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                raise ConfigError(f"Failed to load model config {path.name}: {exc}") from exc

            provider = raw.get("provider")
            model = raw.get("model") or raw.get("api_config", {}).get("model")
            if not provider or not model:
                # Skip invalid entries with explicit error for clarity
                raise ConfigError(f"Model config {path.name} missing required provider/model")

            enabled_raw = raw.get("enabled", True)
            enabled = bool(enabled_raw) if not isinstance(enabled_raw, bool) else enabled_raw

            api_config = raw.get("api_config", {}) if isinstance(raw.get("api_config", {}), dict) else {}

            entries.append(
                ModelConfigEntry(
                    provider=str(provider),
                    model=str(model),
                    enabled=enabled,
                    filename=path.name,
                    display_name=raw.get("display_name"),
                    api_config=api_config,
                )
            )

        return entries

    def _to_resolved(self, cfg: ModelConfigEntry) -> ResolvedModelConfig:
        api_cfg = cfg.api_config

        # Apply API key resolution rules (inline -> api_key_env -> standard env)
        api_key_inline = api_cfg.get("api_key")
        if isinstance(api_key_inline, str) and api_key_inline.strip():
            resolved_api_key: str | None = api_key_inline.strip()
        else:
            resolved_api_key = None
            api_key_env_name = api_cfg.get("api_key_env")
            if isinstance(api_key_env_name, str) and api_key_env_name.strip():
                env_val = os.getenv(api_key_env_name.strip())
                if env_val:
                    resolved_api_key = env_val
            if resolved_api_key is None:
                standard_env = self._standard_api_env(cfg.provider)
                if standard_env:
                    env_val = os.getenv(standard_env)
                    if env_val:
                        resolved_api_key = env_val

        auth_header = api_cfg.get("auth_header")
        auth_format = api_cfg.get("auth_format")
        requires_api_key = False
        if isinstance(auth_format, str) and "{api_key}" in auth_format:
            requires_api_key = True
        if auth_header:
            requires_api_key = True

        # Only fail when the model is actually resolved/used AND key is required
        if requires_api_key and resolved_api_key is None:
            raise ConfigError(
                f"API key not configured for provider={cfg.provider!r}, model={cfg.model!r}. "
                "Set api_config.api_key or provide the expected environment variable."
            )

        return ResolvedModelConfig(
            provider=cfg.provider,
            model=cfg.model,
            endpoint=api_cfg.get("endpoint"),
            base_url=api_cfg.get("default_base_url"),
            timeout=api_cfg.get("timeout"),
            auth_header=auth_header,
            auth_format=auth_format,
            api_key=resolved_api_key,
            filename=cfg.filename,
            display_name=cfg.display_name,
        )

    @staticmethod
    def _standard_api_env(provider: str) -> str | None:
        mapping = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "groq": "GROQ_API_KEY",
            "gemini": "GEMINI_API_KEY",
        }
        return mapping.get(provider.lower())


def sort_model_configs(configs: Iterable[ModelConfigEntry]) -> list[ModelConfigEntry]:
    """Utility for deterministic sorting by filename then provider/model."""
    return sorted(configs, key=lambda c: (c.filename.lower(), c.provider.lower(), c.model.lower()))
