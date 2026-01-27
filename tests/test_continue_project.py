"""Tests for continue_project use case."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.use_cases import continue_project
from openchronicle.core.domain.models.project import TaskStatus


@pytest.fixture
def container(tmp_path: Any) -> CoreContainer:
    db_path = tmp_path / "test.db"
    return CoreContainer(db_path=str(db_path))


@pytest.fixture
def project_id(container: CoreContainer) -> str:
    project = container.orchestrator.create_project("continue-test-project")
    return project.id


class TestContinueProject:
    """Tests for continue_project use case."""

    @pytest.mark.asyncio
    async def test_continue_executes_pending_tasks_in_order(self, container: CoreContainer, project_id: str) -> None:
        """Continue should execute pending tasks in deterministic order (created_at, id)."""
        # Arrange: Create 2 pending tasks
        task1 = container.orchestrator.submit_task(
            project_id=project_id,
            task_type="test.task1",
            payload={"order": 1},
        )
        task2 = container.orchestrator.submit_task(
            project_id=project_id,
            task_type="test.task2",
            payload={"order": 2},
        )

        # Track execution order
        executed_tasks = []

        async def mock_execute(orchestrator: Any, task_id: str, agent_id: str | None = None) -> Any:
            executed_tasks.append(task_id)
            return f"result-{task_id}"

        # Act: Continue with mocked run_task.execute
        with patch("openchronicle.core.application.use_cases.run_task.execute", new=mock_execute):
            summary = await continue_project.execute(container.orchestrator, project_id)

        # Assert: Both tasks executed in order
        assert summary.pending_tasks == 2, "Should report 2 pending tasks"
        assert summary.succeeded == 2, "Both tasks should succeed"
        assert summary.failed == 0, "No tasks should fail"
        assert len(executed_tasks) == 2, "Should execute exactly 2 tasks"
        assert executed_tasks == [task1.id, task2.id], "Tasks should execute in created_at order"
        assert summary.task_ids == [task1.id, task2.id], "Summary should include task IDs"

    @pytest.mark.asyncio
    async def test_continue_with_zero_pending_tasks(self, container: CoreContainer, project_id: str) -> None:
        """Continue with no pending tasks should return empty summary."""
        # Arrange: Create a completed task (no pending)
        task = container.orchestrator.submit_task(
            project_id=project_id,
            task_type="test.completed",
            payload={"test": "data"},
        )
        container.storage.update_task_result(task.id, '{"result": "done"}', TaskStatus.COMPLETED.value)

        # Act: Continue
        summary = await continue_project.execute(container.orchestrator, project_id)

        # Assert: No execution
        assert summary.pending_tasks == 0, "Should report 0 pending tasks"
        assert summary.succeeded == 0, "No tasks should succeed"
        assert summary.failed == 0, "No tasks should fail"
        assert summary.task_ids == [], "Task IDs list should be empty"

    @pytest.mark.asyncio
    async def test_continue_handles_task_failure_gracefully(self, container: CoreContainer, project_id: str) -> None:
        """Continue should continue with remaining tasks if one fails."""
        # Arrange: Create 3 pending tasks
        task1 = container.orchestrator.submit_task(
            project_id=project_id,
            task_type="test.task1",
            payload={"order": 1},
        )
        task2 = container.orchestrator.submit_task(
            project_id=project_id,
            task_type="test.task2",
            payload={"order": 2},
        )
        task3 = container.orchestrator.submit_task(
            project_id=project_id,
            task_type="test.task3",
            payload={"order": 3},
        )

        # Mock execution where task2 fails
        async def mock_execute_with_failure(orchestrator: Any, task_id: str, agent_id: str | None = None) -> Any:
            if task_id == task2.id:
                raise RuntimeError("Task 2 failed")
            return f"result-{task_id}"

        # Act: Continue with failure
        with patch("openchronicle.core.application.use_cases.run_task.execute", new=mock_execute_with_failure):
            summary = await continue_project.execute(container.orchestrator, project_id)

        # Assert: Task2 failed, but task1 and task3 succeeded
        assert summary.pending_tasks == 3, "Should report 3 pending tasks"
        assert summary.succeeded == 2, "Two tasks should succeed"
        assert summary.failed == 1, "One task should fail"
        assert summary.task_ids == [task1.id, task2.id, task3.id], "All task IDs should be present"

    @pytest.mark.asyncio
    async def test_continue_only_executes_pending_not_completed(
        self, container: CoreContainer, project_id: str
    ) -> None:
        """Continue should only execute pending tasks, not completed or failed."""
        # Arrange: Create tasks in different states
        task_pending = container.orchestrator.submit_task(
            project_id=project_id,
            task_type="test.pending",
            payload={"state": "pending"},
        )
        task_completed = container.orchestrator.submit_task(
            project_id=project_id,
            task_type="test.completed",
            payload={"state": "completed"},
        )
        task_failed = container.orchestrator.submit_task(
            project_id=project_id,
            task_type="test.failed",
            payload={"state": "failed"},
        )

        # Set states
        container.storage.update_task_result(task_completed.id, '{"result": "done"}', TaskStatus.COMPLETED.value)
        container.storage.update_task_error(task_failed.id, '{"error": "oops"}', TaskStatus.FAILED.value)

        # Track which tasks get executed
        executed_tasks = []

        async def mock_execute(orchestrator: Any, task_id: str, agent_id: str | None = None) -> Any:
            executed_tasks.append(task_id)
            return f"result-{task_id}"

        # Act: Continue
        with patch("openchronicle.core.application.use_cases.run_task.execute", new=mock_execute):
            summary = await continue_project.execute(container.orchestrator, project_id)

        # Assert: Only pending task executed
        assert summary.pending_tasks == 1, "Should report 1 pending task"
        assert summary.succeeded == 1, "One task should succeed"
        assert executed_tasks == [task_pending.id], "Only pending task should be executed"

    @pytest.mark.asyncio
    async def test_continue_sorts_tasks_deterministically(self, container: CoreContainer, project_id: str) -> None:
        """Continue should sort tasks by created_at, then id for deterministic execution."""
        # Arrange: Create 3 pending tasks
        task1 = container.orchestrator.submit_task(
            project_id=project_id,
            task_type="test.task1",
            payload={"order": 1},
        )
        task2 = container.orchestrator.submit_task(
            project_id=project_id,
            task_type="test.task2",
            payload={"order": 2},
        )
        task3 = container.orchestrator.submit_task(
            project_id=project_id,
            task_type="test.task3",
            payload={"order": 3},
        )

        # Track execution order
        executed_order = []

        async def mock_execute(orchestrator: Any, task_id: str, agent_id: str | None = None) -> Any:
            executed_order.append(task_id)
            return f"result-{task_id}"

        # Act: Continue
        with patch("openchronicle.core.application.use_cases.run_task.execute", new=mock_execute):
            summary = await continue_project.execute(container.orchestrator, project_id)

        # Assert: Execution order matches created_at + id sort
        assert executed_order == [task1.id, task2.id, task3.id], "Tasks should execute in creation order"
        assert summary.task_ids == [task1.id, task2.id, task3.id], "Summary should preserve order"


class TestCLIBoundaryGuard:
    """Tests to ensure CLI does not directly access storage."""

    def test_cli_does_not_import_storage_directly(self) -> None:
        """CLI should not directly access container.storage for resume-project --continue."""
        # Read the CLI file
        with open("src/openchronicle/interfaces/cli/main.py", encoding="utf-8") as f:
            cli_content = f.read()

        # Check for the specific boundary violation in resume-project command
        # The old code had: container.storage.list_tasks_by_project in the --continue path
        resume_section_start = cli_content.find('if args.command == "resume-project":')
        resume_section_end = cli_content.find("if args.command ==", resume_section_start + 1)
        if resume_section_end == -1:
            resume_section_end = cli_content.find("parser.print_help()", resume_section_start)

        resume_section = cli_content[resume_section_start:resume_section_end]

        # Verify the new implementation doesn't have storage access in --continue path
        assert "container.storage.list_tasks_by_project" not in resume_section, (
            "CLI resume-project --continue should not directly access container.storage; "
            "use continue_project use case instead"
        )

        # Verify it uses the use case
        assert "continue_project.execute" in resume_section, (
            "CLI resume-project --continue should use continue_project.execute"
        )
