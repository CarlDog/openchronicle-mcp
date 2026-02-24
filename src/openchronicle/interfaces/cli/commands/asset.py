"""Asset CLI commands: asset upload/list/show/link."""

from __future__ import annotations

import argparse

from openchronicle.core.application.use_cases import link_asset, upload_asset
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.infrastructure.wiring.container import CoreContainer


def cmd_asset(args: argparse.Namespace, container: CoreContainer) -> int:
    """Dispatch to asset subcommands."""
    from collections.abc import Callable

    asset_dispatch: dict[str, Callable[[argparse.Namespace, CoreContainer], int]] = {
        "upload": cmd_asset_upload,
        "list": cmd_asset_list,
        "show": cmd_asset_show,
        "link": cmd_asset_link,
    }
    handler = asset_dispatch.get(args.asset_command)
    if handler is None:
        print("Usage: oc asset <subcommand>")
        return 1
    return handler(args, container)


def cmd_asset_upload(args: argparse.Namespace, container: CoreContainer) -> int:
    asset, is_new = upload_asset.execute(
        store=container.storage,
        file_storage=container.asset_file_storage,
        emit_event=container.event_logger.append,
        project_id=args.project_id,
        source_path=args.source_path,
        filename=args.filename,
        mime_type=args.mime_type,
    )
    status = "new" if is_new else "dedup"
    print(f"{asset.id}\t{status}\t{asset.filename}\t{asset.mime_type}\t{asset.size_bytes}")
    return 0


def cmd_asset_list(args: argparse.Namespace, container: CoreContainer) -> int:
    assets = container.storage.list_assets(args.project_id, limit=args.limit)
    for a in assets:
        print(f"{a.id}\t{a.filename}\t{a.mime_type}\t{a.size_bytes}\t{a.created_at.isoformat()}")
    return 0


def cmd_asset_show(args: argparse.Namespace, container: CoreContainer) -> int:
    asset = container.storage.get_asset(args.asset_id)
    if asset is None:
        print(f"Asset not found: {args.asset_id}")
        return 1
    print(f"id: {asset.id}")
    print(f"project_id: {asset.project_id}")
    print(f"filename: {asset.filename}")
    print(f"mime_type: {asset.mime_type}")
    print(f"file_path: {asset.file_path}")
    print(f"size_bytes: {asset.size_bytes}")
    print(f"content_hash: {asset.content_hash}")
    print(f"metadata: {asset.metadata}")
    print(f"created_at: {asset.created_at.isoformat()}")
    links = container.storage.list_asset_links(asset_id=asset.id)
    if links:
        print("links:")
        for link in links:
            print(f"  {link.id}\t{link.target_type}\t{link.target_id}\t{link.role}")
    return 0


def cmd_asset_link(args: argparse.Namespace, container: CoreContainer) -> int:
    try:
        link = link_asset.execute(
            store=container.storage,
            emit_event=container.event_logger.append,
            asset_id=args.asset_id,
            target_type=args.target_type,
            target_id=args.target_id,
            role=args.role,
        )
    except (ValueError, NotFoundError) as exc:
        print(str(exc))
        return 1
    print(link.id)
    return 0
