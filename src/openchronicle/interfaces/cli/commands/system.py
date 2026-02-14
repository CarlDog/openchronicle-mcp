"""System and setup CLI commands: init, init-config, provider, list-models, list-handlers, serve, rpc."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.use_cases import init_config, init_runtime, provider_setup
from openchronicle.core.domain.errors.error_codes import INVALID_JSON, INVALID_REQUEST
from openchronicle.interfaces.cli.commands._helpers import json_envelope, json_error_payload, print_json
from openchronicle.interfaces.cli.stdio import (
    STDIO_RPC_PROTOCOL_VERSION,
    dispatch_request,
    json_dumps_line,
    serve_stdio,
)


def cmd_version(args: argparse.Namespace) -> int:
    """Print version information."""
    import importlib.metadata

    from openchronicle.interfaces.cli.commands._helpers import json_envelope, print_json

    try:
        pkg_version = importlib.metadata.version("openchronicle")
    except importlib.metadata.PackageNotFoundError:
        pkg_version = "unknown"

    python_version = sys.version.split()[0]
    protocol_version = STDIO_RPC_PROTOCOL_VERSION

    if args.json:
        payload = json_envelope(
            command="version",
            ok=True,
            result={
                "package_version": pkg_version,
                "python_version": python_version,
                "protocol_version": protocol_version,
            },
            error=None,
        )
        print_json(payload)
        return 0

    print(f"openchronicle {pkg_version}")
    print(f"Python {python_version}")
    print(f"Protocol v{protocol_version}")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """Dispatch config subcommands."""
    sub = getattr(args, "config_command", None)
    if sub == "show":
        return cmd_config_show(args)
    print("Usage: oc config {show}")
    return 0


def _mask_secret(value: str) -> str:
    """Mask a string that looks like a secret (API key, token, etc.)."""
    if len(value) <= 8:
        return "****"
    return value[:4] + "****" + value[-4:]


def cmd_config_show(args: argparse.Namespace) -> int:
    """Show effective runtime configuration."""
    from dataclasses import asdict

    from openchronicle.core.application.routing.pool_config import load_pool_config
    from openchronicle.core.infrastructure.config.budget_config import load_budget_policy
    from openchronicle.core.infrastructure.config.settings import (
        load_privacy_outbound_settings,
        load_router_assist_settings,
        load_telemetry_settings,
    )

    # Resolved paths
    paths = {
        "db_path": os.getenv("OC_DB_PATH", "data/openchronicle.db"),
        "config_dir": os.getenv("OC_CONFIG_DIR", "config"),
        "plugin_dir": os.getenv("OC_PLUGIN_DIR", "plugins"),
        "output_dir": os.getenv("OC_OUTPUT_DIR", "output"),
    }

    # Provider
    provider = os.getenv("OC_LLM_PROVIDER", "stub")

    # Pools
    pool_config = load_pool_config()
    pools = {
        "fast_pool": [f"{c.provider}:{c.model}" for c in pool_config.fast_pool],
        "quality_pool": [f"{c.provider}:{c.model}" for c in pool_config.quality_pool],
        "nsfw_pool": [f"{c.provider}:{c.model}" for c in pool_config.nsfw_pool],
        "provider_weights": pool_config.provider_weights,
        "max_fallbacks": pool_config.max_fallbacks,
        "fallback_on_transient": pool_config.fallback_on_transient,
        "fallback_on_constraint": pool_config.fallback_on_constraint,
        "fallback_on_refusal": pool_config.fallback_on_refusal,
    }

    # Budget
    budget = load_budget_policy()
    budget_dict = budget.to_dict()

    # Privacy
    privacy = load_privacy_outbound_settings()
    privacy_dict = asdict(privacy)

    # Telemetry
    telemetry = load_telemetry_settings()
    telemetry_dict = asdict(telemetry)

    # Router assist
    router_assist = load_router_assist_settings()
    router_assist_dict = asdict(router_assist)

    # Mask any env vars that look like secrets
    masked_env: dict[str, str] = {}
    for key in sorted(os.environ):
        if key.startswith("OC_") and any(s in key.upper() for s in ("KEY", "SECRET", "TOKEN", "PASSWORD")):
            masked_env[key] = _mask_secret(os.environ[key])

    if args.json:
        payload = json_envelope(
            command="config.show",
            ok=True,
            result={
                "paths": paths,
                "provider": provider,
                "pools": pools,
                "budget": budget_dict,
                "privacy": privacy_dict,
                "telemetry": telemetry_dict,
                "router_assist": router_assist_dict,
                "masked_secrets": masked_env,
            },
            error=None,
        )
        print_json(payload)
        return 0

    print("Paths:")
    for key, value in paths.items():
        print(f"  {key:<16} {value}")

    print(f"\nProvider: {provider}")

    print("\nPools:")
    fast_list: list[str] = pools["fast_pool"]  # type: ignore[assignment]
    quality_list: list[str] = pools["quality_pool"]  # type: ignore[assignment]
    nsfw_list: list[str] = pools["nsfw_pool"]  # type: ignore[assignment]
    print(f"  fast:    {', '.join(fast_list) or '(empty)'}")
    print(f"  quality: {', '.join(quality_list) or '(empty)'}")
    print(f"  nsfw:    {', '.join(nsfw_list) or '(empty)'}")
    print(f"  weights: {pools['provider_weights']}")
    print(f"  max_fallbacks: {pools['max_fallbacks']}")

    print("\nBudget:")
    print(f"  max_total_tokens: {budget_dict['max_total_tokens'] or '(none)'}")
    print(f"  max_llm_calls:    {budget_dict['max_llm_calls'] or '(none)'}")

    print("\nPrivacy:")
    for key, value in privacy_dict.items():
        print(f"  {key:<20} {value}")

    print("\nTelemetry:")
    for key, value in telemetry_dict.items():
        print(f"  {key:<35} {value}")

    print("\nRouter Assist:")
    for key, value in router_assist_dict.items():
        print(f"  {key:<16} {value}")

    if masked_env:
        print("\nMasked Secrets:")
        for key, value in masked_env.items():
            print(f"  {key}: {value}")

    return 0


def _configure_stdio_logging() -> None:
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(stream=sys.stderr, level=logging.INFO)


def cmd_init(args: argparse.Namespace) -> int:
    paths = init_runtime.resolve_runtime_paths()
    result = init_runtime.execute(paths, write_templates=not args.no_templates, force=args.force)
    if args.json:
        print_json(result)
        return 0

    def _print_status(label: str, payload: dict[str, object]) -> None:
        status = payload.get("status")
        path = payload.get("path")
        extra = payload.get("parent")
        if extra:
            print(f"{label}: {status} ({path}; parent={extra})")
        else:
            print(f"{label}: {status} ({path})")

    print("Runtime paths:")
    _print_status("db_path", result["paths"]["db_path"])
    _print_status("config_dir", result["paths"]["config_dir"])
    _print_status("plugin_dir", result["paths"]["plugin_dir"])
    _print_status("output_dir", result["paths"]["output_dir"])

    print("Templates:")
    _print_status("model_config", result["templates"]["model_config"])
    _print_status("router_assist_model", result["templates"]["router_assist_model"])
    return 0


def cmd_init_config(args: argparse.Namespace) -> int:
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


def cmd_list_models(args: argparse.Namespace, container: CoreContainer) -> int:
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
            f"{cfg.provider}\t{cfg.model}\t{status}\t{display}\t{'[set]' if key_set else '[missing]'}\t{cfg.filename}"
        )

    return 0


def cmd_list_handlers(args: argparse.Namespace, container: CoreContainer) -> int:
    orchestrator = container.orchestrator
    builtins = orchestrator.list_builtin_handlers()
    plugins = orchestrator.list_registered_handlers()
    print("Built-in handlers:")
    for h in builtins:
        print(f"  {h}")
    print("Plugin handlers:")
    for h in plugins:
        print(f"  {h}")
    return 0


def cmd_serve(args: argparse.Namespace, container: CoreContainer) -> int:
    _configure_stdio_logging()
    return serve_stdio(container, idle_timeout_seconds=args.idle_timeout_seconds)


def cmd_rpc(args: argparse.Namespace, container: CoreContainer) -> int:
    _configure_stdio_logging()
    request_raw = args.request
    if request_raw is None:
        request_raw = ""
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            if line.strip():
                request_raw = line.strip()
                break

    try:
        request = json.loads(request_raw)
    except json.JSONDecodeError as exc:
        payload = json_envelope(
            command="unknown",
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=INVALID_JSON,
                message=str(exc),
                hint=None,
            ),
        )
        payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
        sys.stdout.write(json_dumps_line(payload) + "\n")
        sys.stdout.flush()
        return 0

    if not isinstance(request, dict):
        payload = json_envelope(
            command="unknown",
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=INVALID_REQUEST,
                message="Request must be a JSON object",
                hint=None,
            ),
        )
        payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
        sys.stdout.write(json_dumps_line(payload) + "\n")
        sys.stdout.flush()
        return 0

    payload = dispatch_request(container, request)
    sys.stdout.write(json_dumps_line(payload) + "\n")
    sys.stdout.flush()
    return 0


def cmd_provider(args: argparse.Namespace) -> int:
    """Dispatch provider subcommands."""
    sub = getattr(args, "provider_command", None)
    if sub == "list":
        return _cmd_provider_list()
    if sub == "setup":
        return _cmd_provider_setup(args)
    if sub == "custom":
        return _cmd_provider_custom(args)
    # No subcommand — print usage
    print("Usage: oc provider {list|setup|custom}")
    print()
    print("  list    List known providers and their models")
    print("  setup   Set up model configs for a provider")
    print("  custom  Set up a custom provider config")
    return 0


def _cmd_provider_list() -> int:
    """Print table of known providers and models."""
    providers = provider_setup.list_providers()
    if not providers:
        print("No providers registered.")
        return 0

    for p in providers:
        key_info = f"(key: ${p['api_key_env']})" if p["requires_api_key"] else "(no key needed)"
        print(f"\n  {p['name']:<12} {p['display_name']}  {key_info}")
        models = p.get("models", [])
        if isinstance(models, list):
            for m in models:
                if isinstance(m, dict):
                    print(f"    - {m['model_id']:<30} [{m['pool_hint']}]  {m.get('display_name', '')}")
    print()
    return 0


def _cmd_provider_setup(args: argparse.Namespace) -> int:
    """Set up model configs for a known provider (interactive or non-interactive)."""
    import getpass

    config_dir = args.config_dir or os.getenv("OC_CONFIG_DIR", "config")
    provider_name = args.provider
    api_key = args.api_key
    api_key_env = args.api_key_env
    model_filter = [m.strip() for m in args.models.split(",")] if args.models else None
    non_interactive = provider_name is not None

    # Interactive mode: prompt for provider
    if provider_name is None:
        providers = provider_setup.list_providers()
        print("\nAvailable providers:\n")
        for i, p in enumerate(providers, 1):
            key_info = f"(key: ${p['api_key_env']})" if p["requires_api_key"] else "(no key needed)"
            print(f"  {i}. {p['name']:<12} {p['display_name']}  {key_info}")
        print()

        try:
            choice = input("Select provider [number]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 1

        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(providers):
                print(f"Invalid selection: {choice}")
                return 1
            provider_name = str(providers[idx]["name"])
        except ValueError:
            # Accept name directly
            provider_name = choice

    # Validate provider exists
    info = provider_setup.get_provider_info(provider_name)
    if info is None:
        print(f"Unknown provider: {provider_name}")
        return 1

    # Interactive key prompt (only in interactive mode)
    if not non_interactive and api_key is None and api_key_env is None and info["requires_api_key"]:
        default_env = str(info["api_key_env"]) if info["api_key_env"] else None
        print(f"\n{provider_name} requires an API key.")
        if default_env:
            print(f"  Default env var: {default_env}")

        try:
            key_input = getpass.getpass("  Enter API key (or press Enter to use env var): ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 1

        if key_input.strip():
            api_key = key_input.strip()
        # else: leave both None — service will write api_key_env from registry default

    # Interactive model selection (only in interactive mode)
    if not non_interactive and model_filter is None:
        models_list = info.get("models", [])
        if isinstance(models_list, list) and len(models_list) > 1:
            print(f"\nModels for {provider_name}:\n")
            for i, m in enumerate(models_list, 1):
                if isinstance(m, dict):
                    print(f"  {i}. {m['model_id']:<30} [{m['pool_hint']}]  {m.get('description', '')}")
            print()

            try:
                selection = input("Select models [numbers, comma-separated, or Enter for all]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 1

            if selection:
                try:
                    indices = [int(s.strip()) - 1 for s in selection.split(",")]
                    model_filter = []
                    for idx in indices:
                        if 0 <= idx < len(models_list):
                            m = models_list[idx]
                            if isinstance(m, dict):
                                model_filter.append(str(m["model_id"]))
                except ValueError:
                    print(f"Invalid selection: {selection}")
                    return 1

    try:
        result = provider_setup.setup_provider(
            provider_name=provider_name,
            config_dir=config_dir,
            api_key=api_key,
            api_key_env=api_key_env,
            models=model_filter,
        )
    except ValueError as exc:
        print(str(exc))
        return 1

    _print_setup_result(result)
    return 0


def _cmd_provider_custom(args: argparse.Namespace) -> int:
    """Set up a custom/blank provider config (interactive or non-interactive)."""
    config_dir = args.config_dir or os.getenv("OC_CONFIG_DIR", "config")
    provider = args.provider
    model = args.model

    # Interactive prompts for required fields
    if provider is None:
        try:
            provider = input("Provider name: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 1
        if not provider:
            print("Provider name is required.")
            return 1

    if model is None:
        try:
            model = input("Model identifier: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 1
        if not model:
            print("Model identifier is required.")
            return 1

    result = provider_setup.setup_custom(
        config_dir=config_dir,
        provider=provider,
        model=model,
        display_name=args.display_name,
        description=args.description,
        endpoint=args.endpoint,
        base_url=args.base_url,
        auth_header=args.auth_header,
        auth_format=args.auth_format,
        api_key=args.api_key,
        api_key_env=args.api_key_env,
        timeout=args.timeout,
    )
    _print_setup_result(result)
    return 0


def _print_setup_result(result: dict[str, str | int | list[str]]) -> None:
    """Shared output formatting for provider setup results."""
    print(f"\nProvider: {result['provider']}")
    print(f"Config dir: {result['models_dir']}")
    print()

    created = result["created"]
    if isinstance(created, list) and created:
        print(f"Created {result['created_count']} config(s):")
        for f in created:
            print(f"  + {f}")
    else:
        print("No new configs created (all already exist).")

    skipped = result["skipped"]
    if isinstance(skipped, list) and skipped:
        print(f"\nSkipped {result['skipped_count']} existing config(s):")
        for f in skipped:
            print(f"  - {f}")
