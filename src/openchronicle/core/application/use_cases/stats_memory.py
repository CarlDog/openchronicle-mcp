"""Summarize memory contents: totals plus tag and source histograms.

Extracted because the body existed twice, verbatim, in the MCP tool and
the REST route — and both copies did the thing `MemoryStorePort`'s own
docstring warns against, answering "how many?" by pulling every row into
Python and taking `len(...)`.

`total` now comes from `count_memory`, which is a COUNT(*) at the SQL
layer. The histograms still need row access — tags are a JSON column with
no cheap aggregate — but they read a project-scoped `list_memory` rather
than the whole table, so a scoped stats call stops loading every other
project's rows to throw them away.
"""

from __future__ import annotations

from typing import Any

from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort

DEFAULT_TOP_TAGS = 25
"""How many tags ``by_tag`` shows by default.

The histogram used to be unbounded, and a global-scope call against the
live corpus returned ~700 tag entries — most with count 1, ~95% of the
payload — to a caller who wanted one number (observed 2026-08-28,
mcp-feedback). Count-ordered and capped, with an ``other_tags`` rollup,
the map answers "what are the dominant tags?" without eating the
caller's context; ``top_tags`` widens it when the long tail is the
question.
"""


def execute(
    store: MemoryStorePort,
    project_id: str | None = None,
    top_tags: int = DEFAULT_TOP_TAGS,
) -> dict[str, Any]:
    """Return total/pinned counts and per-tag / per-source breakdowns.

    ``by_tag`` holds the ``top_tags`` most frequent tags (count
    descending, then name for determinism); when tags were rolled up,
    ``other_tags`` counts the distinct tags not shown. ``by_source`` is
    naturally small and stays complete.
    """
    total = store.count_memory(project_id=project_id)
    items = store.list_memory(limit=None, pinned_only=False, project_id=project_id)

    by_tag: dict[str, int] = {}
    by_source: dict[str, int] = {}
    pinned = 0
    for item in items:
        if item.pinned:
            pinned += 1
        for tag in item.tags:
            by_tag[tag] = by_tag.get(tag, 0) + 1
        source = item.source or "unknown"
        by_source[source] = by_source.get(source, 0) + 1

    ranked = sorted(by_tag.items(), key=lambda kv: (-kv[1], kv[0]))
    result: dict[str, Any] = {
        "total": total,
        "pinned": pinned,
        "by_tag": dict(ranked[:top_tags]),
        "by_source": by_source,
    }
    if len(ranked) > top_tags:
        result["other_tags"] = len(ranked) - top_tags
    return result
