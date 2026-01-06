"""Tests for hash-chain verification and tampering detection."""

from __future__ import annotations

import sqlite3

import pytest

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.domain.services.verification import VerificationService


@pytest.fixture
def container() -> CoreContainer:
    """Create a fresh container for each test."""
    return CoreContainer()


@pytest.mark.asyncio
async def test_hash_chain_detects_tampering(container: CoreContainer) -> None:
    """Test that hash-chain verification detects tampered events."""
    # Create a project and agents
    orchestrator = container.orchestrator
    project = orchestrator.create_project("Tamper Test Project")

    supervisor = orchestrator.register_agent(
        project_id=project.id, name="Supervisor", role="supervisor", provider="stub", model="stub-model"
    )
    orchestrator.register_agent(
        project_id=project.id, name="Worker1", role="worker", provider="stub", model="stub-model"
    )
    orchestrator.register_agent(
        project_id=project.id, name="Worker2", role="worker", provider="stub", model="stub-model"
    )

    # Run a demo-summary to generate multiple events
    task = orchestrator.submit_task(project.id, "analysis.summary", {"text": "Test text for tampering detection"})
    await orchestrator.execute_task(task.id, agent_id=supervisor.id)

    # Verify the chain is valid before tampering
    verification_service = VerificationService(container.storage)
    result_before = verification_service.verify_task_chain(task.id)
    assert result_before.success, "Chain should be valid before tampering"

    # Tamper with one event's hash in the database
    events = container.storage.list_events(task.id)
    assert len(events) > 1, "Should have multiple events to tamper with"

    # Tamper with the second event's hash (not the first to avoid prev_hash issues)
    tampered_event = events[1]
    conn = sqlite3.connect(container.storage.db_path)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE events SET hash = ? WHERE id = ?",
        ("0" * 64, tampered_event.id),  # Set to a fake hash
    )
    conn.commit()
    conn.close()

    # Verify the chain now detects the tampering
    result_after = verification_service.verify_task_chain(task.id)
    assert not result_after.success, "Chain should detect tampering"
    assert result_after.first_mismatch is not None, "Should report mismatch details"
    assert result_after.first_mismatch["event_id"] == tampered_event.id, "Should identify the tampered event"
    assert "expected_hash" in result_after.first_mismatch, "Should include expected hash"
    assert "computed_hash" in result_after.first_mismatch, "Should include computed hash"


@pytest.mark.asyncio
async def test_hash_chain_detects_prev_hash_tampering(container: CoreContainer) -> None:
    """Test that hash-chain verification detects tampered prev_hash linkage."""
    # Create a project and task
    orchestrator = container.orchestrator
    project = orchestrator.create_project("Prev Hash Tamper Test")
    supervisor = orchestrator.register_agent(
        project_id=project.id, name="Supervisor", role="supervisor", provider="stub", model="stub-model"
    )
    orchestrator.register_agent(
        project_id=project.id, name="Worker1", role="worker", provider="stub", model="stub-model"
    )
    orchestrator.register_agent(
        project_id=project.id, name="Worker2", role="worker", provider="stub", model="stub-model"
    )

    # Run a task to generate events
    task = orchestrator.submit_task(project.id, "analysis.summary", {"text": "Test prev_hash tampering"})
    await orchestrator.execute_task(task.id, agent_id=supervisor.id)

    # Tamper with prev_hash in the database
    events = container.storage.list_events(task.id)
    assert len(events) > 2, "Should have multiple events"

    # Tamper with the third event's prev_hash
    tampered_event = events[2]
    conn = sqlite3.connect(container.storage.db_path)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE events SET prev_hash = ? WHERE id = ?",
        ("9" * 64, tampered_event.id),  # Set to a fake prev_hash
    )
    conn.commit()
    conn.close()

    # Verify the chain now detects the tampering
    verification_service = VerificationService(container.storage)
    result = verification_service.verify_task_chain(task.id)
    assert not result.success, "Chain should detect prev_hash tampering"
    assert result.first_mismatch is not None, "Should report mismatch details"
    assert "expected_prev_hash" in result.first_mismatch, "Should include expected prev_hash"
    assert "actual_prev_hash" in result.first_mismatch, "Should include actual prev_hash"
