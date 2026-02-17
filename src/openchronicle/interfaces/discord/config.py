"""Discord bot configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DiscordConfig:
    """Immutable Discord bot configuration loaded from env vars.

    Required:
        DISCORD_BOT_TOKEN — Bot authentication token.

    Optional:
        OC_DISCORD_GUILD_IDS — CSV guild IDs for slash command sync.
        OC_DISCORD_CHANNEL_ALLOWLIST — CSV channel IDs (empty = all channels).
        OC_DISCORD_SESSION_STORE_PATH — Path for session JSON file.
    """

    token: str
    guild_ids: list[int] = field(default_factory=list)
    channel_allowlist: list[int] = field(default_factory=list)
    session_store_path: str = "data/discord_sessions.json"

    @classmethod
    def from_env(cls) -> DiscordConfig:
        """Load config from environment variables.

        Raises:
            ValueError: If DISCORD_BOT_TOKEN is not set or empty.
        """
        token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
        if not token:
            raise ValueError("DISCORD_BOT_TOKEN environment variable is required but not set")

        guild_ids = _parse_int_csv(os.environ.get("OC_DISCORD_GUILD_IDS", ""))
        channel_allowlist = _parse_int_csv(os.environ.get("OC_DISCORD_CHANNEL_ALLOWLIST", ""))
        session_store_path = os.environ.get("OC_DISCORD_SESSION_STORE_PATH", "data/discord_sessions.json").strip()

        return cls(
            token=token,
            guild_ids=guild_ids,
            channel_allowlist=channel_allowlist,
            session_store_path=session_store_path,
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
