from __future__ import annotations

from typing import Any

from openchronicle.core.application.services.orchestrator import OrchestratorService
from openchronicle.core.domain.models.project import Project


def execute(orchestrator: OrchestratorService, name: str, metadata: dict[str, Any] | None = None) -> Project:
    return orchestrator.create_project(name=name, metadata=metadata or {})
