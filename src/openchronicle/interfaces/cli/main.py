from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.services.orchestrator import OrchestratorService
from openchronicle.core.application.use_cases import (
    add_memory,
    ask_conversation,
    continue_project,
    convo_mode,
    create_conversation,
    create_project,
    diagnose_runtime,
    explain_turn,
    export_convo,
    init_config,
    list_conversations,
    list_memory,
    list_projects,
    pin_memory,
    register_agent,
    remember_turn,
    resume_project,
    run_task,
    search_memory,
    show_conversation,
    show_memory,
    show_task,
    smoke_live,
)
from openchronicle.core.application.use_cases.replay_project import (
    ReplayService as ProjectReplayService,
)
from openchronicle.core.domain.models.failure_category import failure_category_description
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Agent
from openchronicle.core.domain.ports.llm_port import LLMProviderError
from openchronicle.core.domain.services.replay import ReplayMode
from openchronicle.core.domain.services.replay import ReplayService as DomainReplayService
from openchronicle.core.domain.services.verification import (
    VerificationResult,
    VerificationService,
)
from openchronicle.interfaces.cli.stdio import (
    json_envelope as _json_envelope,
)
from openchronicle.interfaces.cli.stdio import (
    json_error_payload as _json_error_payload,
)
from openchronicle.interfaces.cli.stdio import (
    serve_stdio,
)


def _parse_json(value: str) -> dict[str, Any]:
    try:
        result: dict[str, Any] = json.loads(value)
        return result
    except json.JSONDecodeError:
        return {"raw": value}


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True, indent=2))


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

    init_project_cmd = sub.add_parser("init-project", help="Create a project")
    init_project_cmd.add_argument("name")

    init_config_cmd = sub.add_parser("init-config", help="Initialize model configuration with examples")
    init_config_cmd.add_argument(
        "--config-dir",
        default=None,
        help="Configuration directory (default: OC_CONFIG_DIR env var or 'config')",
    )

    list_models_cmd = sub.add_parser("list-models", help="List available model configs (v1)")
    list_models_cmd.add_argument(
        "--config-dir",
        default=None,
        help="Configuration directory (default: OC_CONFIG_DIR env var or 'config')",
    )

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
    sub.add_parser("serve", help="Run stdio JSON command server")

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

    convo_cmd = sub.add_parser("convo", help="Conversation commands")
    convo_sub = convo_cmd.add_subparsers(dest="convo_command")

    convo_new_cmd = convo_sub.add_parser("new", help="Create a new conversation")
    convo_new_cmd.add_argument("--title", default=None, help="Optional conversation title")

    convo_show_cmd = convo_sub.add_parser("show", help="Show conversation transcript")
    convo_show_cmd.add_argument("conversation_id")
    convo_show_cmd.add_argument("--limit", type=int, default=None, help="Limit number of turns shown")
    convo_show_cmd.add_argument("--explain", action="store_true", help="Explain each turn from events")
    convo_show_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

    convo_export_cmd = convo_sub.add_parser("export", help="Export conversation as JSON")
    convo_export_cmd.add_argument("conversation_id")
    convo_export_cmd.add_argument("--explain", action="store_true", help="Include explain bundles per turn")
    convo_export_cmd.add_argument("--verify", action="store_true", help="Include verification results")
    convo_export_cmd.add_argument("--fail-on-verify", action="store_true", help="Exit non-zero on verification failure")
    convo_export_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

    convo_verify_cmd = convo_sub.add_parser("verify", help="Verify conversation event hash chain")
    convo_verify_cmd.add_argument("conversation_id")
    convo_verify_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

    convo_mode_cmd = convo_sub.add_parser("mode", help="Get or set conversation mode")
    convo_mode_cmd.add_argument("conversation_id")
    convo_mode_cmd.add_argument(
        "--set",
        dest="mode",
        choices=convo_mode.ALLOWED_CONVERSATION_MODES,
        help="Set the conversation mode",
    )
    convo_mode_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

    convo_ask_cmd = convo_sub.add_parser("ask", help="Ask a prompt in a conversation")
    convo_ask_cmd.add_argument("conversation_id")
    convo_ask_cmd.add_argument("prompt")
    convo_ask_cmd.add_argument("--last-n", type=int, default=10, help="Number of prior turns to include")
    convo_ask_cmd.add_argument("--top-k-memory", type=int, default=8, help="Number of memory items to include")
    convo_ask_cmd.add_argument("--explain", action="store_true", help="Explain the turn from events")
    convo_ask_cmd.add_argument("--json", action="store_true", help="Emit JSON output")
    convo_ask_group = convo_ask_cmd.add_mutually_exclusive_group()
    convo_ask_group.add_argument("--include-pinned-memory", dest="include_pinned_memory", action="store_true")
    convo_ask_group.add_argument("--no-include-pinned-memory", dest="include_pinned_memory", action="store_false")
    convo_ask_cmd.set_defaults(include_pinned_memory=True)

    convo_list_cmd = convo_sub.add_parser("list", help="List conversations")
    convo_list_cmd.add_argument("--limit", type=int, default=None, help="Limit number of conversations shown")

    convo_remember_cmd = convo_sub.add_parser("remember", help="Remember a turn as memory")
    convo_remember_cmd.add_argument("conversation_id")
    convo_remember_cmd.add_argument("turn_index", type=int)
    convo_remember_cmd.add_argument("--which", choices=["user", "assistant"], required=True)
    convo_remember_cmd.add_argument("--tags", default="", help="Comma-separated tags")
    convo_remember_cmd.add_argument("--pin", action="store_true", help="Pin this memory item")
    convo_remember_cmd.add_argument("--source", default="turn", help="Source label")

    memory_cmd = sub.add_parser("memory", help="Memory commands")
    memory_sub = memory_cmd.add_subparsers(dest="memory_command")

    memory_add_cmd = memory_sub.add_parser("add", help="Add a memory item")
    memory_add_cmd.add_argument("content")
    memory_add_cmd.add_argument("--tags", default="", help="Comma-separated tags")
    memory_add_cmd.add_argument("--pin", action="store_true", help="Pin this memory item")
    memory_add_cmd.add_argument("--source", default="manual", help="Source label")
    memory_add_cmd.add_argument("--conversation-id", default=None, help="Associated conversation id")
    memory_add_cmd.add_argument("--project-id", default=None, help="Associated project id")

    memory_list_cmd = memory_sub.add_parser("list", help="List memory items")
    memory_list_cmd.add_argument("--limit", type=int, default=None, help="Limit number of memories shown")
    memory_list_cmd.add_argument("--pinned-only", action="store_true", help="Show only pinned items")

    memory_show_cmd = memory_sub.add_parser("show", help="Show memory item")
    memory_show_cmd.add_argument("memory_id")

    memory_pin_cmd = memory_sub.add_parser("pin", help="Toggle memory pin state")
    memory_pin_cmd.add_argument("memory_id")
    pin_group = memory_pin_cmd.add_mutually_exclusive_group(required=True)
    pin_group.add_argument("--on", dest="pin_on", action="store_true")
    pin_group.add_argument("--off", dest="pin_on", action="store_false")

    memory_search_cmd = memory_sub.add_parser("search", help="Search memory items")
    memory_search_cmd.add_argument("query")
    memory_search_cmd.add_argument("--top-k", type=int, default=8, help="Number of memory items to return")
    memory_search_cmd.add_argument("--conversation-id", default=None, help="Restrict to conversation")
    memory_search_cmd.add_argument("--project-id", default=None, help="Restrict to project")
    memory_search_group = memory_search_cmd.add_mutually_exclusive_group()
    memory_search_group.add_argument("--include-pinned", dest="include_pinned", action="store_true")
    memory_search_group.add_argument("--no-include-pinned", dest="include_pinned", action="store_false")
    memory_search_cmd.set_defaults(include_pinned=True)

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

    smoke_cmd = sub.add_parser("smoke-live", help="Smoke test: minimal end-to-end LLM call with real provider")
    smoke_cmd.add_argument("--provider", default=None, help="Force provider (optional override)")
    smoke_cmd.add_argument("--model", default=None, help="Force model (optional override)")
    smoke_cmd.add_argument("--prompt", default=None, help="Custom prompt (optional)")
    smoke_cmd.add_argument("--json", action="store_true", help="Output result as JSON")

    diag_cmd = sub.add_parser("diagnose", help="Troubleshoot runtime, paths, persistence, and provider config")
    diag_cmd.add_argument("--json", action="store_true", help="Output diagnostics as JSON")

    args = parser.parse_args(argv)
    container = CoreContainer()
    orchestrator = container.orchestrator

    if args.command == "init-project":
        project = create_project.execute(orchestrator, args.name)
        print(project)
        return 0

    if args.command == "init-config":
        import os

        config_dir = args.config_dir or os.getenv("OC_CONFIG_DIR", "config")
        result = init_config.execute(config_dir)

        print(f"\nConfiguration initialized at: {result['config_dir']}")
        print(f"Models directory: {result['models_dir']}")
        print()

        created_files = result["created"]
        if isinstance(created_files, list) and created_files:
            print(f"Created {result['created_count']} model config(s):")
            for filename in created_files:
                print(f"  - {filename}")
        else:
            print("No new configs created (all examples already exist)")

        skipped_files = result["skipped"]
        if isinstance(skipped_files, list) and skipped_files:
            print(f"\nSkipped {result['skipped_count']} existing config(s):")
            for filename in skipped_files:
                print(f"  - {filename}")

        return 0

    if args.command == "list-models":
        import os

        from openchronicle.core.application.config.model_config import ModelConfigLoader, sort_model_configs

        config_dir = args.config_dir or os.getenv("OC_CONFIG_DIR", "config")
        loader = ModelConfigLoader(config_dir)
        configs = loader.list_all()

        if not configs:
            print("No model configs found")
            return 0

        print("provider\tmodel\tstatus\tdisplay_name\tapi_key\tfile")
        for cfg in sort_model_configs(configs):
            api_cfg = cfg.api_config
            inline_key = api_cfg.get("api_key")
            env_name = api_cfg.get("api_key_env")
            standard_env = loader._standard_api_env(cfg.provider)  # noqa: SLF001 - intentionally reuse helper
            env_set = bool(env_name and os.getenv(str(env_name)))
            standard_env_set = bool(standard_env and os.getenv(standard_env))
            key_set = bool(inline_key) or env_set or standard_env_set

            status = "enabled" if cfg.enabled else "disabled"
            display = cfg.display_name or "-"
            print(
                f"{cfg.provider}\t{cfg.model}\t{status}\t{display}\t"
                f"{'[set]' if key_set else '[missing]'}\t{cfg.filename}"
            )

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
            llm = create_provider_aware_llm()
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

    if args.command == "serve":
        return serve_stdio(container)

    if args.command == "verify-task":
        verification_service = VerificationService(container.storage)
        verify_result: VerificationResult = verification_service.verify_task_chain(args.task_id)
        _print_verification_result(verify_result)
        return 0 if verify_result.success else 1

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

    if args.command == "convo":
        if args.convo_command == "new":
            conversation = create_conversation.execute(
                storage=container.storage,
                convo_store=container.storage,
                emit_event=container.event_logger.append,
                title=args.title,
            )
            print(conversation.id)
            return 0

        if args.convo_command == "show":
            try:
                conversation, turns = show_conversation.execute(
                    convo_store=container.storage,
                    conversation_id=args.conversation_id,
                    limit=args.limit,
                )
            except ValueError as exc:
                if args.json:
                    payload = _json_envelope(
                        command="convo.show",
                        ok=False,
                        result=None,
                        error=_json_error_payload(
                            error_code=None,
                            message=str(exc),
                            hint=None,
                        ),
                    )
                    _print_json(payload)
                    return 1

                print(str(exc))
                return 1

            if args.json:
                turns_payload: list[dict[str, object]] = []
                for turn in turns:
                    explain_payload: dict[str, object] | None = None
                    if args.explain:
                        try:
                            explain_payload = explain_turn.execute(
                                storage=container.storage,
                                conversation_id=args.conversation_id,
                                turn_id=turn.id,
                            )
                        except ValueError:
                            explain_payload = None
                    turns_payload.append(
                        {
                            "turn_id": turn.id,
                            "turn_index": turn.turn_index,
                            "user_text": turn.user_text,
                            "assistant_text": turn.assistant_text,
                            "explain": explain_payload if args.explain else None,
                        }
                    )

                payload = _json_envelope(
                    command="convo.show",
                    ok=True,
                    result={
                        "conversation_id": conversation.id,
                        "mode": conversation.mode,
                        "turns": turns_payload,
                    },
                    error=None,
                )
                _print_json(payload)
                return 0

            for turn in turns:
                if not args.explain:
                    print(f"{turn.turn_index}\t{turn.user_text}\t{turn.assistant_text}")
                    continue

                print(f"Turn {turn.turn_index}:")
                print(f"user: {turn.user_text}")
                print(f"assistant: {turn.assistant_text}")

                try:
                    explain = explain_turn.execute(
                        storage=container.storage,
                        conversation_id=args.conversation_id,
                        turn_id=turn.id,
                    )
                except ValueError:
                    print("EXPLAIN")
                    print("unavailable: missing events")
                    continue

                reasons = explain.get("routing_reasons", [])
                reasons_str = ",".join(reasons) if isinstance(reasons, list) else ""
                memory_info = explain.get("memory")
                memory_dict = memory_info if isinstance(memory_info, dict) else {}
                pinned_ids = memory_dict.get("pinned_ids", []) if isinstance(memory_dict, dict) else []
                relevant_ids = memory_dict.get("relevant_ids", []) if isinstance(memory_dict, dict) else []
                pinned_str = ",".join(pinned_ids) if isinstance(pinned_ids, list) else ""
                relevant_str = ",".join(relevant_ids) if isinstance(relevant_ids, list) else ""
                memory_written_ids = explain.get("memory_written_ids", [])
                memory_written_str = ",".join(memory_written_ids) if isinstance(memory_written_ids, list) else ""
                llm_info = explain.get("llm")
                llm_dict = llm_info if isinstance(llm_info, dict) else {}
                usage_info = llm_dict.get("usage") if isinstance(llm_dict, dict) else {}
                usage_dict = usage_info if isinstance(usage_info, dict) else {}
                usage_in = usage_dict.get("input_tokens")
                usage_out = usage_dict.get("output_tokens")
                usage_total = usage_dict.get("total_tokens")
                latency_ms = llm_dict.get("latency_ms")
                finish_reason = llm_dict.get("finish_reason")

                print("EXPLAIN")
                print(f"provider: {explain.get('provider') or ''}")
                print(f"model: {explain.get('model') or ''}")
                print(f"reasons: {reasons_str}")
                print(f"pinned_memory_ids: {pinned_str}")
                print(f"relevant_memory_ids: {relevant_str}")
                print(f"memory_written_ids: {memory_written_str}")
                print(
                    "usage: "
                    f"in={'' if usage_in is None else usage_in} "
                    f"out={'' if usage_out is None else usage_out} "
                    f"total={'' if usage_total is None else usage_total} "
                    f"latency_ms={'' if latency_ms is None else latency_ms} "
                    f"finish_reason={'' if finish_reason is None else finish_reason}"
                )
            return 0

        if args.convo_command == "export":
            try:
                export = export_convo.execute(
                    storage=container.storage,
                    convo_store=container.storage,
                    conversation_id=args.conversation_id,
                    include_explain=args.explain,
                    include_verify=args.verify,
                )
            except ValueError as exc:
                if args.json:
                    payload = _json_envelope(
                        command="convo.export",
                        ok=False,
                        result=None,
                        error=_json_error_payload(
                            error_code=None,
                            message=str(exc),
                            hint=None,
                        ),
                    )
                    _print_json(payload)
                    return 1

                print(str(exc))
                return 1

            if args.json:
                ok = True
                if args.verify:
                    verification = export.get("verification") if isinstance(export, dict) else None
                    verification_dict = verification if isinstance(verification, dict) else {}
                    ok = verification_dict.get("ok") is True

                payload = _json_envelope(
                    command="convo.export",
                    ok=ok,
                    result=export,
                    error=None
                    if ok
                    else _json_error_payload(
                        error_code=None,
                        message="verification failed",
                        hint=None,
                    ),
                )
                _print_json(payload)
                if args.verify and args.fail_on_verify and not ok:
                    return 1
                return 0

            print(json.dumps(export, sort_keys=True, indent=2))
            if args.verify and args.fail_on_verify:
                verification = export.get("verification") if isinstance(export, dict) else None
                verification_dict = verification if isinstance(verification, dict) else {}
                if verification_dict.get("ok") is not True:
                    return 1
            return 0

        if args.convo_command == "verify":
            verification_service = VerificationService(container.storage)
            convo_verify_result: VerificationResult = verification_service.verify_task_chain(args.conversation_id)
            if args.json:
                first_mismatch = convo_verify_result.first_mismatch or {}
                expected_hash = first_mismatch.get("expected_hash")
                actual_hash = first_mismatch.get("computed_hash")
                if expected_hash is None and actual_hash is None:
                    expected_hash = first_mismatch.get("expected_prev_hash")
                    actual_hash = first_mismatch.get("actual_prev_hash")
                verification_payload = {
                    "ok": convo_verify_result.success,
                    "failure_event_id": first_mismatch.get("event_id"),
                    "expected_hash": expected_hash,
                    "actual_hash": actual_hash,
                }
                payload = _json_envelope(
                    command="convo.verify",
                    ok=convo_verify_result.success,
                    result={
                        "conversation_id": args.conversation_id,
                        "verification": verification_payload,
                    },
                    error=None
                    if convo_verify_result.success
                    else _json_error_payload(
                        error_code=None,
                        message=convo_verify_result.error_message or "verification failed",
                        hint=None,
                    ),
                )
                _print_json(payload)
                return 0 if convo_verify_result.success else 1

            if convo_verify_result.success:
                print("OK")
                return 0

            error_message = convo_verify_result.error_message or "verification failed"
            print(f"FAIL: {error_message}")

            first_mismatch = convo_verify_result.first_mismatch or {}
            event_id = first_mismatch.get("event_id")
            if event_id:
                print(f"event_id: {event_id}")

            expected_hash = first_mismatch.get("expected_hash")
            actual_hash = first_mismatch.get("computed_hash")
            if expected_hash is None and actual_hash is None:
                expected_hash = first_mismatch.get("expected_prev_hash")
                actual_hash = first_mismatch.get("actual_prev_hash")
            if expected_hash is not None or actual_hash is not None:
                print(f"expected_hash: {'' if expected_hash is None else expected_hash}")
                print(f"actual_hash: {'' if actual_hash is None else actual_hash}")

            print(f"hint: run oc replay-task {args.conversation_id} --mode verify or oc diagnose")
            return 1

        if args.convo_command == "mode":
            try:
                if args.mode is None:
                    conversation_mode = convo_mode.get_mode(
                        convo_store=container.storage,
                        conversation_id=args.conversation_id,
                    )
                else:
                    conversation_mode = convo_mode.set_mode(
                        convo_store=container.storage,
                        conversation_id=args.conversation_id,
                        mode=args.mode,
                    )
            except ValueError as exc:
                if args.json:
                    payload = _json_envelope(
                        command="convo.mode",
                        ok=False,
                        result=None,
                        error=_json_error_payload(
                            error_code=None,
                            message=str(exc),
                            hint=None,
                        ),
                    )
                    _print_json(payload)
                    return 1

                print(str(exc))
                return 1

            if args.json:
                payload = _json_envelope(
                    command="convo.mode",
                    ok=True,
                    result={
                        "conversation_id": args.conversation_id,
                        "mode": conversation_mode,
                    },
                    error=None,
                )
                _print_json(payload)
                return 0

            print(conversation_mode)
            return 0

        if args.convo_command == "list":
            conversations = list_conversations.execute(convo_store=container.storage, limit=args.limit)
            for conversation in conversations:
                print(f"{conversation.id}\t{conversation.title}\t{conversation.created_at.isoformat()}")
            return 0

        if args.convo_command == "remember":
            tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()]
            item = remember_turn.execute(
                storage=container.storage,
                convo_store=container.storage,
                memory_store=container.storage,
                emit_event=container.event_logger.append,
                conversation_id=args.conversation_id,
                turn_index=args.turn_index,
                which=args.which,
                tags=tags,
                pinned=args.pin,
                source=args.source,
            )
            print(item.id)
            return 0

        if args.convo_command == "ask":

            async def _run_ask() -> int:
                try:
                    turn = await ask_conversation.execute(
                        convo_store=container.storage,
                        storage=container.storage,
                        memory_store=container.storage,
                        llm=container.llm,
                        interaction_router=container.interaction_router,
                        emit_event=container.event_logger.append,
                        conversation_id=args.conversation_id,
                        prompt_text=args.prompt,
                        last_n=args.last_n,
                        top_k_memory=args.top_k_memory,
                        include_pinned_memory=args.include_pinned_memory,
                    )
                except (ValueError, LLMProviderError) as exc:
                    if not args.json:
                        print(str(exc))
                        return 1

                    error_code = exc.error_code if isinstance(exc, LLMProviderError) else None
                    hint = exc.hint if isinstance(exc, LLMProviderError) else None
                    payload = _json_envelope(
                        command="convo.ask",
                        ok=False,
                        result=None,
                        error=_json_error_payload(
                            error_code=error_code,
                            message=str(exc),
                            hint=hint,
                        ),
                    )
                    _print_json(payload)
                    return 1

                if args.json:
                    explain_payload: dict[str, object] | None = None
                    if args.explain:
                        try:
                            explain_payload = explain_turn.execute(
                                storage=container.storage,
                                conversation_id=args.conversation_id,
                                turn_id=turn.id,
                            )
                        except ValueError:
                            explain_payload = None
                    payload = _json_envelope(
                        command="convo.ask",
                        ok=True,
                        result={
                            "conversation_id": turn.conversation_id,
                            "turn_id": turn.id,
                            "turn_index": turn.turn_index,
                            "assistant_text": turn.assistant_text,
                            "explain": explain_payload if args.explain else None,
                        },
                        error=None,
                    )
                    _print_json(payload)
                    return 0

                print(turn.assistant_text)

                if args.explain:
                    explain = explain_turn.execute(
                        storage=container.storage,
                        conversation_id=args.conversation_id,
                        turn_id=turn.id,
                    )
                    reasons = explain.get("routing_reasons", [])
                    reasons_str = ",".join(reasons) if isinstance(reasons, list) else ""
                    memory_info = explain.get("memory")
                    memory_dict = memory_info if isinstance(memory_info, dict) else {}
                    pinned_ids = memory_dict.get("pinned_ids", []) if isinstance(memory_dict, dict) else []
                    relevant_ids = memory_dict.get("relevant_ids", []) if isinstance(memory_dict, dict) else []
                    pinned_str = ",".join(pinned_ids) if isinstance(pinned_ids, list) else ""
                    relevant_str = ",".join(relevant_ids) if isinstance(relevant_ids, list) else ""
                    memory_written_ids = explain.get("memory_written_ids", [])
                    memory_written_str = ",".join(memory_written_ids) if isinstance(memory_written_ids, list) else ""
                    llm_info = explain.get("llm")
                    llm_dict = llm_info if isinstance(llm_info, dict) else {}
                    usage_info = llm_dict.get("usage") if isinstance(llm_dict, dict) else {}
                    usage_dict = usage_info if isinstance(usage_info, dict) else {}
                    usage_in = usage_dict.get("input_tokens")
                    usage_out = usage_dict.get("output_tokens")
                    usage_total = usage_dict.get("total_tokens")
                    latency_ms = llm_dict.get("latency_ms")
                    finish_reason = llm_dict.get("finish_reason")

                    print()
                    print("EXPLAIN")
                    print(f"provider: {explain.get('provider') or ''}")
                    print(f"model: {explain.get('model') or ''}")
                    print(f"reasons: {reasons_str}")
                    print(f"pinned_memory_ids: {pinned_str}")
                    print(f"relevant_memory_ids: {relevant_str}")
                    print(f"memory_written_ids: {memory_written_str}")
                    print(
                        "usage: "
                        f"in={'' if usage_in is None else usage_in} "
                        f"out={'' if usage_out is None else usage_out} "
                        f"total={'' if usage_total is None else usage_total} "
                        f"latency_ms={'' if latency_ms is None else latency_ms} "
                        f"finish_reason={'' if finish_reason is None else finish_reason}"
                    )
                return 0

            return asyncio.run(_run_ask())

    if args.command == "memory":
        if args.memory_command == "add":
            tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()]
            project_id = args.project_id
            if project_id is None and args.conversation_id:
                maybe_conversation = container.storage.get_conversation(args.conversation_id)
                if maybe_conversation is None:
                    print(f"Conversation not found: {args.conversation_id}")
                    return 1
                project_id = maybe_conversation.project_id
            if project_id is None:
                print("project_id is required when adding memory")
                return 1
            item = add_memory.execute(
                store=container.storage,
                emit_event=container.event_logger.append,
                item=MemoryItem(
                    content=args.content,
                    tags=tags,
                    pinned=args.pin,
                    conversation_id=args.conversation_id,
                    project_id=project_id,
                    source=args.source,
                ),
            )
            print(item.id)
            return 0

        if args.memory_command == "list":
            items = list_memory.execute(
                store=container.storage,
                limit=args.limit,
                pinned_only=args.pinned_only,
            )
            for item in items:
                tags_str = ",".join(item.tags)
                snippet = item.content if len(item.content) <= 120 else item.content[:120] + "..."
                print(f"{item.id}\t{item.pinned}\t{item.created_at.isoformat()}\t{tags_str}\t{snippet}")
            return 0

        if args.memory_command == "show":
            try:
                item = show_memory.execute(container.storage, args.memory_id)
            except ValueError as exc:
                print(str(exc))
                return 1

            print(f"id: {item.id}")
            print(f"pinned: {item.pinned}")
            print(f"created_at: {item.created_at.isoformat()}")
            print(f"tags: {','.join(item.tags)}")
            print(f"source: {item.source}")
            print(f"conversation_id: {item.conversation_id or ''}")
            print(f"project_id: {item.project_id or ''}")
            print("content:")
            print(item.content)
            return 0

        if args.memory_command == "pin":
            pin_memory.execute(
                store=container.storage,
                emit_event=container.event_logger.append,
                memory_id=args.memory_id,
                pinned=args.pin_on,
            )
            return 0

        if args.memory_command == "search":
            items = search_memory.execute(
                store=container.storage,
                query=args.query,
                top_k=args.top_k,
                conversation_id=args.conversation_id,
                project_id=args.project_id,
                include_pinned=args.include_pinned,
            )
            for item in items:
                tags_str = ",".join(item.tags)
                snippet = item.content if len(item.content) <= 120 else item.content[:120] + "..."
                print(f"{item.id}\t{item.pinned}\t{item.created_at.isoformat()}\t{tags_str}\t{snippet}")
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

    if args.command == "smoke-live":
        # Run smoke test with optional provider/model overrides
        async def _smoke() -> int:
            result = await smoke_live.execute(
                orchestrator,
                prompt=args.prompt,
                provider=args.provider,
                model=args.model,
            )

            if args.json:
                # Output JSON result
                print(json.dumps(result.to_dict(), indent=2))
            else:
                # Output human-readable result
                print("\n" + "=" * 60)
                print("SMOKE TEST RESULT")
                print("=" * 60)
                print(f"Project ID:       {result.project_id}")
                print(f"Task ID:          {result.task_id}")
                print(f"Execution ID:     {result.execution_id}")
                print(f"Attempt ID:       {result.attempt_id}")
                print()
                print("PROVIDER & MODEL")
                provider_line = f"Provider Requested: {result.provider_requested or '(default)'}"
                print(provider_line)
                print(f"Provider Used:      {result.provider_used}")
                model_line = f"Model Requested:    {result.model_requested or '(default)'}"
                print(model_line)
                print(f"Model Used:         {result.model_used}")
                print()
                print("OUTCOME")
                print(f"Outcome:            {result.outcome}")
                if result.failure_category:
                    category_desc = failure_category_description(result.failure_category)
                    print(f"Failure Category:   {result.failure_category} ({category_desc})")
                if result.error_code:
                    print(f"Error Code:         {result.error_code}")
                if result.error_message:
                    print(f"Error Message:      {result.error_message}")
                print()
                print("TOKEN USAGE")
                print(f"Prompt Tokens:      {result.prompt_tokens or 'N/A'}")
                print(f"Completion Tokens:  {result.completion_tokens or 'N/A'}")
                print(f"Total Tokens:       {result.total_tokens or 'N/A'}")
                if result.latency_ms:
                    print(f"Latency (ms):       {result.latency_ms}")
                print("=" * 60)

            return 0 if result.outcome == "completed" else 1

        return asyncio.run(_smoke())

    if args.command == "diagnose":
        report = diagnose_runtime.execute()
        if args.json:
            # JSON output
            output_dict = {
                "timestamp_utc": report.timestamp_utc.isoformat(),
                "db_path": report.db_path,
                "db_exists": report.db_exists,
                "db_size_bytes": report.db_size_bytes,
                "db_modified_utc": report.db_modified_utc.isoformat() if report.db_modified_utc else None,
                "config_dir": report.config_dir,
                "config_dir_exists": report.config_dir_exists,
                "plugin_dir": report.plugin_dir,
                "plugin_dir_exists": report.plugin_dir_exists,
                "running_in_container_hint": report.running_in_container_hint,
                "persistence_hint": report.persistence_hint,
                "provider_env_summary": report.provider_env_summary,
            }
            print(json.dumps(output_dict, indent=2))
        else:
            # Human-readable output
            print("\n" + "=" * 60)
            print("RUNTIME DIAGNOSTICS")
            print("=" * 60)
            print(f"Timestamp:           {report.timestamp_utc.isoformat()}")
            print()
            print("PATHS")
            print("  Database:")
            print(f"    Path:             {report.db_path}")
            print(f"    Exists:           {report.db_exists}")
            if report.db_exists:
                size_mb = (report.db_size_bytes or 0) / (1024 * 1024)
                print(f"    Size:             {report.db_size_bytes} bytes ({size_mb:.2f} MB)")
                if report.db_modified_utc:
                    print(f"    Last modified:    {report.db_modified_utc.isoformat()}")
            print()
            print("  Config:")
            print(f"    Path:             {report.config_dir}")
            print(f"    Exists:           {report.config_dir_exists}")
            print()
            print("  Plugins:")
            print(f"    Path:             {report.plugin_dir}")
            print(f"    Exists:           {report.plugin_dir_exists}")
            print()
            print("RUNTIME")
            print(f"  In Container:       {report.running_in_container_hint}")
            print(f"  Persistence Hint:   {report.persistence_hint}")
            print()
            print("PROVIDER CONFIG")
            for key, value in sorted(report.provider_env_summary.items()):  # type: ignore
                print(f"  {key:25} {value}")
            print("=" * 60)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
