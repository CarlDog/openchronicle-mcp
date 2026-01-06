"""Tests for project-wide verification."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.domain.services.verification import VerificationService


@pytest.fixture
def container() -> CoreContainer:
    """Create a fresh container with isolated database for each test."""
    # Create temporary database file
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.db"
    return CoreContainer(db_path=str(db_path))


@pytest.mark.asyncio
async def test_verify_project_all_tasks_valid(container: CoreContainer) -> None:
    """Test project verification when all tasks are valid."""
    orchestrator = container.orchestrator
    project = orchestrator.create_project("Project Verification Test")
    supervisor = orchestrator.register_agent(
        project_id=project.id, name="Supervisor", role="supervisor", provider="stub", model="stub-model"
    )
    orchestrator.register_agent(
        project_id=project.id, name="Worker1", role="worker", provider="stub", model="stub-model"
    )
    orchestrator.register_agent(
        project_id=project.id, name="Worker2", role="worker", provider="stub", model="stub-model"
    )

    # Create two tasks
    task1 = orchestrator.submit_task(project.id, "analysis.summary", {"text": "First task"})
    await orchestrator.execute_task(task1.id, agent_id=supervisor.id)

    task2 = orchestrator.submit_task(project.id, "analysis.summary", {"text": "Second task"})
    await orchestrator.execute_task(task2.id, agent_id=supervisor.id)

    # Verify project
    verification_service = VerificationService(container.storage)
    result = verification_service.verify_project(project.id)

    assert result.success, "Project verification should succeed when all tasks are valid"
    # Note: analysis.summary creates 3 tasks total (1 main + 2 worker sub-tasks)
    # So 2 analysis.summary calls = 6 tasks total
    assert result.total_tasks == 6, "Should have 6 tasks (2 main + 4 worker sub-tasks)"
    assert result.passed_tasks == 6, "All tasks should pass"
    assert result.failed_tasks == 0, "No tasks should fail"
    assert len(result.failures) == 0, "Failures list should be empty"


@pytest.mark.asyncio
async def test_verify_project_with_tampered_task(container: CoreContainer) -> None:
    """Test project verification when one task has been tampered with."""
    orchestrator = container.orchestrator
    project = orchestrator.create_project("Project Tamper Test")
    supervisor = orchestrator.register_agent(
        project_id=project.id, name="Supervisor", role="supervisor", provider="stub", model="stub-model"
    )
    orchestrator.register_agent(
        project_id=project.id, name="Worker1", role="worker", provider="stub", model="stub-model"
    )
    orchestrator.register_agent(
        project_id=project.id, name="Worker2", role="worker", provider="stub", model="stub-model"
    )

    # Create two tasks
    task1 = orchestrator.submit_task(project.id, "analysis.summary", {"text": "First task"})
    await orchestrator.execute_task(task1.id, agent_id=supervisor.id)

    task2 = orchestrator.submit_task(project.id, "analysis.summary", {"text": "Second task"})
    await orchestrator.execute_task(task2.id, agent_id=supervisor.id)

    # Tamper with task1's event hash in SQLite
    events = container.storage.list_events(task1.id)
    assert len(events) > 0, "Task1 should have events"

    # Directly update the hash in the database to simulate tampering

    conn = container.storage._conn  # Access internal connection
    cur = conn.cursor()
    cur.execute(
        "UPDATE events SET hash = ? WHERE id = ?",
        ("tampered_hash_value", events[0].id),
    )
    conn.commit()

    # Verify project
    verification_service = VerificationService(container.storage)
    result = verification_service.verify_project(project.id)

    assert not result.success, "Project verification should fail when a task is tampered"
    # Note: 2 analysis.summary calls = 6 tasks total (2 main + 4 worker sub-tasks)
    assert result.total_tasks == 6, "Should have 6 tasks total"
    assert result.passed_tasks == 5, "Five tasks should pass"
    assert result.failed_tasks == 1, "One task should fail"
    assert len(result.failures) == 1, "Should have 1 failure"

    # Check failure details
    failure = result.failures[0]
    assert failure["task_id"] == task1.id, "Failed task should be task1"
    assert failure["task_type"] == "analysis.summary", "Task type should be preserved"
    assert failure["first_mismatch_event_id"] is not None, "Should have mismatch event ID"
    assert failure["error_message"] is not None, "Should have error message"


@pytest.mark.asyncio
async def test_verify_empty_project(container: CoreContainer) -> None:
    """Test project verification when project has no tasks."""
    orchestrator = container.orchestrator
    project = orchestrator.create_project("Empty Project")

    verification_service = VerificationService(container.storage)
    result = verification_service.verify_project(project.id)

    assert result.success, "Empty project should verify successfully"
    assert result.total_tasks == 0, "Should have 0 tasks"
    assert result.passed_tasks == 0, "Should have 0 passed tasks"
    assert result.failed_tasks == 0, "Should have 0 failed tasks"
    assert len(result.failures) == 0, "Failures list should be empty"
