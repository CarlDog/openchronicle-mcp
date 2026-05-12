"""Project CLI commands: init-project, list-projects, show-project, update-project, delete-project."""

from __future__ import annotations

import argparse
import json

from openchronicle.core.application.use_cases import (
    create_project,
    delete_project,
    list_projects,
    update_project,
)
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.infrastructure.wiring.container import CoreContainer


def cmd_init_project(args: argparse.Namespace, container: CoreContainer) -> int:
    project = create_project.execute(container.storage, args.name)
    print(project.id)
    return 0


def cmd_list_projects(args: argparse.Namespace, container: CoreContainer) -> int:
    projects = list_projects.execute(container.storage)
    for p in projects:
        print(f"{p.id}\t{p.name}")
    return 0


def cmd_show_project(args: argparse.Namespace, container: CoreContainer) -> int:
    """Show project details."""
    from openchronicle.interfaces.cli.commands._helpers import json_envelope, print_json

    project = container.storage.get_project(args.project_id)
    if project is None:
        print(f"Project not found: {args.project_id}")
        return 1

    if args.json:
        payload = json_envelope(
            command="show-project",
            ok=True,
            result={
                "project_id": project.id,
                "name": project.name,
                "created_at": project.created_at.isoformat(),
            },
            error=None,
        )
        print_json(payload)
        return 0

    print(f"Project: {project.name}")
    print(f"ID: {project.id}")
    print(f"Created: {project.created_at.isoformat()}")
    return 0


def cmd_update_project(args: argparse.Namespace, container: CoreContainer) -> int:
    """Rename a project or update its metadata."""
    from openchronicle.interfaces.cli.commands._helpers import (
        json_envelope,
        json_error_payload,
        print_json,
    )

    name = args.name
    metadata: dict[str, object] | None
    if args.metadata is None:
        metadata = None
    else:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError as exc:
            print(f"--metadata must be valid JSON: {exc}")
            return 2
        if not isinstance(metadata, dict):
            print("--metadata must decode to a JSON object")
            return 2

    if name is None and metadata is None:
        print("Provide at least one of --name or --metadata")
        return 2

    try:
        project = update_project.execute(
            store=container.storage,
            project_id=args.project_id,
            name=name,
            metadata=metadata,
        )
    except NotFoundError as exc:
        if args.json:
            payload = json_envelope(
                command="update-project",
                ok=False,
                result=None,
                error=json_error_payload(
                    error_code=exc.code,
                    message=str(exc),
                    hint="Run `oc list-projects` to see valid project IDs.",
                ),
            )
            print_json(payload)
        else:
            print(str(exc))
        return 1

    if args.json:
        payload = json_envelope(
            command="update-project",
            ok=True,
            result={
                "project_id": project.id,
                "name": project.name,
                "metadata": project.metadata,
            },
            error=None,
        )
        print_json(payload)
        return 0

    print(f"Updated project {project.id} ({project.name})")
    return 0


def cmd_delete_project(args: argparse.Namespace, container: CoreContainer) -> int:
    """Preview or delete a project and all its memories."""
    from openchronicle.interfaces.cli.commands._helpers import (
        json_envelope,
        json_error_payload,
        print_json,
    )

    try:
        result = delete_project.execute(
            store=container.storage,
            memory_store=container.storage,
            project_id=args.project_id,
            confirm=args.confirm,
        )
    except NotFoundError as exc:
        if args.json:
            payload = json_envelope(
                command="delete-project",
                ok=False,
                result=None,
                error=json_error_payload(
                    error_code=exc.code,
                    message=str(exc),
                    hint="Run `oc list-projects` to see valid project IDs.",
                ),
            )
            print_json(payload)
        else:
            print(str(exc))
        return 1

    if args.json:
        payload = json_envelope(
            command="delete-project",
            ok=True,
            result=result,
            error=None,
        )
        print_json(payload)
        return 0

    if result["status"] == "preview":
        print(
            f"Would delete project {result['project_id']} ({result['name']}) "
            f"with {result['memory_count']} memories. "
            f"Re-run with --confirm to proceed."
        )
    else:
        print(
            f"Deleted project {result['project_id']} ({result['name']}); removed {result['deleted_memories']} memories."
        )
    return 0
