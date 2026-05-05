"""System routes — health check + maintenance status."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from openchronicle.core.application.use_cases import diagnose_runtime
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.api.deps import get_container

router = APIRouter()

ContainerDep = Annotated[CoreContainer, Depends(get_container)]


@router.get("/health")
def health(container: ContainerDep) -> dict[str, Any]:
    """Readiness probe: DB reachability, config status, embedding subsystem."""
    report = diagnose_runtime.execute()
    report.embedding_status = container.embedding_status_dict()
    data = asdict(report)
    if data.get("timestamp_utc"):
        data["timestamp_utc"] = data["timestamp_utc"].isoformat()
    if data.get("db_modified_utc"):
        data["db_modified_utc"] = data["db_modified_utc"].isoformat()
    data["maintenance_degraded"] = bool(getattr(container, "maintenance_degraded", False))
    return data


@router.get("/maintenance/status")
def maintenance_status(request: Request) -> dict[str, Any]:
    """Per-job last-run state for the in-process maintenance loop."""
    loop = getattr(request.app.state, "maintenance", None)
    if loop is None:
        return {"enabled": False, "jobs": []}
    return {"enabled": True, "jobs": loop.status()}
