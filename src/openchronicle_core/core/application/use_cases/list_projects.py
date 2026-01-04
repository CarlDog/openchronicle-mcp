from __future__ import annotations

from openchronicle_core.core.domain.models.project import Project
from openchronicle_core.core.domain.services.orchestrator import OrchestratorService


def execute(orchestrator: OrchestratorService) -> list[Project]:
    return orchestrator.storage.list_projects()
