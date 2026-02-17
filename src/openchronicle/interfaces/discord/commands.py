"""Discord slash commands — Cog for OpenChronicle bot operations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from openchronicle.core.application.use_cases import add_memory, convo_mode
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.interfaces.discord.formatting import format_explain, format_turn_summary

if TYPE_CHECKING:
    from openchronicle.interfaces.discord.bot import DiscordBot

logger = logging.getLogger(__name__)


class OpenChronicleCog(commands.Cog):
    """Slash commands for OpenChronicle Discord bot."""

    def __init__(self, bot: DiscordBot) -> None:
        self.bot = bot

    @app_commands.command(name="newconvo", description="Start a new conversation")
    async def newconvo(self, interaction: discord.Interaction) -> None:
        """Clear session mapping — next message auto-creates a new conversation."""
        discord_user_id = str(interaction.user.id)
        self.bot.sessions.clear(discord_user_id)
        await interaction.response.send_message("New conversation started. Your next message begins a fresh chat.")

    @app_commands.command(name="remember", description="Save something to memory")
    @app_commands.describe(text="The text to remember")
    async def remember(self, interaction: discord.Interaction, text: str) -> None:
        """Save text as an OC memory item linked to the user's conversation."""
        discord_user_id = str(interaction.user.id)
        conversation_id = self.bot.sessions.get_conversation_id(discord_user_id)

        if conversation_id is None:
            await interaction.response.send_message("No active conversation. Send a message first.")
            return

        conversation = self.bot.container.storage.get_conversation(conversation_id)
        if conversation is None:
            await interaction.response.send_message("Conversation not found. Send a message to start a new one.")
            self.bot.sessions.clear(discord_user_id)
            return

        try:
            item = add_memory.execute(
                store=self.bot.container.storage,
                emit_event=self.bot.container.event_logger.append,
                item=MemoryItem(
                    content=text,
                    conversation_id=conversation_id,
                    project_id=conversation.project_id,
                    source="discord",
                ),
            )
            await interaction.response.send_message(f"Remembered: {text[:100]}{'...' if len(text) > 100 else ''}")
            logger.info("Memory saved: %s", item.id)
        except Exception as exc:
            logger.exception("Error saving memory")
            await interaction.response.send_message(f"Failed to save memory: {exc}")

    @app_commands.command(name="forget", description="Delete a memory item by ID")
    @app_commands.describe(memory_id="The memory ID to delete")
    async def forget(self, interaction: discord.Interaction, memory_id: str) -> None:
        """Delete a memory item by its ID."""
        item = self.bot.container.storage.get_memory(memory_id)
        if item is None:
            await interaction.response.send_message(f"Memory item not found: {memory_id}")
            return

        self.bot.container.storage.delete_memory(memory_id)
        await interaction.response.send_message(f"Deleted memory item: {memory_id}")

    @app_commands.command(name="explain", description="Show details about the last conversation turn")
    async def explain(self, interaction: discord.Interaction) -> None:
        """Show provider, model, routing, and memory info for the last turn."""
        discord_user_id = str(interaction.user.id)
        conversation_id = self.bot.sessions.get_conversation_id(discord_user_id)

        if conversation_id is None:
            await interaction.response.send_message("No active conversation.")
            return

        turns = self.bot.container.storage.list_turns(conversation_id, limit=1)
        if not turns:
            await interaction.response.send_message("No turns in this conversation yet.")
            return

        turn = turns[-1]
        text = format_explain(
            provider=turn.provider,
            model=turn.model,
            routing_reasons=turn.routing_reasons,
            memory_count=len(turn.memory_written_ids),
            tokens_used=None,  # Token data not stored on Turn
        )
        await interaction.response.send_message(text)

    @app_commands.command(name="mode", description="Change conversation mode")
    @app_commands.describe(mode="The mode to set (general, persona, story)")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="general", value="general"),
            app_commands.Choice(name="persona", value="persona"),
            app_commands.Choice(name="story", value="story"),
        ]
    )
    async def mode(self, interaction: discord.Interaction, mode: app_commands.Choice[str]) -> None:
        """Change the conversation mode."""
        discord_user_id = str(interaction.user.id)
        conversation_id = self.bot.sessions.get_conversation_id(discord_user_id)

        if conversation_id is None:
            await interaction.response.send_message("No active conversation.")
            return

        try:
            result = convo_mode.set_mode(self.bot.container.storage, conversation_id, mode.value)
            await interaction.response.send_message(f"Conversation mode set to: **{result}**")
        except ValueError as exc:
            await interaction.response.send_message(str(exc))

    @app_commands.command(name="history", description="Show recent conversation turns")
    @app_commands.describe(limit="Number of turns to show (default: 5)")
    async def history(self, interaction: discord.Interaction, limit: int = 5) -> None:
        """Show recent turns from the current conversation."""
        discord_user_id = str(interaction.user.id)
        conversation_id = self.bot.sessions.get_conversation_id(discord_user_id)

        if conversation_id is None:
            await interaction.response.send_message("No active conversation.")
            return

        turns = self.bot.container.storage.list_turns(conversation_id, limit=limit)
        if not turns:
            await interaction.response.send_message("No turns in this conversation yet.")
            return

        lines = [format_turn_summary(t.turn_index, t.user_text, t.assistant_text) for t in turns]
        text = "\n\n".join(lines)
        if len(text) > 1950:
            text = text[:1947] + "..."
        await interaction.response.send_message(text)


async def setup_commands(bot: DiscordBot) -> None:
    """Register slash commands with the bot."""
    cog = OpenChronicleCog(bot)
    await bot.add_cog(cog)

    if bot.config.guild_ids:
        for guild_id in bot.config.guild_ids:
            guild = discord.Object(id=guild_id)
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
    else:
        await bot.tree.sync()
