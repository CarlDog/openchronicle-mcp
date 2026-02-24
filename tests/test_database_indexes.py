"""
Tests for database indexes.

Verifies that performance indexes are created correctly on both new databases
and during migration from existing databases.
"""

from pathlib import Path

import pytest

from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


@pytest.fixture
def fresh_db(tmp_path: Path) -> SqliteStore:
    """Create a fresh database with all indexes."""
    db_path = tmp_path / "test.db"
    store = SqliteStore(str(db_path))
    store.init_schema()
    return store


@pytest.fixture
def migrated_db(tmp_path: Path) -> SqliteStore:
    """Create a database, then re-initialize to simulate migration."""
    db_path = tmp_path / "test.db"

    # First initialization
    store = SqliteStore(str(db_path))
    store.init_schema()

    # Close and reopen to simulate migration path
    store._conn.close()
    store = SqliteStore(str(db_path))
    store.init_schema()

    return store


def test_fresh_database_has_all_indexes(fresh_db: SqliteStore) -> None:
    """Verify that a fresh database has all expected indexes."""
    cur = fresh_db._conn.cursor()

    # Query sqlite_master for indexes (excluding auto-created primary key indexes)
    indexes = cur.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND (name LIKE 'idx_%' OR name LIKE 'ux_%')"
    ).fetchall()

    index_names = {row[0] for row in indexes}

    # Expected indexes as defined in schema.py
    expected = {
        "idx_tasks_project_created",
        "idx_tasks_parent",
        "idx_tasks_status",
        "idx_tasks_updated",
        "idx_events_task_created",
        "idx_spans_task_created",
        "idx_llm_usage_project_created",
        "idx_llm_usage_task_created",
        "idx_llm_usage_agent_created",
        "idx_conversations_created",
        "idx_turns_conversation_order",
        "ux_turns_conversation_turn_index",
        "idx_memory_pinned_created",
        "idx_memory_convo_created",
        "idx_memory_project_created",
        "idx_memory_source",
        "idx_scheduled_jobs_due",
        "idx_scheduled_jobs_project",
        "idx_mcp_tool_usage_tool_created",
        "idx_mcp_tool_usage_created",
        "idx_moe_usage_created",
        "idx_moe_usage_winner",
        "ux_assets_project_hash",
        "idx_assets_project_created",
        "idx_asset_links_asset",
        "idx_asset_links_target",
    }

    assert index_names == expected, f"Missing or unexpected indexes. Got {index_names}, expected {expected}"


def test_migration_creates_indexes_on_existing_db(migrated_db: SqliteStore) -> None:
    """Verify that indexes are created during migration of existing database."""
    cur = migrated_db._conn.cursor()

    indexes = cur.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND (name LIKE 'idx_%' OR name LIKE 'ux_%')"
    ).fetchall()

    index_names = {row[0] for row in indexes}

    expected = {
        "idx_tasks_project_created",
        "idx_tasks_parent",
        "idx_tasks_status",
        "idx_tasks_updated",
        "idx_events_task_created",
        "idx_spans_task_created",
        "idx_llm_usage_project_created",
        "idx_llm_usage_task_created",
        "idx_llm_usage_agent_created",
        "idx_conversations_created",
        "idx_turns_conversation_order",
        "ux_turns_conversation_turn_index",
        "idx_memory_pinned_created",
        "idx_memory_convo_created",
        "idx_memory_project_created",
        "idx_memory_source",
        "idx_scheduled_jobs_due",
        "idx_scheduled_jobs_project",
        "idx_mcp_tool_usage_tool_created",
        "idx_mcp_tool_usage_created",
        "idx_moe_usage_created",
        "idx_moe_usage_winner",
        "ux_assets_project_hash",
        "idx_assets_project_created",
        "idx_asset_links_asset",
        "idx_asset_links_target",
    }

    assert index_names == expected


def test_indexes_are_on_correct_tables_and_columns(fresh_db: SqliteStore) -> None:
    """Verify that each index is created on the correct table and columns."""
    cur = fresh_db._conn.cursor()

    # Get detailed index information
    index_info = {}
    for idx_name in [
        "idx_tasks_project_created",
        "idx_tasks_parent",
        "idx_tasks_status",
        "idx_tasks_updated",
        "idx_events_task_created",
        "idx_spans_task_created",
        "idx_conversations_created",
        "idx_turns_conversation_order",
        "ux_turns_conversation_turn_index",
        "idx_memory_pinned_created",
        "idx_memory_convo_created",
        "idx_memory_project_created",
    ]:
        # Get the table name for this index
        table_row = cur.execute(
            "SELECT tbl_name FROM sqlite_master WHERE type = 'index' AND name = ?", (idx_name,)
        ).fetchone()
        assert table_row is not None, f"Index {idx_name} not found"

        table_name = table_row[0]

        # Get columns in the index
        columns = cur.execute(f"PRAGMA index_info({idx_name})").fetchall()
        column_names = [row[2] for row in columns]

        index_info[idx_name] = {"table": table_name, "columns": column_names}

    # Verify each index
    assert index_info["idx_tasks_project_created"] == {"table": "tasks", "columns": ["project_id", "created_at", "id"]}
    assert index_info["idx_tasks_parent"] == {"table": "tasks", "columns": ["parent_task_id"]}
    assert index_info["idx_tasks_status"] == {"table": "tasks", "columns": ["status"]}
    assert index_info["idx_tasks_updated"] == {"table": "tasks", "columns": ["updated_at"]}
    assert index_info["idx_events_task_created"] == {"table": "events", "columns": ["task_id", "created_at", "id"]}
    assert index_info["idx_spans_task_created"] == {"table": "spans", "columns": ["task_id", "created_at", "id"]}
    assert index_info["idx_conversations_created"] == {"table": "conversations", "columns": ["created_at", "id"]}
    assert index_info["idx_turns_conversation_order"] == {
        "table": "turns",
        "columns": ["conversation_id", "turn_index", "id"],
    }
    assert index_info["ux_turns_conversation_turn_index"] == {
        "table": "turns",
        "columns": ["conversation_id", "turn_index"],
    }
    assert index_info["idx_memory_pinned_created"] == {
        "table": "memory_items",
        "columns": ["pinned", "created_at", "id"],
    }
    assert index_info["idx_memory_convo_created"] == {
        "table": "memory_items",
        "columns": ["conversation_id", "created_at", "id"],
    }
    assert index_info["idx_memory_project_created"] == {
        "table": "memory_items",
        "columns": ["project_id", "created_at", "id"],
    }


def test_index_creation_is_idempotent(tmp_path: Path) -> None:
    """Verify that running init_schema multiple times doesn't cause errors."""
    db_path = tmp_path / "test.db"

    store = SqliteStore(str(db_path))
    store.init_schema()

    # Run init_schema again - should not raise errors
    store.init_schema()

    # Verify indexes still exist and are correct
    cur = store._conn.cursor()
    indexes = cur.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND (name LIKE 'idx_%' OR name LIKE 'ux_%')"
    ).fetchall()

    index_names = {row[0] for row in indexes}

    expected = {
        "idx_tasks_project_created",
        "idx_tasks_parent",
        "idx_tasks_status",
        "idx_tasks_updated",
        "idx_events_task_created",
        "idx_spans_task_created",
        "idx_llm_usage_project_created",
        "idx_llm_usage_task_created",
        "idx_llm_usage_agent_created",
        "idx_conversations_created",
        "idx_turns_conversation_order",
        "ux_turns_conversation_turn_index",
        "idx_memory_pinned_created",
        "idx_memory_convo_created",
        "idx_memory_project_created",
        "idx_memory_source",
        "idx_scheduled_jobs_due",
        "idx_scheduled_jobs_project",
        "idx_mcp_tool_usage_tool_created",
        "idx_mcp_tool_usage_created",
        "idx_moe_usage_created",
        "idx_moe_usage_winner",
        "ux_assets_project_hash",
        "idx_assets_project_created",
        "idx_asset_links_asset",
        "idx_asset_links_target",
    }

    assert index_names == expected
