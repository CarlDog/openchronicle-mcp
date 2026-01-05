from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.use_cases import (
    create_project,
    list_projects,
    register_agent,
    run_task,
    show_task,
)
from openchronicle.core.domain.models.project import Agent
from openchronicle.core.domain.services.orchestrator import OrchestratorService
from openchronicle.core.domain.services.replay import ReplayMode, ReplayService
from openchronicle.core.domain.services.verification import VerificationService


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

    sub.add_parser("list-handlers", help="List registered task handlers")

    verify_cmd = sub.add_parser("verify-task", help="Verify task event hash chain")
    verify_cmd.add_argument("task_id")

    replay_cmd = sub.add_parser("replay-task", help="Replay task execution")
    replay_cmd.add_argument("task_id")
    replay_cmd.add_argument(
        "--mode", choices=["verify", "replay-events", "dry-run"], default="verify", help="Replay mode"
    )

    explain_cmd = sub.add_parser("explain-task", help="Show detailed task execution trace")
    explain_cmd.add_argument("task_id")

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

    if args.command == "verify-task":
        verification_service = VerificationService(container.storage)
        result = verification_service.verify_task_chain(args.task_id)

        if result.success:
            print("✓ Hash chain verified successfully")
            print(f"  Total events: {result.total_events}")
            print(f"  Verified events: {result.verified_events}")
            return 0
        print("✗ Hash chain verification failed")
        print(f"  Error: {result.error_message}")
        if result.first_mismatch:
            print(f"  First mismatch at event {result.first_mismatch.get('event_index')}:")
            print(f"    Event ID: {result.first_mismatch.get('event_id')}")
            print(f"    Event type: {result.first_mismatch.get('event_type')}")
            for key, value in result.first_mismatch.items():
                if key not in ["event_index", "event_id", "event_type"]:
                    print(f"    {key}: {value}")
        return 1

    if args.command == "replay-task":
        replay_service = ReplayService(container.storage)
        mode_map = {
            "verify": ReplayMode.VERIFY,
            "replay-events": ReplayMode.REPLAY_EVENTS,
            "dry-run": ReplayMode.DRY_RUN,
        }
        mode = mode_map[args.mode]
        replay_result = replay_service.replay_task(args.task_id, mode)

        if args.mode == "verify":
            # Verify mode - show verification results
            if replay_result.success:
                print("✓ Hash chain verified successfully")
                if replay_result.verification_details:
                    print(f"  Total events: {replay_result.verification_details.get('total_events')}")
                    print(f"  Verified events: {replay_result.verification_details.get('verified_events')}")
                return 0
            print("✗ Hash chain verification failed")
            if replay_result.verification_details and replay_result.verification_details.get("error_message"):
                print(f"  Error: {replay_result.verification_details['error_message']}")
            if replay_result.verification_details and replay_result.verification_details.get("first_mismatch"):
                mismatch = replay_result.verification_details["first_mismatch"]
                print(f"  First mismatch at event {mismatch.get('event_index')}:")
                print(f"    Event ID: {mismatch.get('event_id')}")
                print(f"    Event type: {mismatch.get('event_type')}")
                for key, value in mismatch.items():
                    if key not in ["event_index", "event_id", "event_type"]:
                        print(f"    {key}: {value}")
            return 1
        if args.mode == "replay-events":
            # Replay events mode - show reconstructed output
            if replay_result.success:
                print("✓ Task replay successful")
                print("\nReconstructed output:")
                print(json.dumps(replay_result.reconstructed_output, indent=2))
                return 0
            print(f"✗ Task replay failed: {replay_result.error_message}")
            return 1
        if args.mode == "dry-run":
            # Dry run mode - show execution trace
            if replay_result.success:
                print("✓ Dry run successful")
                print("\nExecution trace:")
                print(json.dumps(replay_result.reconstructed_output, indent=2))
                return 0
            print(f"✗ Dry run failed: {replay_result.error_message}")
            return 1

    if args.command == "explain-task":
        maybe_task = container.storage.get_task(args.task_id)
        if maybe_task is None:
            print(f"Task not found: {args.task_id}")
            return 1
        task = maybe_task

        print(f"Task: {args.task_id}")
        print(f"  Type: {task.type}")
        print(f"  Status: {task.status.value}")
        print(f"  Created: {task.created_at.isoformat()}")
        print(f"  Updated: {task.updated_at.isoformat()}")

        # Show agents involved
        events = container.storage.list_events(args.task_id)
        agent_ids = {e.agent_id for e in events if e.agent_id}
        if agent_ids:
            print("\nAgents involved:")
            for agent_id in agent_ids:
                maybe_agent = next(
                    (a for a in container.storage.list_agents(task.project_id) if a.id == agent_id), None
                )
                if maybe_agent:
                    print(f"  - {maybe_agent.name} ({maybe_agent.role}) [{agent_id}]")

        # Show spans
        spans = container.storage.list_spans(args.task_id)
        if spans:
            print(f"\nExecution spans ({len(spans)}):")
            for span in spans:
                duration = ""
                if span.ended_at:
                    delta = (span.ended_at - span.created_at).total_seconds()
                    duration = f" [{delta:.2f}s]"
                print(f"  - {span.name} ({span.status.value}){duration}")

        # Show events
        print(f"\nEvents ({len(events)}):")
        for idx, event in enumerate(events):
            payload_preview = str(event.payload)[:80]
            if len(str(event.payload)) > 80:
                payload_preview += "..."
            print(f"  {idx + 1}. [{event.created_at.isoformat()}] {event.type}")
            print(f"      {payload_preview}")

        # Show final result
        replay_service = ReplayService(container.storage)
        replay_result = replay_service.replay_task(args.task_id, ReplayMode.REPLAY_EVENTS)
        if replay_result.success and replay_result.reconstructed_output is not None:
            print("\nFinal result:")
            result_str = json.dumps(replay_result.reconstructed_output, indent=2)
            if len(result_str) > 500:
                result_str = result_str[:500] + "\n  ..."
            print(f"  {result_str}")

        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
