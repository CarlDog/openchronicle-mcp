from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

from openchronicle.core.application.config.paths import RuntimePaths
from openchronicle.core.application.use_cases import convo_mode
from openchronicle.core.domain.ports.llm_port import LLMProviderError
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.cli.commands import COMMANDS, PRE_CONTAINER_COMMANDS
from openchronicle.interfaces.cli.commands._helpers import json_envelope, json_error_payload, print_json


def _build_container(args: argparse.Namespace) -> CoreContainer | None:
    """Build CoreContainer with acceptance-provider-override logic."""
    # CLI --config-dir overrides env/default for any subcommand that accepts it
    cli_config_dir = getattr(args, "config_dir", None)
    if cli_config_dir:
        os.environ["OC_CONFIG_DIR"] = cli_config_dir

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


def _discover_plugin_cli_commands(
    sub: argparse._SubParsersAction,
    core_commands: set[str],
) -> dict[str, ModuleType]:
    """Scan the plugin directory for plugins that provide CLI commands.

    Each plugin with CLI commands provides ``{plugin_dir}/{name}/cli.py``
    exporting: ``COMMAND`` (str), ``setup_parser(sub)`` (callable),
    ``run(args, container)`` (callable).

    Returns a dict mapping command names to loaded modules.
    """
    plugin_dir = Path(RuntimePaths.resolve().plugin_dir)
    result: dict[str, ModuleType] = {}

    if not plugin_dir.is_dir():
        return result

    for candidate in sorted(plugin_dir.iterdir()):
        cli_file = candidate / "cli.py"
        if not candidate.is_dir() or not cli_file.is_file():
            continue

        module_name = f"oc_plugins.{candidate.name}.cli"

        # Load the module
        try:
            spec = importlib.util.spec_from_file_location(module_name, cli_file)
            if spec is None or spec.loader is None:
                print(f"Warning: could not create spec for {cli_file}", file=sys.stderr)
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: failed to load plugin CLI {cli_file}: {exc}", file=sys.stderr)
            sys.modules.pop(module_name, None)
            continue

        # Validate protocol attributes
        command = getattr(module, "COMMAND", None)
        if not isinstance(command, str) or not command:
            print(f"Warning: {cli_file} missing or invalid COMMAND attribute, skipping", file=sys.stderr)
            sys.modules.pop(module_name, None)
            continue

        setup_fn = getattr(module, "setup_parser", None)
        run_fn = getattr(module, "run", None)
        if not callable(setup_fn):
            print(f"Warning: {cli_file} missing setup_parser() callable, skipping", file=sys.stderr)
            sys.modules.pop(module_name, None)
            continue
        if not callable(run_fn):
            print(f"Warning: {cli_file} missing run() callable, skipping", file=sys.stderr)
            sys.modules.pop(module_name, None)
            continue

        # Collision detection: core commands
        if command in core_commands:
            print(
                f"Warning: plugin {candidate.name} CLI command '{command}' collides with a core command, skipping",
                file=sys.stderr,
            )
            sys.modules.pop(module_name, None)
            continue

        # Collision detection: another plugin
        if command in result:
            print(
                f"Warning: plugin {candidate.name} CLI command '{command}' collides with another plugin, skipping",
                file=sys.stderr,
            )
            sys.modules.pop(module_name, None)
            continue

        # Register argparse subcommands
        try:
            setup_fn(sub)
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: {cli_file} setup_parser() failed: {exc}", file=sys.stderr)
            sys.modules.pop(module_name, None)
            continue

        result[command] = module

    return result


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

    events_cmd = sub.add_parser("events", help="View raw event log")
    events_cmd.add_argument("project_id")
    events_cmd.add_argument("--task-id", default=None, help="Filter by task ID")
    events_cmd.add_argument("--type", dest="event_type", default=None, help="Filter by event type")
    events_cmd.add_argument("--limit", type=int, default=50, help="Max events shown (default: 50)")
    events_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

    show_project_cmd = sub.add_parser("show-project", help="Show project details")
    show_project_cmd.add_argument("project_id")
    show_project_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

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
    convo_show_cmd.add_argument("conversation_id", nargs="?", default=None)
    convo_show_cmd.add_argument("--latest", action="store_true", help="Use most recent conversation")
    convo_show_cmd.add_argument("--limit", type=int, default=None, help="Limit number of turns shown")
    convo_show_cmd.add_argument("--explain", action="store_true", help="Explain each turn from events")
    convo_show_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

    convo_export_cmd = convo_sub.add_parser("export", help="Export conversation as JSON")
    convo_export_cmd.add_argument("conversation_id", nargs="?", default=None)
    convo_export_cmd.add_argument("--latest", action="store_true", help="Use most recent conversation")
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
    convo_ask_cmd.add_argument(
        "conversation_id", nargs="?", default=None, help="Conversation ID (or prompt if --latest)"
    )
    convo_ask_cmd.add_argument("prompt", nargs="?", default=None, help="Prompt text")
    convo_ask_cmd.add_argument("--latest", action="store_true", help="Use most recent conversation")
    convo_ask_cmd.add_argument("--last-n", type=int, default=None, help="Number of prior turns to include")
    convo_ask_cmd.add_argument("--top-k-memory", type=int, default=None, help="Number of memory items to include")
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
    convo_ask_cmd.set_defaults(include_pinned_memory=None)
    convo_ask_cmd.add_argument("--moe", action="store_true", help="Use Mixture-of-Experts consensus mode")

    convo_delete_cmd = convo_sub.add_parser("delete", help="Delete conversation and all related data")
    convo_delete_cmd.add_argument("conversation_id")
    convo_delete_cmd.add_argument("--force", action="store_true", help="Required for destructive delete")
    convo_delete_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

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
    memory_list_cmd.add_argument("--offset", type=int, default=0, help="Skip first N items")

    memory_show_cmd = memory_sub.add_parser("show", help="Show memory item")
    memory_show_cmd.add_argument("memory_id")

    memory_pin_cmd = memory_sub.add_parser("pin", help="Toggle memory pin state")
    memory_pin_cmd.add_argument("memory_id")
    pin_group = memory_pin_cmd.add_mutually_exclusive_group(required=True)
    pin_group.add_argument("--on", dest="pin_on", action="store_true")
    pin_group.add_argument("--off", dest="pin_on", action="store_false")

    memory_delete_cmd = memory_sub.add_parser("delete", help="Delete a memory item")
    memory_delete_cmd.add_argument("memory_id")
    memory_delete_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

    memory_search_cmd = memory_sub.add_parser("search", help="Search memory items")
    memory_search_cmd.add_argument("query")
    memory_search_cmd.add_argument("--top-k", type=int, default=8, help="Number of memory items to return")
    memory_search_cmd.add_argument("--conversation-id", default=None, help="Restrict to conversation")
    memory_search_cmd.add_argument("--project-id", default=None, help="Restrict to project")
    memory_search_cmd.add_argument("--tags", default=None, help="Filter by tags (comma-separated, AND logic)")
    memory_search_group = memory_search_cmd.add_mutually_exclusive_group()
    memory_search_group.add_argument("--include-pinned", dest="include_pinned", action="store_true")
    memory_search_group.add_argument("--no-include-pinned", dest="include_pinned", action="store_false")
    memory_search_cmd.set_defaults(include_pinned=True)
    memory_search_cmd.add_argument("--offset", type=int, default=0, help="Skip first N results")
    memory_search_cmd.add_argument("--full", action="store_true", help="Print full content (for context injection)")

    memory_update_cmd = memory_sub.add_parser("update", help="Update a memory item")
    memory_update_cmd.add_argument("memory_id")
    memory_update_cmd.add_argument("--content", default=None, help="New content (replaces existing)")
    memory_update_cmd.add_argument("--tags", default=None, help="New tags, comma-separated (replaces existing)")

    memory_embed_cmd = memory_sub.add_parser("embed", help="Generate embeddings for memory items")
    memory_embed_cmd.add_argument("--force", action="store_true", help="Regenerate all embeddings (model change)")
    memory_embed_cmd.add_argument("--status", action="store_true", help="Show embedding coverage stats")
    memory_embed_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

    # --- Provider commands ---
    provider_cmd = sub.add_parser("provider", help="Provider setup and management")
    provider_sub = provider_cmd.add_subparsers(dest="provider_command")

    provider_sub.add_parser("list", help="List known providers and their models")

    provider_setup_cmd = provider_sub.add_parser("setup", help="Set up model configs for a provider")
    provider_setup_cmd.add_argument("--provider", default=None, help="Provider name (interactive if omitted)")
    provider_setup_cmd.add_argument("--api-key", default=None, help="API key (written inline to config)")
    provider_setup_cmd.add_argument("--api-key-env", default=None, help="Env var name for API key")
    provider_setup_cmd.add_argument("--models", default=None, help="Comma-separated model IDs (default: all)")
    provider_setup_cmd.add_argument(
        "--config-dir",
        default=None,
        help="Configuration directory (default: OC_CONFIG_DIR env var or 'config')",
    )

    provider_custom_cmd = provider_sub.add_parser("custom", help="Set up a custom provider config")
    provider_custom_cmd.add_argument("--provider", default=None, help="Provider name")
    provider_custom_cmd.add_argument("--model", default=None, help="Model identifier")
    provider_custom_cmd.add_argument("--display-name", default=None, help="Display name")
    provider_custom_cmd.add_argument("--description", default=None, help="Model description")
    provider_custom_cmd.add_argument("--endpoint", default=None, help="API endpoint URL")
    provider_custom_cmd.add_argument("--base-url", default=None, help="Base URL for SDK")
    provider_custom_cmd.add_argument("--auth-header", default=None, help="Auth header name")
    provider_custom_cmd.add_argument("--auth-format", default=None, help="Auth format (e.g. 'Bearer {api_key}')")
    provider_custom_cmd.add_argument("--api-key", default=None, help="API key (written inline to config)")
    provider_custom_cmd.add_argument("--api-key-env", default=None, help="Env var name for API key")
    provider_custom_cmd.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    provider_custom_cmd.add_argument(
        "--config-dir",
        default=None,
        help="Configuration directory (default: OC_CONFIG_DIR env var or 'config')",
    )

    # --- Config commands ---
    config_cmd = sub.add_parser("config", help="Configuration commands")
    config_sub = config_cmd.add_subparsers(dest="config_command")
    config_show_cmd = config_sub.add_parser("show", help="Show effective configuration")
    config_show_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

    # --- Version command ---
    version_cmd = sub.add_parser("version", help="Show version information")
    version_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

    # --- Database commands ---
    db_cmd = sub.add_parser("db", help="Database maintenance commands")
    db_sub = db_cmd.add_subparsers(dest="db_command")

    db_info_cmd = db_sub.add_parser("info", help="Show database information")
    db_info_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

    db_sub.add_parser("vacuum", help="Compact database and truncate WAL")

    db_backup_cmd = db_sub.add_parser("backup", help="Hot-backup database to a file")
    db_backup_cmd.add_argument("path", help="Destination file path")
    db_backup_cmd.add_argument("--force", action="store_true", help="Overwrite if destination exists")

    db_stats_cmd = db_sub.add_parser("stats", help="Show global token usage statistics")
    db_stats_cmd.add_argument("--json", action="store_true", help="Emit JSON output")

    # --- Scheduler commands ---
    sched_cmd = sub.add_parser("scheduler", help="Scheduled job management")
    sched_sub = sched_cmd.add_subparsers(dest="scheduler_command")

    sched_add = sched_sub.add_parser("add", help="Create a scheduled job")
    sched_add.add_argument("--project-id", required=True, help="Project ID")
    sched_add.add_argument("--name", required=True, help="Job name")
    sched_add.add_argument("--task-type", required=True, help="Task type to submit")
    sched_add.add_argument("--payload", required=True, help="JSON task payload")
    sched_add.add_argument("--due-at", default=None, help="ISO datetime for first fire")
    sched_add.add_argument("--interval", type=int, default=None, help="Recurrence interval in seconds")
    sched_add.add_argument("--max-failures", type=int, default=0, help="Max consecutive failures (0=unlimited)")
    sched_add.add_argument("--json", action="store_true", help="Emit JSON output")

    sched_list = sched_sub.add_parser("list", help="List scheduled jobs")
    sched_list.add_argument("--project-id", default=None, help="Filter by project ID")
    sched_list.add_argument("--status", default=None, help="Filter by status")
    sched_list.add_argument("--json", action="store_true", help="Emit JSON output")

    sched_pause = sched_sub.add_parser("pause", help="Pause a scheduled job")
    sched_pause.add_argument("job_id", help="Job ID to pause")
    sched_pause.add_argument("--json", action="store_true", help="Emit JSON output")

    sched_resume = sched_sub.add_parser("resume", help="Resume a paused job")
    sched_resume.add_argument("job_id", help="Job ID to resume")
    sched_resume.add_argument("--json", action="store_true", help="Emit JSON output")

    sched_cancel = sched_sub.add_parser("cancel", help="Cancel a scheduled job")
    sched_cancel.add_argument("job_id", help="Job ID to cancel")
    sched_cancel.add_argument("--json", action="store_true", help="Emit JSON output")

    sched_tick = sched_sub.add_parser("tick", help="Fire one scheduler tick")
    sched_tick.add_argument("--max-jobs", type=int, default=10, help="Max jobs per tick")
    sched_tick.add_argument("--json", action="store_true", help="Emit JSON output")

    # --- Discord commands ---
    discord_cmd = sub.add_parser("discord", help="Discord bot commands")
    discord_sub = discord_cmd.add_subparsers(dest="discord_command")
    discord_start = discord_sub.add_parser("start", help="Start the Discord bot (long-running)")
    discord_start.add_argument("--force", action="store_true", help="Ignore existing PID file and start anyway")

    # --- MCP commands ---
    mcp_cmd = sub.add_parser("mcp", help="MCP server commands")
    mcp_sub = mcp_cmd.add_subparsers(dest="mcp_command")
    mcp_serve = mcp_sub.add_parser("serve", help="Start the MCP server")
    mcp_serve.add_argument(
        "--transport", choices=["stdio", "sse"], default=None, help="Transport protocol (default: stdio)"
    )
    mcp_serve.add_argument("--host", default=None, help="Bind address for SSE transport (default: 127.0.0.1)")
    mcp_serve.add_argument("--port", type=int, default=None, help="Port for SSE transport (default: 8080)")
    mcp_serve.add_argument(
        "--config-dir",
        default=None,
        help="Configuration directory (default: OC_CONFIG_DIR env var or 'config')",
    )

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
    serve_cmd.add_argument(
        "--http-only",
        action="store_true",
        default=False,
        help="Run only the HTTP API server (no stdio). Use in Docker or headless deployments.",
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

    # --- Onboard commands ---
    onboard_cmd = sub.add_parser("onboard", help="Onboarding commands")
    onboard_sub = onboard_cmd.add_subparsers(dest="onboard_command")

    onboard_git_cmd = onboard_sub.add_parser("git", help="Bootstrap memories from git history")
    onboard_git_cmd.add_argument("--project-id", dest="project_id", required=True, help="Project ID")
    onboard_git_cmd.add_argument("--repo-path", dest="repo_path", default=".", help="Path to git repo (default: .)")
    onboard_git_cmd.add_argument(
        "--max-commits", dest="max_commits", type=int, default=500, help="Max commits to analyze (default: 500)"
    )
    onboard_git_cmd.add_argument(
        "--max-memories", dest="max_memories", type=int, default=15, help="Max memories to create (default: 15)"
    )
    onboard_git_cmd.add_argument("--force", action="store_true", help="Delete existing git-onboard memories and re-run")
    onboard_git_cmd.add_argument(
        "--no-llm", dest="no_llm", action="store_true", help="Skip LLM synthesis, use raw format"
    )
    onboard_git_cmd.add_argument("--dry-run", dest="dry_run", action="store_true", help="Show clusters without saving")

    # --- Asset commands ---
    asset_cmd = sub.add_parser("asset", help="Asset management commands")
    asset_sub = asset_cmd.add_subparsers(dest="asset_command")

    asset_upload_cmd = asset_sub.add_parser("upload", help="Upload a file as an asset")
    asset_upload_cmd.add_argument("project_id", help="Project ID")
    asset_upload_cmd.add_argument("source_path", help="Path to file to upload")
    asset_upload_cmd.add_argument("--filename", default=None, help="Override filename")
    asset_upload_cmd.add_argument("--mime-type", dest="mime_type", default=None, help="Override MIME type")

    asset_list_cmd = asset_sub.add_parser("list", help="List assets in a project")
    asset_list_cmd.add_argument("project_id", help="Project ID")
    asset_list_cmd.add_argument("--limit", type=int, default=None, help="Limit number of assets shown")

    asset_show_cmd = asset_sub.add_parser("show", help="Show asset details and links")
    asset_show_cmd.add_argument("asset_id", help="Asset ID")

    asset_link_cmd = asset_sub.add_parser("link", help="Link an asset to an entity")
    asset_link_cmd.add_argument("asset_id", help="Asset ID")
    asset_link_cmd.add_argument("target_type", help="Entity type (project, conversation, turn, memory_item)")
    asset_link_cmd.add_argument("target_id", help="Entity ID")
    asset_link_cmd.add_argument("--role", default="reference", help="Link role (default: reference)")

    # --- Media commands ---
    media_cmd = sub.add_parser("media", help="Media generation commands")
    media_sub = media_cmd.add_subparsers(dest="media_command")

    media_gen_cmd = media_sub.add_parser("generate", help="Generate media from a text prompt")
    media_gen_cmd.add_argument("prompt", help="Text prompt for generation")
    media_gen_cmd.add_argument("--project-id", dest="project_id", required=True, help="Project ID")
    media_gen_cmd.add_argument("--type", dest="media_type", default="image", help="Media type (image, video)")
    media_gen_cmd.add_argument("--model", default=None, help="Override model name")
    media_gen_cmd.add_argument("--width", type=int, default=None, help="Image width in pixels")
    media_gen_cmd.add_argument("--height", type=int, default=None, help="Image height in pixels")
    media_gen_cmd.add_argument("--negative-prompt", dest="negative_prompt", default=None, help="Negative prompt")
    media_gen_cmd.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    media_gen_cmd.add_argument("--steps", type=int, default=None, help="Number of diffusion steps")

    # --- Webhook commands ---
    webhook_cmd = sub.add_parser("webhook", help="Webhook subscription commands")
    webhook_sub = webhook_cmd.add_subparsers(dest="webhook_command")

    webhook_reg_cmd = webhook_sub.add_parser("register", help="Register a new webhook subscription")
    webhook_reg_cmd.add_argument("url", help="Target endpoint URL")
    webhook_reg_cmd.add_argument("--project-id", dest="project_id", required=True, help="Project ID")
    webhook_reg_cmd.add_argument("--filter", default="*", help="Event filter glob pattern (default: *)")
    webhook_reg_cmd.add_argument("--description", default="", help="Human-readable description")

    webhook_list_cmd = webhook_sub.add_parser("list", help="List webhook subscriptions")
    webhook_list_cmd.add_argument("--project-id", dest="project_id", default=None, help="Filter by project ID")
    webhook_list_cmd.add_argument("--active-only", dest="active_only", action="store_true", help="Show only active")

    webhook_del_cmd = webhook_sub.add_parser("delete", help="Delete a webhook subscription")
    webhook_del_cmd.add_argument("webhook_id", help="Webhook subscription ID")

    webhook_deliv_cmd = webhook_sub.add_parser("deliveries", help="List delivery attempts for a webhook")
    webhook_deliv_cmd.add_argument("webhook_id", help="Webhook subscription ID")
    webhook_deliv_cmd.add_argument("--limit", type=int, default=20, help="Limit number of deliveries shown")

    # --- Ollama commands ---
    ollama_cmd = sub.add_parser("ollama", help="Ollama model management commands")
    ollama_sub = ollama_cmd.add_subparsers(dest="ollama_command")

    ollama_list_cmd = ollama_sub.add_parser("list", help="List installed Ollama models and config status")
    ollama_list_cmd.add_argument("--json", dest="json_output", action="store_true", help="Output as JSON")

    ollama_show_cmd = ollama_sub.add_parser("show", help="Show details for an installed Ollama model")
    ollama_show_cmd.add_argument("model", help="Model name (e.g. mistral:instruct, llava:latest)")
    ollama_show_cmd.add_argument("--config", dest="show_config", action="store_true", help="Show generated config")

    ollama_add_cmd = ollama_sub.add_parser("add", help="Create a config file for an installed model")
    ollama_add_cmd.add_argument("model", help="Model name (e.g. mistral:instruct)")
    ollama_add_cmd.add_argument("--force", action="store_true", help="Overwrite existing config")

    ollama_rm_cmd = ollama_sub.add_parser("remove", help="Remove a model's config file")
    ollama_rm_cmd.add_argument("model", help="Model name (e.g. mistral:instruct)")

    ollama_sync_cmd = ollama_sub.add_parser("sync", help="Create configs for all unconfigured installed models")
    ollama_sync_cmd.add_argument("--prune", action="store_true", help="Remove stale configs for uninstalled models")

    # --- Chat ---
    chat_cmd = sub.add_parser("chat", help="Interactive chat session")
    chat_cmd.add_argument("--conversation-id", default=None, help="Resume specific conversation by ID")
    chat_cmd.add_argument("--resume", action="store_true", help="Resume most recent conversation")
    chat_cmd.add_argument("--title", default=None, help="Title for new conversation")
    chat_cmd.add_argument("--no-stream", dest="no_stream", action="store_true", help="Disable streaming output")
    chat_cmd.add_argument("--moe", action="store_true", help="Use Mixture-of-Experts consensus mode")

    # --- Plugin CLI commands (discovered dynamically) ---
    _all_core_commands = set(COMMANDS) | set(PRE_CONTAINER_COMMANDS)
    plugin_cli_commands = _discover_plugin_cli_commands(sub, _all_core_commands)

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

    # Plugin CLI dispatch
    plugin_module = plugin_cli_commands.get(args.command)
    if plugin_module is not None:
        return int(plugin_module.run(args, container))

    # Core dispatch
    handler = COMMANDS.get(args.command)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args, container)


if __name__ == "__main__":
    raise SystemExit(main())
