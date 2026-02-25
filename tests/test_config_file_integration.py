"""Integration tests for file-based configuration system.

Tests that the core.json config file propagates through the container and into
the services that consume them, with env vars overriding file values.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from openchronicle.core.application.config.budget_config import load_budget_policy
from openchronicle.core.application.config.settings import (
    load_embedding_settings,
    load_privacy_outbound_settings,
    load_router_assist_settings,
    load_telemetry_settings,
)
from openchronicle.core.application.routing.pool_config import load_pool_config
from openchronicle.core.infrastructure.config.config_loader import CORE_CONFIG_NAME, load_config_files


def _write_core(tmp_path: Path, data: dict[str, Any]) -> None:
    (tmp_path / CORE_CONFIG_NAME).write_text(json.dumps(data), encoding="utf-8")


# ---------- Three-layer precedence tests ----------


class TestThreeLayerPrecedence:
    """Verify: dataclass defaults -> JSON file -> env var override."""

    def test_defaults_when_no_file_no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No file, no env var => dataclass defaults."""
        monkeypatch.delenv("OC_PRIVACY_OUTBOUND_MODE", raising=False)
        settings = load_privacy_outbound_settings()
        assert settings.mode == "off"
        assert settings.external_only is True
        assert settings.redact_style == "mask"

    def test_file_values_override_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """File config overrides dataclass defaults."""
        monkeypatch.delenv("OC_PRIVACY_OUTBOUND_MODE", raising=False)
        monkeypatch.delenv("OC_PRIVACY_OUTBOUND_EXTERNAL_ONLY", raising=False)
        settings = load_privacy_outbound_settings({"mode": "redact", "external_only": False})
        assert settings.mode == "redact"
        assert settings.external_only is False

    def test_env_overrides_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env var overrides file config."""
        monkeypatch.setenv("OC_PRIVACY_OUTBOUND_MODE", "block")
        settings = load_privacy_outbound_settings({"mode": "redact"})
        assert settings.mode == "block"

    def test_env_overrides_file_bool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env var overrides a file bool."""
        monkeypatch.setenv("OC_PRIVACY_OUTBOUND_EXTERNAL_ONLY", "0")
        settings = load_privacy_outbound_settings({"external_only": True})
        assert settings.external_only is False

    def test_file_categories_as_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """File config categories can be a JSON array."""
        monkeypatch.delenv("OC_PRIVACY_OUTBOUND_CATEGORIES", raising=False)
        settings = load_privacy_outbound_settings({"categories": ["email", "phone"]})
        assert settings.categories == ["email", "phone"]

    def test_env_categories_override_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env var overrides file categories (CSV string)."""
        monkeypatch.setenv("OC_PRIVACY_OUTBOUND_CATEGORIES", "ssn,cc")
        settings = load_privacy_outbound_settings({"categories": ["email", "phone"]})
        assert settings.categories == ["ssn", "cc"]


class TestTelemetryFilePrecedence:
    def test_file_disables_telemetry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OC_TELEMETRY_ENABLED", raising=False)
        settings = load_telemetry_settings({"enabled": False})
        assert settings.enabled is False

    def test_env_overrides_file_telemetry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_TELEMETRY_ENABLED", "1")
        settings = load_telemetry_settings({"enabled": False})
        assert settings.enabled is True


class TestBudgetFilePrecedence:
    def test_file_sets_budget_limits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OC_BUDGET_MAX_TOKENS", raising=False)
        monkeypatch.delenv("OC_BUDGET_MAX_CALLS", raising=False)
        policy = load_budget_policy({"max_total_tokens": 5000, "max_llm_calls": 100})
        assert policy.max_total_tokens == 5000
        assert policy.max_llm_calls == 100

    def test_env_overrides_file_budget(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_BUDGET_MAX_TOKENS", "9999")
        policy = load_budget_policy({"max_total_tokens": 5000})
        assert policy.max_total_tokens == 9999

    def test_zero_budget_means_unlimited(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OC_BUDGET_MAX_TOKENS", raising=False)
        monkeypatch.delenv("OC_BUDGET_MAX_CALLS", raising=False)
        policy = load_budget_policy({"max_total_tokens": 0})
        assert policy.max_total_tokens is None  # 0 => None => no constraint


class TestPoolConfigFilePrecedence:
    def test_file_sets_pools(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OC_LLM_FAST_POOL", raising=False)
        monkeypatch.delenv("OC_LLM_QUALITY_POOL", raising=False)
        monkeypatch.delenv("OC_LLM_PROVIDER_WEIGHTS", raising=False)
        config = load_pool_config(
            {
                "pools": {"fast": "openai:gpt-4o-mini", "quality": "openai:gpt-4o"},
                "weights": {"openai": 50},
            }
        )
        assert len(config.fast_pool) == 1
        assert config.fast_pool[0].provider == "openai"
        assert config.fast_pool[0].model == "gpt-4o-mini"
        assert config.fast_pool[0].weight == 50

    def test_file_sets_fallback_controls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OC_LLM_MAX_FALLBACKS", raising=False)
        monkeypatch.delenv("OC_LLM_FALLBACK_ON_REFUSAL", raising=False)
        config = load_pool_config(
            {
                "fallback": {"max_fallbacks": 3, "on_refusal": True},
            }
        )
        assert config.max_fallbacks == 3
        assert config.fallback_on_refusal is True

    def test_weights_as_json_object(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OC_LLM_PROVIDER_WEIGHTS", raising=False)
        config = load_pool_config(
            {
                "pools": {"fast": "openai:gpt-4o-mini,ollama:llama3.1"},
                "weights": {"openai": 20, "ollama": 100},
            }
        )
        assert config.provider_weights == {"openai": 20, "ollama": 100}
        # Ollama should have higher weight
        assert config.fast_pool[0].weight == 20  # openai
        assert config.fast_pool[1].weight == 100  # ollama


class TestEmbeddingFilePrecedence:
    def test_defaults_when_no_file_no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OC_EMBEDDING_PROVIDER", raising=False)
        monkeypatch.delenv("OC_EMBEDDING_MODEL", raising=False)
        monkeypatch.delenv("OC_EMBEDDING_DIMENSIONS", raising=False)
        settings = load_embedding_settings()
        assert settings.provider == "none"
        assert settings.model == ""
        assert settings.dimensions is None

    def test_file_sets_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OC_EMBEDDING_PROVIDER", raising=False)
        settings = load_embedding_settings({"provider": "openai"})
        assert settings.provider == "openai"

    def test_file_sets_model_and_dimensions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OC_EMBEDDING_PROVIDER", raising=False)
        monkeypatch.delenv("OC_EMBEDDING_MODEL", raising=False)
        monkeypatch.delenv("OC_EMBEDDING_DIMENSIONS", raising=False)
        settings = load_embedding_settings(
            {"provider": "openai", "model": "text-embedding-3-large", "dimensions": 1536}
        )
        assert settings.provider == "openai"
        assert settings.model == "text-embedding-3-large"
        assert settings.dimensions == 1536

    def test_env_overrides_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_EMBEDDING_PROVIDER", "ollama")
        settings = load_embedding_settings({"provider": "openai"})
        assert settings.provider == "ollama"

    def test_env_overrides_file_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_EMBEDDING_MODEL", "nomic-embed-text")
        settings = load_embedding_settings({"model": "text-embedding-3-small"})
        assert settings.model == "nomic-embed-text"

    def test_provider_normalized_to_lowercase(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OC_EMBEDDING_PROVIDER", raising=False)
        settings = load_embedding_settings({"provider": "OpenAI"})
        assert settings.provider == "openai"

    def test_invalid_provider_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OC_EMBEDDING_PROVIDER", raising=False)
        with pytest.raises(ValueError, match="embedding provider"):
            load_embedding_settings({"provider": "banana"})

    def test_invalid_dimensions_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OC_EMBEDDING_DIMENSIONS", raising=False)
        with pytest.raises(ValueError, match="embedding dimensions"):
            load_embedding_settings({"provider": "stub", "dimensions": -1})


class TestRouterAssistFilePrecedence:
    def test_file_enables_assist(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OC_ROUTER_ASSIST_ENABLED", raising=False)
        monkeypatch.delenv("OC_ROUTER_ASSIST_BACKEND", raising=False)
        settings = load_router_assist_settings({"enabled": True, "backend": "onnx"})
        assert settings.enabled is True
        assert settings.backend == "onnx"


# ---------- load_config_files integration ----------


class TestLoadConfigFilesIntegration:
    def test_roundtrip_core_config(self, tmp_path: Path) -> None:
        """Write core.json, load it, feed sections to factories."""
        _write_core(
            tmp_path,
            {
                "provider": "openai",
                "default_mode": "quality",
                "pools": {"fast": "openai:gpt-4o-mini"},
                "weights": {"openai": 80},
                "fallback": {"max_fallbacks": 2},
                "budget": {"max_total_tokens": 10000},
                "retry": {"max_retries": 3},
                "privacy": {"mode": "redact", "log_events": False},
                "telemetry": {"enabled": False, "perf_enabled": False},
                "router": {
                    "rules": {"enabled": True, "nsfw_route_gte": 0.80},
                    "assist": {"enabled": False},
                },
            },
        )

        configs = load_config_files(tmp_path)
        assert configs["provider"] == "openai"
        assert configs["pools"]["fast"] == "openai:gpt-4o-mini"
        assert configs["budget"]["max_total_tokens"] == 10000
        assert configs["privacy"]["mode"] == "redact"
        assert configs["telemetry"]["enabled"] is False
        assert configs["router"]["rules"]["nsfw_route_gte"] == 0.80

    def test_missing_core_json_returns_empty(self, tmp_path: Path) -> None:
        """Config dir with no core.json -> empty dict, factories use defaults."""
        configs = load_config_files(tmp_path)
        privacy = load_privacy_outbound_settings(configs.get("privacy"))
        assert privacy.mode == "off"  # default
        telemetry = load_telemetry_settings(configs.get("telemetry"))
        assert telemetry.enabled is True  # default
