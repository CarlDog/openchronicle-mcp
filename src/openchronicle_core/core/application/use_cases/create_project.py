from __future__ import annotations

from typing import Any

from openchronicle_core.core.domain.models.project import Project
from openchronicle_core.core.domain.services.orchestrator import OrchestratorService


def execute(orchestrator: OrchestratorService, name: str, metadata: dict[str, Any] | None = None) -> Project:
    return orchestrator.create_project(name=name, metadata=metadata or {})
