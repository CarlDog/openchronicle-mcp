"""Tests for Discord bot configuration loading."""

from __future__ import annotations

import pytest

from openchronicle.interfaces.discord.config import DiscordConfig, _parse_int_csv


class TestParseIntCsv:
    def test_empty_string(self) -> None:
        assert _parse_int_csv("") == []

    def test_whitespace_only(self) -> None:
        assert _parse_int_csv("   ") == []

    def test_single_value(self) -> None:
        assert _parse_int_csv("123") == [123]

    def test_multiple_values(self) -> None:
        assert _parse_int_csv("1,2,3") == [1, 2, 3]

    def test_whitespace_around_values(self) -> None:
        assert _parse_int_csv(" 1 , 2 , 3 ") == [1, 2, 3]

    def test_trailing_comma(self) -> None:
        assert _parse_int_csv("1,2,") == [1, 2]

    def test_invalid_value(self) -> None:
        with pytest.raises(ValueError, match="Invalid integer"):
            _parse_int_csv("1,abc,3")


class TestDiscordConfig:
    def test_missing_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
        with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN"):
            DiscordConfig.from_env()

    def test_empty_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "   ")
        with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN"):
            DiscordConfig.from_env()

    def test_minimal_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token")
        monkeypatch.delenv("OC_DISCORD_GUILD_IDS", raising=False)
        monkeypatch.delenv("OC_DISCORD_CHANNEL_ALLOWLIST", raising=False)
        monkeypatch.delenv("OC_DISCORD_SESSION_STORE_PATH", raising=False)

        config = DiscordConfig.from_env()
        assert config.token == "test-token"
        assert config.guild_ids == []
        assert config.channel_allowlist == []
        assert config.session_store_path == "data/discord_sessions.json"

    def test_full_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token")
        monkeypatch.setenv("OC_DISCORD_GUILD_IDS", "111,222")
        monkeypatch.setenv("OC_DISCORD_CHANNEL_ALLOWLIST", "333,444,555")
        monkeypatch.setenv("OC_DISCORD_SESSION_STORE_PATH", "/tmp/sessions.json")

        config = DiscordConfig.from_env()
        assert config.token == "test-token"
        assert config.guild_ids == [111, 222]
        assert config.channel_allowlist == [333, 444, 555]
        assert config.session_store_path == "/tmp/sessions.json"

    def test_frozen(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token")
        config = DiscordConfig.from_env()
        with pytest.raises(AttributeError):
            config.token = "changed"  # type: ignore[misc]
