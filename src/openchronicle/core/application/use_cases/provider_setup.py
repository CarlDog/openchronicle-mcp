"""Provider setup use case — write model config files for known or custom providers.

Follows the init_config.py pattern: module-level functions, returns result dicts.
No container dependency. Idempotent (skips existing files by default).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from openchronicle.core.application.config.provider_registry import (
    ProviderDefinition,
    get_provider,
)
from openchronicle.core.application.config.provider_registry import (
    list_providers as registry_list_providers,
)
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError


def list_providers() -> list[dict[str, object]]:
    """Provider info suitable for display."""
    result = []
    for p in registry_list_providers():
        result.append(
            {
                "name": p.name,
                "display_name": p.display_name,
                "requires_api_key": p.requires_api_key,
                "api_key_env": p.api_key_env,
                "models": [
                    {"model_id": m.model_id, "display_name": m.display_name, "pool_hint": m.pool_hint} for m in p.models
                ],
            }
        )
    return result


def get_provider_info(name: str) -> dict[str, object] | None:
    """Single provider details, or None if unknown."""
    p = get_provider(name)
    if p is None:
        return None
    return {
        "name": p.name,
        "display_name": p.display_name,
        "adapter_provider": p.adapter_provider,
        "requires_api_key": p.requires_api_key,
        "api_key_env": p.api_key_env,
        "endpoint": p.endpoint,
        "base_url": p.base_url,
        "default_timeout": p.default_timeout,
        "models": [
            {
                "model_id": m.model_id,
                "display_name": m.display_name,
                "description": m.description,
                "pool_hint": m.pool_hint,
                "timeout": m.timeout,
            }
            for m in p.models
        ],
    }


def setup_provider(
    provider_name: str,
    config_dir: str,
    api_key: str | None = None,
    api_key_env: str | None = None,
    models: list[str] | None = None,
) -> dict[str, str | int | list[str]]:
    """Write model configs for a known provider. Idempotent (skips existing).

    Args:
        provider_name: Registry name (e.g. "openai", "xai").
        config_dir: Base configuration directory.
        api_key: Inline API key (written to config if provided).
        api_key_env: Env var name for API key (written to config if provided).
        models: Model IDs to include, or None for all.

    Returns:
        Dict with created/skipped file lists.

    Raises:
        ValueError: If provider_name is not in the registry.
    """
    provider = get_provider(provider_name)
    if provider is None:
        raise DomainValidationError(f"Unknown provider: {provider_name!r}")

    models_dir = Path(config_dir) / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    selected_models = provider.models
    if models is not None:
        model_set = set(models)
        selected_models = tuple(m for m in provider.models if m.model_id in model_set)

    created: list[str] = []
    skipped: list[str] = []

    for model_def in selected_models:
        filename = _config_filename(provider.name, model_def.model_id)
        filepath = models_dir / filename

        if filepath.exists():
            skipped.append(filename)
            continue

        config = _build_config_dict(
            provider=provider,
            model_id=model_def.model_id,
            display_name=model_def.display_name,
            description=model_def.description,
            timeout=model_def.timeout or provider.default_timeout,
            api_key=api_key,
            api_key_env=api_key_env,
        )
        filepath.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        created.append(filename)

    return {
        "config_dir": str(config_dir),
        "models_dir": str(models_dir),
        "provider": provider_name,
        "created_count": len(created),
        "created": created,
        "skipped_count": len(skipped),
        "skipped": skipped,
    }


def setup_custom(
    config_dir: str,
    provider: str,
    model: str,
    display_name: str | None = None,
    description: str | None = None,
    endpoint: str | None = None,
    base_url: str | None = None,
    auth_header: str | None = None,
    auth_format: str | None = None,
    api_key: str | None = None,
    api_key_env: str | None = None,
    timeout: int = 30,
) -> dict[str, str | int | list[str]]:
    """Write a single custom/blank config. Idempotent.

    For any OpenAI-compatible API not in the registry.
    """
    models_dir = Path(config_dir) / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    filename = _config_filename(provider, model)
    filepath = models_dir / filename

    if filepath.exists():
        return {
            "config_dir": str(config_dir),
            "models_dir": str(models_dir),
            "provider": provider,
            "created_count": 0,
            "created": [],
            "skipped_count": 1,
            "skipped": [filename],
        }

    config: dict[str, Any] = {
        "provider": provider,
        "model": model,
        "display_name": display_name or f"{provider} - {model}",
        "description": description or f"Custom {provider} model: {model}",
        "api_config": {},
    }

    api_config: dict[str, Any] = {}
    if endpoint is not None:
        api_config["endpoint"] = endpoint
    if base_url is not None:
        api_config["default_base_url"] = base_url
    api_config["timeout"] = timeout
    if auth_header is not None:
        api_config["auth_header"] = auth_header
    if auth_format is not None:
        api_config["auth_format"] = auth_format

    # Key resolution: explicit key > env var > placeholder
    if api_key is not None:
        api_config["api_key"] = api_key
    elif api_key_env is not None:
        api_config["api_key_env"] = api_key_env

    config["api_config"] = api_config
    filepath.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    return {
        "config_dir": str(config_dir),
        "models_dir": str(models_dir),
        "provider": provider,
        "created_count": 1,
        "created": [filename],
        "skipped_count": 0,
        "skipped": [],
    }


# --- Internal helpers ---


def _config_filename(provider_name: str, model_id: str) -> str:
    """Sanitize provider + model into a config filename.

    Uses the registry name (not adapter_provider) to avoid collisions:
    xai/grok-3 -> xai_grok_3.json, not openai_grok_3.json.
    """
    safe = re.sub(r"[^a-z0-9]+", "_", f"{provider_name}_{model_id}".lower())
    safe = safe.strip("_")
    return f"{safe}.json"


def _build_config_dict(
    provider: ProviderDefinition,
    model_id: str,
    display_name: str,
    description: str,
    timeout: int,
    api_key: str | None = None,
    api_key_env: str | None = None,
) -> dict[str, Any]:
    """Build a JSON-serializable config dict matching ModelConfigLoader format."""
    api_config: dict[str, Any] = {
        "endpoint": provider.endpoint,
    }
    if provider.base_url is not None:
        api_config["default_base_url"] = provider.base_url
    api_config["timeout"] = timeout
    if provider.auth_header is not None:
        api_config["auth_header"] = provider.auth_header
    if provider.auth_format is not None:
        api_config["auth_format"] = provider.auth_format

    # Key resolution: explicit key > explicit env var > provider default env var > placeholder
    if api_key is not None:
        api_config["api_key"] = api_key
    elif api_key_env is not None:
        api_config["api_key_env"] = api_key_env
    elif provider.requires_api_key and provider.api_key_env:
        api_config["api_key_env"] = provider.api_key_env

    return {
        "provider": provider.adapter_provider,
        "model": model_id,
        "display_name": display_name,
        "description": description,
        "api_config": api_config,
    }
