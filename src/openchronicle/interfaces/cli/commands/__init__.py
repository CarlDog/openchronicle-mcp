"""CLI command dispatch tables.

Maps command names to handler functions. Two tables:
- PRE_CONTAINER_COMMANDS: Commands that don't need CoreContainer (init, init-config)
- COMMANDS: Commands that receive (args, container)
"""

from __future__ import annotations

import argparse
from collections.abc import Callable

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.interfaces.cli.chat import cmd_chat

from . import conversation, db, debug, memory, project, system, task

# Pre-container commands (no CoreContainer needed)
PRE_CONTAINER_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "init": system.cmd_init,
    "init-config": system.cmd_init_config,
    "provider": system.cmd_provider,
    "version": system.cmd_version,
    "config": system.cmd_config,
}

# Post-container commands
COMMANDS: dict[str, Callable[[argparse.Namespace, CoreContainer], int]] = {
    # Project
    "init-project": project.cmd_init_project,
    "list-projects": project.cmd_list_projects,
    "show-project": project.cmd_show_project,
    "events": project.cmd_events,
    "register-agent": project.cmd_register_agent,
    "resume-project": project.cmd_resume_project,
    "replay-project": project.cmd_replay_project,
    # Task
    "run-task": task.cmd_run_task,
    "show-task": task.cmd_show_task,
    "list-tasks": task.cmd_list_tasks,
    "verify-task": task.cmd_verify_task,
    "verify-project": task.cmd_verify_project,
    "replay-task": task.cmd_replay_task,
    "explain-task": task.cmd_explain_task,
    "task-tree": task.cmd_task_tree,
    "usage": task.cmd_usage,
    # Conversation
    "convo": conversation.cmd_convo,
    # Memory
    "memory": memory.cmd_memory,
    # Database
    "db": db.cmd_db,
    # System
    "list-models": system.cmd_list_models,
    "list-handlers": system.cmd_list_handlers,
    "serve": system.cmd_serve,
    "rpc": system.cmd_rpc,
    # Chat
    "chat": cmd_chat,
    # Debug/demo
    "demo-summary": debug.cmd_demo_summary,
    "smoke-live": debug.cmd_smoke_live,
    "selftest": debug.cmd_selftest,
    "diagnose": debug.cmd_diagnose,
    "acceptance": debug.cmd_acceptance,
}
