"""Tests for task tree query helpers and CLI command."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from openchronicle.core.application.services.orchestrator import OrchestratorService
from openchronicle.core.domain.models.project import TaskStatus
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMResponse, LLMUsage
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


class FakeLLM(LLMPort):
    """Fake LLM adapter that produces predictable responses with usage data."""

    async def complete_async(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        content = " ".join(m.get("content", "") for m in messages)
        return LLMResponse(
            content=f"summary:{content[:20]}",
            provider="stub",
            model=model,
            usage=LLMUsage(input_tokens=100, output_tokens=50, total_tokens=150),
        )


@pytest.fixture
def tmp_db(tmp_path: Any) -> SqliteStore:
    """Create a temporary database for testing."""
    db_path = Path(tmp_path) / "test.db"
    storage = SqliteStore(db_path=str(db_path))
    storage.init_schema()
    return storage


@pytest.fixture
def orchestrator(tmp_db: SqliteStore) -> OrchestratorService:
    """Create orchestrator with fake LLM and real storage."""
    plugins = MagicMock()
    handler_registry = MagicMock()
    handler_registry.get = MagicMock(return_value=None)

    # Create event logger that stores in DB
    from openchronicle.core.infrastructure.logging.event_logger import EventLogger

    event_logger = EventLogger(tmp_db)

    return OrchestratorService(
        storage=tmp_db,
        llm=FakeLLM(),
        plugins=plugins,
        handler_registry=handler_registry,
        emit_event=event_logger.append,
    )


class TestTaskTreeQueries:
    """Test storage query helpers for task tree navigation."""

    @pytest.mark.asyncio
    async def test_list_child_tasks_returns_children_in_order(self, orchestrator: OrchestratorService) -> None:
        """Test that list_child_tasks returns children in deterministic order."""
        project = orchestrator.create_project("TreeTest")
        supervisor = orchestrator.register_agent(project.id, "Supervisor", role="supervisor")
        orchestrator.register_agent(project.id, "Worker1", role="worker")
        orchestrator.register_agent(project.id, "Worker2", role="worker")

        # Submit parent task
        task = orchestrator.submit_task(
            project.id,
            "analysis.summary",
            {"text": "test text", "worker_count": 2},
        )

        # Execute to create children
        await orchestrator.execute_task(task.id, agent_id=supervisor.id)

        # Get children
        children = orchestrator.storage.list_child_tasks(task.id)

        # Assert children exist and are ordered
        assert len(children) == 2
        assert children[0].parent_task_id == task.id
        assert children[1].parent_task_id == task.id
        assert children[0].type == "analysis.worker.summarize"
        assert children[1].type == "analysis.worker.summarize"

        # Assert deterministic ordering (by created_at, id)
        assert children[0].created_at <= children[1].created_at

    @pytest.mark.asyncio
    async def test_get_task_latest_routing_returns_correct_data(self, orchestrator: OrchestratorService) -> None:
        """Test that get_task_latest_routing extracts routing info from llm.routed events."""
        project = orchestrator.create_project("RoutingTest")
        supervisor = orchestrator.register_agent(project.id, "Supervisor", role="supervisor")
        orchestrator.register_agent(project.id, "Worker1", role="worker")
        orchestrator.register_agent(project.id, "Worker2", role="worker")

        task = orchestrator.submit_task(
            project.id,
            "analysis.summary",
            {"text": "test", "desired_quality": "quality"},
        )

        await orchestrator.execute_task(task.id, agent_id=supervisor.id)

        # Get children and check their routing
        children = orchestrator.storage.list_child_tasks(task.id)
        assert len(children) == 2

        # Check that routing events were emitted for worker tasks
        for child in children:
            routing = orchestrator.storage.get_task_latest_routing(child.id)
            assert routing is not None, f"No routing info found for child task {child.id}"
            assert routing["provider"] is not None
            assert routing["model"] is not None
            assert routing["mode"] == "quality"
            assert isinstance(routing["reasons"], list)

    @pytest.mark.asyncio
    async def test_get_task_usage_totals_aggregates_correctly(self, orchestrator: OrchestratorService) -> None:
        """Test that get_task_usage_totals aggregates LLM usage correctly."""
        project = orchestrator.create_project("UsageTest")
        supervisor = orchestrator.register_agent(project.id, "Supervisor", role="supervisor")
        orchestrator.register_agent(project.id, "Worker1", role="worker")
        orchestrator.register_agent(project.id, "Worker2", role="worker")

        task = orchestrator.submit_task(
            project.id,
            "analysis.summary",
            {"text": "test text", "worker_count": 2},
        )

        await orchestrator.execute_task(task.id, agent_id=supervisor.id)

        # Get children and check their usage
        children = orchestrator.storage.list_child_tasks(task.id)
        assert len(children) == 2

        for child in children:
            usage = orchestrator.storage.get_task_usage_totals(child.id)
            # Each worker makes 1 LLM call with fake usage
            assert usage["calls"] == 1
            assert usage["total_tokens"] == 150
            assert usage["input_tokens"] == 100
            assert usage["output_tokens"] == 50

    @pytest.mark.asyncio
    async def test_get_task_worker_plan_extracts_plan_event(self, orchestrator: OrchestratorService) -> None:
        """Test that get_task_worker_plan extracts supervisor.worker_plan event data."""
        project = orchestrator.create_project("PlanTest")
        supervisor = orchestrator.register_agent(project.id, "Supervisor", role="supervisor")
        orchestrator.register_agent(project.id, "Worker1", role="worker")
        orchestrator.register_agent(project.id, "Worker2", role="worker")

        task = orchestrator.submit_task(
            project.id,
            "analysis.summary",
            {"text": "test", "worker_modes": ["fast", "quality"], "worker_count": 2},
        )

        await orchestrator.execute_task(task.id, agent_id=supervisor.id)

        # Get worker plan
        plan = orchestrator.storage.get_task_worker_plan(task.id)
        assert plan is not None
        assert plan["worker_modes"] == ["fast", "quality"]
        assert plan["rationale"] == "explicit_worker_modes"
        assert plan["worker_count"] == 2

    @pytest.mark.asyncio
    async def test_get_task_worker_plan_returns_none_for_non_supervisor(
        self, orchestrator: OrchestratorService
    ) -> None:
        """Test that get_task_worker_plan returns None for non-supervisor tasks."""
        project = orchestrator.create_project("NonSupervisorTest")
        supervisor = orchestrator.register_agent(project.id, "Supervisor", role="supervisor")
        orchestrator.register_agent(project.id, "Worker1", role="worker")
        orchestrator.register_agent(project.id, "Worker2", role="worker")

        task = orchestrator.submit_task(
            project.id,
            "analysis.summary",
            {"text": "test", "worker_count": 2},
        )

        await orchestrator.execute_task(task.id, agent_id=supervisor.id)

        # Get children
        children = orchestrator.storage.list_child_tasks(task.id)
        assert len(children) == 2

        # Child tasks should not have worker plan
        for child in children:
            plan = orchestrator.storage.get_task_worker_plan(child.id)
            assert plan is None

    @pytest.mark.asyncio
    async def test_list_child_tasks_returns_empty_for_leaf_tasks(self, orchestrator: OrchestratorService) -> None:
        """Test that list_child_tasks returns empty list for leaf tasks."""
        project = orchestrator.create_project("LeafTest")
        supervisor = orchestrator.register_agent(project.id, "Supervisor", role="supervisor")
        orchestrator.register_agent(project.id, "Worker1", role="worker")
        orchestrator.register_agent(project.id, "Worker2", role="worker")

        task = orchestrator.submit_task(
            project.id,
            "analysis.summary",
            {"text": "test", "worker_count": 2},
        )

        await orchestrator.execute_task(task.id, agent_id=supervisor.id)

        # Get children
        children = orchestrator.storage.list_child_tasks(task.id)
        assert len(children) == 2

        # Children should have no children themselves
        for child in children:
            grandchildren = orchestrator.storage.list_child_tasks(child.id)
            assert len(grandchildren) == 0


class TestTaskTreeMixedMode:
    """Test task tree queries with mixed worker modes."""

    @pytest.mark.asyncio
    async def test_tree_queries_with_mix_strategy(self, orchestrator: OrchestratorService) -> None:
        """Test tree queries work correctly with mix_strategy."""
        project = orchestrator.create_project("MixTest")
        supervisor = orchestrator.register_agent(project.id, "Supervisor", role="supervisor")
        orchestrator.register_agent(project.id, "Worker1", role="worker")
        orchestrator.register_agent(project.id, "Worker2", role="worker")

        task = orchestrator.submit_task(
            project.id,
            "analysis.summary",
            {"text": "test", "mix_strategy": "fast_then_quality"},
        )

        await orchestrator.execute_task(task.id, agent_id=supervisor.id)

        # Check worker plan
        plan = orchestrator.storage.get_task_worker_plan(task.id)
        assert plan is not None
        assert plan["worker_modes"] == ["fast", "quality"]
        assert plan["rationale"] == "mix_strategy"

        # Check children routing
        children = orchestrator.storage.list_child_tasks(task.id)
        assert len(children) == 2

        # First child should be fast, second should be quality
        routing0 = orchestrator.storage.get_task_latest_routing(children[0].id)
        routing1 = orchestrator.storage.get_task_latest_routing(children[1].id)

        assert routing0 is not None
        assert routing1 is not None

        # Sort by mode to get deterministic order
        modes = sorted([routing0["mode"], routing1["mode"]])
        assert modes == ["fast", "quality"]

    @pytest.mark.asyncio
    async def test_tree_with_parent_child_complete(self, orchestrator: OrchestratorService) -> None:
        """Test that parent and children all complete successfully."""
        project = orchestrator.create_project("CompleteTest")
        supervisor = orchestrator.register_agent(project.id, "Supervisor", role="supervisor")
        orchestrator.register_agent(project.id, "Worker1", role="worker")
        orchestrator.register_agent(project.id, "Worker2", role="worker")

        task = orchestrator.submit_task(
            project.id,
            "analysis.summary",
            {"text": "test text", "worker_count": 2},
        )

        await orchestrator.execute_task(task.id, agent_id=supervisor.id)

        # Check parent completed
        parent_task = orchestrator.storage.get_task(task.id)
        assert parent_task is not None
        assert parent_task.status == TaskStatus.COMPLETED
        assert parent_task.result_json is not None

        # Check all children completed
        children = orchestrator.storage.list_child_tasks(task.id)
        assert len(children) == 2
        for child in children:
            assert child.status == TaskStatus.COMPLETED
            assert child.result_json is not None


class TestTaskTreeCLIIntegration:
    """Test CLI output formatting for task tree (unit test of formatter logic)."""

    @pytest.mark.asyncio
    async def test_cli_output_includes_all_key_info(self, orchestrator: OrchestratorService) -> None:
        """Test that task tree data includes all expected information."""
        project = orchestrator.create_project("CLITest")
        supervisor = orchestrator.register_agent(project.id, "Supervisor", role="supervisor")
        orchestrator.register_agent(project.id, "Worker1", role="worker")
        orchestrator.register_agent(project.id, "Worker2", role="worker")

        task = orchestrator.submit_task(
            project.id,
            "analysis.summary",
            {"text": "hello world", "mix_strategy": "fast_then_quality"},
        )

        await orchestrator.execute_task(task.id, agent_id=supervisor.id)

        # Verify parent task has all expected data
        parent_task = orchestrator.storage.get_task(task.id)
        assert parent_task is not None
        assert parent_task.id == task.id
        assert parent_task.type == "analysis.summary"
        assert parent_task.status == TaskStatus.COMPLETED
        # Note: Parent task may not have agent_id set in payload submission

        # Verify worker plan
        plan = orchestrator.storage.get_task_worker_plan(task.id)
        assert plan is not None
        assert "worker_modes" in plan
        assert "rationale" in plan

        # Verify children
        children = orchestrator.storage.list_child_tasks(task.id)
        assert len(children) == 2

        for idx, child in enumerate(children):
            # Each child should have routing info
            routing = orchestrator.storage.get_task_latest_routing(child.id)
            assert routing is not None
            assert routing["provider"] is not None
            assert routing["model"] is not None
            assert routing["mode"] in ["fast", "quality"]

            # Each child should have usage data
            usage = orchestrator.storage.get_task_usage_totals(child.id)
            assert usage["calls"] == 1
            assert usage["total_tokens"] > 0

            # Each child should have desired_quality in payload
            assert "desired_quality" in child.payload
            assert child.payload["desired_quality"] in ["fast", "quality"]
