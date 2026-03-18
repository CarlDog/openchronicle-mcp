"""Storytelling plugin CLI commands (plugin protocol).

Discovered dynamically by ``_discover_plugin_cli_commands()`` in the core CLI.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from openchronicle.core.infrastructure.wiring.container import CoreContainer

# ---------------------------------------------------------------------------
# Plugin CLI protocol
# ---------------------------------------------------------------------------

COMMAND = "story"
HELP = "Storytelling project commands"


def setup_parser(sub: argparse._SubParsersAction) -> None:
    """Register ``oc story`` subcommands on the root subparser."""
    story_cmd = sub.add_parser(COMMAND, help=HELP)
    story_sub = story_cmd.add_subparsers(dest="story_command")

    # oc story import <path> --project-id <id> [--project-name <name>] [--dry-run]
    import_parser = story_sub.add_parser("import", help="Import a storytelling project from a directory")
    import_parser.add_argument("path", help="Path to the project directory")
    import_parser.add_argument("--project-id", required=True, help="OC project ID")
    import_parser.add_argument("--project-name", help="Project name (default: directory name)")
    import_parser.add_argument("--dry-run", action="store_true", help="Parse and classify without saving")

    # oc story list --project-id <id> [--type <type>]
    list_parser = story_sub.add_parser("list", help="List imported storytelling content")
    list_parser.add_argument("--project-id", required=True, help="OC project ID")
    list_parser.add_argument(
        "--type",
        choices=["character", "location", "style-guide", "scene", "instructions", "worldbuilding", "all"],
        default="all",
        help="Filter by content type",
    )

    # oc story show <memory-id>
    show_parser = story_sub.add_parser("show", help="Show a single storytelling memory item")
    show_parser.add_argument("memory_id", help="Memory item ID")

    # oc story scene --project-id <id> [--mode <mode>] [--sandbox] [--character <name>] [--location <name>] [--save] <prompt...>
    scene_parser = story_sub.add_parser("scene", help="Generate a storytelling scene")
    scene_parser.add_argument("prompt", nargs="+", help="Scene prompt / direction")
    scene_parser.add_argument("--project-id", required=True, help="OC project ID")
    scene_parser.add_argument(
        "--mode",
        choices=["participant", "director", "audience"],
        default="director",
        help="Engagement mode (default: director)",
    )
    canon_group = scene_parser.add_mutually_exclusive_group()
    canon_group.add_argument("--canon", action="store_true", default=True, help="Canon mode (default)")
    canon_group.add_argument("--sandbox", action="store_true", help="Sandbox (non-canon) mode")
    scene_parser.add_argument("--character", help="Player character name (for participant mode)")
    scene_parser.add_argument("--location", help="Location hint for context retrieval")
    scene_parser.add_argument("--save", action="store_true", help="Save the generated scene as a memory item")
    scene_parser.add_argument("--max-tokens", type=int, default=2048, help="Max output tokens (default: 2048)")
    scene_parser.add_argument("--temperature", type=float, default=0.8, help="LLM temperature (default: 0.8)")


def run(args: argparse.Namespace, container: CoreContainer) -> int:
    """Dispatch ``oc story <subcommand>``."""
    story_dispatch: dict[str, Callable[[argparse.Namespace, CoreContainer], int]] = {
        "import": _cmd_story_import,
        "list": _cmd_story_list,
        "show": _cmd_story_show,
        "scene": _cmd_story_scene,
    }
    handler = story_dispatch.get(args.story_command)
    if handler is None:
        print("Usage: oc story <import|list|show|scene>")
        return 1
    return handler(args, container)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def _cmd_story_import(args: argparse.Namespace, container: CoreContainer) -> int:
    """Import a storytelling project via the orchestrator."""
    from pathlib import Path

    from openchronicle.core.application.use_cases import run_task

    project_id = args.project_id
    source_path = Path(args.path)
    project_name = args.project_name or source_path.name
    dry_run = args.dry_run

    # Validate project exists
    project = container.storage.get_project(project_id)
    if project is None:
        print(f"Error: Project '{project_id}' not found.")
        print("List projects with: oc project list")
        return 1

    if not source_path.is_dir():
        print(f"Error: Directory not found: {args.path}")
        return 1

    action = "Dry-run import" if dry_run else "Importing"
    print(f"{action} '{project_name}' from {source_path}...")

    # Submit and execute through the orchestrator
    task = run_task.submit(
        container.orchestrator,
        project_id,
        "plugin.invoke",
        {
            "handler": "story.import",
            "input": {
                "source_dir": str(source_path),
                "project_name": project_name,
                "dry_run": dry_run,
            },
        },
    )

    try:
        result = asyncio.run(run_task.execute(container.orchestrator, task.id))
    except Exception as exc:  # noqa: BLE001
        print(f"Error: Import failed: {exc}")
        return 1

    # Display results
    result_data = result.result if hasattr(result, "result") else result
    if isinstance(result_data, str):
        result_data = json.loads(result_data)

    if isinstance(result_data, dict):
        imported = result_data.get("imported", {})
        skipped = result_data.get("skipped", [])
        warnings = result_data.get("warnings", [])

        print(f"\n{'[DRY RUN] ' if dry_run else ''}Import complete: {project_name}")
        print("-" * 40)
        total = 0
        for content_type, count in sorted(imported.items()):
            print(f"  {content_type:20s}  {count}")
            total += count
        print(f"  {'total':20s}  {total}")

        if skipped:
            print(f"\nSkipped ({len(skipped)}):")
            for name in skipped:
                print(f"  - {name}")

        if warnings:
            print(f"\nWarnings ({len(warnings)}):")
            for warning in warnings:
                print(f"  ! {warning}")
    else:
        print(f"Import result: {result_data}")

    return 0


def _cmd_story_list(args: argparse.Namespace, container: CoreContainer) -> int:
    """List imported storytelling content from memory."""
    from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort

    project_id = args.project_id
    content_type = args.type

    memory_store: MemoryStorePort = container.storage

    # Search with tag filtering
    tags = ["story"]
    if content_type != "all":
        tags.append(content_type)

    items = memory_store.search_memory("story", project_id=project_id, top_k=200, tags=tags)

    if not items:
        print("No storytelling content found.")
        return 0

    print(f"Storytelling content ({len(items)} items):")
    print(f"{'ID':38s}  {'Type':15s}  {'Preview'}")
    print("-" * 80)
    for item in items:
        # Extract content type from tags
        item_type = _extract_type_from_tags(item.tags)
        # First line of content as preview
        preview = item.content.split("\n")[0][:50] if item.content else ""
        print(f"{item.id:38s}  {item_type:15s}  {preview}")

    return 0


def _cmd_story_show(args: argparse.Namespace, container: CoreContainer) -> int:
    """Show a single storytelling memory item."""
    from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort

    memory_store: MemoryStorePort = container.storage
    item = memory_store.get_memory(args.memory_id)

    if item is None:
        print(f"Error: Memory item '{args.memory_id}' not found.")
        return 1

    print(f"ID:      {item.id}")
    print(f"Tags:    {', '.join(item.tags)}")
    print(f"Pinned:  {item.pinned}")
    print(f"Created: {item.created_at}")
    print("-" * 40)
    print(item.content)

    return 0


def _cmd_story_scene(args: argparse.Namespace, container: CoreContainer) -> int:
    """Generate a storytelling scene via the orchestrator."""
    from openchronicle.core.application.use_cases import run_task

    project_id = args.project_id
    user_prompt = " ".join(args.prompt)
    mode = args.mode
    canon = not args.sandbox
    character = args.character
    location = args.location
    save_scene = args.save
    max_tokens = args.max_tokens
    temperature = args.temperature

    # Validate project exists
    project = container.storage.get_project(project_id)
    if project is None:
        print(f"Error: Project '{project_id}' not found.")
        print("List projects with: oc project list")
        return 1

    canon_label = "canon" if canon else "sandbox"
    print(f"Generating scene ({mode}, {canon_label})...")

    task = run_task.submit(
        container.orchestrator,
        project_id,
        "plugin.invoke",
        {
            "handler": "story.scene",
            "input": {
                "prompt": user_prompt,
                "mode": mode,
                "canon": canon,
                "player_character": character,
                "location": location,
                "save_scene": save_scene,
                "max_output_tokens": max_tokens,
                "temperature": temperature,
            },
        },
    )

    try:
        result = asyncio.run(run_task.execute(container.orchestrator, task.id))
    except Exception as exc:  # noqa: BLE001
        print(f"Error: Scene generation failed: {exc}")
        return 1

    result_data = result.result if hasattr(result, "result") else result
    if isinstance(result_data, str):
        result_data = json.loads(result_data)

    if isinstance(result_data, dict):
        scene_text = result_data.get("scene_text", "")
        scene_mode = result_data.get("mode", mode)
        scene_canon = result_data.get("canon", canon)
        chars_used = result_data.get("characters_used", 0)
        scene_id = result_data.get("scene_id")

        print(f"\n{'=' * 60}")
        print(f"Mode: {scene_mode} | Canon: {scene_canon} | Characters: {chars_used}")
        if scene_id:
            print(f"Saved as: {scene_id}")
        print(f"{'=' * 60}\n")
        print(scene_text)
    else:
        print(f"Scene result: {result_data}")

    return 0


def _extract_type_from_tags(tags: list[str]) -> str:
    """Extract the content type from story tags."""
    type_tags = {"character", "location", "style-guide", "instructions", "scene", "worldbuilding", "project-meta"}
    for tag in tags:
        if tag in type_tags:
            return tag
    return "unknown"
