"""System routes — health check + maintenance status."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from openchronicle.core.application.use_cases.diagnose_runtime import build_health_payload
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.api.deps import get_container
from openchronicle.interfaces.api.middleware.auth import request_has_key

router = APIRouter()

ContainerDep = Annotated[CoreContainer, Depends(get_container)]

# /api/v1/health is auth-exempt so probes and monitors work without the key,
# but the filesystem layout is for callers holding it (phase-end audit
# 2026-09-29; security_posture.md). With auth off there is nothing to protect.
_PATH_FIELDS = ("db_path", "config_dir")


@router.get("/health")
def health(request: Request, container: ContainerDep) -> dict[str, Any]:
    """Readiness probe: DB reachability, config status, embedding subsystem."""
    payload = build_health_payload(container)
    api_key = getattr(getattr(request.app.state, "http_config", None), "api_key", None)
    if api_key and not request_has_key(request, api_key):
        for field in _PATH_FIELDS:
            payload.pop(field, None)
    return payload


@router.get("/maintenance/status")
def maintenance_status(request: Request) -> dict[str, Any]:
    """Per-job last-run state for the in-process maintenance loop."""
    loop = getattr(request.app.state, "maintenance", None)
    if loop is None:
        return {"enabled": False, "jobs": []}
    return {"enabled": True, "jobs": loop.status()}
