"""Task CLI commands: run-task, show-task, list-tasks, verify-task, verify-project, replay-task, explain-task, task-tree, usage."""

from __future__ import annotations

import argparse
import asyncio
import json

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.use_cases import run_task, show_task
from openchronicle.core.domain.services.replay import ReplayMode
from openchronicle.core.domain.services.replay import ReplayService as DomainReplayService
from openchronicle.core.domain.services.verification import VerificationResult, VerificationService

from ._helpers import parse_json, print_verification_result


def cmd_run_task(args: argparse.Namespace, container: CoreContainer) -> int:
    payload = parse_json(args.payload)
    task = run_task.submit(container.orchestrator, args.project_id, args.task_type, payload)

    async def _run() -> None:
        result = await run_task.execute(container.orchestrator, task.id, agent_id=args.agent_id)
        print(result)

    asyncio.run(_run())
    return 0


def cmd_show_task(args: argparse.Namespace, container: CoreContainer) -> int:
    if args.result:
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

    events = show_task.timeline(container.orchestrator, args.task_id)
    for e in events:
        print(f"{e.created_at.isoformat()} {e.type} {e.payload}")
    return 0


def cmd_list_tasks(args: argparse.Namespace, container: CoreContainer) -> int:
    tasks = container.storage.list_tasks_by_project(args.project_id)
    if not tasks:
        print("No tasks found")
        return 0

    for task in tasks:
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

        print(f"{task.id} | {task.type:30} | {task.status.value:10} | {task.updated_at.isoformat()} | {result_preview}")
    return 0


def cmd_verify_task(args: argparse.Namespace, container: CoreContainer) -> int:
    verification_service = VerificationService(container.storage)
    verify_result: VerificationResult = verification_service.verify_task_chain(args.task_id)
    print_verification_result(verify_result)
    return 0 if verify_result.success else 1


def cmd_verify_project(args: argparse.Namespace, container: CoreContainer) -> int:
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
        print("\n[PASS] All tasks verified successfully")
        return 0
    print("\n[FAIL] Some tasks failed verification")
    return 1


def cmd_replay_task(args: argparse.Namespace, container: CoreContainer) -> int:
    replay_service = DomainReplayService(container.storage)
    mode_map = {
        "verify": ReplayMode.VERIFY,
        "replay-events": ReplayMode.REPLAY_EVENTS,
        "dry-run": ReplayMode.DRY_RUN,
    }
    mode = mode_map[args.mode]
    replay_result = replay_service.replay_task(args.task_id, mode)

    if args.mode == "verify":
        if replay_result.verification_result:
            print_verification_result(replay_result.verification_result)
            return 0 if replay_result.success else 1
        print("[FAIL] Verification failed - no result available")
        return 1
    if args.mode == "replay-events":
        if replay_result.success:
            print("[PASS] Task replay successful")
            print("\nReconstructed output:")
            print(json.dumps(replay_result.reconstructed_output, indent=2))
            return 0
        print(f"[FAIL] Task replay failed: {replay_result.error_message}")
        return 1
    if args.mode == "dry-run":
        if replay_result.success:
            print("[PASS] Dry run successful")
            print("\nExecution trace:")
            print(json.dumps(replay_result.reconstructed_output, indent=2))
            return 0
        print(f"[FAIL] Dry run failed: {replay_result.error_message}")
        return 1

    return 1  # unreachable but satisfies type checker


def cmd_explain_task(args: argparse.Namespace, container: CoreContainer) -> int:
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

    events = container.storage.list_events(args.task_id)
    agent_ids = {e.agent_id for e in events if e.agent_id}
    if agent_ids:
        print("\nAgents involved:")
        for agent_id in agent_ids:
            maybe_agent = next((a for a in container.storage.list_agents(task.project_id) if a.id == agent_id), None)
            if maybe_agent:
                print(f"  - {maybe_agent.name} ({maybe_agent.role}) [{agent_id}]")

    spans = container.storage.list_spans(args.task_id)
    if spans:
        print(f"\nExecution spans ({len(spans)}):")
        for span in spans:
            duration = ""
            if span.ended_at:
                delta = (span.ended_at - span.created_at).total_seconds()
                duration = f" [{delta:.2f}s]"
            print(f"  - {span.name} ({span.status.value}){duration}")

    print(f"\nEvents ({len(events)}):")
    for idx, event in enumerate(events):
        payload_preview = str(event.payload)[:80]
        if len(str(event.payload)) > 80:
            payload_preview += "..."
        print(f"  {idx + 1}. [{event.created_at.isoformat()}] {event.type}")
        print(f"      {payload_preview}")

    domain_replay_service = DomainReplayService(container.storage)
    replay_result = domain_replay_service.replay_task(args.task_id, ReplayMode.REPLAY_EVENTS)
    if replay_result.success and replay_result.reconstructed_output is not None:
        print("\nFinal result:")
        result_str = json.dumps(replay_result.reconstructed_output, indent=2)
        if len(result_str) > 500:
            result_str = result_str[:500] + "\n  ..."
        print(f"  {result_str}")

    return 0


def cmd_task_tree(args: argparse.Namespace, container: CoreContainer) -> int:
    task_maybe = container.storage.get_task(args.task_id)
    if not task_maybe:
        print(f"Error: Task not found: {args.task_id}")
        return 1
    task = task_maybe

    print(f"Task: {task.id}")
    print(f"  Type:       {task.type}")
    print(f"  Status:     {task.status.value}")
    print(f"  Agent:      {task.agent_id or 'N/A'}")
    print(f"  Created:    {task.created_at.isoformat()}")
    print(f"  Updated:    {task.updated_at.isoformat()}")
    print(f"  Result:     {'Yes' if task.result_json else 'No'}")
    print(f"  Error:      {'Yes' if task.error_json else 'No'}")

    worker_plan = container.storage.get_task_worker_plan(args.task_id)
    if worker_plan:
        print("  Worker Plan:")
        print(f"    Modes:     {worker_plan['worker_modes']}")
        print(f"    Rationale: {worker_plan['rationale']}")
        print(f"    Count:     {worker_plan['worker_count']}")

    routing = container.storage.get_task_latest_routing(args.task_id)
    if routing:
        print("  Routing:")
        print(f"    Provider:  {routing['provider']}")
        print(f"    Model:     {routing['model']}")
        print(f"    Mode:      {routing['mode']}")
        if args.show_reasons and routing["reasons"]:
            print(f"    Reasons:   {', '.join(routing['reasons'][:5])}")

    usage = container.storage.get_task_usage_totals(args.task_id)
    if usage["calls"] > 0:
        print("  Usage:")
        print(f"    Calls:     {usage['calls']}")
        print(
            f"    Tokens:    {usage['total_tokens']:,} (in:{usage['input_tokens']:,}, out:{usage['output_tokens']:,})"
        )
        if usage["avg_latency_ms"] > 0:
            print(f"    Avg Latency: {usage['avg_latency_ms']}ms")

    children = container.storage.list_child_tasks(args.task_id)
    if children:
        print(f"\nChild Tasks ({len(children)}):")
        for idx, child in enumerate(children):
            print(f"\n  [{idx}] {child.id}")
            print(f"      Type:       {child.type}")
            print(f"      Status:     {child.status.value}")
            print(f"      Agent:      {child.agent_id or 'N/A'}")
            print(f"      Result:     {'Yes' if child.result_json else 'No'}")

            if "desired_quality" in child.payload:
                print(f"      Desired:    {child.payload['desired_quality']}")

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

            child_usage = container.storage.get_task_usage_totals(child.id)
            if child_usage["calls"] > 0:
                print(f"      Usage:      {child_usage['total_tokens']:,} tokens, {child_usage['calls']} calls")
    else:
        print("\nNo child tasks found.")

    return 0


def cmd_usage(args: argparse.Namespace, container: CoreContainer) -> int:
    project_totals = container.storage.sum_tokens_by_project(args.project_id)
    recent_calls = container.storage.list_llm_usage_by_project(args.project_id, limit=args.limit)

    print(f"LLM Usage for project: {args.project_id}")
    print("\nTotals:")
    print(f"  Input tokens:  {project_totals.get('input_tokens') or 0:,}")
    print(f"  Output tokens: {project_totals.get('output_tokens') or 0:,}")
    print(f"  Total tokens:  {project_totals.get('total_tokens') or 0:,}")

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
