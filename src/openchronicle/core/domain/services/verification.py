"""Hash-chain verification service for event integrity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openchronicle.core.domain.ports.storage_port import StoragePort


@dataclass
class VerificationResult:
    """Result of hash-chain verification."""

    success: bool
    total_events: int
    verified_events: int
    first_mismatch: dict[str, Any] | None = None
    error_message: str | None = None


class VerificationService:
    """Verifies the integrity of event hash chains."""

    def __init__(self, storage: StoragePort) -> None:
        self.storage = storage

    def verify_task_chain(self, task_id: str) -> VerificationResult:
        """
        Verify the hash chain for all events in a task.

        Returns:
            VerificationResult with success status and details of any mismatch.
        """
        events = self.storage.list_events(task_id)

        if not events:
            return VerificationResult(
                success=True, total_events=0, verified_events=0, error_message="No events found for task"
            )

        total = len(events)
        verified = 0
        prev_hash = None

        for idx, event in enumerate(events):
            # Verify prev_hash linkage
            if event.prev_hash != prev_hash:
                return VerificationResult(
                    success=False,
                    total_events=total,
                    verified_events=verified,
                    first_mismatch={
                        "event_index": idx,
                        "event_id": event.id,
                        "event_type": event.type,
                        "expected_prev_hash": prev_hash,
                        "actual_prev_hash": event.prev_hash,
                    },
                    error_message=f"prev_hash mismatch at event {idx} (type={event.type})",
                )

            # Recompute hash and verify
            computed_hash = event.compute_hash()
            if computed_hash != event.hash:
                return VerificationResult(
                    success=False,
                    total_events=total,
                    verified_events=verified,
                    first_mismatch={
                        "event_index": idx,
                        "event_id": event.id,
                        "event_type": event.type,
                        "expected_hash": event.hash,
                        "computed_hash": computed_hash,
                    },
                    error_message=f"Hash mismatch at event {idx} (type={event.type})",
                )

            verified += 1
            prev_hash = event.hash

        return VerificationResult(success=True, total_events=total, verified_events=verified)
