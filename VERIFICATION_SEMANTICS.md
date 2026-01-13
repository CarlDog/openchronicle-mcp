# Verification Semantics Implementation

## Overview

This implementation introduces **first-class verification semantics** to OpenChronicle v2, enabling the system to explicitly distinguish between:

- Task execution status (pending, running, completed, failed)
- Task verification status (not_verified, verified, failed)

Verification is **orthogonal to execution**—a task can complete successfully but remain unverified, or fail execution but have its error handling verified as correct.

## Components Added

### 1. Domain Model: VerificationStatus

**File**: `src/openchronicle/core/domain/models/verification_status.py`

Pure enum with three states:

- `NOT_VERIFIED`: Default state; no verification performed
- `VERIFIED`: Task output passed verification checks
- `FAILED`: Task output failed verification checks

### 2. Verification Events

Two new event types are recognized by the replay service:

#### `task.verified`

Emitted when task output passes verification checks.

**Payload**:

```python
{
    "attempt_id": str,  # Which attempt was verified
    "verification_type": str,  # e.g., "schema", "tests", "lint", "manual"
    "reason": str | None,  # Optional explanation
}
```

#### `task.verification_failed`

Emitted when task output fails verification checks.

**Payload**:

```python
{
    "attempt_id": str,  # Which attempt failed verification
    "verification_type": str,  # e.g., "schema", "tests", "lint"
    "reason": str | None,  # Optional explanation of failure
}
```

### 3. Replay Service Updates

**File**: `src/openchronicle/core/application/use_cases/replay_project.py`

Extended to:

- Process `task.verified` and `task.verification_failed` events
- Track verification status per task attempt
- Derive verification state deterministically from event stream
- Support multiple verification events per attempt (latest wins)

### 4. Task Attempt Model

**File**: `src/openchronicle/core/application/replay/project_state.py`

Extended `TaskAttempt` dataclass with:

- `verification_status: VerificationStatus` field (defaults to NOT_VERIFIED)
- `to_dict()` method includes verification_status for output

## Design Principles

### 1. Explicit, Event-Driven

Verification is **never implicit**. The system does not automatically verify anything. Verification status changes only through explicit events.

### 2. Orthogonal to Execution

- A completed task can have failed verification (e.g., code compiles but tests fail)
- A failed task can be verified (e.g., error handling worked correctly)
- Execution status and verification status are independent dimensions

### 3. Deterministic Replay

Verification state is derived purely from the event stream:

- Same events → same verification state
- No hidden state or side effects
- Multiple replays produce identical results

### 4. Per-Attempt Tracking

Each task attempt has independent verification status:

- First attempt: completed, verification failed
- Second attempt: completed, verified
- Replay shows latest attempt's verification status

### 5. Latest Event Wins

For a given attempt, the most recent verification event determines status:

- Multiple verification checks can run on same attempt
- Later verification events override earlier ones
- Supports iterative verification workflows

## Usage Examples

### Example 1: Schema Validation

```python
# Task completes
event = Event(
    task_id=task.id,
    type="task.completed",
    payload={"attempt_id": "attempt-1"}
)

# Verify output against schema
event = Event(
    task_id=task.id,
    type="task.verified",
    payload={
        "attempt_id": "attempt-1",
        "verification_type": "schema",
        "reason": "Output matches expected JSON schema"
    }
)
```

### Example 2: Test Failure

```python
# Task completes (code generated)
event = Event(
    task_id=task.id,
    type="task.completed",
    payload={"attempt_id": "attempt-1"}
)

# Run tests on generated code
event = Event(
    task_id=task.id,
    type="task.verification_failed",
    payload={
        "attempt_id": "attempt-1",
        "verification_type": "tests",
        "reason": "3 of 10 unit tests failed"
    }
)
```

### Example 3: Error Handling Verification

```python
# Task fails (as expected)
event = Event(
    task_id=task.id,
    type="task.failed",
    payload={"attempt_id": "attempt-1", "error": "Invalid input"}
)

# Verify error handling is correct
event = Event(
    task_id=task.id,
    type="task.verified",
    payload={
        "attempt_id": "attempt-1",
        "verification_type": "error_handling",
        "reason": "Failed with correct error code and message"
    }
)
```

## Testing

Comprehensive test suite in `tests/test_verification_semantics.py` covering:

- Default NOT_VERIFIED status for all tasks
- Event-driven status updates (verified/failed)
- Orthogonality (execution vs verification independence)
- Deterministic replay across multiple runs
- Per-attempt verification tracking
- Latest-event-wins behavior

**Test Results**: 9/9 tests pass ✅
**Full Suite**: 237/237 tests pass ✅
**Type Checking**: No errors ✅

## Non-Changes

As specified, this implementation:

- ❌ Does NOT add actual verification logic (no pytest, no linting)
- ❌ Does NOT automatically re-run tasks based on verification
- ❌ Does NOT modify routing, budget, retry, or resume semantics
- ❌ Does NOT touch v1.reference
- ❌ Does NOT add sandboxing or command execution
- ✅ Only adds semantic foundation for future verification tools

## Future Work

This foundation enables future batches to add:

1. Verification adapters (pytest, ruff, schema validators)
2. Automatic verification after task completion
3. Retry-on-verification-failure policies
4. Verification requirements in task definitions
5. Verification dashboards and reporting

All without changing the core semantics established here.
