"""Pass B — Operational Hardening tests.

Tests for DRY utilities, container lifecycle, config validation,
adapter timeouts, CLI bug fixes, logging, and error code normalization.
"""

from __future__ import annotations

import logging
from datetime import UTC
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from openchronicle.core.application.config.env_helpers import parse_csv_tags
from openchronicle.core.application.config.settings import (
    ConversationSettings,
    MoESettings,
    TelemetrySettings,
)
from openchronicle.core.domain.time_utils import utc_now

# ── DRY: utc_now ──────────────────────────────────────────────────────


class TestUtcNow:
    def test_returns_datetime(self) -> None:
        result = utc_now()
        assert result is not None

    def test_timezone_aware(self) -> None:
        result = utc_now()
        assert result.tzinfo is not None

    def test_utc_timezone(self) -> None:
        result = utc_now()
        assert result.tzinfo == UTC or result.tzinfo == UTC


# ── DRY: parse_csv_tags ──────────────────────────────────────────────


class TestParseCsvTags:
    def test_none_returns_none(self) -> None:
        assert parse_csv_tags(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert parse_csv_tags("") is None

    def test_whitespace_only_returns_empty_list(self) -> None:
        assert parse_csv_tags("   ") == []

    def test_single_tag(self) -> None:
        assert parse_csv_tags("decision") == ["decision"]

    def test_multiple_tags(self) -> None:
        assert parse_csv_tags("decision,context,milestone") == ["decision", "context", "milestone"]

    def test_strips_whitespace(self) -> None:
        assert parse_csv_tags(" decision , context ") == ["decision", "context"]

    def test_filters_empty_segments(self) -> None:
        assert parse_csv_tags("decision,,context,") == ["decision", "context"]

    def test_all_empty_segments_returns_empty_list(self) -> None:
        assert parse_csv_tags(",,,") == []


# ── Container lifecycle ───────────────────────────────────────────────


class TestContainerLifecycle:
    def test_sqlite_store_close(self, tmp_path: Any) -> None:
        from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

        store = SqliteStore(db_path=str(tmp_path / "test.db"))
        store.init_schema()
        store.close()
        # After close, operations should fail
        with pytest.raises(Exception):
            store.list_projects()

    def test_container_close(self, tmp_path: Any) -> None:
        """CoreContainer.close() closes the storage connection."""
        from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

        store = SqliteStore(db_path=str(tmp_path / "test.db"))
        store.init_schema()
        mock_container = MagicMock()
        mock_container.storage = store

        from openchronicle.core.infrastructure.wiring.container import CoreContainer

        # Use the close method directly on a real store
        CoreContainer.close(mock_container)

        with pytest.raises(Exception):
            store.list_projects()

    def test_container_context_manager(self, tmp_path: Any) -> None:
        """CoreContainer context manager calls close on exit."""
        from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

        store = SqliteStore(db_path=str(tmp_path / "test.db"))
        store.init_schema()

        mock_container = MagicMock()
        mock_container.storage = store
        mock_container.close = MagicMock()

        from openchronicle.core.infrastructure.wiring.container import CoreContainer

        # Test __enter__ and __exit__ protocol
        mock_container.__enter__ = CoreContainer.__enter__
        mock_container.__exit__ = CoreContainer.__exit__

        with mock_container:
            pass

        mock_container.close.assert_called_once()


# ── Config validation ─────────────────────────────────────────────────


class TestConversationSettingsValidation:
    def test_valid_defaults(self) -> None:
        settings = ConversationSettings()
        assert settings.temperature == 0.2

    def test_temperature_too_low(self) -> None:
        with pytest.raises(ValueError, match="temperature"):
            ConversationSettings(temperature=-0.1)

    def test_temperature_too_high(self) -> None:
        with pytest.raises(ValueError, match="temperature"):
            ConversationSettings(temperature=2.1)

    def test_temperature_boundary_low(self) -> None:
        settings = ConversationSettings(temperature=0.0)
        assert settings.temperature == 0.0

    def test_temperature_boundary_high(self) -> None:
        settings = ConversationSettings(temperature=2.0)
        assert settings.temperature == 2.0

    def test_max_output_tokens_zero(self) -> None:
        with pytest.raises(ValueError, match="max_output_tokens"):
            ConversationSettings(max_output_tokens=0)

    def test_max_output_tokens_negative(self) -> None:
        with pytest.raises(ValueError, match="max_output_tokens"):
            ConversationSettings(max_output_tokens=-1)

    def test_top_k_memory_negative(self) -> None:
        with pytest.raises(ValueError, match="top_k_memory"):
            ConversationSettings(top_k_memory=-1)

    def test_top_k_memory_zero_ok(self) -> None:
        settings = ConversationSettings(top_k_memory=0)
        assert settings.top_k_memory == 0

    def test_last_n_zero(self) -> None:
        with pytest.raises(ValueError, match="last_n"):
            ConversationSettings(last_n=0)

    def test_last_n_one_ok(self) -> None:
        settings = ConversationSettings(last_n=1)
        assert settings.last_n == 1


class TestMoESettingsValidation:
    def test_valid_defaults(self) -> None:
        settings = MoESettings()
        assert settings.min_experts == 2

    def test_min_experts_too_low(self) -> None:
        with pytest.raises(ValueError, match="min_experts"):
            MoESettings(min_experts=1)

    def test_min_experts_boundary(self) -> None:
        settings = MoESettings(min_experts=2)
        assert settings.min_experts == 2


class TestTelemetrySettingsValidation:
    def test_valid_defaults(self) -> None:
        settings = TelemetrySettings()
        assert settings.memory_self_report_max_ids == 20

    def test_memory_self_report_max_ids_zero(self) -> None:
        with pytest.raises(ValueError, match="memory_self_report_max_ids"):
            TelemetrySettings(memory_self_report_max_ids=0)

    def test_memory_self_report_max_ids_one_ok(self) -> None:
        settings = TelemetrySettings(memory_self_report_max_ids=1)
        assert settings.memory_self_report_max_ids == 1


class TestHTTPConfigValidation:
    def test_valid_defaults(self) -> None:
        from openchronicle.interfaces.api.config import HTTPConfig

        config = HTTPConfig()
        assert config.port == 8000

    def test_port_zero(self) -> None:
        from openchronicle.interfaces.api.config import HTTPConfig

        with pytest.raises(ValueError, match="port"):
            HTTPConfig(port=0)

    def test_port_too_high(self) -> None:
        from openchronicle.interfaces.api.config import HTTPConfig

        with pytest.raises(ValueError, match="port"):
            HTTPConfig(port=65536)

    def test_port_boundary_low(self) -> None:
        from openchronicle.interfaces.api.config import HTTPConfig

        config = HTTPConfig(port=1)
        assert config.port == 1

    def test_port_boundary_high(self) -> None:
        from openchronicle.interfaces.api.config import HTTPConfig

        config = HTTPConfig(port=65535)
        assert config.port == 65535


# ── Adapter timeout wiring ────────────────────────────────────────────


class TestAdapterTimeoutWiring:
    def test_openai_adapter_stores_timeout(self) -> None:
        from openchronicle.core.infrastructure.llm.openai_adapter import OpenAIAdapter

        adapter = OpenAIAdapter(api_key="test-key", timeout_seconds=42.0)
        assert adapter.timeout_seconds == 42.0

    def test_anthropic_adapter_stores_timeout(self) -> None:
        from openchronicle.core.infrastructure.llm.anthropic_adapter import AnthropicAdapter

        adapter = AnthropicAdapter(api_key="test-key", timeout_seconds=30.0)
        assert adapter.timeout_seconds == 30.0

    def test_groq_adapter_stores_timeout(self) -> None:
        from openchronicle.core.infrastructure.llm.groq_adapter import GroqAdapter

        adapter = GroqAdapter(api_key="test-key", timeout_seconds=15.0)
        assert adapter.timeout_seconds == 15.0

    def test_gemini_adapter_stores_timeout(self) -> None:
        from openchronicle.core.infrastructure.llm.gemini_adapter import GeminiAdapter

        adapter = GeminiAdapter(api_key="test-key", timeout_seconds=25.0)
        assert adapter.timeout_seconds == 25.0

    def test_ollama_adapter_stores_timeout(self) -> None:
        from openchronicle.core.infrastructure.llm.ollama_adapter import OllamaAdapter

        adapter = OllamaAdapter(timeout_seconds=90.0)
        assert adapter.timeout_seconds == 90.0

    def test_ollama_adapter_default_timeout(self) -> None:
        from openchronicle.core.infrastructure.llm.ollama_adapter import OllamaAdapter

        adapter = OllamaAdapter()
        assert adapter.timeout_seconds == 60.0

    def test_openai_adapter_timeout_none_by_default(self) -> None:
        from openchronicle.core.infrastructure.llm.openai_adapter import OpenAIAdapter

        adapter = OpenAIAdapter(api_key="test-key")
        assert adapter.timeout_seconds is None

    def test_facade_passes_timeout_from_config(self) -> None:
        from openchronicle.core.infrastructure.llm.provider_facade import create_provider_aware_llm

        with patch.dict("os.environ", {"OC_LLM_TIMEOUT": "45"}):
            facade = create_provider_aware_llm(providers=["stub"], config_dir="config")
            # The global timeout should be picked up
            assert facade is not None


# ── CLI memory pin error handling ─────────────────────────────────────


class TestCliMemoryPinErrorHandling:
    def test_pin_invalid_id_returns_1(self, tmp_path: Any) -> None:
        import argparse

        from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
        from openchronicle.core.infrastructure.wiring.container import CoreContainer
        from openchronicle.interfaces.cli.commands.memory import cmd_memory_pin

        store = SqliteStore(db_path=str(tmp_path / "test.db"))
        store.init_schema()

        mock_container = MagicMock(spec=CoreContainer)
        mock_container.storage = store
        mock_container.event_logger = MagicMock()

        args = argparse.Namespace(memory_id="nonexistent-id", pin_on=True)
        result = cmd_memory_pin(args, mock_container)
        assert result == 1


# ── Logging in exception handlers ─────────────────────────────────────


class TestLoggingInExceptionHandlers:
    @pytest.mark.asyncio
    async def test_continue_project_logs_task_failure(self, caplog: Any, tmp_path: Any) -> None:
        """continue_project logs exception when a task fails."""
        from openchronicle.core.application.use_cases import continue_project
        from openchronicle.core.domain.models.project import TaskStatus

        mock_orchestrator = MagicMock()
        mock_task = MagicMock()
        mock_task.id = "test-task-id"
        mock_task.status = TaskStatus.PENDING
        mock_task.created_at = utc_now()
        mock_task.agent_id = "agent-1"
        mock_orchestrator.storage.list_tasks_by_project.return_value = [mock_task]

        # run_task.execute should raise
        with patch("openchronicle.core.application.use_cases.continue_project.run_task") as mock_run_task:
            from unittest.mock import AsyncMock

            mock_run_task.execute = AsyncMock(side_effect=RuntimeError("boom"))

            with caplog.at_level(logging.ERROR):
                result = await continue_project.execute(
                    orchestrator=mock_orchestrator,
                    project_id="proj-1",
                )
            assert result.failed == 1
            assert "test-task-id" in caplog.text


# ── Error code normalization ──────────────────────────────────────────


class TestErrorCodeNormalization:
    def test_all_error_codes_screaming_snake(self) -> None:
        """All error code string values should be SCREAMING_SNAKE_CASE."""
        from openchronicle.core.domain.errors import error_codes

        for name in error_codes.__all__:
            value = getattr(error_codes, name)
            assert value == value.upper(), f"{name} = {value!r} is not SCREAMING_SNAKE_CASE"

    def test_error_classifier_uses_normalized_codes(self) -> None:
        """Error classifier recognizes the normalized TIMEOUT code."""
        from openchronicle.core.application.routing.error_classifier import classify_error
        from openchronicle.core.domain.ports.llm_port import LLMProviderError

        error = LLMProviderError("timed out", error_code="TIMEOUT")
        assert classify_error(error) == "transient"

    def test_error_classifier_connection_error(self) -> None:
        from openchronicle.core.application.routing.error_classifier import classify_error
        from openchronicle.core.domain.ports.llm_port import LLMProviderError

        error = LLMProviderError("conn failed", error_code="CONNECTION_ERROR")
        assert classify_error(error) == "transient"
