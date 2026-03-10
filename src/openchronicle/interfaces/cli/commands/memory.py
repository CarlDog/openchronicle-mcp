"""Memory CLI commands: memory add/list/show/pin/search."""

from __future__ import annotations

import argparse

from openchronicle.core.application.config.env_helpers import parse_csv_tags
from openchronicle.core.application.use_cases import (
    add_memory,
    delete_memory,
    list_memory,
    pin_memory,
    search_memory,
    show_memory,
    update_memory,
)
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.infrastructure.wiring.container import CoreContainer


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
        "update": cmd_memory_update,
        "embed": cmd_memory_embed,
    }
    handler = memory_dispatch.get(args.memory_command)
    if handler is None:
        print("Usage: oc memory <subcommand>")
        return 1
    return handler(args, container)


def cmd_memory_add(args: argparse.Namespace, container: CoreContainer) -> int:
    tags = parse_csv_tags(args.tags) or []
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
        emit_event=container.emit_event,
        item=MemoryItem(
            content=args.content,
            tags=tags,
            pinned=args.pin,
            conversation_id=args.conversation_id,
            project_id=project_id,
            source=args.source,
        ),
        embedding_service=container.embedding_service,
    )
    print(item.id)
    return 0


def cmd_memory_list(args: argparse.Namespace, container: CoreContainer) -> int:
    items = list_memory.execute(
        store=container.storage,
        limit=args.limit,
        pinned_only=args.pinned_only,
        offset=args.offset,
    )
    for item in items:
        tags_str = ",".join(item.tags)
        snippet = item.content if len(item.content) <= 120 else item.content[:120] + "..."
        print(f"{item.id}\t{item.pinned}\t{item.created_at.isoformat()}\t{tags_str}\t{snippet}")
    return 0


def cmd_memory_show(args: argparse.Namespace, container: CoreContainer) -> int:
    try:
        item = show_memory.execute(container.storage, args.memory_id)
    except (ValueError, NotFoundError, DomainValidationError) as exc:
        print(str(exc))
        return 1

    print(f"id: {item.id}")
    print(f"pinned: {item.pinned}")
    print(f"created_at: {item.created_at.isoformat()}")
    print(f"updated_at: {item.updated_at.isoformat() if item.updated_at else ''}")
    print(f"tags: {','.join(item.tags)}")
    print(f"source: {item.source}")
    print(f"conversation_id: {item.conversation_id or ''}")
    print(f"project_id: {item.project_id or ''}")
    print("content:")
    print(item.content)
    return 0


def cmd_memory_pin(args: argparse.Namespace, container: CoreContainer) -> int:
    try:
        pin_memory.execute(
            store=container.storage,
            emit_event=container.emit_event,
            memory_id=args.memory_id,
            pinned=args.pin_on,
        )
    except (NotFoundError, DomainValidationError) as exc:
        print(str(exc))
        return 1
    return 0


def cmd_memory_search(args: argparse.Namespace, container: CoreContainer) -> int:
    tag_list = parse_csv_tags(args.tags)
    items = search_memory.execute(
        store=container.storage,
        query=args.query,
        top_k=args.top_k,
        conversation_id=args.conversation_id,
        project_id=args.project_id,
        include_pinned=args.include_pinned,
        tags=tag_list,
        offset=args.offset,
        embedding_service=container.embedding_service,
    )
    full = getattr(args, "full", False)
    for item in items:
        if full:
            tags_str = ",".join(item.tags)
            print(f"--- [{tags_str}] (pinned={item.pinned}) ---")
            print(item.content)
            print()
        else:
            tags_str = ",".join(item.tags)
            snippet = item.content if len(item.content) <= 120 else item.content[:120] + "..."
            print(f"{item.id}\t{item.pinned}\t{item.created_at.isoformat()}\t{tags_str}\t{snippet}")
    return 0


def cmd_memory_delete(args: argparse.Namespace, container: CoreContainer) -> int:
    """Delete a memory item."""
    from openchronicle.interfaces.cli.commands._helpers import json_envelope, json_error_payload, print_json

    try:
        delete_memory.execute(
            store=container.storage,
            emit_event=container.emit_event,
            memory_id=args.memory_id,
        )
    except (ValueError, NotFoundError, DomainValidationError):
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


def cmd_memory_update(args: argparse.Namespace, container: CoreContainer) -> int:
    """Update an existing memory item's content and/or tags."""
    tags = parse_csv_tags(args.tags)
    content = args.content if args.content else None

    if content is None and tags is None:
        print("At least one of --content or --tags must be provided")
        return 1

    try:
        updated = update_memory.execute(
            store=container.storage,
            emit_event=container.emit_event,
            memory_id=args.memory_id,
            content=content,
            tags=tags,
            embedding_service=container.embedding_service,
        )
    except (ValueError, NotFoundError, DomainValidationError) as exc:
        print(str(exc))
        return 1

    print(updated.id)
    return 0


def cmd_memory_embed(args: argparse.Namespace, container: CoreContainer) -> int:
    """Generate embeddings for memory items."""
    import json as _json

    service = container.embedding_service
    if service is None:
        print("Embedding service not configured. Set OC_EMBEDDING_PROVIDER (stub, openai, ollama).")
        return 1

    if getattr(args, "status", False):
        status = service.embedding_status()
        if getattr(args, "json", False):
            print(_json.dumps(status))
        else:
            print(f"Total memories: {status['total_memories']}")
            print(f"Embedded:       {status['embedded']}")
            print(f"Missing:        {status['missing']}")
            print(f"Stale:          {status['stale']}")
            print(f"Model:          {service.port.model_name()}")
        return 0

    force = getattr(args, "force", False)
    count = service.generate_missing(force=force)
    if getattr(args, "json", False):
        print(_json.dumps({"generated": count, "force": force}))
    else:
        print(f"Generated {count} embedding(s).")
    return 0
