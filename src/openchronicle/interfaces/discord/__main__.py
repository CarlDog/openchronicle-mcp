"""Entry point: python -m openchronicle.interfaces.discord"""

from __future__ import annotations

import logging
import sys

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.interfaces.discord.bot import DiscordBot
from openchronicle.interfaces.discord.commands import setup_commands
from openchronicle.interfaces.discord.config import DiscordConfig


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    try:
        config = DiscordConfig.from_env()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    container = CoreContainer()
    bot = DiscordBot(container, config)

    async def on_ready_with_commands() -> None:
        await setup_commands(bot)
        await bot.__class__.on_ready(bot)

    bot.on_ready = on_ready_with_commands  # type: ignore[method-assign]

    bot.run(config.token, log_handler=None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
