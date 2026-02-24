"""Tests for provider setup use case."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openchronicle.core.application.config.model_config import ModelConfigLoader
from openchronicle.core.application.config.provider_registry import PROVIDERS
from openchronicle.core.application.use_cases.provider_setup import setup_custom, setup_provider
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError


@pytest.fixture()
def config_dir(tmp_path: Path) -> str:
    return str(tmp_path / "config")


class TestSetupProvider:
    """setup_provider creates correct config files."""

    def test_creates_all_models(self, config_dir: str) -> None:
        result = setup_provider("openai", config_dir)
        assert result["created_count"] == 3
        assert result["skipped_count"] == 0
        created = result["created"]
        assert isinstance(created, list)
        assert len(created) == 3

    def test_idempotent_second_run(self, config_dir: str) -> None:
        setup_provider("openai", config_dir)
        result = setup_provider("openai", config_dir)
        assert result["created_count"] == 0
        assert result["skipped_count"] == 3

    def test_model_filter(self, config_dir: str) -> None:
        result = setup_provider("openai", config_dir, models=["gpt-4o-mini"])
        assert result["created_count"] == 1
        created = result["created"]
        assert isinstance(created, list)
        assert len(created) == 1
        assert "gpt_4o_mini" in created[0]

    def test_api_key_inline(self, config_dir: str) -> None:
        setup_provider("openai", config_dir, api_key="test-key", models=["gpt-4o-mini"])
        models_dir = Path(config_dir) / "models"
        files = list(models_dir.glob("*.json"))
        assert len(files) == 1
        config = json.loads(files[0].read_text(encoding="utf-8"))
        assert config["api_config"]["api_key"] == "test-key"
        assert "api_key_env" not in config["api_config"]

    def test_api_key_env(self, config_dir: str) -> None:
        setup_provider("openai", config_dir, api_key_env="MY_OPENAI_KEY", models=["gpt-4o-mini"])
        models_dir = Path(config_dir) / "models"
        files = list(models_dir.glob("*.json"))
        config = json.loads(files[0].read_text(encoding="utf-8"))
        assert config["api_config"]["api_key_env"] == "MY_OPENAI_KEY"
        assert "api_key" not in config["api_config"]

    def test_default_env_var_when_no_key(self, config_dir: str) -> None:
        """Provider's default api_key_env is written when no key provided."""
        setup_provider("openai", config_dir, models=["gpt-4o-mini"])
        models_dir = Path(config_dir) / "models"
        files = list(models_dir.glob("*.json"))
        config = json.loads(files[0].read_text(encoding="utf-8"))
        assert config["api_config"]["api_key_env"] == "OPENAI_API_KEY"

    def test_xai_writes_openai_provider(self, config_dir: str) -> None:
        setup_provider("xai", config_dir, models=["grok-3"])
        models_dir = Path(config_dir) / "models"
        files = list(models_dir.glob("*.json"))
        config = json.loads(files[0].read_text(encoding="utf-8"))
        assert config["provider"] == "openai"
        assert config["api_config"]["api_key_env"] == "XAI_API_KEY"

    def test_ollama_no_auth(self, config_dir: str) -> None:
        setup_provider("ollama", config_dir, models=["llama3.1:8b"])
        models_dir = Path(config_dir) / "models"
        files = list(models_dir.glob("*.json"))
        config = json.loads(files[0].read_text(encoding="utf-8"))
        assert "auth_header" not in config["api_config"]
        assert "auth_format" not in config["api_config"]
        assert "api_key" not in config["api_config"]
        assert "api_key_env" not in config["api_config"]

    def test_unknown_provider_raises(self, config_dir: str) -> None:
        with pytest.raises(DomainValidationError, match="Unknown provider"):
            setup_provider("nonexistent", config_dir)

    def test_configs_loadable_by_model_config_loader(self, config_dir: str) -> None:
        """Written configs must be parseable by ModelConfigLoader."""
        setup_provider("openai", config_dir)
        loader = ModelConfigLoader(config_dir)
        configs = loader.list_all()
        assert len(configs) == 3
        providers = {c.provider for c in configs}
        assert "openai" in providers

    @pytest.mark.parametrize("name", list(PROVIDERS.keys()))
    def test_all_providers_produce_valid_configs(self, config_dir: str, name: str) -> None:
        """Every registered provider produces configs loadable by ModelConfigLoader."""
        result = setup_provider(name, config_dir)
        created_count = result["created_count"]
        assert isinstance(created_count, int) and created_count >= 1
        loader = ModelConfigLoader(config_dir)
        configs = loader.list_all()
        assert len(configs) == result["created_count"]


class TestSetupCustom:
    """setup_custom creates a single config file."""

    def test_creates_config(self, config_dir: str) -> None:
        result = setup_custom(config_dir, provider="myapi", model="my-model-v1")
        assert result["created_count"] == 1
        assert result["skipped_count"] == 0

    def test_idempotent(self, config_dir: str) -> None:
        setup_custom(config_dir, provider="myapi", model="my-model-v1")
        result = setup_custom(config_dir, provider="myapi", model="my-model-v1")
        assert result["created_count"] == 0
        assert result["skipped_count"] == 1

    def test_custom_fields(self, config_dir: str) -> None:
        setup_custom(
            config_dir,
            provider="myapi",
            model="my-model",
            display_name="My Model",
            description="Custom model",
            endpoint="https://example.com/v1/chat",
            base_url="https://example.com/v1",
            auth_header="Authorization",
            auth_format="Bearer {api_key}",
            api_key_env="MY_KEY",
            timeout=60,
        )
        models_dir = Path(config_dir) / "models"
        files = list(models_dir.glob("*.json"))
        assert len(files) == 1
        config = json.loads(files[0].read_text(encoding="utf-8"))
        assert config["provider"] == "myapi"
        assert config["model"] == "my-model"
        assert config["display_name"] == "My Model"
        assert config["api_config"]["endpoint"] == "https://example.com/v1/chat"
        assert config["api_config"]["api_key_env"] == "MY_KEY"

    def test_loadable_by_model_config_loader(self, config_dir: str) -> None:
        setup_custom(
            config_dir,
            provider="myapi",
            model="my-model",
            endpoint="https://example.com/v1/chat",
        )
        loader = ModelConfigLoader(config_dir)
        configs = loader.list_all()
        assert len(configs) == 1
        assert configs[0].provider == "myapi"
        assert configs[0].model == "my-model"
