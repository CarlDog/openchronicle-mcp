"""Operator backup and restore-preparation tools, registered only with HTTP auth."""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from openchronicle.interfaces.mcp.tools._context import get_container


def register(mcp: FastMCP) -> None:
    """Add fixed-root tools; final restore activation remains offline."""

    @mcp.tool()
    async def db_backup_create(ctx: Context) -> dict[str, Any]:
        """Create one consistent SQLite snapshot in the exposed manual backup directory.

        Use before an upgrade or a risky data change. Returns an artifact ID,
        checksum and counts, never raw database bytes. The server chooses the
        destination; there is no path or overwrite parameter.
        """
        return await asyncio.to_thread(get_container(ctx).backups.create, "manual")

    @mcp.tool()
    async def db_backup_list(ctx: Context, limit: int = 50) -> list[dict[str, Any]]:
        """List completed local SQLite snapshots, newest first.

        This reports catalog metadata, not a fresh integrity verdict. Call
        `db_backup_verify` for a candidate before relying on it.
        """
        return await asyncio.to_thread(get_container(ctx).backups.list, limit=limit)

    @mcp.tool()
    async def db_backup_verify(artifact_id: str, ctx: Context) -> dict[str, Any]:
        """Check one snapshot's digest, SQLite integrity, schema and counts.

        The ID must come from `db_backup_list`; arbitrary paths are rejected.
        Verification does not change the running database.
        """
        return await asyncio.to_thread(get_container(ctx).backups.verify, artifact_id)

    @mcp.tool()
    async def db_restore_plan(artifact_id: str, ctx: Context) -> dict[str, Any]:
        """Compare a verified snapshot with the running database before restore.

        Read-only. Reports the candidate and current schema/counts and the
        offline cutover step. It does not restore or pause the server.
        """
        return await asyncio.to_thread(get_container(ctx).backups.restore_plan, artifact_id)

    @mcp.tool()
    async def db_restore_stage(artifact_id: str, ctx: Context) -> dict[str, Any]:
        """Copy and reverify one candidate on the database volume for offline recovery.

        This only prepares a private staged file. It cannot replace the live
        database; stop writes and use the operator runbook for cutover.
        """
        return await asyncio.to_thread(get_container(ctx).backups.restore_stage, artifact_id)
