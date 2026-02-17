"""Discord bot configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DiscordConfig:
    """Immutable Discord bot configuration loaded from env vars and file config.

    Required:
        DISCORD_BOT_TOKEN (env var) or token (in core.json discord section).

    Optional (env var > file config > default):
        OC_DISCORD_GUILD_IDS — CSV guild IDs for slash command sync.
        OC_DISCORD_CHANNEL_ALLOWLIST — CSV channel IDs (empty = all channels).
        OC_DISCORD_SESSION_STORE_PATH — Path for session JSON file.
        OC_DISCORD_CONVERSATION_TITLE — Default title for new Discord conversations.
        OC_DISCORD_HISTORY_LIMIT — Default number of turns shown by /history.
    """

    token: str
    guild_ids: list[int] = field(default_factory=list)
    channel_allowlist: list[int] = field(default_factory=list)
    session_store_path: str = "data/discord_sessions.json"
    conversation_title: str = "Discord chat"
    history_limit: int = 5

    @classmethod
    def from_env(cls, file_config: dict[str, object] | None = None) -> DiscordConfig:
        """Load config from environment variables with file_config fallback.

        Raises:
            ValueError: If bot token is not found in env var or file config.
        """
        fc = file_config or {}
        token = os.environ.get("DISCORD_BOT_TOKEN", "").strip() or _str_or_default(fc.get("token"), "")
        if not token:
            raise ValueError(
                "Bot token not found. Set DISCORD_BOT_TOKEN env var or add"
                ' "token" to the discord section in core.json'
            )

        guild_ids = _resolve_int_list("OC_DISCORD_GUILD_IDS", fc.get("guild_ids"))
        channel_allowlist = _resolve_int_list("OC_DISCORD_CHANNEL_ALLOWLIST", fc.get("channel_allowlist"))

        session_store_path = os.environ.get("OC_DISCORD_SESSION_STORE_PATH", "").strip() or _str_or_default(
            fc.get("session_store_path"), "data/discord_sessions.json"
        )
        conversation_title = os.environ.get("OC_DISCORD_CONVERSATION_TITLE", "").strip() or _str_or_default(
            fc.get("conversation_title"), "Discord chat"
        )
        history_limit_env = os.environ.get("OC_DISCORD_HISTORY_LIMIT", "").strip()
        history_limit_file = fc.get("history_limit")
        if history_limit_env:
            history_limit = int(history_limit_env)
        elif isinstance(history_limit_file, int):
            history_limit = history_limit_file
        else:
            history_limit = 5

        return cls(
            token=token,
            guild_ids=guild_ids,
            channel_allowlist=channel_allowlist,
            session_store_path=session_store_path,
            conversation_title=conversation_title,
            history_limit=history_limit,
        )


def _parse_int_csv(value: str) -> list[int]:
    """Parse a CSV string of integers, ignoring blanks and whitespace."""
    if not value or not value.strip():
        return []
    result: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if part:
            try:
                result.append(int(part))
            except ValueError:
                raise ValueError(f"Invalid integer in CSV: {part!r}") from None
    return result


def _resolve_int_list(env_name: str, file_value: object) -> list[int]:
    """Resolve an int list: env var (CSV) > file_config (list) > empty."""
    env_val = os.environ.get(env_name, "").strip()
    if env_val:
        return _parse_int_csv(env_val)
    if isinstance(file_value, list):
        return [int(v) for v in file_value]
    return []


def _str_or_default(value: object, default: str) -> str:
    """Return value as str if truthy, else default."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default
