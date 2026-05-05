"""Project CLI commands: init-project, list-projects, show-project."""

from __future__ import annotations

import argparse

from openchronicle.core.application.use_cases import create_project, list_projects
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
