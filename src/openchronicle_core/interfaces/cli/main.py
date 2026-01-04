from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from openchronicle_core.core.application.runtime.container import CoreContainer
from openchronicle_core.core.application.use_cases import (
    create_project,
    list_projects,
    register_agent,
    run_task,
    show_task,
)
from openchronicle_core.core.domain.models.project import Agent
from openchronicle_core.core.domain.services.orchestrator import OrchestratorService


def _parse_json(value: str) -> dict[str, Any]:
    try:
        result: dict[str, Any] = json.loads(value)
        return result
    except json.JSONDecodeError:
        return {"raw": value}


def _ensure_agent(orchestrator: OrchestratorService, project_id: str, name: str, role: str) -> Agent:
    existing = [a for a in orchestrator.storage.list_agents(project_id) if a.name == name and a.role == role]
    if existing:
        return existing[0]
    return register_agent.execute(orchestrator, project_id=project_id, name=name, role=role)


def _ensure_demo_agents(orchestrator: OrchestratorService, project_id: str) -> tuple[Agent, Agent, Agent]:
    supervisor = _ensure_agent(orchestrator, project_id, "Supervisor", "supervisor")
    worker1 = _ensure_agent(orchestrator, project_id, "Worker 1", "worker")
    worker2 = _ensure_agent(orchestrator, project_id, "Worker 2", "worker")
    return supervisor, worker1, worker2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="oc", description="OpenChronicle v2 minimal CLI")
    sub = parser.add_subparsers(dest="command")

    init_cmd = sub.add_parser("init-project", help="Create a project")
    init_cmd.add_argument("name")

    sub.add_parser("list-projects", help="List projects")

    reg_cmd = sub.add_parser("register-agent", help="Register an agent")
    reg_cmd.add_argument("project_id")
    reg_cmd.add_argument("name")
    reg_cmd.add_argument("--role", default="worker")
    reg_cmd.add_argument("--provider", default="")
    reg_cmd.add_argument("--model", default="")

    run_cmd = sub.add_parser("run-task", help="Submit and run a task")
    run_cmd.add_argument("project_id")
    run_cmd.add_argument("task_type")
    run_cmd.add_argument("payload", help="JSON payload or plain text")
    run_cmd.add_argument("--agent-id", dest="agent_id", default=None)

    show_cmd = sub.add_parser("show-task", help="Show task timeline")
    show_cmd.add_argument("task_id")

    demo_cmd = sub.add_parser("demo-summary", help="Run supervisor+worker summary demo")
    demo_cmd.add_argument("project_id")
    demo_cmd.add_argument("text")

    list_handlers_cmd = sub.add_parser("list-handlers", help="List registered task handlers")

    args = parser.parse_args(argv)
    container = CoreContainer()
    orchestrator = container.orchestrator

    if args.command == "init-project":
        project = create_project.execute(orchestrator, args.name)
        print(project)
        return 0

    if args.command == "list-projects":
        projects = list_projects.execute(orchestrator)
        for p in projects:
            print(f"{p.id}\t{p.name}")
        return 0

    if args.command == "register-agent":
        agent = register_agent.execute(
            orchestrator,
            project_id=args.project_id,
            name=args.name,
            role=args.role,
            provider=args.provider,
            model=args.model,
        )
        print(agent)
        return 0

    if args.command == "run-task":
        payload = _parse_json(args.payload)
        task = run_task.submit(orchestrator, args.project_id, args.task_type, payload)

        async def _run() -> None:
            result = await run_task.execute(orchestrator, task.id, agent_id=args.agent_id)
            print(result)

        asyncio.run(_run())
        return 0

    if args.command == "show-task":
        events = show_task.timeline(orchestrator, args.task_id)
        for e in events:
            print(f"{e.created_at.isoformat()} {e.type} {e.payload}")
        return 0

    if args.command == "demo-summary":
        supervisor, worker1, worker2 = _ensure_demo_agents(orchestrator, args.project_id)
        task = run_task.submit(orchestrator, args.project_id, "analysis.summary", {"text": args.text})

        async def _run_demo() -> None:
            result = await run_task.execute(orchestrator, task.id, agent_id=supervisor.id)
            print(json.dumps(result, indent=2))
            print(f"task_id: {task.id}")

        asyncio.run(_run_demo())
        return 0

    if args.command == "list-handlers":
        builtins = orchestrator.list_builtin_handlers()
        plugins = orchestrator.list_registered_handlers()
        print("Built-in handlers:")
        for h in builtins:
            print(f"  {h}")
        print("Plugin handlers:")
        for h in plugins:
            print(f"  {h}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
