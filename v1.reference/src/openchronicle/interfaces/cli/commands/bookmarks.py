"""
OpenChronicle CLI - Bookmarks Commands

Manage story bookmarks via the domain services using dependency-injected ports.
"""

from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime

import typer

from openchronicle.domain.ports.persistence_inmemory import InMemorySqlitePersistence
from openchronicle.domain.services.timeline.shared.bookmark_manager import SimpleBookmarkManager
from openchronicle.interfaces.cli.support.output_manager import OutputManager


bookmarks_app = typer.Typer(help="Manage story bookmarks")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@bookmarks_app.command("list")
def list_bookmarks(story_id: str = typer.Argument(..., help="Story ID")):
    """List bookmarks for a story."""
    output = OutputManager()
    persistence = InMemorySqlitePersistence()
    persistence.init_database(story_id)

    bm = SimpleBookmarkManager(persistence)
    bookmarks = bm.get_bookmarks(story_id)

    if not bookmarks:
        output.warning("No bookmarks found")
        return

    # Normalize data for table output
    rows = [
        {
            "bookmark_id": b.get("bookmark_id", ""),
            "scene_id": b.get("scene_id", ""),
            "timestamp": b.get("timestamp", ""),
            "description": b.get("description", ""),
        }
        for b in bookmarks
    ]
    output.table(
        rows, title=f"Bookmarks for {story_id}", headers=["bookmark_id", "scene_id", "timestamp", "description"]
    )


@bookmarks_app.command("add")
def add_bookmark(
    story_id: str = typer.Argument(..., help="Story ID"),
    scene_id: str = typer.Argument(..., help="Scene ID to bookmark"),
    description: str = typer.Option("", "--description", "-d", help="Bookmark description"),
    bookmark_id: str | None = typer.Option(None, "--id", "-i", help="Optional bookmark id (defaults to uuid4)"),
    timestamp: str | None = typer.Option(None, "--timestamp", "-t", help="ISO timestamp (defaults to now)"),
):
    """Create a bookmark for a story/scene."""
    output = OutputManager()

    bid = bookmark_id or str(uuid.uuid4())
    ts = timestamp or _now_iso()

    persistence = InMemorySqlitePersistence()
    persistence.init_database(story_id)

    bm = SimpleBookmarkManager(persistence)
    ok = bm.create_bookmark(
        story_id=story_id,
        bookmark_id=bid,
        scene_id=scene_id,
        timestamp=ts,
        description=description,
        data=None,
    )

    if ok:
        output.success(
            "Bookmark created", data={"story_id": story_id, "bookmark_id": bid, "scene_id": scene_id, "timestamp": ts}
        )
    else:
        output.error("Failed to create bookmark")


@bookmarks_app.command("remove")
def remove_bookmark(
    story_id: str = typer.Argument(..., help="Story ID"),
    bookmark_id: str = typer.Argument(..., help="Bookmark ID to remove"),
):
    """Remove a specific bookmark by ID."""
    output = OutputManager()
    persistence = InMemorySqlitePersistence()
    persistence.init_database(story_id)
    bm = SimpleBookmarkManager(persistence)
    if bm.delete_bookmark(story_id, bookmark_id):
        output.success("Bookmark removed", data={"story_id": story_id, "bookmark_id": bookmark_id})
    else:
        output.error("Failed to remove bookmark")


@bookmarks_app.command("clear")
def clear_bookmarks(story_id: str = typer.Argument(..., help="Story ID")):
    """Remove all bookmarks for a story."""
    output = OutputManager()
    persistence = InMemorySqlitePersistence()
    persistence.init_database(story_id)
    bm = SimpleBookmarkManager(persistence)
    if bm.clear_bookmarks(story_id):
        output.success("All bookmarks cleared", data={"story_id": story_id})
    else:
        output.error("Failed to clear bookmarks")
