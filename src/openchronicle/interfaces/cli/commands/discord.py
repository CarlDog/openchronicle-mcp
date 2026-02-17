"""CLI commands for the Discord bot (oc discord start)."""

from __future__ import annotations

import argparse
import logging
import sys

from openchronicle.core.application.runtime.container import CoreContainer


def cmd_discord(args: argparse.Namespace, container: CoreContainer) -> int:
    """Dispatch discord subcommands."""
    sub = getattr(args, "discord_command", None)
    if sub == "start":
        return _cmd_discord_start(args, container)
    print("Usage: oc discord start")
    return 0


def _cmd_discord_start(args: argparse.Namespace, container: CoreContainer) -> int:
    """Start the Discord bot (long-running)."""
    try:
        import discord  # noqa: F401
    except ImportError:
        print("discord.py is not installed. Install with: pip install -e '.[discord]'", file=sys.stderr)
        return 1

    from openchronicle.interfaces.discord.bot import DiscordBot
    from openchronicle.interfaces.discord.commands import setup_commands
    from openchronicle.interfaces.discord.config import DiscordConfig

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    try:
        config = DiscordConfig.from_env()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    bot = DiscordBot(container, config)

    async def on_ready_with_commands() -> None:
        await setup_commands(bot)
        await bot.__class__.on_ready(bot)

    bot.on_ready = on_ready_with_commands  # type: ignore[method-assign]

    print("Starting Discord bot...")
    bot.run(config.token, log_handler=None)
    return 0
