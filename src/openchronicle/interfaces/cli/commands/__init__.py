"""CLI command dispatch tables.

Maps command names to handler functions. Two tables:
- PRE_CONTAINER_COMMANDS: Commands that don't need CoreContainer (init, init-config)
- COMMANDS: Commands that receive (args, container)
"""

from __future__ import annotations

import argparse
from collections.abc import Callable

from openchronicle.core.infrastructure.wiring.container import CoreContainer

from . import (
    db,
    memory,
    onboard,
    project,
    system,
)

# Pre-container commands (no CoreContainer needed)
PRE_CONTAINER_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "init": system.cmd_init,
    "init-config": system.cmd_init_config,
    "version": system.cmd_version,
    "config": system.cmd_config,
}

# Post-container commands
COMMANDS: dict[str, Callable[[argparse.Namespace, CoreContainer], int]] = {
    # Project
    "init-project": project.cmd_init_project,
    "list-projects": project.cmd_list_projects,
    "show-project": project.cmd_show_project,
    # Memory
    "memory": memory.cmd_memory,
    # Database
    "db": db.cmd_db,
    # Onboard
    "onboard": onboard.cmd_onboard,
    # System
    "serve": system.cmd_serve,
}
