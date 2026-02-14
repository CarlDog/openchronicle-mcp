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


def cmd_show_project(args: argparse.Namespace, container: CoreContainer) -> int:
    """Show aggregated project details."""
    from collections import Counter

    from openchronicle.interfaces.cli.commands._helpers import json_envelope, print_json

    project = container.storage.get_project(args.project_id)
    if project is None:
        print(f"Project not found: {args.project_id}")
        return 1

    agents = container.storage.list_agents(args.project_id)
    tasks = container.storage.list_tasks_by_project(args.project_id)
    status_counts: Counter[str] = Counter(str(t.status) for t in tasks)
    token_totals = container.storage.sum_tokens_by_project(args.project_id)

    # Direct SQL for conversation count and latest activity
    conn = container.storage._conn  # noqa: SLF001
    cur = conn.execute(
        "SELECT COUNT(*) FROM conversations WHERE project_id = ?",
        (args.project_id,),
    )
    convo_count = cur.fetchone()[0]

    cur = conn.execute(
        "SELECT MAX(created_at) FROM events WHERE project_id = ?",
        (args.project_id,),
    )
    row = cur.fetchone()
    latest_activity = row[0] if row and row[0] else None

    if args.json:
        payload = json_envelope(
            command="show-project",
            ok=True,
            result={
                "project_id": project.id,
                "name": project.name,
                "created_at": project.created_at.isoformat(),
                "agents": [{"id": a.id, "name": a.name, "role": a.role} for a in agents],
                "task_status_counts": dict(status_counts),
                "total_tasks": len(tasks),
                "token_totals": token_totals,
                "conversation_count": convo_count,
                "latest_activity": latest_activity,
            },
            error=None,
        )
        print_json(payload)
        return 0

    print(f"Project: {project.name}")
    print(f"ID: {project.id}")
    print(f"Created: {project.created_at.isoformat()}")

    print(f"\nAgents ({len(agents)}):")
    for a in agents:
        print(f"  {a.name} ({a.role})")

    print(f"\nTasks ({len(tasks)}):")
    for status in ("pending", "running", "completed", "failed"):
        print(f"  {status:<12} {status_counts.get(status, 0)}")

    print(f"\nTokens: {token_totals}")
    print(f"Conversations: {convo_count}")
    print(f"Latest activity: {latest_activity or 'none'}")
    return 0


def cmd_events(args: argparse.Namespace, container: CoreContainer) -> int:
    """View raw event log for a project."""
    import json as json_mod

    from openchronicle.interfaces.cli.commands._helpers import json_envelope, print_json

    events = container.storage.list_events(
        task_id=args.task_id,
        project_id=args.project_id,
    )

    # Post-filter by event_type if specified
    if args.event_type:
        events = [e for e in events if e.type == args.event_type]

    # Slice to most recent N (list_events returns ASC order)
    if args.limit and len(events) > args.limit:
        events = events[-args.limit :]

    if args.json:
        events_payload = [
            {
                "id": e.id,
                "type": e.type,
                "task_id": e.task_id,
                "project_id": e.project_id,
                "payload": e.payload,
                "created_at": e.created_at.isoformat(),
                "hash": e.hash,
                "prev_hash": e.prev_hash,
            }
            for e in events
        ]
        payload = json_envelope(
            command="events",
            ok=True,
            result={
                "project_id": args.project_id,
                "event_count": len(events),
                "events": events_payload,
            },
            error=None,
        )
        print_json(payload)
        return 0

    if not events:
        print("No events found.")
        return 0

    for e in events:
        payload_str = json_mod.dumps(e.payload) if isinstance(e.payload, dict) else str(e.payload)
        if len(payload_str) > 80:
            payload_str = payload_str[:77] + "..."
        task_part = f"task={e.task_id}" if e.task_id else "task=none"
        print(f"{e.created_at.isoformat()}  {e.type:<24}  {task_part}  {payload_str}")
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
