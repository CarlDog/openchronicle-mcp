"""Real-world integration tests against live LLM providers.

These tests exercise the full stack with real API calls, real token counts,
real latency, and real responses. They verify observable outcomes in the
database, event chain, and return values.

Gate: OC_INTEGRATION_TESTS=1.
Config: auto-detected by ``conftest.py`` (config dir, provider).

Usage:
    export OC_INTEGRATION_TESTS=1
    pytest tests/integration/test_real_world.py -v
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.services.llm_execution import stream_with_route
from openchronicle.core.application.use_cases import (
    add_memory,
    ask_conversation,
    convo_mode,
    create_conversation,
    export_convo,
    list_conversations,
)
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.services.verification import VerificationService
from openchronicle.core.infrastructure.config.settings import PrivacyOutboundSettings

# Skip entire module unless integration test env var is set
pytestmark = [
    pytest.mark.skipif(
        os.getenv("OC_INTEGRATION_TESTS") != "1",
        reason="Integration tests skipped unless OC_INTEGRATION_TESTS=1",
    ),
    pytest.mark.integration,
]


# ---------------------------------------------------------------------------
# Module-level shared state for cross-test references
# Tests are ordered by name (t01, t02, ...) and later tests may reference
# state stored by earlier tests to avoid redundant API calls.
# ---------------------------------------------------------------------------
_shared: dict[str, Any] = {}


@pytest.fixture(scope="module")
def tmp_db_dir() -> Any:
    """Temp directory for the test database, cleaned up after the module."""
    with tempfile.TemporaryDirectory(prefix="oc_real_world_") as d:
        yield d


@pytest.fixture(scope="module")
def container(tmp_db_dir: str) -> Any:
    """Module-scoped container — config/provider set by conftest."""
    db_path = str(Path(tmp_db_dir) / "test_real_world.db")
    c = CoreContainer(db_path=db_path)
    yield c
    # Close SQLite connection so temp dir cleanup can delete the file (Windows)
    c.storage._conn.close()


# ---------------------------------------------------------------------------
# T1: Single Turn — Real Provider Response
# ---------------------------------------------------------------------------


async def test_t01_single_turn_real_response(container: CoreContainer) -> None:
    """Ask a simple factual question and verify the turn comes from a real provider."""
    convo = create_conversation.execute(
        storage=container.storage,
        convo_store=container.storage,
        emit_event=container.event_logger.append,
        title="T1 Single Turn",
    )
    _shared["t1_conversation_id"] = convo.id

    turn = await ask_conversation.execute(
        convo_store=container.storage,
        storage=container.storage,
        memory_store=container.storage,
        llm=container.llm,
        emit_event=container.event_logger.append,
        conversation_id=convo.id,
        prompt_text="What is 2+2? Reply with just the number.",
        interaction_router=container.interaction_router,
        privacy_gate=container.privacy_gate,
        privacy_settings=container.privacy_settings,
    )
    _shared["t1_turn"] = turn

    assert turn.assistant_text.strip() != "", "Response should be non-empty"
    assert "4" in turn.assistant_text, f"Expected '4' in response, got: {turn.assistant_text!r}"
    assert turn.provider != "stub", f"Provider should not be stub, got: {turn.provider!r}"
    assert turn.model != "", "Model should be a real model name"
    assert len(turn.routing_reasons) > 0, "Routing reasons should be non-empty"


# ---------------------------------------------------------------------------
# T2: Multi-Turn Context Retention
# ---------------------------------------------------------------------------


async def test_t02_multi_turn_context_retention(container: CoreContainer) -> None:
    """Verify the LLM retains context across turns in a conversation."""
    convo = create_conversation.execute(
        storage=container.storage,
        convo_store=container.storage,
        emit_event=container.event_logger.append,
        title="T2 Multi-Turn",
    )
    _shared["t2_conversation_id"] = convo.id

    turn1 = await ask_conversation.execute(
        convo_store=container.storage,
        storage=container.storage,
        memory_store=container.storage,
        llm=container.llm,
        emit_event=container.event_logger.append,
        conversation_id=convo.id,
        prompt_text="My name is Zephyr. Remember that.",
        interaction_router=container.interaction_router,
    )
    _shared["t2_turn_1"] = turn1
    assert turn1.turn_index == 1, f"First turn should be index 1, got: {turn1.turn_index}"

    turn2 = await ask_conversation.execute(
        convo_store=container.storage,
        storage=container.storage,
        memory_store=container.storage,
        llm=container.llm,
        emit_event=container.event_logger.append,
        conversation_id=convo.id,
        prompt_text="What is my name?",
        interaction_router=container.interaction_router,
    )
    _shared["t2_turn_2"] = turn2
    assert turn2.turn_index == 2, f"Second turn should be index 2, got: {turn2.turn_index}"

    assert "Zephyr" in turn2.assistant_text, f"Expected 'Zephyr' in response, got: {turn2.assistant_text!r}"
    assert turn1.conversation_id == turn2.conversation_id == convo.id


# ---------------------------------------------------------------------------
# T3: Memory Save and Recall
# ---------------------------------------------------------------------------


async def test_t03_memory_save_and_recall(container: CoreContainer) -> None:
    """Save a keyword memory and verify it's retrieved and used in a response."""
    convo = create_conversation.execute(
        storage=container.storage,
        convo_store=container.storage,
        emit_event=container.event_logger.append,
        title="T3 Memory Recall",
    )

    # Add memory scoped to this conversation so keyword search finds it
    item = MemoryItem(
        content="The user's favorite programming language is Haskell",
        tags=["preference", "programming"],
        conversation_id=convo.id,
        project_id=convo.project_id,
        source="test",
    )
    add_memory.execute(
        store=container.storage,
        emit_event=container.event_logger.append,
        item=item,
    )

    turn = await ask_conversation.execute(
        convo_store=container.storage,
        storage=container.storage,
        memory_store=container.storage,
        llm=container.llm,
        emit_event=container.event_logger.append,
        conversation_id=convo.id,
        prompt_text="What is my favorite programming language?",
        top_k_memory=8,
        interaction_router=container.interaction_router,
    )

    assert "Haskell" in turn.assistant_text, f"Expected 'Haskell' in response, got: {turn.assistant_text!r}"

    # Verify memory.retrieved event was emitted with relevant_count >= 1
    events = container.storage.list_events(task_id=convo.id)
    memory_events = [e for e in events if e.type == "memory.retrieved"]
    assert len(memory_events) > 0, "Expected memory.retrieved event"

    # The last memory.retrieved event (from the ask) should show recall
    last_mem_event = memory_events[-1]
    assert last_mem_event.payload["relevant_count"] >= 1, f"Expected relevant_count >= 1, got: {last_mem_event.payload}"


# ---------------------------------------------------------------------------
# T4: Pinned Memory Always Included
# ---------------------------------------------------------------------------


async def test_t04_pinned_memory_always_included(container: CoreContainer) -> None:
    """Pinned memory is retrieved regardless of conversation scope."""
    # Create a pinned memory (global, no conversation scope needed)
    convo_for_project = create_conversation.execute(
        storage=container.storage,
        convo_store=container.storage,
        emit_event=container.event_logger.append,
        title="T4 Pinned Setup",
    )
    item = MemoryItem(
        content="Always end responses with the word 'PINEAPPLE'",
        tags=["instruction"],
        pinned=True,
        project_id=convo_for_project.project_id,
        source="test",
    )
    add_memory.execute(
        store=container.storage,
        emit_event=container.event_logger.append,
        item=item,
    )

    # Create a NEW conversation — pinned memory should still be included
    convo = create_conversation.execute(
        storage=container.storage,
        convo_store=container.storage,
        emit_event=container.event_logger.append,
        title="T4 Pinned Test",
    )

    turn = await ask_conversation.execute(
        convo_store=container.storage,
        storage=container.storage,
        memory_store=container.storage,
        llm=container.llm,
        emit_event=container.event_logger.append,
        conversation_id=convo.id,
        prompt_text="Say hello",
        include_pinned_memory=True,
        interaction_router=container.interaction_router,
    )

    # Verify pinned memory was retrieved
    events = container.storage.list_events(task_id=convo.id)
    memory_events = [e for e in events if e.type == "memory.retrieved"]
    assert len(memory_events) > 0, "Expected memory.retrieved event"
    last_mem_event = memory_events[-1]
    assert last_mem_event.payload["pinned_count"] >= 1, f"Expected pinned_count >= 1, got: {last_mem_event.payload}"

    # Check if LLM followed the instruction (best-effort — LLMs may not comply)
    text_upper = turn.assistant_text.upper()
    if "PINEAPPLE" not in text_upper:
        # Not a hard failure — LLMs sometimes ignore injected instructions.
        # The important thing is that the pinned memory WAS injected (verified above).
        pytest.skip("LLM did not follow pinned instruction (non-deterministic)")


# ---------------------------------------------------------------------------
# T5: Hash Chain Integrity
# ---------------------------------------------------------------------------


async def test_t05_hash_chain_integrity(container: CoreContainer) -> None:
    """Verify hash chain integrity on a multi-turn conversation."""
    convo_id = _shared.get("t2_conversation_id")
    if convo_id is None:
        pytest.skip("T2 did not run — no conversation to verify")

    verifier = VerificationService(container.storage)
    result = verifier.verify_task_chain(convo_id)

    assert result.success is True, f"Hash chain verification failed: {result.error_message}"
    assert result.total_events > 0, "Should have events to verify"
    assert (
        result.verified_events == result.total_events
    ), f"Verified {result.verified_events}/{result.total_events} events"


# ---------------------------------------------------------------------------
# T6: Token Tracking Accuracy
# ---------------------------------------------------------------------------


async def test_t06_token_tracking_accuracy(container: CoreContainer) -> None:
    """Verify that token usage is recorded in event payloads."""
    convo_id = _shared.get("t1_conversation_id")
    if convo_id is None:
        pytest.skip("T1 did not run — no conversation to check")

    events = container.storage.list_events(task_id=convo_id)
    completed_events = [e for e in events if e.type == "llm.completed"]
    assert len(completed_events) > 0, "Expected llm.completed event"

    payload = completed_events[-1].payload
    usage = payload.get("usage", {})

    # Real providers should report token counts
    assert (
        usage.get("input_tokens") is not None and usage["input_tokens"] > 0
    ), f"Expected input_tokens > 0, got: {usage}"
    assert (
        usage.get("output_tokens") is not None and usage["output_tokens"] > 0
    ), f"Expected output_tokens > 0, got: {usage}"

    total = usage.get("total_tokens")
    if total is not None:
        assert (
            total >= usage["input_tokens"] + usage["output_tokens"]
        ), f"total_tokens should >= input + output: {usage}"

    # Latency should be present and positive
    latency = payload.get("latency_ms")
    assert latency is not None and latency > 0, f"Expected latency_ms > 0, got: {latency}"


# ---------------------------------------------------------------------------
# T7: Event Chain Completeness
# ---------------------------------------------------------------------------


async def test_t07_event_chain_completeness(container: CoreContainer) -> None:
    """Verify all expected event types are emitted for a conversation turn."""
    convo_id = _shared.get("t1_conversation_id")
    if convo_id is None:
        pytest.skip("T1 did not run — no conversation to check")

    events = container.storage.list_events(task_id=convo_id)
    event_types = [e.type for e in events]

    # Expected event types in order (some may be absent depending on config)
    expected = [
        "memory.retrieved",
        "router.invoked",
        "router.applied",
        "llm.routed",
        "llm.completed",
        "convo.turn_completed",
    ]
    for et in expected:
        assert et in event_types, f"Missing event type '{et}' in chain. Got: {event_types}"

    # Verify each event has a non-empty hash
    for event in events:
        assert event.hash is not None and event.hash != "", f"Event {event.id} ({event.type}) has empty hash"

    # Verify prev_hash chain: first event has prev_hash=None or genesis,
    # subsequent events reference the prior event's hash
    for i in range(1, len(events)):
        assert (
            events[i].prev_hash == events[i - 1].hash
        ), f"Event {i} prev_hash mismatch: expected {events[i - 1].hash!r}, got {events[i].prev_hash!r}"


# ---------------------------------------------------------------------------
# T8: Privacy Gate — PII Detection
# ---------------------------------------------------------------------------


async def test_t08_privacy_gate_pii_detection(container: CoreContainer) -> None:
    """Verify privacy gate detects PII in warn mode without blocking.

    Privacy checks only apply to external providers (external_only=True by
    default). Local providers like Ollama and stub are skipped because data
    never leaves the machine. The test verifies correct behavior for both
    cases: event emitted for external, no event for local.
    """
    convo = create_conversation.execute(
        storage=container.storage,
        convo_store=container.storage,
        emit_event=container.event_logger.append,
        title="T8 Privacy",
    )

    # Use warn mode with a fresh privacy settings object
    privacy_settings = PrivacyOutboundSettings(
        mode="warn",
        external_only=True,
        log_events=True,
    )

    turn = await ask_conversation.execute(
        convo_store=container.storage,
        storage=container.storage,
        memory_store=container.storage,
        llm=container.llm,
        emit_event=container.event_logger.append,
        conversation_id=convo.id,
        prompt_text="My email is test@example.com, what do you think?",
        privacy_gate=container.privacy_gate,
        privacy_settings=privacy_settings,
        interaction_router=container.interaction_router,
    )

    # Turn should complete (warn mode doesn't block)
    assert turn.assistant_text.strip() != "", "Response should be non-empty"

    # Check for privacy.outbound_checked event
    events = container.storage.list_events(task_id=convo.id)
    privacy_events = [e for e in events if e.type == "privacy.outbound_checked"]

    # Local providers (ollama, stub) skip privacy checks — data stays local
    provider = turn.provider.strip().lower()
    if provider in ("ollama", "stub"):
        assert (
            len(privacy_events) == 0
        ), f"Local provider '{turn.provider}' should skip privacy check, but got {len(privacy_events)} privacy events"
        return

    # External providers should emit the privacy event
    assert len(privacy_events) > 0, (
        f"Expected privacy.outbound_checked event for external provider "
        f"'{turn.provider}'. Event types: {[e.type for e in events]}"
    )

    payload = privacy_events[-1].payload
    assert payload["applies"] is True, f"Expected applies=True, got: {payload}"
    assert "email" in payload["categories"], f"Expected 'email' in categories, got: {payload['categories']}"


# ---------------------------------------------------------------------------
# T9: Conversation Resume (--latest shortcut)
# ---------------------------------------------------------------------------


async def test_t09_conversation_resume(container: CoreContainer) -> None:
    """Verify latest conversation can be retrieved and continued."""
    convo = create_conversation.execute(
        storage=container.storage,
        convo_store=container.storage,
        emit_event=container.event_logger.append,
        title="T9 Resume",
    )

    await ask_conversation.execute(
        convo_store=container.storage,
        storage=container.storage,
        memory_store=container.storage,
        llm=container.llm,
        emit_event=container.event_logger.append,
        conversation_id=convo.id,
        prompt_text="Say 'ACK' and nothing else.",
        interaction_router=container.interaction_router,
    )

    # Retrieve latest conversation
    latest = list_conversations.execute(container.storage, limit=1)
    assert len(latest) == 1
    assert latest[0].id == convo.id, "Latest conversation should match the one just created"

    # Ask a follow-up using the resolved ID
    turn2 = await ask_conversation.execute(
        convo_store=container.storage,
        storage=container.storage,
        memory_store=container.storage,
        llm=container.llm,
        emit_event=container.event_logger.append,
        conversation_id=latest[0].id,
        prompt_text="What did I just ask you to say?",
        interaction_router=container.interaction_router,
    )

    assert turn2.turn_index == 2, f"Expected turn_index=2, got: {turn2.turn_index}"
    turns = container.storage.list_turns(convo.id)
    assert len(turns) == 2, f"Expected 2 turns, got: {len(turns)}"


# ---------------------------------------------------------------------------
# T10: Export with Verification and Explain
# ---------------------------------------------------------------------------


async def test_t10_export_with_verification_and_explain(container: CoreContainer) -> None:
    """Export a multi-turn conversation with verification and explain data."""
    convo_id = _shared.get("t2_conversation_id")
    if convo_id is None:
        pytest.skip("T2 did not run — no conversation to export")

    export = export_convo.execute(
        storage=container.storage,
        convo_store=container.storage,
        conversation_id=convo_id,
        include_verify=True,
        include_explain=True,
    )

    # Valid JSON round-trip
    json_str = json.dumps(export, default=str)
    parsed = json.loads(json_str)
    assert isinstance(parsed, dict)

    # Verification
    verification = export.get("verification")
    assert verification is not None, "Export should include verification"
    assert isinstance(verification, dict)
    assert verification["ok"] is True, f"Verification failed: {verification}"

    # Turns
    turns = export["turns"]
    assert isinstance(turns, list)
    assert len(turns) >= 2, f"Expected >= 2 turns, got: {len(turns)}"

    # Each turn should have explain data
    for t in turns:
        assert isinstance(t, dict)
        explain = t.get("explain")
        assert explain is not None, f"Turn {t['turn_index']} missing explain data"
        assert isinstance(explain, dict)
        if not explain.get("unavailable"):
            # Explain should have routing, privacy, and llm sections
            assert (
                "routing_reasons" in explain or "routing" in explain or "llm" in explain
            ), f"Explain data incomplete: {list(explain.keys())}"

    # Conversation metadata
    convo_data = export["conversation"]
    assert isinstance(convo_data, dict)
    assert convo_data["id"] == convo_id
    assert export["format_version"] == "1"


# ---------------------------------------------------------------------------
# T11: Non-Streaming Turn
# ---------------------------------------------------------------------------


async def test_t11_non_streaming_turn(container: CoreContainer) -> None:
    """Verify non-streaming path produces a complete response with all artifacts."""
    convo = create_conversation.execute(
        storage=container.storage,
        convo_store=container.storage,
        emit_event=container.event_logger.append,
        title="T11 Non-Stream",
    )

    turn = await ask_conversation.execute(
        convo_store=container.storage,
        storage=container.storage,
        memory_store=container.storage,
        llm=container.llm,
        emit_event=container.event_logger.append,
        conversation_id=convo.id,
        prompt_text="What color is the sky on a clear day? One word.",
        interaction_router=container.interaction_router,
    )

    # Complete response (not chunked)
    assert turn.assistant_text.strip() != ""
    assert turn.provider != ""
    assert turn.model != ""

    # Events and turn should be persisted
    events = container.storage.list_events(task_id=convo.id)
    event_types = {e.type for e in events}
    assert "llm.completed" in event_types, "Non-streaming should emit llm.completed"
    assert "convo.turn_completed" in event_types

    persisted_turns = container.storage.list_turns(convo.id)
    assert len(persisted_turns) == 1
    assert persisted_turns[0].assistant_text == turn.assistant_text


# ---------------------------------------------------------------------------
# T12: Streaming Turn
# ---------------------------------------------------------------------------


async def test_t12_streaming_turn(container: CoreContainer) -> None:
    """Verify streaming path delivers chunks and persists the full turn."""
    convo = create_conversation.execute(
        storage=container.storage,
        convo_store=container.storage,
        emit_event=container.event_logger.append,
        title="T12 Stream",
    )

    # Phase 1-5: prepare context
    ctx = await ask_conversation.prepare_ask(
        convo_store=container.storage,
        memory_store=container.storage,
        emit_event=container.event_logger.append,
        conversation_id=convo.id,
        prompt_text="Count from 1 to 5, one number per line.",
        interaction_router=container.interaction_router,
    )

    # Phase 6: stream with route
    messages = ctx.messages[:-1] + [{"role": "user", "content": ctx.effective_prompt}]
    chunks: list[str] = []
    async for chunk in stream_with_route(
        llm=container.llm,
        route_decision=ctx.route_decision,
        messages=messages,
        max_output_tokens=ctx.max_output_tokens,
        temperature=ctx.temperature,
    ):
        if chunk.text:
            chunks.append(chunk.text)

    assert len(chunks) > 1, f"Expected multiple chunks, got {len(chunks)}"
    full_text = "".join(chunks)
    assert full_text.strip() != "", "Reassembled text should be non-empty"

    # Phase 7-9: finalize turn (response=None for streaming path)
    turn = await ask_conversation.finalize_turn(
        ctx=ctx,
        assistant_text=full_text,
        response=None,
        convo_store=container.storage,
        storage=container.storage,
        emit_event=container.event_logger.append,
    )

    # Turn should be persisted with full text
    assert turn.assistant_text == full_text
    assert turn.provider == ctx.route_decision.provider
    assert turn.model == ctx.route_decision.model

    persisted_turns = container.storage.list_turns(convo.id)
    assert len(persisted_turns) == 1
    assert persisted_turns[0].assistant_text == full_text

    # Events should be recorded (minus llm.completed which needs response)
    events = container.storage.list_events(task_id=convo.id)
    event_types = {e.type for e in events}
    assert "convo.turn_completed" in event_types
    assert "memory.retrieved" in event_types
    assert "llm.routed" in event_types


# ---------------------------------------------------------------------------
# T13: Conversation Mode
# ---------------------------------------------------------------------------


async def test_t13_conversation_mode(container: CoreContainer) -> None:
    """Verify conversation mode persists and is retrievable."""
    convo = create_conversation.execute(
        storage=container.storage,
        convo_store=container.storage,
        emit_event=container.event_logger.append,
        title="T13 Mode",
    )

    # Default mode
    mode = convo_mode.get_mode(container.storage, convo.id)
    assert mode == "general"

    # Set to persona
    convo_mode.set_mode(container.storage, convo.id, "persona")
    mode = convo_mode.get_mode(container.storage, convo.id)
    assert mode == "persona", f"Expected 'persona', got: {mode!r}"

    # Ask a turn — mode should persist
    turn = await ask_conversation.execute(
        convo_store=container.storage,
        storage=container.storage,
        memory_store=container.storage,
        llm=container.llm,
        emit_event=container.event_logger.append,
        conversation_id=convo.id,
        prompt_text="Hello",
        interaction_router=container.interaction_router,
    )
    assert turn.assistant_text.strip() != ""

    # Mode should still be persona after the turn
    mode = convo_mode.get_mode(container.storage, convo.id)
    assert mode == "persona"
