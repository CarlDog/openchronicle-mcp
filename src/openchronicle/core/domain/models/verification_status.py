"""Verification status for task outputs.

Represents whether a task's output has been verified against objective criteria.
Verification is orthogonal to execution status—a task can complete successfully
but remain unverified until explicit verification events are recorded.
"""

from enum import Enum


class VerificationStatus(str, Enum):
    """Status of task output verification.

    Verification is explicit and event-driven:
    - NOT_VERIFIED: Default state; task output not yet checked
    - VERIFIED: Task output passed verification checks
    - FAILED: Task output failed verification checks

    Verification events do not affect task execution status.
    """

    NOT_VERIFIED = "not_verified"
    VERIFIED = "verified"
    FAILED = "failed"
