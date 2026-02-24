"""Link an existing asset to any entity."""

from __future__ import annotations

from collections.abc import Callable

from openchronicle.core.domain.errors.error_codes import ASSET_NOT_FOUND
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.models.asset import AssetLink
from openchronicle.core.domain.models.project import Event
from openchronicle.core.domain.ports.asset_store_port import AssetStorePort


def execute(
    store: AssetStorePort,
    emit_event: Callable[[Event], None],
    *,
    asset_id: str,
    target_type: str,
    target_id: str,
    role: str = "reference",
) -> AssetLink:
    """Create an AssetLink between an existing asset and any entity.

    Raises NotFoundError if the asset does not exist.
    """
    asset = store.get_asset(asset_id)
    if asset is None:
        raise NotFoundError(f"Asset not found: {asset_id}", code=ASSET_NOT_FOUND)

    link = AssetLink(
        asset_id=asset_id,
        target_type=target_type,
        target_id=target_id,
        role=role,
    )
    store.add_asset_link(link)

    emit_event(
        Event(
            project_id=asset.project_id,
            type="asset.linked",
            payload={
                "asset_id": asset_id,
                "link_id": link.id,
                "target_type": target_type,
                "target_id": target_id,
                "role": role,
            },
        )
    )

    return link
