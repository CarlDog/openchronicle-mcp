"""System and setup CLI commands: init, init-config, list-models, list-handlers, serve, rpc."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.use_cases import init_config, init_runtime
from openchronicle.core.domain.errors.error_codes import INVALID_JSON, INVALID_REQUEST
from openchronicle.interfaces.cli.commands._helpers import json_envelope, json_error_payload, print_json
from openchronicle.interfaces.cli.stdio import (
    STDIO_RPC_PROTOCOL_VERSION,
    dispatch_request,
    json_dumps_line,
    serve_stdio,
)


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
            f"{cfg.provider}\t{cfg.model}\t{status}\t{display}\t"
            f"{'[set]' if key_set else '[missing]'}\t{cfg.filename}"
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
