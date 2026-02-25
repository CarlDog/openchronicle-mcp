"""CLI commands for the Discord bot (oc discord start)."""

from __future__ import annotations

import argparse
import logging
import sys

from openchronicle.core.infrastructure.wiring.container import CoreContainer


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
    from openchronicle.interfaces.discord.pid_file import PidFile

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    try:
        # Merge RuntimePaths-resolved session path into file_config so OC_DATA_DIR
        # propagates to Discord config (per-path env var still wins in from_env).
        discord_fc = dict(container.file_configs.get("discord") or {})
        if "session_store_path" not in discord_fc:
            discord_fc["session_store_path"] = str(container.paths.discord_session_path)
        config = DiscordConfig.from_env(file_config=discord_fc)
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    pid = PidFile(path=str(container.paths.discord_pid_path))
    force = getattr(args, "force", False)
    if not force and pid.is_alive():
        print(
            f"Bot already running (PID {pid.read_pid()}). Use --force to override.",
            file=sys.stderr,
        )
        return 1

    bot = DiscordBot(container, config)

    async def on_ready_with_commands() -> None:
        await setup_commands(bot)
        await bot.__class__.on_ready(bot)

    bot.on_ready = on_ready_with_commands  # type: ignore[method-assign]

    print("Starting Discord bot...")
    pid.acquire()
    try:
        bot.run(config.token, log_handler=None)
    finally:
        pid.release()
    return 0
