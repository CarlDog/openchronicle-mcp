"""Hygiene tests: config loaders exist, defaults stay in sync, file_config wiring works."""

from __future__ import annotations

import inspect

import pytest

from openchronicle.core.infrastructure.config.settings import (
    ConversationSettings,
    load_conversation_settings,
    load_privacy_outbound_settings,
    load_router_assist_settings,
    load_telemetry_settings,
)

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


# ---------------------------------------------------------------------------
# C. DiscordConfig loads from file_config
# ---------------------------------------------------------------------------


class TestDiscordConfigFileConfig:
    """DiscordConfig.from_env() picks up file_config values for all fields."""

    @pytest.fixture(autouse=True)
    def _set_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token")
        # Clear any env overrides so file_config wins
        for var in (
            "OC_DISCORD_GUILD_IDS",
            "OC_DISCORD_CHANNEL_ALLOWLIST",
            "OC_DISCORD_SESSION_STORE_PATH",
            "OC_DISCORD_CONVERSATION_TITLE",
            "OC_DISCORD_HISTORY_LIMIT",
        ):
            monkeypatch.delenv(var, raising=False)

    def test_file_config_guild_ids(self) -> None:
        from openchronicle.interfaces.discord.config import DiscordConfig

        config = DiscordConfig.from_env(file_config={"guild_ids": [111, 222]})
        assert config.guild_ids == [111, 222]

    def test_file_config_channel_allowlist(self) -> None:
        from openchronicle.interfaces.discord.config import DiscordConfig

        config = DiscordConfig.from_env(file_config={"channel_allowlist": [333]})
        assert config.channel_allowlist == [333]

    def test_file_config_session_store_path(self) -> None:
        from openchronicle.interfaces.discord.config import DiscordConfig

        config = DiscordConfig.from_env(file_config={"session_store_path": "/custom/path.json"})
        assert config.session_store_path == "/custom/path.json"

    def test_file_config_conversation_title(self) -> None:
        from openchronicle.interfaces.discord.config import DiscordConfig

        config = DiscordConfig.from_env(file_config={"conversation_title": "My Bot"})
        assert config.conversation_title == "My Bot"

    def test_file_config_history_limit(self) -> None:
        from openchronicle.interfaces.discord.config import DiscordConfig

        config = DiscordConfig.from_env(file_config={"history_limit": 20})
        assert config.history_limit == 20

    def test_env_overrides_file_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from openchronicle.interfaces.discord.config import DiscordConfig

        monkeypatch.setenv("OC_DISCORD_CONVERSATION_TITLE", "Env Title")
        config = DiscordConfig.from_env(file_config={"conversation_title": "File Title"})
        assert config.conversation_title == "Env Title"

    def test_token_from_file_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from openchronicle.interfaces.discord.config import DiscordConfig

        monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
        config = DiscordConfig.from_env(file_config={"token": "file-token"})
        assert config.token == "file-token"

    def test_env_token_overrides_file_token(self) -> None:
        from openchronicle.interfaces.discord.config import DiscordConfig

        config = DiscordConfig.from_env(file_config={"token": "file-token"})
        assert config.token == "test-token"  # env wins

    def test_defaults_without_file_config(self) -> None:
        from openchronicle.interfaces.discord.config import DiscordConfig

        config = DiscordConfig.from_env(file_config={})
        assert config.guild_ids == []
        assert config.channel_allowlist == []
        assert config.session_store_path == "data/discord_sessions.json"
        assert config.conversation_title == "Discord chat"
        assert config.history_limit == 5
