"""System CLI commands: init, init-config, version, config, serve."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any

from openchronicle.core.application.use_cases import init_config, init_runtime
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.cli.commands._helpers import json_envelope, print_json


def cmd_version(args: argparse.Namespace) -> int:
    import importlib.metadata

    try:
        pkg_version = importlib.metadata.version("openchronicle")
    except importlib.metadata.PackageNotFoundError:
        pkg_version = "unknown"

    python_version = sys.version.split()[0]

    if args.json:
        payload = json_envelope(
            command="version",
            ok=True,
            result={
                "package_version": pkg_version,
                "python_version": python_version,
            },
            error=None,
        )
        print_json(payload)
        return 0

    print(f"openchronicle {pkg_version}")
    print(f"Python {python_version}")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    sub = getattr(args, "config_command", None)
    if sub == "show":
        return cmd_config_show(args)
    print("Usage: oc config {show}")
    return 0


def _mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "****"
    return value[:4] + "****" + value[-4:]


def cmd_config_show(args: argparse.Namespace) -> int:
    from pathlib import Path

    from openchronicle.core.application.config.paths import RuntimePaths
    from openchronicle.core.infrastructure.config.config_loader import load_config_files

    rt = RuntimePaths.resolve()
    paths = {
        "db_path": str(rt.db_path),
        "config_dir": str(rt.config_dir),
        "output_dir": str(rt.output_dir),
    }

    config_path = Path(rt.config_dir)
    file_configs = load_config_files(config_path) if config_path.exists() else {}
    core_loaded = bool(file_configs)

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
                "core_config_loaded": core_loaded,
                "core_config": file_configs,
                "masked_secrets": masked_env,
            },
            error=None,
        )
        print_json(payload)
        return 0

    print("Paths:")
    for key, value in paths.items():
        print(f"  {key:<16} {value}")

    if core_loaded:
        print("\nConfig file: core.json (loaded)")
    else:
        print("\nConfig file: core.json (not found, using defaults)")

    if masked_env:
        print("\nMasked Secrets:")
        for key, value in masked_env.items():
            print(f"  {key}: {value}")

    return 0


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
    for key, payload in result["paths"].items():
        if isinstance(payload, dict):
            _print_status(key, payload)
    return 0


def cmd_init_config(args: argparse.Namespace) -> int:
    config_dir = args.config_dir or os.getenv("OC_CONFIG_DIR", "config")
    result = init_config.execute(config_dir)

    print(f"\nConfiguration initialized at: {result['config_dir']}")
    print()

    created_files = result["created"]
    if isinstance(created_files, list) and created_files:
        print(f"Created {result['created_count']} config(s):")
        for filename in created_files:
            print(f"  + {filename}")
    else:
        print("No new configs created (all already exist)")

    skipped_files = result["skipped"]
    if isinstance(skipped_files, list) and skipped_files:
        print(f"\nSkipped {result['skipped_count']} existing config(s):")
        for filename in skipped_files:
            print(f"  - {filename}")

    return 0


def cmd_serve(args: argparse.Namespace, container: CoreContainer) -> int:
    """Run the unified HTTP + MCP ASGI server in the foreground.

    Single uvicorn process hosts FastAPI at ``/api/v1/*`` and FastMCP at
    ``/mcp``. Default port is 18000 (the v2 HTTP port — MCP collapses
    onto the same port). Logging respects ``OC_LOG_FORMAT=human|json``
    via ``configure_root_logger``.
    """
    import signal

    import uvicorn

    from openchronicle.interfaces.api.app import create_app
    from openchronicle.interfaces.api.config import HTTPConfig
    from openchronicle.interfaces.logging_setup import configure_root_logger

    configure_root_logger()
    log = logging.getLogger(__name__)

    config = HTTPConfig.from_env(file_config=container.file_configs.get("api"))
    # HTTPConfig is frozen — use dataclasses.replace for the CLI overrides
    # rather than mutating in place.
    overrides: dict[str, Any] = {}
    if getattr(args, "host", None):
        overrides["host"] = args.host
    if getattr(args, "port", None):
        overrides["port"] = args.port
    if overrides:
        from dataclasses import replace

        config = replace(config, **overrides)

    app = create_app(container, config)
    # uvicorn's `log_config=None` keeps our root-logger formatting; the
    # default would replace it with uvicorn's coloured one and break
    # OC_LOG_FORMAT=json output.
    uv_config = uvicorn.Config(
        app,
        host=config.host,
        port=config.port,
        log_level=os.getenv("OC_LOG_LEVEL", "info").lower(),
        log_config=None,
    )
    server = uvicorn.Server(uv_config)

    def _handle_signal(signum: int, _frame: object) -> None:
        log.info("Received signal %d, shutting down", signum)
        server.should_exit = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    log.info(
        "OpenChronicle serving on %s:%d (HTTP at /api/v1/*, MCP at /mcp)",
        config.host,
        config.port,
    )
    server.run()
    return 0
