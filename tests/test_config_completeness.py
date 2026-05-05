"""Hygiene tests: config loaders exist, defaults stay in sync, file_config wiring works."""

from __future__ import annotations

import inspect

import pytest

from openchronicle.core.application.config.budget_config import load_budget_policy
from openchronicle.core.application.config.settings import (
    ConversationSettings,
    load_conversation_settings,
    load_moe_settings,
    load_privacy_outbound_settings,
    load_router_assist_settings,
    load_telemetry_settings,
)
from openchronicle.core.application.routing.pool_config import load_pool_config

# ---------------------------------------------------------------------------
# A. Config sections have working loaders
# ---------------------------------------------------------------------------


class TestConfigLoadersExist:
    """Each loader instantiates with an empty dict and returns a valid object."""

    def test_privacy_outbound_loader(self) -> None:
        settings = load_privacy_outbound_settings({})
        assert settings is not None

    def test_telemetry_loader(self) -> None:
        settings = load_telemetry_settings({})
        assert settings is not None

    def test_router_assist_loader(self) -> None:
        settings = load_router_assist_settings({})
        assert settings is not None

    def test_conversation_loader(self) -> None:
        settings = load_conversation_settings({})
        assert settings is not None

    def test_conversation_loader_with_none(self) -> None:
        settings = load_conversation_settings(None)
        assert settings is not None

    def test_budget_policy_loader(self) -> None:
        policy = load_budget_policy({})
        assert policy is not None

    def test_budget_policy_loader_with_none(self) -> None:
        policy = load_budget_policy(None)
        assert policy is not None

    def test_pool_config_loader(self) -> None:
        config = load_pool_config({})
        assert config is not None

    def test_pool_config_loader_with_none(self) -> None:
        config = load_pool_config(None)
        assert config is not None

    def test_moe_config_loader(self) -> None:
        settings = load_moe_settings({})
        assert settings is not None

    def test_moe_config_loader_with_none(self) -> None:
        settings = load_moe_settings(None)
        assert settings is not None


# ---------------------------------------------------------------------------
# B. ConversationSettings defaults match ask_conversation.prepare_ask()
# ---------------------------------------------------------------------------


class TestConversationSettingsMatchPrepareAsk:
    """Defaults in ConversationSettings must equal prepare_ask() parameter defaults.

    If someone changes a default in one place but not the other, this test
    catches the drift immediately.
    """

    @pytest.fixture()
    def prepare_ask_defaults(self) -> dict[str, object]:
        from openchronicle.core.application.use_cases.ask_conversation import (
            prepare_ask,
        )

        sig = inspect.signature(prepare_ask)
        return {
            name: param.default
            for name, param in sig.parameters.items()
            if param.default is not inspect.Parameter.empty
        }

    @pytest.fixture()
    def settings_defaults(self) -> ConversationSettings:
        return ConversationSettings()

    def test_temperature(
        self,
        prepare_ask_defaults: dict[str, object],
        settings_defaults: ConversationSettings,
    ) -> None:
        assert settings_defaults.temperature == prepare_ask_defaults["temperature"]

    def test_max_output_tokens(
        self,
        prepare_ask_defaults: dict[str, object],
        settings_defaults: ConversationSettings,
    ) -> None:
        assert settings_defaults.max_output_tokens == prepare_ask_defaults["max_output_tokens"]

    def test_top_k_memory(
        self,
        prepare_ask_defaults: dict[str, object],
        settings_defaults: ConversationSettings,
    ) -> None:
        assert settings_defaults.top_k_memory == prepare_ask_defaults["top_k_memory"]

    def test_last_n(
        self,
        prepare_ask_defaults: dict[str, object],
        settings_defaults: ConversationSettings,
    ) -> None:
        assert settings_defaults.last_n == prepare_ask_defaults["last_n"]

    def test_include_pinned_memory(
        self,
        prepare_ask_defaults: dict[str, object],
        settings_defaults: ConversationSettings,
    ) -> None:
        assert settings_defaults.include_pinned_memory == prepare_ask_defaults["include_pinned_memory"]


