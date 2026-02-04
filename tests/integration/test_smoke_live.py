"""Integration tests for smoke_live use case.

These tests are opt-in and only run when required environment variables are present.
They test real provider integration (e.g., OpenAI, Ollama) when configured.

Marking these as integration tests so unit test suite stays keyless.
"""

from __future__ import annotations

import json
import os

import pytest

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.use_cases import smoke_live
from openchronicle.core.domain.models.failure_category import (
    classify_failure_category,
    failure_category_description,
)

# Skip entire module unless integration test env var is set
pytestmark = pytest.mark.skipif(
    os.getenv("OC_INTEGRATION_TESTS") != "1",
    reason="Integration tests skipped unless OC_INTEGRATION_TESTS=1",
)


class TestSmokeLiveIntegration:
    """Integration tests for smoke_live use case with real providers."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Setup for each test."""
        # Container is created fresh for each test
        self.container = CoreContainer()
        self.orchestrator = self.container.orchestrator

    @pytest.mark.integration
    async def test_smoke_live_with_default_routing(self) -> None:
        """Test smoke_live with default routing (no provider override)."""
        # Use the default routing to select provider
        result = await smoke_live.execute(
            self.orchestrator,
            prompt="What is 2 + 2? Answer in one word.",
            provider=None,
            model=None,
        )

        # Assertions
        assert result.project_id is not None
        assert result.task_id is not None
        assert result.execution_id is not None
        assert result.attempt_id is not None
        assert result.provider_used is not None
        assert result.model_used is not None
        assert result.outcome == "completed", f"Expected outcome=completed, got {result.outcome}"
        # Tokens should be populated if provider supports it
        # (stub provider returns None, real providers return integers)
        # So we just check that if tokens are present, they're non-negative
        if result.total_tokens is not None:
            assert result.total_tokens > 0

    @pytest.mark.integration
    async def test_smoke_live_with_provider_override(self) -> None:
        """Test smoke_live with explicit provider override."""
        # Check if OpenAI is configured
        has_openai = os.getenv("OPENAI_API_KEY") is not None

        if not has_openai:
            pytest.skip("OpenAI not configured (no OPENAI_API_KEY)")

        result = await smoke_live.execute(
            self.orchestrator,
            prompt="Respond with: OK",
            provider="openai",
            model="gpt-4o-mini",
        )

        assert result.project_id is not None
        assert result.provider_requested == "openai"
        assert result.provider_used == "openai"
        assert result.model_requested == "gpt-4o-mini"
        assert result.model_used == "gpt-4o-mini"
        assert result.outcome == "completed"

    @pytest.mark.integration
    async def test_smoke_live_missing_credentials_error(self) -> None:
        """Test that missing credentials raise clear errors (no secrets leaked)."""
        # Force a provider that is not configured
        # Save original env var if present
        original_key = os.environ.pop("OPENAI_API_KEY", None)

        try:
            result = await smoke_live.execute(
                self.orchestrator,
                prompt="test",
                provider="openai",
                model="gpt-4o-mini",
            )

            # Should get a "blocked" or "failed" outcome with error_code
            assert result.outcome in ("blocked", "failed")
            assert result.error_code is not None
            # Ensure no secrets are in error message
            # Note: error CODE names like [invalid_api_key] are not secrets
            if result.error_message:
                # Check for actual API key patterns (e.g., OpenAI keys start with "sk-")
                assert "sk-" not in result.error_message
                # Extract message portion after error code bracket for additional checks
                msg_part = (
                    result.error_message.split("] ", 1)[-1] if "]" in result.error_message else result.error_message
                )
                assert "OPENAI" not in msg_part  # (but "OpenAI" is ok in message text)
        finally:
            # Restore original env var
            if original_key:
                os.environ["OPENAI_API_KEY"] = original_key

    @pytest.mark.integration
    async def test_smoke_live_with_custom_prompt(self) -> None:
        """Test smoke_live with custom prompt."""
        custom_prompt = "This is a custom test prompt for smoke testing."

        result = await smoke_live.execute(
            self.orchestrator,
            prompt=custom_prompt,
            provider=None,
            model=None,
        )

        assert result.project_id is not None
        assert result.prompt_text == custom_prompt
        # Outcome depends on provider availability
        assert result.outcome in ("completed", "failed", "blocked")

    @pytest.mark.integration
    async def test_smoke_live_emits_events(self) -> None:
        """Test that smoke_live properly emits events to storage."""
        result = await smoke_live.execute(
            self.orchestrator,
            prompt="Short test",
            provider=None,
            model=None,
        )

        # Retrieve events from storage
        events = self.container.storage.list_events(result.task_id)

        # Should have at least: routed, and either execution_recorded or failed
        assert len(events) > 0, "No events emitted for task"

        event_types = {e.type for e in events}

        # Should include routing decision
        assert "llm.routed" in event_types, f"Missing llm.routed event. Got: {event_types}"

        # Should include either success or failure
        if result.outcome == "completed":
            assert "llm.execution_recorded" in event_types, f"Missing llm.execution_recorded. Got: {event_types}"
        else:
            assert (
                "task_failed" in event_types or "llm.budget_exceeded" in event_types
            ), f"Missing failure event for outcome={result.outcome}. Got: {event_types}"

    @pytest.mark.integration
    async def test_smoke_live_result_serializeable(self) -> None:
        """Test that SmokeResult can be serialized to dict/JSON."""
        result = await smoke_live.execute(
            self.orchestrator,
            prompt="test",
            provider=None,
            model=None,
        )

        # Should serialize to dict
        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert result_dict["project_id"] == result.project_id
        assert result_dict["outcome"] == result.outcome

        # Should be JSON serializable
        json_str = json.dumps(result_dict)
        assert json_str is not None
        assert len(json_str) > 0

        # Should deserialize back
        deserialized = json.loads(json_str)
        assert deserialized["project_id"] == result.project_id


class TestFailureClassification:
    """Tests for failure category classification in smoke_live."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Setup for each test."""
        self.container = CoreContainer()
        self.orchestrator = self.container.orchestrator

    @pytest.mark.integration
    async def test_failure_category_config_error_missing_credentials(self) -> None:
        """Test that missing credentials are classified as CONFIG_ERROR."""
        # Remove OpenAI API key if present
        original_key = os.environ.pop("OPENAI_API_KEY", None)

        try:
            result = await smoke_live.execute(
                self.orchestrator,
                prompt="test",
                provider="openai",
                model="gpt-4o-mini",
            )

            # Should be classified as CONFIG_ERROR
            if result.outcome != "completed":
                # Smoke test expects to fail; check failure classification
                if result.error_code and "credential" in result.error_code.lower():
                    assert result.failure_category == "CONFIG_ERROR"
                elif result.error_code and "auth" in result.error_code.lower():
                    assert result.failure_category == "CONFIG_ERROR"
        finally:
            if original_key:
                os.environ["OPENAI_API_KEY"] = original_key

    @pytest.mark.integration
    async def test_failure_category_budget_blocked(self) -> None:
        """Test that budget exceeded errors are classified as BUDGET_BLOCKED."""
        # Set a very low budget that will be exceeded
        os.environ["OC_LLM_TPM_LIMIT"] = "1"  # 1 token per minute

        try:
            result = await smoke_live.execute(
                self.orchestrator,
                prompt="x" * 1000,  # Large prompt to exceed low TPM limit
                provider=None,
                model=None,
            )

            if result.outcome == "blocked" and result.error_code == "budget_exceeded":
                assert result.failure_category == "BUDGET_BLOCKED"
        finally:
            # Reset TPM limit
            os.environ.pop("OC_LLM_TPM_LIMIT", None)

    @pytest.mark.integration
    async def test_failure_category_serialized_in_result(self) -> None:
        """Test that failure_category is included in serialized result."""
        result = await smoke_live.execute(
            self.orchestrator,
            prompt="test",
            provider=None,
            model=None,
        )

        # Convert to dict
        result_dict = result.to_dict()

        # Should include failure_category field (None if successful, or category if failed)
        assert "failure_category" in result_dict

        # If outcome is failed/blocked, failure_category should be set
        if result.outcome in ("blocked", "failed"):
            assert result.failure_category is not None
            assert result_dict["failure_category"] is not None

    def test_classify_failure_category_direct(self) -> None:
        """Test failure category classification function directly."""
        # Test budget exceeded
        category = classify_failure_category("budget_exceeded", None)
        assert category == "BUDGET_BLOCKED"

        # Test timeout
        category = classify_failure_category("timeout", None)
        assert category == "TIMEOUT"

        # Test credential error
        category = classify_failure_category("credential_error", None)
        assert category == "CONFIG_ERROR"

        # Test auth error
        category = classify_failure_category("auth_error", None)
        assert category == "CONFIG_ERROR"

        # Test provider error (fallback)
        category = classify_failure_category("provider_error", "permanent")
        assert category == "PROVIDER_ERROR"

        # Test unknown
        category = classify_failure_category("unknown", None)
        assert category == "UNKNOWN"

    def test_failure_category_description(self) -> None:
        """Test human-readable descriptions for failure categories."""
        desc = failure_category_description("BUDGET_BLOCKED")
        assert "Budget" in desc

        desc = failure_category_description("CONFIG_ERROR")
        assert "Configuration" in desc or "credential" in desc.lower()

        desc = failure_category_description("PROVIDER_ERROR")
        assert "Provider" in desc

        desc = failure_category_description("REFUSAL")
        assert "policy" in desc.lower() or "rejection" in desc.lower()

        desc = failure_category_description("TIMEOUT")
        assert "timeout" in desc.lower() or "rate" in desc.lower()
