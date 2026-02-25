"""Shared context formatting functions used by prepare_ask and assemble_context."""

from __future__ import annotations

from datetime import UTC, datetime

from openchronicle.core.domain.models.conversation import Conversation, Turn
from openchronicle.core.domain.models.memory_item import MemoryItem

_CONTENT_SNIPPET_MAX = 300


def format_memory_messages(
    pinned: list[MemoryItem],
    relevant: list[MemoryItem],
    include_pinned: bool,
) -> str | None:
    """Format memory items into system message text. None if empty."""
    if not pinned and not relevant:
        return None

    memory_lines: list[str] = []
    if include_pinned and pinned:
        memory_lines.append("Pinned memory:")
        for item in pinned:
            content_snippet = (
                item.content
                if len(item.content) <= _CONTENT_SNIPPET_MAX
                else item.content[:_CONTENT_SNIPPET_MAX] + "..."
            )
            tags_str = ",".join(item.tags)
            memory_lines.append(f"- {item.id} | tags=[{tags_str}] | {content_snippet}")
        memory_lines.append("")

    memory_lines.append("Relevant memory:")
    for item in relevant:
        content_snippet = (
            item.content if len(item.content) <= _CONTENT_SNIPPET_MAX else item.content[:_CONTENT_SNIPPET_MAX] + "..."
        )
        tags_str = ",".join(item.tags)
        memory_lines.append(f"- {item.id} | tags=[{tags_str}] | {content_snippet}")

    return "\n".join(memory_lines)


def format_time_context(
    prior_turns: list[Turn],
    conversation: Conversation,
) -> tuple[str, datetime, int]:
    """Return (message_text, ref_time, delta_seconds)."""
    now = datetime.now(UTC)
    ref_time = prior_turns[-1].created_at if prior_turns else conversation.created_at
    delta_seconds = int((now - ref_time).total_seconds())
    time_ctx_msg = (
        f"Current time: {now.isoformat()}. "
        f"Last interaction: {ref_time.isoformat()}. "
        f"Seconds since last interaction: {delta_seconds}."
    )
    return time_ctx_msg, ref_time, delta_seconds


def build_turn_messages(
    prior_turns: list[Turn],
    prompt_text: str,
) -> list[dict[str, str]]:
    """Convert prior turns + current prompt into [{role, content}]."""
    messages: list[dict[str, str]] = []
    for turn in prior_turns:
        messages.append({"role": "user", "content": turn.user_text})
        messages.append({"role": "assistant", "content": turn.assistant_text})
    messages.append({"role": "user", "content": prompt_text})
    return messages
