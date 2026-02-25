"""Upload an asset — hash, dedup, store file, persist metadata, optional link."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable

from openchronicle.core.application.services.asset_storage import AssetFileStorage
from openchronicle.core.domain.models.asset import Asset, AssetLink
from openchronicle.core.domain.models.project import Event
from openchronicle.core.domain.ports.asset_store_port import AssetStorePort

_logger = logging.getLogger(__name__)


def execute(
    store: AssetStorePort,
    file_storage: AssetFileStorage,
    emit_event: Callable[[Event], None],
    *,
    project_id: str,
    source_path: str,
    filename: str | None = None,
    mime_type: str | None = None,
    metadata: dict | None = None,
    link_target_type: str | None = None,
    link_target_id: str | None = None,
    link_role: str = "reference",
) -> tuple[Asset, bool]:
    """Upload a file as an asset. Returns (asset, is_new).

    If the same content_hash already exists in the project, returns
    the existing asset (with a new link if requested) instead of
    re-uploading. ``is_new`` is False in the dedup case.
    """
    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"Source file not found: {source_path}")

    resolved_filename = filename or os.path.basename(source_path)
    resolved_mime_type = mime_type or _guess_mime_type(resolved_filename)
    content_hash = file_storage.compute_hash_from_path(source_path)
    size_bytes = os.path.getsize(source_path)

    # Dedup check
    existing = store.get_asset_by_hash(project_id, content_hash)
    if existing is not None:
        # Optionally add a new link to the existing asset
        if link_target_type and link_target_id:
            link = AssetLink(
                asset_id=existing.id,
                target_type=link_target_type,
                target_id=link_target_id,
                role=link_role,
            )
            store.add_asset_link(link)
            emit_event(
                Event(
                    project_id=project_id,
                    type="asset.linked",
                    payload={
                        "asset_id": existing.id,
                        "link_id": link.id,
                        "target_type": link_target_type,
                        "target_id": link_target_id,
                        "role": link_role,
                        "dedup": True,
                    },
                )
            )
        return existing, False

    # New asset
    asset = Asset(
        project_id=project_id,
        filename=resolved_filename,
        mime_type=resolved_mime_type,
        size_bytes=size_bytes,
        content_hash=content_hash,
        metadata=metadata or {},
    )

    file_path = file_storage.store_file(source_path, asset)
    asset.file_path = file_path

    store.add_asset(asset)

    emit_event(
        Event(
            project_id=project_id,
            type="asset.created",
            payload={
                "asset_id": asset.id,
                "filename": asset.filename,
                "mime_type": asset.mime_type,
                "size_bytes": asset.size_bytes,
                "content_hash": asset.content_hash,
            },
        )
    )

    # Optional immediate link
    if link_target_type and link_target_id:
        link = AssetLink(
            asset_id=asset.id,
            target_type=link_target_type,
            target_id=link_target_id,
            role=link_role,
        )
        store.add_asset_link(link)
        emit_event(
            Event(
                project_id=project_id,
                type="asset.linked",
                payload={
                    "asset_id": asset.id,
                    "link_id": link.id,
                    "target_type": link_target_type,
                    "target_id": link_target_id,
                    "role": link_role,
                },
            )
        )

    return asset, True


def _guess_mime_type(filename: str) -> str:
    """Guess MIME type from filename extension."""
    ext = os.path.splitext(filename)[1].lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".mp4": "video/mp4",
        ".pdf": "application/pdf",
        ".json": "application/json",
        ".txt": "text/plain",
    }
    return mime_map.get(ext, "application/octet-stream")
