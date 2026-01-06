from __future__ import annotations

from openchronicle.core.application.services.orchestrator import OrchestratorService
from openchronicle.core.domain.models.project import Project


def execute(orchestrator: OrchestratorService) -> list[Project]:
    return orchestrator.storage.list_projects()
