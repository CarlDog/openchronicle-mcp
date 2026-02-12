from __future__ import annotations

import argparse
import os

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.use_cases import convo_mode
from openchronicle.core.domain.ports.llm_port import LLMProviderError
from openchronicle.interfaces.cli.commands import COMMANDS, PRE_CONTAINER_COMMANDS
from openchronicle.interfaces.cli.commands._helpers import json_envelope, json_error_payload, print_json


def _build_container(args: argparse.Namespace) -> CoreContainer | None:
    """Build CoreContainer with acceptance-provider-override logic."""
    provider_override = os.getenv("OC_ACCEPTANCE_PROVIDER", "stub").strip()
    original_provider = None
    if args.command == "acceptance" and provider_override:
        original_provider = os.getenv("OC_LLM_PROVIDER")
        os.environ["OC_LLM_PROVIDER"] = provider_override
        os.environ.setdefault("OC_LLM_FAST_POOL", "")
        os.environ.setdefault("OC_LLM_QUALITY_POOL", "")
        os.environ.setdefault("OC_LLM_POOL_NSFW", "")

    try:
        container = CoreContainer()
    except LLMProviderError as exc:
        if args.command in {"rpc", "acceptance"}:
            payload = json_envelope(
                command=args.command,
                ok=False,
                result=None,
                error=json_error_payload(
                    error_code=exc.error_code,
                    message=str(exc),
                    hint=exc.hint,
                ),
            )
            print_json(payload)
            return None
        print(str(exc))
        return None
    finally:
        if args.command == "acceptance" and original_provider is not None:
            os.environ["OC_LLM_PROVIDER"] = original_provider

    return container


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="oc", description="OpenChronicle v2 minimal CLI")
    sub = parser.add_subparsers(dest="command")

    # --- Project commands ---
    init_project_cmd = sub.add_parser("init-project", help="Create a project")
    init_project_cmd.add_argument("name")

    sub.add_parser("list-projects", help="List projects")

    reg_cmd = sub.add_parser("register-agent", help="Register an agent")
    reg_cmd.add_argument("project_id")
    reg_cmd.add_argument("name")
    reg_cmd.add_argument("--role", default="worker")
    reg_cmd.add_argument("--provider", default="")
    reg_cmd.add_argument("--model", default="")

    resume_cmd = sub.add_parser("resume-project", help="Resume incomplete tasks in a project")
    resume_cmd.add_argument("project_id")
    resume_cmd.add_argument(
        "--continue", dest="continue_exec", action="store_true", help="Continue execution after resume"
    )

    replay_project_cmd = sub.add_parser("replay-project", help="Show derived project state from events")
    replay_project_cmd.add_argument("--project-id", required=True, help="Project identifier")
    replay_project_cmd.add_argument("--show-llm", action="store_true", help="Show LLM execution summaries")

    # --- Task commands ---
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

    tree_cmd = sub.add_parser("task-tree", help="Show task tree with routing and usage")
    tree_cmd.add_argument("task_id")
    tree_cmd.add_argument("--depth", type=int, default=2, help="Tree depth (default: 2 for parent + children)")
    tree_cmd.add_argument("--show-reasons", action="store_true", help="Show routing reasons")

    usage_cmd = sub.add_parser("usage", help="Show LLM usage statistics")
    usage_cmd.add_argument("project_id")
    usage_cmd.add_argument("--limit", type=int, default=20, help="Number of recent calls to show")

    # --- Conversation commands ---
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
    convo_ask_cmd.add_argument("--allow-pii", action="store_true", help="Bypass privacy gate for this request")
    convo_ask_cmd.add_argument(
        "--enqueue-if-unavailable",
        action="store_true",
        help="Queue the ask when provider execution is unavailable",
    )
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

    # --- Memory commands ---
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

    # --- System commands ---
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

    sub.add_parser("list-handlers", help="List registered task handlers")

    serve_cmd = sub.add_parser("serve", help="Run stdio JSON command server")
    serve_cmd.add_argument(
        "--idle-timeout-seconds",
        type=int,
        default=0,
        help="Exit after N seconds of stdin inactivity (default: 0 disables)",
    )

    rpc_cmd = sub.add_parser("rpc", help="Run a single JSON RPC request")
    rpc_cmd.add_argument("--request", default=None, help="JSON request string")

    init_cmd = sub.add_parser("init", help="Initialize runtime directories and optional templates")
    init_cmd.add_argument("--json", action="store_true", help="Emit JSON output")
    init_cmd.add_argument("--force", action="store_true", help="Overwrite templates if they exist")
    init_cmd.add_argument("--no-templates", action="store_true", help="Skip template file creation")

    # --- Debug/demo commands ---
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

    smoke_cmd = sub.add_parser("smoke-live", help="Smoke test: minimal end-to-end LLM call with real provider")
    smoke_cmd.add_argument("--provider", default=None, help="Force provider (optional override)")
    smoke_cmd.add_argument("--model", default=None, help="Force model (optional override)")
    smoke_cmd.add_argument("--prompt", default=None, help="Custom prompt (optional)")
    smoke_cmd.add_argument("--json", action="store_true", help="Output result as JSON")

    selftest_cmd = sub.add_parser("selftest", help="Run deterministic CLI-only selftest")
    selftest_cmd.add_argument(
        "--dir",
        dest="base_dir",
        default="output/selftest",
        help="Base directory for selftest workspace (default: output/selftest)",
    )
    selftest_cmd.add_argument("--json", action="store_true", help="Emit JSON output")
    selftest_cmd.add_argument("--keep-artifacts", action="store_true", help="Keep selftest workspace on success")
    selftest_cmd.add_argument("--no-plugins", action="store_true", help="Skip plugin loading and execution")
    selftest_cmd.add_argument(
        "--telemetry-self-report",
        action="store_true",
        help="Enable telemetry memory self-report for this selftest run",
    )

    diag_cmd = sub.add_parser("diagnose", help="Troubleshoot runtime, paths, persistence, and provider config")
    diag_cmd.add_argument("--json", action="store_true", help="Output diagnostics as JSON")

    acceptance_cmd = sub.add_parser("acceptance", help="Run deterministic acceptance workflow")
    acceptance_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

    # --- Chat ---
    chat_cmd = sub.add_parser("chat", help="Interactive chat session")
    chat_cmd.add_argument("--conversation-id", default=None, help="Resume existing conversation")
    chat_cmd.add_argument("--title", default=None, help="Title for new conversation")

    # --- Parse ---
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    # Pre-container commands (no CoreContainer needed)
    if args.command in PRE_CONTAINER_COMMANDS:
        return PRE_CONTAINER_COMMANDS[args.command](args)

    # Build container
    container = _build_container(args)
    if container is None:
        return 1

    # Dispatch
    handler = COMMANDS.get(args.command)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args, container)


if __name__ == "__main__":
    raise SystemExit(main())
