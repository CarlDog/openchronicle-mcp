"""Entry point: python -m openchronicle.interfaces.discord"""

from __future__ import annotations

import logging
import sys

from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.discord.bot import DiscordBot
from openchronicle.interfaces.discord.commands import setup_commands
from openchronicle.interfaces.discord.config import DiscordConfig
from openchronicle.interfaces.discord.pid_file import PidFile


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    container = CoreContainer()

    try:
        config = DiscordConfig.from_env(file_config=container.file_configs.get("discord"))
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    pid = PidFile()
    force = "--force" in sys.argv
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

    pid.acquire()
    try:
        bot.run(config.token, log_handler=None)
    finally:
        pid.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
