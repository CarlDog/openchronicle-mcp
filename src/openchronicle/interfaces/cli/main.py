from __future__ import annotations

import argparse
import os

from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.cli.commands import COMMANDS, PRE_CONTAINER_COMMANDS


def _build_container(args: argparse.Namespace) -> CoreContainer | None:
    cli_config_dir = getattr(args, "config_dir", None)
    if cli_config_dir:
        os.environ["OC_CONFIG_DIR"] = cli_config_dir

    try:
        return CoreContainer()
    except Exception as exc:  # noqa: BLE001
        print(str(exc))
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="oc", description="OpenChronicle v3 — memory database for LLM agents")
    sub = parser.add_subparsers(dest="command")

    # --- Project commands ---
    init_project_cmd = sub.add_parser("init-project", help="Create a project")
    init_project_cmd.add_argument("name")

    sub.add_parser("list-projects", help="List projects")

    show_project_cmd = sub.add_parser("show-project", help="Show project details")
    show_project_cmd.add_argument("project_id")
    show_project_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

    # --- Memory commands ---
    memory_cmd = sub.add_parser("memory", help="Memory commands")
    memory_sub = memory_cmd.add_subparsers(dest="memory_command")

    memory_add_cmd = memory_sub.add_parser("add", help="Add a memory item")
    memory_add_cmd.add_argument("content")
    memory_add_cmd.add_argument("--tags", default="", help="Comma-separated tags")
    memory_add_cmd.add_argument("--pin", action="store_true", help="Pin this memory item")
    memory_add_cmd.add_argument("--source", default="manual", help="Source label")
    memory_add_cmd.add_argument("--project-id", default=None, help="Associated project id")

    memory_list_cmd = memory_sub.add_parser("list", help="List memory items")
    memory_list_cmd.add_argument("--limit", type=int, default=None, help="Limit number of memories shown")
    memory_list_cmd.add_argument("--pinned-only", action="store_true", help="Show only pinned items")
    memory_list_cmd.add_argument("--offset", type=int, default=0, help="Skip first N items")

    memory_show_cmd = memory_sub.add_parser("show", help="Show memory item")
    memory_show_cmd.add_argument("memory_id")

    memory_pin_cmd = memory_sub.add_parser("pin", help="Toggle memory pin state")
    memory_pin_cmd.add_argument("memory_id")
    pin_group = memory_pin_cmd.add_mutually_exclusive_group(required=True)
    pin_group.add_argument("--on", dest="pin_on", action="store_true")
    pin_group.add_argument("--off", dest="pin_on", action="store_false")

    memory_delete_cmd = memory_sub.add_parser("delete", help="Delete a memory item")
    memory_delete_cmd.add_argument("memory_id")
    memory_delete_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

    memory_search_cmd = memory_sub.add_parser("search", help="Search memory items")
    memory_search_cmd.add_argument("query")
    memory_search_cmd.add_argument("--top-k", type=int, default=8, help="Number of memory items to return")
    memory_search_cmd.add_argument("--project-id", default=None, help="Restrict to project")
    memory_search_cmd.add_argument("--tags", default=None, help="Filter by tags (comma-separated, AND logic)")
    memory_search_group = memory_search_cmd.add_mutually_exclusive_group()
    memory_search_group.add_argument("--include-pinned", dest="include_pinned", action="store_true")
    memory_search_group.add_argument("--no-include-pinned", dest="include_pinned", action="store_false")
    memory_search_cmd.set_defaults(include_pinned=True)
    memory_search_cmd.add_argument("--offset", type=int, default=0, help="Skip first N results")
    memory_search_cmd.add_argument("--full", action="store_true", help="Print full content (for context injection)")

    memory_update_cmd = memory_sub.add_parser("update", help="Update a memory item")
    memory_update_cmd.add_argument("memory_id")
    memory_update_cmd.add_argument("--content", default=None, help="New content (replaces existing)")
    memory_update_cmd.add_argument("--tags", default=None, help="New tags, comma-separated (replaces existing)")

    memory_embed_cmd = memory_sub.add_parser("embed", help="Generate embeddings for memory items")
    memory_embed_cmd.add_argument("--force", action="store_true", help="Regenerate all embeddings (model change)")
    memory_embed_cmd.add_argument("--status", action="store_true", help="Show embedding coverage stats")
    memory_embed_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

    memory_export_cmd = memory_sub.add_parser("export", help="Export memory + projects to JSON")
    memory_export_cmd.add_argument("--out", default=None, help="Destination file (default: stdout)")
    memory_export_cmd.add_argument("--project-id", default=None, help="Restrict to a single project")

    memory_import_cmd = memory_sub.add_parser("import", help="Import memory + projects from JSON")
    memory_import_cmd.add_argument("in_path", help="JSON file produced by `oc memory export`")
    memory_import_cmd.add_argument(
        "--mode",
        choices=["merge", "replace"],
        default="merge",
        help="merge=skip on collision (default); replace=fail if dest non-empty",
    )

    # --- Database commands ---
    db_cmd = sub.add_parser("db", help="Database maintenance commands")
    db_sub = db_cmd.add_subparsers(dest="db_command")

    db_info_cmd = db_sub.add_parser("info", help="Show database information")
    db_info_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

    db_sub.add_parser("vacuum", help="Compact database and truncate WAL")

    db_backup_cmd = db_sub.add_parser("backup", help="Hot-backup database to a file")
    db_backup_cmd.add_argument("path", help="Destination file path")
    db_backup_cmd.add_argument("--force", action="store_true", help="Overwrite if destination exists")

    db_stats_cmd = db_sub.add_parser("stats", help="Show database statistics")
    db_stats_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

    # --- Onboard commands ---
    onboard_cmd = sub.add_parser("onboard", help="Onboarding commands")
    onboard_sub = onboard_cmd.add_subparsers(dest="onboard_command")

    onboard_git_cmd = onboard_sub.add_parser("git", help="Bootstrap memories from git history")
    onboard_git_cmd.add_argument("--project-id", dest="project_id", required=True, help="Project ID")
    onboard_git_cmd.add_argument("--repo-path", dest="repo_path", default=".", help="Path to git repo (default: .)")
    onboard_git_cmd.add_argument(
        "--max-commits", dest="max_commits", type=int, default=500, help="Max commits to analyze (default: 500)"
    )
    onboard_git_cmd.add_argument(
        "--max-memories", dest="max_memories", type=int, default=15, help="Max memories to create (default: 15)"
    )
    onboard_git_cmd.add_argument("--force", action="store_true", help="Delete existing git-onboard memories and re-run")
    onboard_git_cmd.add_argument(
        "--no-llm", dest="no_llm", action="store_true", help="Skip LLM synthesis, use raw format"
    )
    onboard_git_cmd.add_argument("--dry-run", dest="dry_run", action="store_true", help="Show clusters without saving")

    # --- System commands ---
    init_cmd = sub.add_parser("init", help="Initialize runtime directories and optional templates")
    init_cmd.add_argument("--json", action="store_true", help="Emit JSON output")
    init_cmd.add_argument("--force", action="store_true", help="Overwrite templates if they exist")
    init_cmd.add_argument("--no-templates", action="store_true", help="Skip template file creation")

    init_config_cmd = sub.add_parser("init-config", help="Initialize model configuration with examples")
    init_config_cmd.add_argument(
        "--config-dir",
        default=None,
        help="Configuration directory (default: OC_CONFIG_DIR env var or 'config')",
    )

    config_cmd = sub.add_parser("config", help="Configuration commands")
    config_sub = config_cmd.add_subparsers(dest="config_command")
    config_show_cmd = config_sub.add_parser("show", help="Show effective configuration")
    config_show_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

    version_cmd = sub.add_parser("version", help="Show version information")
    version_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

    maintenance_cmd = sub.add_parser("maintenance", help="Inspect or invoke the maintenance loop")
    maintenance_sub = maintenance_cmd.add_subparsers(dest="maintenance_command")
    maintenance_list = maintenance_sub.add_parser("list", help="Show configured jobs")
    maintenance_list.add_argument("--json", action="store_true", help="Emit JSON output")
    maintenance_run = maintenance_sub.add_parser("run-once", help="Run a single job and exit")
    maintenance_run.add_argument(
        "job_name", help="One of: db_backup, db_vacuum, db_integrity_check, embedding_backfill, git_onboard_resync"
    )

    serve_cmd = sub.add_parser("serve", help="Run the unified HTTP + MCP ASGI server")
    serve_cmd.add_argument("--host", default=None, help="Bind address (default: 0.0.0.0)")
    serve_cmd.add_argument("--port", type=int, default=None, help="Port (default: 18000)")

    # --- Parse ---
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    # Pre-container commands (no CoreContainer needed)
    if args.command in PRE_CONTAINER_COMMANDS:
        return PRE_CONTAINER_COMMANDS[args.command](args)

    container = _build_container(args)
    if container is None:
        return 1

    handler = COMMANDS.get(args.command)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args, container)


if __name__ == "__main__":
    raise SystemExit(main())
