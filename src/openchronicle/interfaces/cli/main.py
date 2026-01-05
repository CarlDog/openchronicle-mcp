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
from openchronicle.core.domain.services.verification import (
    VerificationResult,
    VerificationService,
)


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


def _print_verification_result(result: VerificationResult) -> None:
    """Unified printing for verification results (used by verify-task and replay-task --mode verify)."""
    if result.success:
        print("✓ Hash chain verified successfully")
        print(f"  Total events: {result.total_events}")
        print(f"  Verified events: {result.verified_events}")
    else:
        print("✗ Hash chain verification failed")
        print(f"  Error: {result.error_message}")
        if result.first_mismatch:
            print(f"  First mismatch at event {result.first_mismatch.get('event_index')}:")
            print(f"    Event ID: {result.first_mismatch.get('event_id')}")
            print(f"    Event type: {result.first_mismatch.get('event_type')}")
            for key, value in result.first_mismatch.items():
                if key not in ["event_index", "event_id", "event_type"]:
                    print(f"    {key}: {value}")


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
    show_cmd.add_argument("--result", action="store_true", help="Show task result or error")

    list_tasks_cmd = sub.add_parser("list-tasks", help="List tasks in a project")
    list_tasks_cmd.add_argument("project_id")

    demo_cmd = sub.add_parser("demo-summary", help="Run supervisor+worker summary demo")
    demo_cmd.add_argument("project_id")
    demo_cmd.add_argument("text")

    sub.add_parser("list-handlers", help="List registered task handlers")

    verify_cmd = sub.add_parser("verify-task", help="Verify task event hash chain")
    verify_cmd.add_argument("task_id")

    verify_project_cmd = sub.add_parser("verify-project", help="Verify all tasks in a project")
    verify_project_cmd.add_argument("project_id")

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
        if args.result:
            # Show result or error
            maybe_task = container.storage.get_task(args.task_id)
            if maybe_task is None:
                print(f"Task not found: {args.task_id}")
                return 1
            task = maybe_task

            if task.result_json:
                print("Result:")
                try:
                    result = json.loads(task.result_json)
                    print(json.dumps(result, indent=2))
                except json.JSONDecodeError:
                    print(task.result_json)
                return 0
            if task.error_json:
                print("Error:")
                try:
                    error = json.loads(task.error_json)
                    print(json.dumps(error, indent=2))
                except json.JSONDecodeError:
                    print(task.error_json)
                return 1
            print("No result or error available")
            return 0

        # Show timeline
        events = show_task.timeline(orchestrator, args.task_id)
        for e in events:
            print(f"{e.created_at.isoformat()} {e.type} {e.payload}")
        return 0

    if args.command == "list-tasks":
        tasks = container.storage.list_tasks_by_project(args.project_id)
        if not tasks:
            print("No tasks found")
            return 0

        for task in tasks:
            # Format: task_id | type | status | updated_at | result_preview
            result_preview = ""
            if task.result_json:
                try:
                    result = json.loads(task.result_json)
                    preview_text = json.dumps(result)
                    result_preview = preview_text[:60] + ("..." if len(preview_text) > 60 else "")
                except json.JSONDecodeError:
                    result_preview = task.result_json[:60] + ("..." if len(task.result_json) > 60 else "")
            elif task.error_json:
                try:
                    error = json.loads(task.error_json)
                    result_preview = f"ERROR: {error.get('exception_type', 'Unknown')}"
                except json.JSONDecodeError:
                    result_preview = "ERROR: (invalid json)"

            print(
                f"{task.id} | {task.type:30} | {task.status.value:10} | {task.updated_at.isoformat()} | {result_preview}"
            )
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
        _print_verification_result(result)
        return 0 if result.success else 1

    if args.command == "verify-project":
        verification_service = VerificationService(container.storage)
        project_result = verification_service.verify_project(args.project_id)

        print(f"Project verification: {args.project_id}")
        print(f"  Total tasks: {project_result.total_tasks}")
        print(f"  Passed: {project_result.passed_tasks}")
        print(f"  Failed: {project_result.failed_tasks}")

        if project_result.failures:
            print("\nFailed tasks:")
            for failure in project_result.failures:
                print(f"  - Task: {failure['task_id']} (type: {failure['task_type']})")
                if failure["first_mismatch_event_id"]:
                    print(
                        f"    First mismatch: event {failure['first_mismatch_index']} (id: {failure['first_mismatch_event_id']})"
                    )
                if failure["error_message"]:
                    print(f"    Error: {failure['error_message']}")

        if project_result.success:
            print("\n✓ All tasks verified successfully")
            return 0
        print("\n✗ Some tasks failed verification")
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
            # Verify mode - show verification results using unified function
            if replay_result.verification_result:
                _print_verification_result(replay_result.verification_result)
                return 0 if replay_result.success else 1
            print("✗ Verification failed - no result available")
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
