"""System routes — health check, tool/MoE stats."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from openchronicle.core.application.use_cases import diagnose_runtime
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.api.deps import get_container

router = APIRouter()

ContainerDep = Annotated[CoreContainer, Depends(get_container)]


@router.get("/health")
def health(container: ContainerDep) -> dict[str, Any]:
    """Health check: database status, configuration, and provider summary."""
    report = diagnose_runtime.execute()
    report.embedding_status = container.embedding_status_dict()
    data = asdict(report)
    if data.get("timestamp_utc"):
        data["timestamp_utc"] = data["timestamp_utc"].isoformat()
    if data.get("db_modified_utc"):
        data["db_modified_utc"] = data["db_modified_utc"].isoformat()
    return data


@router.get("/stats/tools")
def tool_stats(
    container: ContainerDep,
    tool_name: str | None = Query(default=None, max_length=200),
    since: str | None = Query(default=None, max_length=50),
) -> list[dict[str, Any]]:
    """MCP tool usage statistics."""
    return container.storage.get_mcp_tool_stats(
        tool_name=tool_name,
        since=since,
    )


@router.get("/stats/moe")
def moe_stats(
    container: ContainerDep,
    winner_provider: str | None = Query(default=None, max_length=200),
    winner_model: str | None = Query(default=None, max_length=200),
    since: str | None = Query(default=None, max_length=50),
) -> list[dict[str, Any]]:
    """MoE (Mixture-of-Experts) usage statistics."""
    return container.storage.get_moe_stats(
        winner_provider=winner_provider,
        winner_model=winner_model,
        since=since,
    )
