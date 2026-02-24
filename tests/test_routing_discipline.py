"""
Test: Architectural boundary enforcement for routing discipline.

This test ensures that Application-level code cannot accidentally bypass
the routing system by calling LLM infrastructure directly.
"""

import ast
from pathlib import Path
from typing import Any

from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError


def test_application_layer_must_not_call_llm_port_directly() -> None:
    """
    Architectural constraint: Application code must not call LLMPort.complete_async directly.

    All LLM calls must go through routing-anchored helpers (llm_execution.py).
    This prevents accidental provider selection and enforces routing discipline.
    """
    # Find application layer Python files
    project_root = Path(__file__).parent.parent / "src" / "openchronicle" / "core" / "application"
    application_files = list(project_root.rglob("*.py"))

    violations: list[str] = []

    for file_path in application_files:
        # Skip the llm_execution module itself (it's the boundary)
        if "llm_execution.py" in str(file_path):
            continue

        # Skip __init__ and __pycache__
        if "__init__.py" in str(file_path) or "__pycache__" in str(file_path):
            continue

        content = file_path.read_text(encoding="utf-8")

        # Parse the AST
        try:
            tree = ast.parse(content)
        except SyntaxError:
            # Skip files with syntax errors (shouldn't happen in tests)
            continue

        # Look for calls to llm.complete_async or self.llm.complete_async
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check if this is a call to complete_async
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "complete_async":
                        # Check if the object is 'llm' or 'self.llm'
                        if isinstance(node.func.value, ast.Name) and node.func.value.id == "llm":
                            relative_path = file_path.relative_to(project_root.parent.parent.parent)
                            violations.append(
                                f"{relative_path}:{node.lineno} - Direct call to llm.complete_async found"
                            )
                        elif isinstance(node.func.value, ast.Attribute):
                            if (
                                isinstance(node.func.value.value, ast.Name)
                                and node.func.value.value.id == "self"
                                and node.func.value.attr == "llm"
                            ):
                                relative_path = file_path.relative_to(project_root.parent.parent.parent)
                                violations.append(
                                    f"{relative_path}:{node.lineno} - Direct call to self.llm.complete_async found"
                                )

    if violations:
        violation_msg = "\n".join(violations)
        raise AssertionError(
            f"Application layer must not call LLMPort.complete_async directly.\n"
            f"Use llm_execution.execute_with_explicit_provider or execute_with_route instead.\n\n"
            f"Violations found:\n{violation_msg}"
        )


def test_llm_execution_boundary_validates_provider() -> None:
    """
    Test that the llm_execution boundary enforces provider validation.

    The helpers must reject None or empty provider values to prevent
    accidental unrouted calls.
    """
    from openchronicle.core.application.services.llm_execution import execute_with_explicit_provider
    from openchronicle.core.domain.ports.llm_port import LLMPort, LLMResponse, LLMUsage

    # Create a minimal fake LLM port
    class FakeLLMPort(LLMPort):
        async def complete_async(
            self,
            messages: list[dict[str, str]],  # noqa: ARG002
            *,
            model: str,
            max_output_tokens: int | None = None,  # noqa: ARG002
            temperature: float | None = None,  # noqa: ARG002
            provider: str | None = None,
            **kwargs: Any,
        ) -> LLMResponse:
            return LLMResponse(
                content="test",
                provider=provider or "unknown",
                model=model,
                usage=LLMUsage(input_tokens=10, output_tokens=10, total_tokens=20),
            )

        def complete(
            self,
            messages: list[dict[str, Any]],  # noqa: ARG002
            *,
            model: str,  # noqa: ARG002
            max_output_tokens: int | None = None,  # noqa: ARG002
            temperature: float | None = None,  # noqa: ARG002
            provider: str | None = None,  # noqa: ARG002
            **kwargs: Any,  # noqa: ARG002
        ) -> LLMResponse:
            raise NotImplementedError

    fake_llm = FakeLLMPort()

    # Test 1: Empty provider should be rejected
    try:
        import asyncio

        asyncio.run(
            execute_with_explicit_provider(
                llm=fake_llm,
                provider="",  # Empty string
                model="gpt-4",
                messages=[{"role": "user", "content": "test"}],
            )
        )
        raise AssertionError("Expected DomainValidationError for empty provider")
    except DomainValidationError as e:
        assert "provider is required" in str(e).lower()

    # Test 2: Empty model should be rejected
    try:
        import asyncio

        asyncio.run(
            execute_with_explicit_provider(
                llm=fake_llm,
                provider="openai",
                model="",  # Empty string
                messages=[{"role": "user", "content": "test"}],
            )
        )
        raise AssertionError("Expected DomainValidationError for empty model")
    except DomainValidationError as e:
        assert "model is required" in str(e).lower()
