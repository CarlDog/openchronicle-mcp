from __future__ import annotations

from openchronicle_core.core.domain.models.project import Event
from openchronicle_core.core.domain.services.orchestrator import OrchestratorService


def timeline(orchestrator: OrchestratorService, task_id: str) -> list[Event]:
    return orchestrator.storage.list_events(task_id)
