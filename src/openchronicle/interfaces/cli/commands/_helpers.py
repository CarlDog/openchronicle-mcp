"""Shared utilities for CLI command handlers."""

from __future__ import annotations

import json
from typing import Any

from openchronicle.core.application.services.orchestrator import OrchestratorService
from openchronicle.core.application.use_cases import register_agent
from openchronicle.core.domain.models.project import Agent
from openchronicle.core.domain.services.verification import VerificationResult
from openchronicle.interfaces.cli.stdio import (
    json_envelope as _json_envelope,
)
from openchronicle.interfaces.cli.stdio import (
    json_error_payload as _json_error_payload,
)

# Re-export for use by command handlers
json_envelope = _json_envelope
json_error_payload = _json_error_payload


def parse_json(value: str) -> dict[str, Any]:
    try:
        result: dict[str, Any] = json.loads(value)
        return result
    except json.JSONDecodeError:
        return {"raw": value}


def print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True, indent=2))


def ensure_agent(orchestrator: OrchestratorService, project_id: str, name: str, role: str) -> Agent:
    existing = [a for a in orchestrator.storage.list_agents(project_id) if a.name == name and a.role == role]
    if existing:
        return existing[0]
    return register_agent.execute(orchestrator, project_id=project_id, name=name, role=role)


def ensure_demo_agents(orchestrator: OrchestratorService, project_id: str) -> tuple[Agent, Agent, Agent]:
    supervisor = ensure_agent(orchestrator, project_id, "Supervisor", "supervisor")
    worker1 = ensure_agent(orchestrator, project_id, "Worker 1", "worker")
    worker2 = ensure_agent(orchestrator, project_id, "Worker 2", "worker")
    return supervisor, worker1, worker2


def print_verification_result(result: VerificationResult) -> None:
    """Unified printing for verification results."""
    if result.success:
        print("[PASS] Hash chain verified successfully")
        print(f"  Total events: {result.total_events}")
        print(f"  Verified events: {result.verified_events}")
    else:
        print("[FAIL] Hash chain verification failed")
        print(f"  Error: {result.error_message}")
        if result.first_mismatch:
            print(f"  First mismatch at event {result.first_mismatch.get('event_index')}:")
            print(f"    Event ID: {result.first_mismatch.get('event_id')}")
            print(f"    Event type: {result.first_mismatch.get('event_type')}")
            for key, value in result.first_mismatch.items():
                if key not in ["event_index", "event_id", "event_type"]:
                    print(f"    {key}: {value}")
