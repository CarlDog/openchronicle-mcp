"""Context budget enforcement for memory retrieval."""

from __future__ import annotations

from collections.abc import Callable


def apply_char_budget[T](
    items: list[T],
    get_content: Callable[[T], str],
    max_chars: int | None,
) -> tuple[list[T], int, bool, int]:
    """Enforce a character budget over ranked retrieval items.

    Args:
        items: List of items in rank order.
        get_content: Callable extracting the content string from an item.
        max_chars: Maximum cumulative character budget. If None or <= 0,
            all items are retained without budgeting.

    Returns:
        tuple of:
        - retained_items: List of items fitting within budget (or first item if oversized).
        - total_chars: Cumulative character length of retained items.
        - truncated: True if any items were omitted due to budget constraints.
        - omitted_count: Count of items dropped due to budget constraints.
    """
    if max_chars is None or max_chars <= 0:
        total = sum(len(get_content(item)) for item in items)
        return items, total, False, 0

    if not items:
        return [], 0, False, 0

    retained: list[T] = []
    total_chars = 0
    truncated = False

    for item in items:
        content_len = len(get_content(item))
        if total_chars + content_len <= max_chars:
            retained.append(item)
            total_chars += content_len
        else:
            # If the very first item exceeds max_chars, retain it as the sole result
            # so the caller receives the top candidate rather than an empty set.
            if not retained:
                retained.append(item)
                total_chars += content_len
            truncated = True
            break

    omitted_count = len(items) - len(retained)
    return retained, total_chars, truncated, omitted_count
