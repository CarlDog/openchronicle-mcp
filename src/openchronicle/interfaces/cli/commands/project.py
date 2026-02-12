"""Project CLI commands: init-project, list-projects, register-agent, resume-project, replay-project."""

from __future__ import annotations

import argparse
import asyncio

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.use_cases import (
    continue_project,
    create_project,
    list_projects,
    register_agent,
    resume_project,
)
from openchronicle.core.application.use_cases.replay_project import (
    ReplayService as ProjectReplayService,
)


def cmd_init_project(args: argparse.Namespace, container: CoreContainer) -> int:
    project = create_project.execute(container.orchestrator, args.name)
    print(project.id)
    return 0


def cmd_list_projects(args: argparse.Namespace, container: CoreContainer) -> int:
    projects = list_projects.execute(container.orchestrator)
    for p in projects:
        print(f"{p.id}\t{p.name}")
    return 0


def cmd_register_agent(args: argparse.Namespace, container: CoreContainer) -> int:
    agent = register_agent.execute(
        container.orchestrator,
        project_id=args.project_id,
        name=args.name,
        role=args.role,
        provider=args.provider,
        model=args.model,
    )
    print(agent)
    return 0


def cmd_resume_project(args: argparse.Namespace, container: CoreContainer) -> int:
    summary = resume_project.execute(container.orchestrator, args.project_id)

    print(f"Project resumed: {summary.project_id}")
    print(f"  Tasks moved RUNNING -> PENDING: {summary.orphaned_to_pending}")
    print("  Current status counts:")
    print(f"    PENDING:   {summary.pending}")
    print(f"    RUNNING:   {summary.running}")
    print(f"    COMPLETED: {summary.completed}")
    print(f"    FAILED:    {summary.failed}")

    if args.continue_exec and summary.pending > 0:
        print(f"\nContinuing execution of {summary.pending} pending task(s)...")

        async def _continue_execution() -> None:
            continue_summary = await continue_project.execute(container.orchestrator, args.project_id)
            print("\nExecution complete:")
            print(f"  Tasks executed: {continue_summary.pending_tasks}")
            print(f"  Succeeded: {continue_summary.succeeded}")
            print(f"  Failed: {continue_summary.failed}")

        asyncio.run(_continue_execution())

    return 0


def cmd_replay_project(args: argparse.Namespace, container: CoreContainer) -> int:
    replay_service = ProjectReplayService(container.storage)
    state_view = replay_service.execute(args.project_id)

    print(f"Project State: {state_view.project_id}")
    print(f"  Last event at: {state_view.last_event_at.isoformat() if state_view.last_event_at else 'N/A'}")
    print("\n  Task Counts:")
    print(f"    Pending:   {state_view.task_counts.pending}")
    print(f"    Running:   {state_view.task_counts.running}")
    print(f"    Completed: {state_view.task_counts.completed}")
    print(f"    Failed:    {state_view.task_counts.failed}")

    if state_view.interrupted_task_ids:
        print(f"\n  Interrupted Tasks ({len(state_view.interrupted_task_ids)}):")
        for task_id in state_view.interrupted_task_ids:
            print(f"    - {task_id}")

    if args.show_llm and state_view.llm_executions:
        print(f"\n  LLM Executions ({len(state_view.llm_executions)}):")
        for llm_summary in state_view.llm_executions[:10]:
            provider = llm_summary.provider_used or llm_summary.provider_requested or "unknown"
            outcome = llm_summary.outcome or "unknown"
            print(f"    - {llm_summary.execution_id}: {provider} -> {outcome}")
        if len(state_view.llm_executions) > 10:
            print(f"    ... and {len(state_view.llm_executions) - 10} more")

    return 0
