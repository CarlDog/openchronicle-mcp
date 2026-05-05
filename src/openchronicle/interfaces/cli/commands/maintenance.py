"""Maintenance CLI commands: list / run-once.

The maintenance loop also runs in-process inside ``oc serve``. These
commands are for inspection (`list`) and ad-hoc invocation
(`run-once`) outside a running server.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from openchronicle.core.application.services import maintenance_loop
from openchronicle.core.infrastructure.maintenance import jobs as maintenance_jobs
from openchronicle.core.infrastructure.wiring.container import CoreContainer

from ._helpers import json_envelope, print_json


def cmd_maintenance(args: argparse.Namespace, container: CoreContainer) -> int:
    sub = getattr(args, "maintenance_command", None)
    if sub == "list":
        return cmd_maintenance_list(args, container)
    if sub == "run-once":
        return cmd_maintenance_run_once(args, container)
    print("Usage: oc maintenance {list | run-once <job_name>}")
    return 0


def cmd_maintenance_list(args: argparse.Namespace, container: CoreContainer) -> int:
    """Print the configured maintenance jobs and their schedules."""
    jobs = maintenance_loop.load_jobs(container.file_configs)
    disabled = maintenance_loop.is_disabled()

    if getattr(args, "json", False):
        payload = json_envelope(
            command="maintenance.list",
            ok=True,
            result={
                "loop_disabled": disabled,
                "jobs": [
                    {
                        "name": job.name,
                        "interval_seconds": job.interval_seconds,
                        "enabled": job.enabled,
                    }
                    for job in jobs
                ],
            },
            error=None,
        )
        print_json(payload)
        return 0

    print(f"Maintenance loop: {'DISABLED via env' if disabled else 'enabled'}")
    print()
    print(f"{'Job':<22} {'Interval':>10} {'Status':>10}")
    print("-" * 45)
    for job in jobs:
        status = "ON" if job.enabled else "off"
        print(f"{job.name:<22} {job.interval_seconds:>10}s {status:>10}")
    return 0


def cmd_maintenance_run_once(args: argparse.Namespace, container: CoreContainer) -> int:
    """Manually trigger one maintenance job."""
    if not logging.getLogger().handlers:
        logging.basicConfig(stream=sys.stderr, level=logging.INFO)

    name: str = args.job_name
    handler = maintenance_jobs.HANDLERS.get(name)
    if handler is None:
        print(f"Unknown maintenance job: {name}")
        print(f"Available: {', '.join(sorted(maintenance_jobs.HANDLERS))}")
        return 1

    print(f"Running maintenance job: {name}")
    try:
        asyncio.run(handler(container))
    except Exception as exc:  # noqa: BLE001
        print(f"Error: job {name} failed: {exc}")
        return 1
    print(f"OK: {name} complete")
    return 0
