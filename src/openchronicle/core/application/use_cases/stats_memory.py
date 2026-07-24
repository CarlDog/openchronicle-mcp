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


def execute(store: MemoryStorePort, project_id: str | None = None) -> dict[str, Any]:
    """Return total/pinned counts and per-tag / per-source breakdowns."""
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

    return {
        "total": total,
        "pinned": pinned,
        "by_tag": by_tag,
        "by_source": by_source,
    }
