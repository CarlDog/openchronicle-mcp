"""Project routes — create, get, list, update, delete."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field, model_validator

from openchronicle.core.application.use_cases import (
    create_project,
    delete_project,
    list_projects,
    update_project,
)
from openchronicle.core.domain.errors.error_codes import PROJECT_NOT_FOUND
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.api.deps import get_container
from openchronicle.interfaces.serializers import project_to_dict

router = APIRouter(prefix="/project")

ContainerDep = Annotated[CoreContainer, Depends(get_container)]


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    metadata: dict[str, Any] | None = None


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _require_one_field(self) -> ProjectUpdateRequest:
        if self.name is None and self.metadata is None:
            raise ValueError("Request must set at least one of name or metadata.")
        return self


@router.post("")
def project_create(
    body: ProjectCreateRequest,
    container: ContainerDep,
) -> dict[str, Any]:
    """Create a new project."""
    project = create_project.execute(
        store=container.storage,
        name=body.name,
        metadata=body.metadata,
    )
    return project_to_dict(project)


@router.get("")
def project_list(
    container: ContainerDep,
) -> list[dict[str, Any]]:
    """List all projects."""
    projects = list_projects.execute(store=container.storage)
    return [project_to_dict(p) for p in projects]


@router.get("/{project_id}")
def project_get(
    project_id: Annotated[str, Path(min_length=1, max_length=200)],
    container: ContainerDep,
) -> dict[str, Any]:
    """Fetch a single project by id, or 404."""
    project = container.storage.get_project(project_id)
    if project is None:
        raise NotFoundError(
            f"Project not found: {project_id}",
            code=PROJECT_NOT_FOUND,
        )
    return project_to_dict(project)


@router.put("/{project_id}")
def project_update_route(
    project_id: Annotated[str, Path(min_length=1, max_length=200)],
    body: ProjectUpdateRequest,
    container: ContainerDep,
) -> dict[str, Any]:
    """Rename a project or update its metadata.

    At least one of `name` or `metadata` must be set. Omitted fields are
    left untouched. Pass `metadata: {}` to explicitly clear metadata.
    """
    project = update_project.execute(
        store=container.storage,
        project_id=project_id,
        name=body.name,
        metadata=body.metadata,
    )
    return project_to_dict(project)


@router.delete("/{project_id}")
def project_delete(
    project_id: Annotated[str, Path(min_length=1, max_length=200)],
    container: ContainerDep,
    confirm: Annotated[bool, Query(description="Set true to actually delete; default returns a preview.")] = False,
) -> dict[str, Any]:
    """Preview (confirm=false) or hard-delete (confirm=true) a project.

    The preview returns the project name and memory count without
    touching the DB. The delete cascades all memories (and embeddings)
    in one transaction. There is no soft-delete and no recovery path
    beyond `oc db backup`.
    """
    return delete_project.execute(
        store=container.storage,
        memory_store=container.storage,
        project_id=project_id,
        confirm=confirm,
    )
