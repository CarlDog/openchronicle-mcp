"""System routes — health check + maintenance status."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from openchronicle.core.application.use_cases.diagnose_runtime import build_health_payload
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.api.deps import get_container

router = APIRouter()

ContainerDep = Annotated[CoreContainer, Depends(get_container)]


@router.get("/health")
def health(container: ContainerDep) -> dict[str, Any]:
    """Readiness probe: DB reachability, config status, embedding subsystem."""
    return build_health_payload(container)


@router.get("/maintenance/status")
def maintenance_status(request: Request) -> dict[str, Any]:
    """Per-job last-run state for the in-process maintenance loop."""
    loop = getattr(request.app.state, "maintenance", None)
    if loop is None:
        return {"enabled": False, "jobs": []}
    return {"enabled": True, "jobs": loop.status()}
