"""Discord message formatting utilities.

Handles the 2000-character Discord message limit and builds embeds.
"""

from __future__ import annotations

DISCORD_MAX_LENGTH = 2000
# Leave room for potential formatting overhead
SPLIT_THRESHOLD = DISCORD_MAX_LENGTH - 50


def split_message(text: str, max_length: int = SPLIT_THRESHOLD) -> list[str]:
    """Split a message into chunks that fit within Discord's character limit.

    Splitting priority:
    1. Paragraph boundaries (double newline)
    2. Line boundaries (single newline)
    3. Sentence boundaries (". ")
    4. Hard split at max_length
    """
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        # Try splitting at paragraph boundary
        split_pos = _find_split_point(remaining, max_length, "\n\n")
        if split_pos == -1:
            # Try line boundary
            split_pos = _find_split_point(remaining, max_length, "\n")
        if split_pos == -1:
            # Try sentence boundary
            split_pos = _find_split_point(remaining, max_length, ". ")
        if split_pos == -1:
            # Hard split
            split_pos = max_length

        chunk = remaining[:split_pos].rstrip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_pos:].lstrip()

    return chunks if chunks else [text]


def _find_split_point(text: str, max_length: int, delimiter: str) -> int:
    """Find the last occurrence of delimiter within max_length chars.

    Returns -1 if no suitable split point found.
    """
    search_region = text[:max_length]
    pos = search_region.rfind(delimiter)
    if pos <= 0:
        return -1
    return pos + len(delimiter)


def format_error(error: Exception) -> str:
    """Format an error for Discord display — no stack traces."""
    error_type = type(error).__name__
    message = str(error)
    if not message:
        return f"Something went wrong ({error_type})."
    # Truncate very long error messages
    if len(message) > 500:
        message = message[:497] + "..."
    return f"**Error:** {message}"


def format_turn_summary(
    turn_index: int,
    user_text: str,
    assistant_text: str,
    *,
    max_preview: int = 100,
) -> str:
    """Format a single turn for /history display."""
    user_preview = _truncate(user_text, max_preview)
    assistant_preview = _truncate(assistant_text, max_preview)
    return f"**Turn {turn_index}**\n> **You:** {user_preview}\n> **Bot:** {assistant_preview}"


def format_explain(
    provider: str | None,
    model: str | None,
    routing_reasons: list[str] | None,
    memory_count: int,
    tokens_used: int | None,
) -> str:
    """Format explain data as a readable Discord message."""
    lines = ["**Last Turn Details**"]
    lines.append(f"**Provider:** {provider or 'unknown'}")
    lines.append(f"**Model:** {model or 'unknown'}")
    if routing_reasons:
        lines.append(f"**Routing:** {', '.join(routing_reasons)}")
    lines.append(f"**Memory items retrieved:** {memory_count}")
    if tokens_used is not None:
        lines.append(f"**Tokens used:** {tokens_used}")
    return "\n".join(lines)


def _truncate(text: str, max_length: int) -> str:
    """Truncate text with ellipsis if needed."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
