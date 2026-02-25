"""Discord bot — driving adapter for OpenChronicle conversations.

Same architectural role as CLI chat: message → container.orchestrator → reply.
Runs as a separate process from `oc serve` but shares the same SQLite database
(WAL mode handles concurrent access safely).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from openchronicle.core.application.use_cases import ask_conversation, create_conversation
from openchronicle.interfaces.discord.config import DiscordConfig
from openchronicle.interfaces.discord.formatting import format_error, split_message
from openchronicle.interfaces.discord.session import SessionManager

if TYPE_CHECKING:
    from openchronicle.core.infrastructure.wiring.container import CoreContainer

logger = logging.getLogger(__name__)


class DiscordBot(commands.Bot):
    """OpenChronicle Discord bot.

    Extends commands.Bot (not Client) to support slash command Cogs.
    Injects CoreContainer directly (hexagonal driving adapter, same as CLI).
    Each message triggers the full prepare_ask → stream → finalize pipeline.
    """

    def __init__(self, container: CoreContainer, config: DiscordConfig) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.container = container
        self.config = config
        self.sessions = SessionManager(config.session_store_path)

    async def on_ready(self) -> None:
        logger.info("Discord bot connected as %s", self.user)

    async def on_message(self, message: discord.Message) -> None:
        # Ignore own messages and other bots
        if message.author == self.user or message.author.bot:
            return

        # Channel allowlist check
        if self.config.channel_allowlist and message.channel.id not in self.config.channel_allowlist:
            return

        prompt = message.content.strip()
        if not prompt:
            return

        discord_user_id = str(message.author.id)

        try:
            conversation_id = await self._resolve_conversation(discord_user_id)
            response_text = await self._process_turn(conversation_id, prompt)

            for chunk in split_message(response_text):
                await message.reply(chunk, mention_author=False)

        except Exception as exc:
            logger.exception("Error processing message from %s", message.author)
            await message.reply(format_error(exc), mention_author=False)

    async def _resolve_conversation(self, discord_user_id: str) -> str:
        """Get or create an OC conversation for this Discord user."""
        conversation_id = self.sessions.get_conversation_id(discord_user_id)
        if conversation_id is not None:
            # Verify conversation still exists
            convo = self.container.storage.get_conversation(conversation_id)
            if convo is not None:
                return conversation_id

        # Create new conversation
        conversation = create_conversation.execute(
            storage=self.container.storage,
            convo_store=self.container.storage,
            emit_event=self.container.event_logger.append,
            title=self.config.conversation_title,
        )
        self.sessions.set_conversation_id(discord_user_id, conversation.id)
        return conversation.id

    async def _process_turn(self, conversation_id: str, prompt: str) -> str:
        """Run the full conversation turn pipeline (prepare → stream → finalize)."""
        from openchronicle.core.application.services.llm_execution import stream_with_route

        cs = self.container.conversation_settings
        ctx = await ask_conversation.prepare_ask(
            convo_store=self.container.storage,
            memory_store=self.container.storage,
            emit_event=self.container.event_logger.append,
            conversation_id=conversation_id,
            prompt_text=prompt,
            interaction_router=self.container.interaction_router,
            router_policy=self.container.router_policy,
            last_n=cs.last_n,
            top_k_memory=cs.top_k_memory,
            include_pinned_memory=cs.include_pinned_memory,
            max_output_tokens=cs.max_output_tokens,
            temperature=cs.temperature,
            privacy_gate=getattr(self.container, "privacy_gate", None),
            privacy_settings=getattr(self.container, "privacy_settings", None),
            embedding_service=self.container.embedding_service,
        )

        collected: list[str] = []
        async for chunk in stream_with_route(
            self.container.llm,
            ctx.route_decision,
            ctx.messages[:-1] + [{"role": "user", "content": ctx.effective_prompt}],
            max_output_tokens=ctx.max_output_tokens,
            temperature=ctx.temperature,
        ):
            if chunk.text:
                collected.append(chunk.text)

        assistant_text = "".join(collected)

        await ask_conversation.finalize_turn(
            ctx=ctx,
            assistant_text=assistant_text,
            response=None,
            convo_store=self.container.storage,
            storage=self.container.storage,
            emit_event=self.container.event_logger.append,
        )

        return assistant_text
