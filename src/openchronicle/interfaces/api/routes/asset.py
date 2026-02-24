"""Asset routes — upload, list, get, link."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from openchronicle.core.application.use_cases import link_asset, upload_asset
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.api.deps import get_container
from openchronicle.interfaces.serializers import asset_link_to_dict, asset_to_dict

router = APIRouter(prefix="/asset")

ContainerDep = Annotated[CoreContainer, Depends(get_container)]


class AssetUploadRequest(BaseModel):
    project_id: str = Field(min_length=1, max_length=200)
    source_path: str = Field(min_length=1, max_length=4096)
    filename: str | None = Field(default=None, max_length=255)
    mime_type: str | None = Field(default=None, max_length=200)
    link_target_type: str | None = Field(default=None, min_length=1, max_length=100)
    link_target_id: str | None = Field(default=None, min_length=1, max_length=200)
    link_role: str = Field(default="reference", min_length=1, max_length=100)


@router.post("")
def asset_upload(
    body: AssetUploadRequest,
    container: ContainerDep,
) -> dict[str, Any]:
    """Upload a file as an asset with optional immediate linking."""
    asset, is_new = upload_asset.execute(
        store=container.storage,
        file_storage=container.asset_file_storage,
        emit_event=container.event_logger.append,
        project_id=body.project_id,
        source_path=body.source_path,
        filename=body.filename,
        mime_type=body.mime_type,
        link_target_type=body.link_target_type,
        link_target_id=body.link_target_id,
        link_role=body.link_role,
    )
    result = asset_to_dict(asset)
    result["is_new"] = is_new
    return result


@router.get("")
def asset_list(
    project_id: str,
    container: ContainerDep,
    limit: int | None = Query(default=None, ge=1, le=10_000),
) -> list[dict[str, Any]]:
    """List assets in a project."""
    assets = container.storage.list_assets(project_id, limit=limit)
    return [asset_to_dict(a) for a in assets]


@router.get("/{asset_id}")
def asset_get(
    asset_id: str,
    container: ContainerDep,
) -> dict[str, Any]:
    """Get asset metadata and its links."""
    asset = container.storage.get_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")
    result = asset_to_dict(asset)
    links = container.storage.list_asset_links(asset_id=asset_id)
    result["links"] = [asset_link_to_dict(link) for link in links]
    return result


class AssetLinkRequest(BaseModel):
    target_type: str = Field(min_length=1, max_length=100)
    target_id: str = Field(min_length=1, max_length=200)
    role: str = Field(default="reference", min_length=1, max_length=100)


@router.post("/{asset_id}/link")
def asset_link(
    asset_id: str,
    body: AssetLinkRequest,
    container: ContainerDep,
) -> dict[str, Any]:
    """Link an existing asset to any entity."""
    link = link_asset.execute(
        store=container.storage,
        emit_event=container.event_logger.append,
        asset_id=asset_id,
        target_type=body.target_type,
        target_id=body.target_id,
        role=body.role,
    )
    return asset_link_to_dict(link)
