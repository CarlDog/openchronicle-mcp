"""Tests for Discord message formatting utilities."""

from __future__ import annotations

from openchronicle.interfaces.discord.formatting import (
    format_error,
    format_explain,
    format_turn_summary,
    split_message,
)


class TestSplitMessage:
    def test_short_message_not_split(self) -> None:
        result = split_message("Hello, world!")
        assert result == ["Hello, world!"]

    def test_exact_limit_not_split(self) -> None:
        text = "x" * 1950
        result = split_message(text)
        assert result == [text]

    def test_splits_at_paragraph_boundary(self) -> None:
        part1 = "A" * 1000
        part2 = "B" * 1000
        text = f"{part1}\n\n{part2}"
        result = split_message(text)
        assert len(result) == 2
        assert result[0] == part1
        assert result[1] == part2

    def test_splits_at_line_boundary(self) -> None:
        part1 = "A" * 1000
        part2 = "B" * 1000
        text = f"{part1}\n{part2}"
        result = split_message(text)
        assert len(result) == 2

    def test_splits_at_sentence_boundary(self) -> None:
        part1 = "A" * 1000
        part2 = "B" * 1000
        text = f"{part1}. {part2}"
        result = split_message(text)
        assert len(result) == 2

    def test_hard_split_when_no_boundary(self) -> None:
        text = "A" * 4000
        result = split_message(text)
        assert len(result) >= 2
        assert all(len(chunk) <= 1950 for chunk in result)

    def test_empty_string(self) -> None:
        result = split_message("")
        assert result == [""]

    def test_multiple_splits(self) -> None:
        text = "\n\n".join(["X" * 800] * 5)
        result = split_message(text)
        assert len(result) >= 3
        assert all(len(chunk) <= 1950 for chunk in result)

    def test_custom_max_length(self) -> None:
        text = "Hello world. How are you. Fine thanks."
        result = split_message(text, max_length=20)
        assert len(result) >= 2
        assert all(len(chunk) <= 20 for chunk in result)


class TestFormatError:
    def test_basic_error(self) -> None:
        result = format_error(ValueError("something broke"))
        assert "something broke" in result
        assert "**Error:**" in result

    def test_empty_message(self) -> None:
        result = format_error(RuntimeError())
        assert "RuntimeError" in result

    def test_long_message_truncated(self) -> None:
        result = format_error(ValueError("x" * 1000))
        assert len(result) <= 520
        assert result.endswith("...")


class TestFormatTurnSummary:
    def test_basic_format(self) -> None:
        result = format_turn_summary(0, "Hello", "Hi there!")
        assert "Turn 0" in result
        assert "Hello" in result
        assert "Hi there!" in result

    def test_truncation(self) -> None:
        result = format_turn_summary(1, "x" * 200, "y" * 200, max_preview=50)
        assert "..." in result


class TestFormatExplain:
    def test_full_explain(self) -> None:
        result = format_explain(
            provider="openai",
            model="gpt-4o",
            routing_reasons=["quality pool", "default"],
            memory_count=3,
            tokens_used=150,
        )
        assert "openai" in result
        assert "gpt-4o" in result
        assert "quality pool" in result
        assert "3" in result
        assert "150" in result

    def test_minimal_explain(self) -> None:
        result = format_explain(
            provider=None,
            model=None,
            routing_reasons=None,
            memory_count=0,
            tokens_used=None,
        )
        assert "unknown" in result
        assert "Tokens" not in result
