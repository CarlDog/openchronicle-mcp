from __future__ import annotations

from openchronicle.core.application.services.orchestrator import OrchestratorService
from openchronicle.core.domain.models.project import Event


def timeline(orchestrator: OrchestratorService, task_id: str) -> list[Event]:
    return orchestrator.storage.list_events(task_id)
