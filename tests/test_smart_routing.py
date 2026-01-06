"""
Test Phase 4: Smart Routing for provider/model selection.

Tests cover:
1. Default routing behavior (fast mode by default)
2. Tag-based routing (fast/quality agent tags)
3. Budget-aware downgrade (low remaining tokens → fast)
4. Rate-limit-aware downgrade (recent rate limits → fast)
5. Deterministic output (same inputs → same decision)
6. Provider preference override
7. Explicit quality hint override
"""

import os
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from openchronicle.core.application.routing.router_policy import RouterPolicy
from openchronicle.core.domain.models.project import Agent
from openchronicle.core.domain.ports.llm_port import LLMResponse, LLMUsage
from openchronicle.core.domain.services.orchestrator import OrchestratorService


@dataclass
class FakeLLMAdapter:
    """Fake LLM adapter for testing - no network calls."""

    provider: str = "stub"
    model: str = "stub-model"

    async def complete_async(
        self,
        messages: list[dict],
        model: str | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """Return fake response without making network calls."""
        used_model = model or self.model
        return LLMResponse(
            content=f"Stub response from {used_model}",
            provider=self.provider,
            model=used_model,
            usage=LLMUsage(input_tokens=10, output_tokens=20, total_tokens=30),
            finish_reason="stop",
            latency_ms=100,
            request_id="test-req-123",
        )

    async def generate_async(self, prompt: str, model: str | None = None, parameters: dict | None = None) -> str:
        """Return fake generation without making network calls."""
        return f"Stub generation: {prompt[:50]}"


@pytest.fixture
def temp_env_vars() -> Generator[dict[str, str], None, None]:
    """Set up temporary environment variables for testing."""
    original_env = os.environ.copy()
    test_vars = {
        "OC_LLM_MODEL_FAST": "gpt-4o-mini",
        "OC_LLM_MODEL_QUALITY": "gpt-4o",
        "OC_LLM_DEFAULT_MODE": "fast",
        "OC_LLM_LOW_BUDGET_THRESHOLD": "500",
        "OC_LLM_DOWNGRADE_ON_RATE_LIMIT": "1",
        "OC_LLM_PROVIDER": "stub",
    }
    os.environ.update(test_vars)
    yield test_vars
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def fake_storage() -> MagicMock:
    """Create fake storage for testing."""
    storage = MagicMock()
    storage.get_agent = MagicMock(return_value=Agent(id="agent1", role="analyzer", tags=[]))
    storage.get_events = MagicMock(return_value=[])
    return storage


@pytest.fixture
def orchestrator(temp_env_vars: dict[str, str], fake_storage: MagicMock) -> OrchestratorService:
    """Create orchestrator with fake adapter and storage."""
    fake_llm = FakeLLMAdapter()
    plugins = MagicMock()
    handler_registry = MagicMock()
    handler_registry.get = MagicMock(return_value=None)
    emit_event = MagicMock()

    return OrchestratorService(
        storage=fake_storage,
        llm=fake_llm,  # type: ignore[arg-type]
        plugins=plugins,
        handler_registry=handler_registry,
        emit_event=emit_event,
    )


class TestRouterPolicy:
    """Test RouterPolicy routing logic in isolation."""

    def test_default_routing_no_hints(self, temp_env_vars: dict[str, str]) -> None:
        """Test 1: Default routing when no hints provided."""
        router = RouterPolicy()
        decision = router.route(
            task_type="test.task",
            agent_role="worker",
            agent_tags=[],
            desired_quality=None,
            provider_preference=None,
            current_task_tokens=100,
            max_tokens_per_task=10000,
            rate_limit_triggered=False,
            rpm_limit=None,
        )

        assert decision.provider == "stub"
        assert decision.model == "stub-model"
        assert decision.mode == "fast"
        assert "mode_from_default:fast" in decision.reasons

    def test_tag_based_routing_fast(self, temp_env_vars: dict[str, str]) -> None:
        """Test 2a: Tag-based routing for fast agent."""
        router = RouterPolicy()
        decision = router.route(
            task_type="test.task",
            agent_role="worker",
            agent_tags=["fast", "summarizer"],
            desired_quality=None,
            provider_preference=None,
            current_task_tokens=100,
            max_tokens_per_task=10000,
            rate_limit_triggered=False,
            rpm_limit=None,
        )

        assert decision.mode == "fast"
        assert "mode_from_agent_tags:fast" in decision.reasons

    def test_tag_based_routing_quality(self, temp_env_vars: dict[str, str]) -> None:
        """Test 2b: Tag-based routing for quality agent."""
        router = RouterPolicy()
        decision = router.route(
            task_type="test.task",
            agent_role="worker",
            agent_tags=["quality", "analyzer"],
            desired_quality=None,
            provider_preference=None,
            current_task_tokens=100,
            max_tokens_per_task=10000,
            rate_limit_triggered=False,
            rpm_limit=None,
        )

        assert decision.mode == "quality"
        assert "mode_from_agent_tags:quality" in decision.reasons

    def test_budget_aware_downgrade(self, temp_env_vars: dict[str, str]) -> None:
        """Test 3: Budget-aware downgrade when tokens low."""
        router = RouterPolicy()

        # Start with quality mode but low tokens remaining
        decision = router.route(
            task_type="test.task",
            agent_role="worker",
            agent_tags=["quality"],
            desired_quality=None,
            provider_preference=None,
            current_task_tokens=9600,  # 10000 - 9600 = 400 remaining
            max_tokens_per_task=10000,
            rate_limit_triggered=False,
            rpm_limit=None,
        )

        assert decision.mode == "fast"
        assert "low_budget_downgrade:remaining=400" in decision.reasons

    def test_rate_limit_downgrade_recent_limit(self, temp_env_vars: dict[str, str]) -> None:
        """Test 4a: Rate-limit downgrade when recently limited."""
        router = RouterPolicy()

        decision = router.route(
            task_type="test.task",
            agent_role="worker",
            agent_tags=["quality"],
            desired_quality=None,
            provider_preference=None,
            current_task_tokens=100,
            max_tokens_per_task=10000,
            rate_limit_triggered=True,
            rpm_limit=None,
        )

        assert decision.mode == "fast"
        assert "rate_limit_downgrade" in decision.reasons

    def test_rate_limit_downgrade_low_rpm(self, temp_env_vars: dict[str, str]) -> None:
        """Test 4b: Rate-limit downgrade when RPM is 1 or less."""
        router = RouterPolicy()

        decision = router.route(
            task_type="test.task",
            agent_role="worker",
            agent_tags=["quality"],
            desired_quality=None,
            provider_preference=None,
            current_task_tokens=100,
            max_tokens_per_task=10000,
            rate_limit_triggered=False,
            rpm_limit=1,
        )

        assert decision.mode == "fast"
        assert "rate_limit_downgrade" in decision.reasons

    def test_deterministic_output(self, temp_env_vars: dict[str, str]) -> None:
        """Test 5: Same inputs produce same decision."""
        router = RouterPolicy()

        inputs: dict[str, Any] = {
            "task_type": "test.task",
            "agent_role": "worker",
            "agent_tags": ["quality", "analyzer"],
            "desired_quality": None,
            "provider_preference": None,
            "current_task_tokens": 1000,
            "max_tokens_per_task": 10000,
            "rate_limit_triggered": False,
            "rpm_limit": 10,
        }

        decision1 = router.route(**inputs)
        decision2 = router.route(**inputs)
        decision3 = router.route(**inputs)

        assert decision1.provider == decision2.provider == decision3.provider
        assert decision1.model == decision2.model == decision3.model
        assert decision1.mode == decision2.mode == decision3.mode
        assert decision1.reasons == decision2.reasons == decision3.reasons

    def test_provider_preference_override(self, temp_env_vars: dict[str, str]) -> None:
        """Test 6: Provider preference override."""
        router = RouterPolicy()

        decision = router.route(
            task_type="test.task",
            agent_role="worker",
            agent_tags=[],
            desired_quality=None,
            provider_preference="openai",
            current_task_tokens=100,
            max_tokens_per_task=10000,
            rate_limit_triggered=False,
            rpm_limit=None,
        )

        assert decision.provider == "openai"
        assert "provider_override:openai" in decision.reasons

    def test_explicit_quality_hint(self, temp_env_vars: dict[str, str]) -> None:
        """Test 7: Explicit quality hint overrides tags."""
        router = RouterPolicy()

        # Agent has "fast" tag but explicit quality hint should override
        decision = router.route(
            task_type="test.task",
            agent_role="worker",
            agent_tags=["fast"],
            desired_quality="quality",
            provider_preference=None,
            current_task_tokens=100,
            max_tokens_per_task=10000,
            rate_limit_triggered=False,
            rpm_limit=None,
        )

        assert decision.mode == "quality"
        assert "mode_from_task_payload:quality" in decision.reasons

    def test_quality_model_selection_openai(self, temp_env_vars: dict[str, str]) -> None:
        """Test model selection for quality mode with OpenAI."""
        router = RouterPolicy()

        decision = router.route(
            task_type="test.task",
            agent_role="worker",
            agent_tags=["quality"],
            desired_quality=None,
            provider_preference="openai",
            current_task_tokens=100,
            max_tokens_per_task=10000,
            rate_limit_triggered=False,
            rpm_limit=None,
        )

        assert decision.provider == "openai"
        assert decision.model == "gpt-4o"
        assert "quality_model:gpt-4o" in decision.reasons

    def test_fast_model_selection_openai(self, temp_env_vars: dict[str, str]) -> None:
        """Test model selection for fast mode with OpenAI."""
        router = RouterPolicy()

        decision = router.route(
            task_type="test.task",
            agent_role="worker",
            agent_tags=["fast"],
            desired_quality=None,
            provider_preference="openai",
            current_task_tokens=100,
            max_tokens_per_task=10000,
            rate_limit_triggered=False,
            rpm_limit=None,
        )

        assert decision.provider == "openai"
        assert decision.model == "gpt-4o-mini"
        assert "fast_model:gpt-4o-mini" in decision.reasons


class TestModePropagation:
    """Test mode propagation from supervisor to worker child tasks."""

    @pytest.mark.asyncio
    async def test_mode_propagates_to_worker_tasks(self, tmp_path: Any) -> None:
        """Test that desired_quality propagates from root task to worker child tasks."""
        from pathlib import Path

        from openchronicle.core.application.runtime.plugin_loader import PluginLoader
        from openchronicle.core.application.runtime.task_handler_registry import TaskHandlerRegistry
        from openchronicle.core.domain.models.project import TaskStatus
        from openchronicle.core.domain.ports.llm_port import LLMPort, LLMResponse
        from openchronicle.core.infrastructure.logging.event_logger import EventLogger
        from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

        class FakeLLM(LLMPort):
            async def complete_async(
                self,
                messages: list[dict[str, Any]],
                *,
                model: str,
                max_output_tokens: int | None = None,
                temperature: float | None = None,
            ) -> LLMResponse:
                content = " ".join(m.get("content", "") for m in messages)
                return LLMResponse(content=f"summary:{content[:20]}", provider="stub", model=model)

        db_path = Path(tmp_path) / "test.db"
        storage = SqliteStore(db_path=str(db_path))
        storage.init_schema()
        event_logger = EventLogger(storage)

        handler_registry = TaskHandlerRegistry()
        plugin_loader = PluginLoader(plugins_dir="plugins", handler_registry=handler_registry)
        plugin_loader.load_plugins()

        from openchronicle.core.domain.services.orchestrator import OrchestratorService

        orchestrator = OrchestratorService(
            storage=storage,
            llm=FakeLLM(),
            plugins=plugin_loader.registry_instance(),
            handler_registry=plugin_loader.handler_registry_instance(),
            emit_event=event_logger.append,
        )

        project = orchestrator.create_project("Test")

        # Create agents
        supervisor = orchestrator.register_agent(project.id, "supervisor", "supervisor")
        orchestrator.register_agent(project.id, "worker1", "worker")
        orchestrator.register_agent(project.id, "worker2", "worker")

        # Submit task with desired_quality="quality"
        task = orchestrator.submit_task(
            project.id, "analysis.summary", {"text": "Test text for summary", "desired_quality": "quality"}
        )

        # Execute task
        result = await orchestrator.execute_task(task.id, agent_id=supervisor.id)

        # Verify task completed
        assert result is not None
        stored_task = storage.get_task(task.id)
        assert stored_task is not None
        assert stored_task.status == TaskStatus.COMPLETED

        # Verify supervisor.routing_mode_selected event was emitted
        events = storage.list_events(task.id)
        routing_events = [e for e in events if e.type == "supervisor.routing_mode_selected"]
        assert len(routing_events) == 1
        assert routing_events[0].payload["desired_quality"] == "quality"
        assert routing_events[0].payload["source"] == "task_payload"

        # Find worker child tasks
        all_tasks = storage.list_tasks_by_project(project.id)
        worker_tasks = [t for t in all_tasks if t.type == "analysis.worker.summarize"]
        assert len(worker_tasks) == 2

        # Verify both worker tasks have desired_quality in their payload
        for worker_task in worker_tasks:
            assert "desired_quality" in worker_task.payload
            assert worker_task.payload["desired_quality"] == "quality"

        # Verify llm.routed events show mode from task payload
        all_events = []
        for wt in worker_tasks:
            all_events.extend(storage.list_events(wt.id))

        routed_events = [e for e in all_events if e.type == "llm.routed"]
        assert len(routed_events) == 2  # One for each worker
        for routed_event in routed_events:
            assert routed_event.payload["mode"] == "quality"
            assert any("mode_from_task_payload:quality" in r for r in routed_event.payload.get("reasons", []))

    @pytest.mark.asyncio
    async def test_payload_mode_overrides_agent_tags(self, tmp_path: Any) -> None:
        """Test that payload desired_quality overrides agent tags."""
        from pathlib import Path

        from openchronicle.core.application.runtime.plugin_loader import PluginLoader
        from openchronicle.core.application.runtime.task_handler_registry import TaskHandlerRegistry
        from openchronicle.core.domain.ports.llm_port import LLMPort, LLMResponse
        from openchronicle.core.infrastructure.logging.event_logger import EventLogger
        from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

        class FakeLLM(LLMPort):
            async def complete_async(
                self,
                messages: list[dict[str, Any]],
                *,
                model: str,
                max_output_tokens: int | None = None,
                temperature: float | None = None,
            ) -> LLMResponse:
                content = " ".join(m.get("content", "") for m in messages)
                return LLMResponse(content=f"summary:{content[:20]}", provider="stub", model=model)

        db_path = Path(tmp_path) / "test.db"
        storage = SqliteStore(db_path=str(db_path))
        storage.init_schema()
        event_logger = EventLogger(storage)

        handler_registry = TaskHandlerRegistry()
        plugin_loader = PluginLoader(plugins_dir="plugins", handler_registry=handler_registry)
        plugin_loader.load_plugins()

        from openchronicle.core.domain.services.orchestrator import OrchestratorService

        orchestrator = OrchestratorService(
            storage=storage,
            llm=FakeLLM(),
            plugins=plugin_loader.registry_instance(),
            handler_registry=plugin_loader.handler_registry_instance(),
            emit_event=event_logger.append,
        )

        project = orchestrator.create_project("Test")

        # Create agents with quality tags
        supervisor = orchestrator.register_agent(project.id, "supervisor", "supervisor")
        orchestrator.register_agent(project.id, "worker1", "worker", tags=["quality"])
        orchestrator.register_agent(project.id, "worker2", "worker", tags=["quality"])

        # Submit task with desired_quality="fast" (should override agent tags)
        task = orchestrator.submit_task(
            project.id, "analysis.summary", {"text": "Test text for summary", "desired_quality": "fast"}
        )

        # Execute task
        await orchestrator.execute_task(task.id, agent_id=supervisor.id)

        # Find worker child tasks
        all_tasks = storage.list_tasks_by_project(project.id)
        worker_tasks = [t for t in all_tasks if t.type == "analysis.worker.summarize"]

        # Get llm.routed events
        all_events = []
        for wt in worker_tasks:
            all_events.extend(storage.list_events(wt.id))

        routed_events = [e for e in all_events if e.type == "llm.routed"]
        assert len(routed_events) == 2

        # Verify mode is "fast" (from payload) not "quality" (from agent tags)
        for routed_event in routed_events:
            assert routed_event.payload["mode"] == "fast"
            assert any("mode_from_task_payload:fast" in r for r in routed_event.payload.get("reasons", []))

    @pytest.mark.asyncio
    async def test_default_behavior_without_mode(self, tmp_path: Any) -> None:
        """Test that without desired_quality, routing falls back to tags/env default."""
        from pathlib import Path

        from openchronicle.core.application.runtime.plugin_loader import PluginLoader
        from openchronicle.core.application.runtime.task_handler_registry import TaskHandlerRegistry
        from openchronicle.core.domain.ports.llm_port import LLMPort, LLMResponse
        from openchronicle.core.infrastructure.logging.event_logger import EventLogger
        from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

        class FakeLLM(LLMPort):
            async def complete_async(
                self,
                messages: list[dict[str, Any]],
                *,
                model: str,
                max_output_tokens: int | None = None,
                temperature: float | None = None,
            ) -> LLMResponse:
                content = " ".join(m.get("content", "") for m in messages)
                return LLMResponse(content=f"summary:{content[:20]}", provider="stub", model=model)

        db_path = Path(tmp_path) / "test.db"
        storage = SqliteStore(db_path=str(db_path))
        storage.init_schema()
        event_logger = EventLogger(storage)

        handler_registry = TaskHandlerRegistry()
        plugin_loader = PluginLoader(plugins_dir="plugins", handler_registry=handler_registry)
        plugin_loader.load_plugins()

        from openchronicle.core.domain.services.orchestrator import OrchestratorService

        orchestrator = OrchestratorService(
            storage=storage,
            llm=FakeLLM(),
            plugins=plugin_loader.registry_instance(),
            handler_registry=plugin_loader.handler_registry_instance(),
            emit_event=event_logger.append,
        )

        project = orchestrator.create_project("Test")

        # Create agents with quality tags
        supervisor = orchestrator.register_agent(project.id, "supervisor", "supervisor")
        orchestrator.register_agent(project.id, "worker1", "worker", tags=["quality"])
        orchestrator.register_agent(project.id, "worker2", "worker", tags=["quality"])

        # Submit task WITHOUT desired_quality
        task = orchestrator.submit_task(project.id, "analysis.summary", {"text": "Test text for summary"})

        # Execute task
        await orchestrator.execute_task(task.id, agent_id=supervisor.id)

        # Verify supervisor.routing_mode_selected event shows default source
        events = storage.list_events(task.id)
        routing_events = [e for e in events if e.type == "supervisor.routing_mode_selected"]
        assert len(routing_events) == 1
        assert routing_events[0].payload["desired_quality"] is None
        assert routing_events[0].payload["source"] == "default"

        # Find worker child tasks
        all_tasks = storage.list_tasks_by_project(project.id)
        worker_tasks = [t for t in all_tasks if t.type == "analysis.worker.summarize"]

        # Verify worker tasks do NOT have desired_quality in payload
        for worker_task in worker_tasks:
            assert "desired_quality" not in worker_task.payload

        # Get llm.routed events
        all_events = []
        for wt in worker_tasks:
            all_events.extend(storage.list_events(wt.id))

        routed_events = [e for e in all_events if e.type == "llm.routed"]

        # Verify mode uses agent tags (quality) since no payload override
        for routed_event in routed_events:
            assert routed_event.payload["mode"] == "quality"
            assert any("mode_from_agent_tags:quality" in r for r in routed_event.payload.get("reasons", []))
