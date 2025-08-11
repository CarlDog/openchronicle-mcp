import asyncio
from datetime import datetime, timezone

import pytest

from openchronicle.domain.ports.persistence_inmemory import (
    InMemorySqlitePersistence,
)
from openchronicle.domain.services.timeline.shared.bookmark_manager import (
    SimpleBookmarkManager,
)
from openchronicle.domain.services.timeline.timeline.timeline_manager import (
    TimelineManager,
)


@pytest.mark.asyncio
async def test_timeline_includes_bookmarks():
    story_id = "story-test-bookmarks"
    persistence = InMemorySqlitePersistence()
    persistence.init_database(story_id)

    ts = datetime.now(timezone.utc).isoformat()

    # Insert two scenes
    persistence.execute_update(
        story_id,
        """
        INSERT INTO scenes (scene_id, timestamp, input, output, story_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("scene-1", ts, "Hello", "World", story_id),
    )
    persistence.execute_update(
        story_id,
        """
        INSERT INTO scenes (scene_id, timestamp, input, output, story_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("scene-2", ts, "Foo", "Bar", story_id),
    )

    # Create a bookmark between scenes
    bm = SimpleBookmarkManager(persistence)
    ok = bm.create_bookmark(
        story_id,
        bookmark_id="bm-1",
        scene_id="scene-1",
        timestamp=ts,
        description="First bookmark",
        data={"tag": "check"},
    )
    assert ok

    # Build timeline
    tm = TimelineManager(story_id, persistence_port=persistence, bookmark_manager=bm)
    timeline = await tm.build_full_timeline(include_bookmarks=True, include_summaries=False)

    # Validate entries include a bookmark
    types = [e["type"] for e in timeline["entries"]]
    assert "bookmark" in types

    # Bookmark carries our data
    bookmark_entries = [e for e in timeline["entries"] if e["type"] == "bookmark"]
    assert bookmark_entries and bookmark_entries[0]["bookmark_data"]["description"] == "First bookmark"


@pytest.mark.asyncio
async def test_timeline_without_bookmarks_is_ok():
    story_id = "story-no-bookmarks"
    persistence = InMemorySqlitePersistence()
    persistence.init_database(story_id)

    ts = datetime.now(timezone.utc).isoformat()

    # Insert one scene
    persistence.execute_update(
        story_id,
        """
        INSERT INTO scenes (scene_id, timestamp, input, output, story_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("scene-1", ts, "Hello", "World", story_id),
    )

    # Build timeline without a bookmark manager
    tm = TimelineManager(story_id, persistence_port=persistence, bookmark_manager=None)
    timeline = await tm.build_full_timeline(include_bookmarks=True, include_summaries=False)

    # Validate entries contain only the scene
    types = [e["type"] for e in timeline["entries"]]
    assert types == ["scene"]


@pytest.mark.asyncio
async def test_timeline_bookmark_ordering_by_timestamp():
    story_id = "story-bookmark-order"
    persistence = InMemorySqlitePersistence()
    persistence.init_database(story_id)

    # Distinct timestamps to verify ordering
    ts1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc).isoformat()
    tsb = datetime(2025, 1, 1, 12, 30, 0, tzinfo=timezone.utc).isoformat()
    ts2 = datetime(2025, 1, 1, 13, 0, 0, tzinfo=timezone.utc).isoformat()

    persistence.execute_update(
        story_id,
        """
        INSERT INTO scenes (scene_id, timestamp, input, output, story_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("scene-1", ts1, "S1 in", "S1 out", story_id),
    )
    persistence.execute_update(
        story_id,
        """
        INSERT INTO scenes (scene_id, timestamp, input, output, story_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("scene-2", ts2, "S2 in", "S2 out", story_id),
    )

    bm = SimpleBookmarkManager(persistence)
    assert bm.create_bookmark(
        story_id,
        bookmark_id="bm-mid",
        scene_id="scene-1",
        timestamp=tsb,
        description="Midpoint",
        data=None,
    )

    tm = TimelineManager(story_id, persistence_port=persistence, bookmark_manager=bm)
    timeline = await tm.build_full_timeline(include_bookmarks=True, include_summaries=False)

    items = [(e["type"], e["timestamp"]) for e in timeline["entries"]]
    assert items == [("scene", ts1), ("bookmark", tsb), ("scene", ts2)]
