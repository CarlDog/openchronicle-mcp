"""Project routes — create, list."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from openchronicle.core.application.use_cases import create_project, list_projects
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.api.deps import get_container
from openchronicle.interfaces.serializers import project_to_dict

router = APIRouter(prefix="/project")

ContainerDep = Annotated[CoreContainer, Depends(get_container)]


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    metadata: dict[str, Any] | None = None


@router.post("")
def project_create(
    body: ProjectCreateRequest,
    container: ContainerDep,
) -> dict[str, Any]:
    """Create a new project."""
    project = create_project.execute(
        orchestrator=container.orchestrator,
        name=body.name,
        metadata=body.metadata,
    )
    return project_to_dict(project)


@router.get("")
def project_list(
    container: ContainerDep,
) -> list[dict[str, Any]]:
    """List all projects."""
    projects = list_projects.execute(orchestrator=container.orchestrator)
    return [project_to_dict(p) for p in projects]
