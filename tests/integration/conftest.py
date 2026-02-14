"""Shared fixtures for integration tests.

Auto-detects the application's config directory and LLM provider so that
integration tests only need ``OC_INTEGRATION_TESTS=1`` to run.  Explicit
env vars (``OC_CONFIG_DIR``, ``OC_LLM_PROVIDER``) always take precedence.

Detection order for config directory:
  1. ``OC_CONFIG_DIR`` env var (if set)
  2. Well-known deployment paths that contain ``models/*.json``
  3. Repo-local ``config/`` (fallback)

Detection order for LLM provider:
  1. ``OC_LLM_PROVIDER`` env var (if set)
  2. API-key env vars (``OPENAI_API_KEY`` → openai, etc.)
  3. First provider found in model config files
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Well-known config directories (tried in order).
# ---------------------------------------------------------------------------
_CONFIG_DIR_CANDIDATES = [
    Path(r"C:\Docker\openchronicle\config"),
    Path("/opt/openchronicle/config"),
    Path("config"),
]

# API-key env var → provider name (preference order).
_KEY_TO_PROVIDER: list[tuple[str, str]] = [
    ("OPENAI_API_KEY", "openai"),
    ("ANTHROPIC_API_KEY", "anthropic"),
    ("GROQ_API_KEY", "groq"),
    ("GEMINI_API_KEY", "gemini"),
    ("GOOGLE_API_KEY", "gemini"),
]


def _resolve_config_dir() -> str:
    """Return the best available config directory."""
    explicit = os.getenv("OC_CONFIG_DIR")
    if explicit:
        return explicit
    for candidate in _CONFIG_DIR_CANDIDATES:
        if candidate.is_dir() and any(candidate.glob("models/*.json")):
            return str(candidate)
    return "config"


def _resolve_provider(config_dir: str) -> str | None:
    """Infer the default LLM provider."""
    explicit = os.getenv("OC_LLM_PROVIDER", "").strip()
    if explicit:
        return explicit
    # Check API-key env vars
    for env_var, provider in _KEY_TO_PROVIDER:
        if os.getenv(env_var):
            return provider
    # Scan model configs for embedded keys
    from openchronicle.core.application.config.model_config import ModelConfigLoader

    providers = sorted(ModelConfigLoader(config_dir).providers())
    for preferred in ("openai", "anthropic"):
        if preferred in providers:
            return preferred
    return providers[0] if providers else None


@pytest.fixture(scope="session", autouse=True)
def _integration_env():  # type: ignore[no-untyped-def]
    """Set ``OC_CONFIG_DIR`` and ``OC_LLM_PROVIDER`` for the session.

    Only touches env vars that are not already set.  Restores originals
    on teardown so the process env is left clean.
    """
    saved: dict[str, str | None] = {}

    config_dir = _resolve_config_dir()
    if not os.getenv("OC_CONFIG_DIR"):
        saved["OC_CONFIG_DIR"] = None
        os.environ["OC_CONFIG_DIR"] = config_dir

    provider = _resolve_provider(config_dir)
    if provider and not os.getenv("OC_LLM_PROVIDER"):
        saved["OC_LLM_PROVIDER"] = None
        os.environ["OC_LLM_PROVIDER"] = provider

    yield

    for key, old_val in saved.items():
        if old_val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = old_val
