"""Memory CLI commands: memory add/list/show/pin/search."""

from __future__ import annotations

import argparse

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.use_cases import (
    add_memory,
    list_memory,
    pin_memory,
    search_memory,
    show_memory,
)
from openchronicle.core.domain.models.memory_item import MemoryItem


def cmd_memory(args: argparse.Namespace, container: CoreContainer) -> int:
    """Dispatch to memory subcommands."""
    from collections.abc import Callable

    memory_dispatch: dict[str, Callable[[argparse.Namespace, CoreContainer], int]] = {
        "add": cmd_memory_add,
        "list": cmd_memory_list,
        "show": cmd_memory_show,
        "pin": cmd_memory_pin,
        "search": cmd_memory_search,
        "delete": cmd_memory_delete,
    }
    handler = memory_dispatch.get(args.memory_command)
    if handler is None:
        print("Usage: oc memory <subcommand>")
        return 1
    return handler(args, container)


def cmd_memory_add(args: argparse.Namespace, container: CoreContainer) -> int:
    tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()]
    project_id = args.project_id
    if project_id is None and args.conversation_id:
        maybe_conversation = container.storage.get_conversation(args.conversation_id)
        if maybe_conversation is None:
            print(f"Conversation not found: {args.conversation_id}")
            return 1
        project_id = maybe_conversation.project_id
    if project_id is None:
        print("project_id is required when adding memory")
        return 1
    item = add_memory.execute(
        store=container.storage,
        emit_event=container.event_logger.append,
        item=MemoryItem(
            content=args.content,
            tags=tags,
            pinned=args.pin,
            conversation_id=args.conversation_id,
            project_id=project_id,
            source=args.source,
        ),
    )
    print(item.id)
    return 0


def cmd_memory_list(args: argparse.Namespace, container: CoreContainer) -> int:
    items = list_memory.execute(
        store=container.storage,
        limit=args.limit,
        pinned_only=args.pinned_only,
    )
    for item in items:
        tags_str = ",".join(item.tags)
        snippet = item.content if len(item.content) <= 120 else item.content[:120] + "..."
        print(f"{item.id}\t{item.pinned}\t{item.created_at.isoformat()}\t{tags_str}\t{snippet}")
    return 0


def cmd_memory_show(args: argparse.Namespace, container: CoreContainer) -> int:
    try:
        item = show_memory.execute(container.storage, args.memory_id)
    except ValueError as exc:
        print(str(exc))
        return 1

    print(f"id: {item.id}")
    print(f"pinned: {item.pinned}")
    print(f"created_at: {item.created_at.isoformat()}")
    print(f"tags: {','.join(item.tags)}")
    print(f"source: {item.source}")
    print(f"conversation_id: {item.conversation_id or ''}")
    print(f"project_id: {item.project_id or ''}")
    print("content:")
    print(item.content)
    return 0


def cmd_memory_pin(args: argparse.Namespace, container: CoreContainer) -> int:
    pin_memory.execute(
        store=container.storage,
        emit_event=container.event_logger.append,
        memory_id=args.memory_id,
        pinned=args.pin_on,
    )
    return 0


def cmd_memory_search(args: argparse.Namespace, container: CoreContainer) -> int:
    items = search_memory.execute(
        store=container.storage,
        query=args.query,
        top_k=args.top_k,
        conversation_id=args.conversation_id,
        project_id=args.project_id,
        include_pinned=args.include_pinned,
    )
    for item in items:
        tags_str = ",".join(item.tags)
        snippet = item.content if len(item.content) <= 120 else item.content[:120] + "..."
        print(f"{item.id}\t{item.pinned}\t{item.created_at.isoformat()}\t{tags_str}\t{snippet}")
    return 0


def cmd_memory_delete(args: argparse.Namespace, container: CoreContainer) -> int:
    """Delete a memory item."""
    from openchronicle.interfaces.cli.commands._helpers import json_envelope, json_error_payload, print_json

    # Verify exists
    item = container.storage.get_memory(args.memory_id)
    if item is None:
        if args.json:
            payload = json_envelope(
                command="memory.delete",
                ok=False,
                result=None,
                error=json_error_payload(
                    error_code=None, message=f"Memory item not found: {args.memory_id}", hint=None
                ),
            )
            print_json(payload)
            return 1
        print(f"Memory item not found: {args.memory_id}")
        return 1

    container.storage.delete_memory(args.memory_id)

    if args.json:
        payload = json_envelope(
            command="memory.delete",
            ok=True,
            result={"memory_id": args.memory_id},
            error=None,
        )
        print_json(payload)
        return 0

    print(f"Deleted memory item {args.memory_id}")
    return 0
