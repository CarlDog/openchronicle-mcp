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
    name_contains: str | None = None,
    compact: bool = False,
) -> list[dict[str, Any]]:
    """List projects, newest first.

    `name_contains` is a case-insensitive substring match on the project
    name, matched literally. `compact` swaps metadata for its keys and size.
    """
    projects = list_projects.execute(store=container.storage, name_contains=name_contains)
    return [project_to_dict(p, compact=compact) for p in projects]


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
    confirm: Annotated[bool, Query(description="Required. True deletes; false returns a preview.")],
) -> dict[str, Any]:
    """Preview (confirm=false) or hard-delete (confirm=true) a project.

    The preview returns the project name and memory count without
    touching the DB, alongside `deleted: false` and a `next_step`. The
    delete cascades all memories (and embeddings) in one transaction.
    There is no soft-delete and no recovery path beyond `oc db backup`.

    `confirm` is required — omitting it is a 422, not a preview. See the
    memory delete route for why.
    """
    return delete_project.execute(
        store=container.storage,
        memory_store=container.storage,
        project_id=project_id,
        confirm=confirm,
    )
