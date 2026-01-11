from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.services.orchestrator import OrchestratorService
from openchronicle.core.application.use_cases import (
    continue_project,
    create_project,
    list_projects,
    register_agent,
    resume_project,
    run_task,
    show_task,
)
from openchronicle.core.application.use_cases.replay_project import (
    ReplayService as ProjectReplayService,
)
from openchronicle.core.domain.models.project import Agent
from openchronicle.core.domain.services.replay import ReplayMode
from openchronicle.core.domain.services.replay import ReplayService as DomainReplayService
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
    demo_cmd.add_argument("--use-openai", action="store_true", help="Force using OpenAI if configured")
    demo_cmd.add_argument("--mode", choices=["fast", "quality"], help="Routing mode (fast or quality)")
    demo_cmd.add_argument(
        "--mix",
        choices=["fast_then_quality", "quality_then_fast"],
        help="Mixed worker strategy (overrides --mode)",
    )

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

    usage_cmd = sub.add_parser("usage", help="Show LLM usage statistics")
    usage_cmd.add_argument("project_id")
    usage_cmd.add_argument("--limit", type=int, default=20, help="Number of recent calls to show")

    tree_cmd = sub.add_parser("task-tree", help="Show task tree with routing and usage")
    tree_cmd.add_argument("task_id")
    tree_cmd.add_argument("--depth", type=int, default=2, help="Tree depth (default: 2 for parent + children)")
    tree_cmd.add_argument("--show-reasons", action="store_true", help="Show routing reasons")

    resume_cmd = sub.add_parser("resume-project", help="Resume incomplete tasks in a project")
    resume_cmd.add_argument("project_id")
    resume_cmd.add_argument(
        "--continue", dest="continue_exec", action="store_true", help="Continue execution after resume"
    )

    replay_project_cmd = sub.add_parser("replay-project", help="Show derived project state from events")
    replay_project_cmd.add_argument("--project-id", required=True, help="Project identifier")
    replay_project_cmd.add_argument("--show-llm", action="store_true", help="Show LLM execution summaries")

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
        # Handle provider selection from --use-openai flag
        # If --use-openai is set, we create facade with openai as default_provider
        if args.use_openai:
            from openchronicle.core.infrastructure.llm.provider_facade import create_provider_aware_llm

            # Create facade with openai as default provider
            llm = create_provider_aware_llm(providers=["openai", "stub"])
            demo_container = CoreContainer(db_path=str(container.storage.db_path), llm=llm)
        else:
            # Use existing container (stub provider)
            demo_container = container

        supervisor, worker1, worker2 = _ensure_demo_agents(demo_container.orchestrator, args.project_id)

        # Build task payload with optional desired_quality or mix_strategy
        # Precedence: --mix > --mode > default
        task_payload = {"text": args.text}
        if args.mix:
            task_payload["mix_strategy"] = args.mix
        elif args.mode:
            task_payload["desired_quality"] = args.mode

        task = run_task.submit(demo_container.orchestrator, args.project_id, "analysis.summary", task_payload)

        async def _run_demo() -> None:
            result = await run_task.execute(demo_container.orchestrator, task.id, agent_id=supervisor.id)
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
        replay_service = DomainReplayService(container.storage)
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
        domain_replay_service = DomainReplayService(container.storage)
        replay_result = domain_replay_service.replay_task(args.task_id, ReplayMode.REPLAY_EVENTS)
        if replay_result.success and replay_result.reconstructed_output is not None:
            print("\nFinal result:")
            result_str = json.dumps(replay_result.reconstructed_output, indent=2)
            if len(result_str) > 500:
                result_str = result_str[:500] + "\n  ..."
            print(f"  {result_str}")

        return 0

    if args.command == "usage":
        # Get project-level totals
        project_totals = container.storage.sum_tokens_by_project(args.project_id)

        # Get recent calls
        recent_calls = container.storage.list_llm_usage_by_project(args.project_id, limit=args.limit)

        print(f"LLM Usage for project: {args.project_id}")
        print("\nTotals:")
        print(f"  Input tokens:  {project_totals.get('input_tokens') or 0:,}")
        print(f"  Output tokens: {project_totals.get('output_tokens') or 0:,}")
        print(f"  Total tokens:  {project_totals.get('total_tokens') or 0:,}")

        # Group by provider/model for breakdown
        if recent_calls:
            provider_model_stats: dict[tuple[str, str], dict[str, int]] = {}
            for call in recent_calls:
                key = (call.provider, call.model)
                if key not in provider_model_stats:
                    provider_model_stats[key] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "count": 0}
                provider_model_stats[key]["input_tokens"] += call.input_tokens or 0
                provider_model_stats[key]["output_tokens"] += call.output_tokens or 0
                provider_model_stats[key]["total_tokens"] += call.total_tokens or 0
                provider_model_stats[key]["count"] += 1

            print(f"\nBreakdown by provider/model (last {args.limit} calls):")
            for (provider, model), stats in provider_model_stats.items():
                print(f"  {provider}/{model}:")
                print(f"    Calls: {stats['count']}")
                print(f"    Input:  {stats['input_tokens']:,}")
                print(f"    Output: {stats['output_tokens']:,}")
                print(f"    Total:  {stats['total_tokens']:,}")

            print(f"\nRecent calls (last {min(len(recent_calls), args.limit)}):")
            for call in recent_calls[: args.limit]:
                latency_str = f"{call.latency_ms}ms" if call.latency_ms else "N/A"
                tokens_str = f"in:{call.input_tokens or 0} out:{call.output_tokens or 0} total:{call.total_tokens or 0}"
                print(f"  {call.created_at} | {call.provider}/{call.model} | {tokens_str} | {latency_str}")
        else:
            print("\nNo usage data available yet")

        return 0

    if args.command == "task-tree":
        # Get the task
        task_maybe = container.storage.get_task(args.task_id)
        if not task_maybe:
            print(f"Error: Task not found: {args.task_id}")
            return 1
        task = task_maybe

        # Print parent task header
        print(f"Task: {task.id}")
        print(f"  Type:       {task.type}")
        print(f"  Status:     {task.status.value}")
        print(f"  Agent:      {task.agent_id or 'N/A'}")
        print(f"  Created:    {task.created_at.isoformat()}")
        print(f"  Updated:    {task.updated_at.isoformat()}")
        print(f"  Result:     {'Yes' if task.result_json else 'No'}")
        print(f"  Error:      {'Yes' if task.error_json else 'No'}")

        # Get worker plan if available
        worker_plan = container.storage.get_task_worker_plan(args.task_id)
        if worker_plan:
            print("  Worker Plan:")
            print(f"    Modes:     {worker_plan['worker_modes']}")
            print(f"    Rationale: {worker_plan['rationale']}")
            print(f"    Count:     {worker_plan['worker_count']}")

        # Get routing for parent
        routing = container.storage.get_task_latest_routing(args.task_id)
        if routing:
            print("  Routing:")
            print(f"    Provider:  {routing['provider']}")
            print(f"    Model:     {routing['model']}")
            print(f"    Mode:      {routing['mode']}")
            if args.show_reasons and routing["reasons"]:
                print(f"    Reasons:   {', '.join(routing['reasons'][:5])}")

        # Get usage for parent
        usage = container.storage.get_task_usage_totals(args.task_id)
        if usage["calls"] > 0:
            print("  Usage:")
            print(f"    Calls:     {usage['calls']}")
            print(
                f"    Tokens:    {usage['total_tokens']:,} (in:{usage['input_tokens']:,}, out:{usage['output_tokens']:,})"
            )
            if usage["avg_latency_ms"] > 0:
                print(f"    Avg Latency: {usage['avg_latency_ms']}ms")

        # Get and display children
        children = container.storage.list_child_tasks(args.task_id)
        if children:
            print(f"\nChild Tasks ({len(children)}):")
            for idx, child in enumerate(children):
                print(f"\n  [{idx}] {child.id}")
                print(f"      Type:       {child.type}")
                print(f"      Status:     {child.status.value}")
                print(f"      Agent:      {child.agent_id or 'N/A'}")
                print(f"      Result:     {'Yes' if child.result_json else 'No'}")

                # Get desired_quality from payload if present
                if "desired_quality" in child.payload:
                    print(f"      Desired:    {child.payload['desired_quality']}")

                # Get routing for child
                child_routing = container.storage.get_task_latest_routing(child.id)
                if child_routing:
                    print(
                        f"      Routed:     {child_routing['provider']}/{child_routing['model']} ({child_routing['mode']})"
                    )
                    if args.show_reasons and child_routing["reasons"]:
                        reasons_str = ", ".join(child_routing["reasons"][:3])
                        if len(child_routing["reasons"]) > 3:
                            reasons_str += f", ... (+{len(child_routing['reasons']) - 3} more)"
                        print(f"      Reasons:    {reasons_str}")

                # Get usage for child
                child_usage = container.storage.get_task_usage_totals(child.id)
                if child_usage["calls"] > 0:
                    print(f"      Usage:      {child_usage['total_tokens']:,} tokens, {child_usage['calls']} calls")
        else:
            print("\nNo child tasks found.")

        return 0

    if args.command == "resume-project":
        # Resume the project (transition orphaned tasks)
        summary = resume_project.execute(orchestrator, args.project_id)

        print(f"Project resumed: {summary.project_id}")
        print(f"  Tasks moved RUNNING → PENDING: {summary.orphaned_to_pending}")
        print("  Current status counts:")
        print(f"    PENDING:   {summary.pending}")
        print(f"    RUNNING:   {summary.running}")
        print(f"    COMPLETED: {summary.completed}")
        print(f"    FAILED:    {summary.failed}")

        # If --continue flag is set, execute pending tasks
        if args.continue_exec and summary.pending > 0:
            print(f"\nContinuing execution of {summary.pending} pending task(s)...")

            # Execute all pending tasks via Application use case
            async def _continue_execution() -> None:
                continue_summary = await continue_project.execute(orchestrator, args.project_id)
                print("\nExecution complete:")
                print(f"  Tasks executed: {continue_summary.pending_tasks}")
                print(f"  Succeeded: {continue_summary.succeeded}")
                print(f"  Failed: {continue_summary.failed}")

            asyncio.run(_continue_execution())

        return 0

    if args.command == "replay-project":
        # Derive project state from events (READ-ONLY)
        replay_service = ProjectReplayService(container.storage)  # type: ignore
        state_view = replay_service.execute(args.project_id)  # type: ignore

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
            for llm_summary in state_view.llm_executions[:10]:  # Show top 10
                provider = llm_summary.provider_used or llm_summary.provider_requested or "unknown"
                outcome = llm_summary.outcome or "unknown"
                print(f"    - {llm_summary.execution_id}: {provider} → {outcome}")
            if len(state_view.llm_executions) > 10:
                print(f"    ... and {len(state_view.llm_executions) - 10} more")

        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
