"""OpenAI-compatible API stress tests.

Tests the full API request path from HTTP through container to storage,
using the real SqliteStore and FastAPI TestClient.  LLM calls are stubbed
(StubLLMAdapter) — we're testing OC infrastructure, not provider APIs.

Concurrent tests use **per-thread containers** (separate SQLite connections
to the same database file), matching the multi-process concurrency model.
Sequential tests use a single container for throughput and correctness.

Gate: OC_INTEGRATION_TESTS=1
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from openchronicle.core.domain.models.conversation import Conversation
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.domain.services.verification import VerificationService
from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.api.app import create_app
from openchronicle.interfaces.api.config import HTTPConfig

pytestmark = [
    pytest.mark.skipif(
        os.getenv("OC_INTEGRATION_TESTS") != "1",
        reason="Integration tests skipped unless OC_INTEGRATION_TESTS=1",
    ),
    pytest.mark.integration,
]

# Env vars that can interfere with isolated test containers.
_OC_ENV_VARS = [
    "OC_DB_PATH",
    "OC_DATA_DIR",
    "OC_CONFIG_DIR",
    "OC_PLUGIN_DIR",
    "OC_OUTPUT_DIR",
    "OC_ASSETS_DIR",
    "OC_EMBEDDING_PROVIDER",
    "OC_STUB_ERROR_CODE",
    "OC_STUB_TOOL_CALLS",
    "OC_STUB_META_ECHO",
    "OC_LLM_PROVIDER",
    "OC_MEDIA_MODEL",
]


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove OC env vars so containers use only explicit paths."""
    for var in _OC_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture()
def stress_paths(_clean_env: None, tmp_path: Path) -> tuple[str, str, str, str]:
    """Temp directories with minimal stub config.  Schema initialized.

    Returns (db_path, config_dir, plugin_dir, output_dir).
    """
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    models_dir = config_dir / "models"
    models_dir.mkdir()
    (models_dir / "stub.json").write_text(
        json.dumps(
            {
                "provider": "stub",
                "model": "stress-test",
                "enabled": True,
                "display_name": "Stress Test",
            }
        )
    )
    paths = (
        str(tmp_path / "stress.db"),
        str(config_dir),
        str(tmp_path / "plugins"),
        str(tmp_path / "output"),
    )
    # Initialize the schema once.
    c = _make_container(paths)
    c.close()
    return paths


def _make_container(paths: tuple[str, str, str, str]) -> CoreContainer:
    """Create a new CoreContainer with a fresh SQLite connection."""
    db_path, config_dir, plugin_dir, output_dir = paths
    return CoreContainer(
        db_path=db_path,
        config_dir=config_dir,
        plugin_dir=plugin_dir,
        output_dir=output_dir,
        llm=StubLLMAdapter(),
    )


def _make_client(container: CoreContainer) -> TestClient:
    """Create a TestClient bound to a container."""
    return TestClient(create_app(container, HTTPConfig()))


# Convenience fixtures for sequential tests.


@pytest.fixture()
def seq_container(stress_paths: tuple[str, str, str, str]) -> Generator[CoreContainer]:
    """Single container for sequential tests."""
    c = _make_container(stress_paths)
    yield c
    c.close()


@pytest.fixture()
def seq_client(seq_container: CoreContainer) -> TestClient:
    """TestClient for sequential tests."""
    return _make_client(seq_container)


@pytest.fixture()
def project_id(stress_paths: tuple[str, str, str, str]) -> str:
    """Fresh project in the shared database."""
    c = _make_container(stress_paths)
    project = Project(name="stress-project")
    c.storage.add_project(project)
    c.close()
    return project.id


# Helpers


def _post_chat(
    c: TestClient,
    path: str,
    content: str = "hello",
    model: str = "auto",
    stream: bool = False,
) -> Any:
    """POST a chat completion request."""
    return c.post(
        path,
        json={
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "stream": stream,
        },
    )


def _parse_sse(text: str) -> list[dict[str, Any] | str]:
    """Parse SSE text into list of parsed JSON dicts or raw strings."""
    events: list[dict[str, Any] | str] = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or not line.startswith("data: "):
            continue
        payload = line[len("data: ") :]
        if payload == "[DONE]":
            events.append("[DONE]")
        else:
            events.append(json.loads(payload))
    return events


def _count_webui_conversations(store: SqliteStore, pid: str) -> int:
    """Count conversations with mode='webui' for a project."""
    convos = store.list_conversations(project_id=pid)
    return sum(1 for c in convos if c.mode == "webui")


def _get_turns(store: SqliteStore, conversation_id: str) -> list[Any]:
    """Get all turns for a conversation."""
    return store.list_turns(conversation_id)


# ---------------------------------------------------------------------------
# S1: WebUI Session Race — Duplicate Conversation Creation
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason=(
        "Known race: _get_or_create_webui_session has no transaction "
        "protection around the read-then-write pattern. Multi-connection "
        "concurrent first requests can create duplicate webui conversations."
    ),
    strict=False,
)
def test_s1_webui_session_race(
    stress_paths: tuple[str, str, str, str],
    project_id: str,
) -> None:
    """Concurrent first requests can race in _get_or_create_webui_session.

    Each thread uses its own container (separate SQLite connection),
    modeling a multi-process deployment.  Two connections can both
    read no existing webui conversation and both create one.
    """
    n_threads = 10
    containers = [_make_container(stress_paths) for _ in range(n_threads)]
    clients = [_make_client(c) for c in containers]

    barrier = threading.Barrier(n_threads)
    errors: list[Exception] = []
    statuses: list[int] = []
    lock = threading.Lock()

    def _worker(idx: int) -> None:
        barrier.wait()
        try:
            resp = _post_chat(clients[idx], f"/v1/p/{project_id}/chat/completions")
            with lock:
                statuses.append(resp.status_code)
        except Exception as exc:
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    for c in containers:
        c.close()

    assert not errors, f"Thread errors: {errors}"
    assert all(s == 200 for s in statuses), f"Non-200 statuses: {statuses}"

    verify = _make_container(stress_paths)
    webui_count = _count_webui_conversations(verify.storage, project_id)
    verify.close()

    assert webui_count == 1, (
        f"Session race: {webui_count} webui conversations created "
        f"(expected exactly 1). This is the read-then-write race in "
        f"_get_or_create_webui_session."
    )


# ---------------------------------------------------------------------------
# S2: Concurrent Turn Recording — Turn Index Uniqueness
# ---------------------------------------------------------------------------


def test_s2_concurrent_turn_recording(
    stress_paths: tuple[str, str, str, str],
    project_id: str,
) -> None:
    """Multiple concurrent connections must produce unique turn indices."""
    n_threads = 10

    # Pre-create a webui conversation so the session race doesn't interfere.
    setup = _make_container(stress_paths)
    convo = Conversation(project_id=project_id, title="s2-convo", mode="webui")
    setup.storage.add_conversation(convo)
    convo_id = convo.id
    setup.close()

    containers = [_make_container(stress_paths) for _ in range(n_threads)]
    clients = [_make_client(c) for c in containers]

    barrier = threading.Barrier(n_threads)
    errors: list[Exception] = []
    statuses: list[int] = []
    lock = threading.Lock()

    def _worker(idx: int) -> None:
        barrier.wait()
        try:
            resp = _post_chat(
                clients[idx],
                f"/v1/p/{project_id}/chat/completions",
                content=f"turn-{idx}",
            )
            with lock:
                statuses.append(resp.status_code)
        except Exception as exc:
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    for c in containers:
        c.close()

    assert not errors, f"Thread errors: {errors}"
    assert all(s == 200 for s in statuses), f"Non-200 statuses: {statuses}"

    verify = _make_container(stress_paths)
    turns = _get_turns(verify.storage, convo_id)
    verify.close()

    assert len(turns) == n_threads, f"Expected {n_threads} turns, got {len(turns)} (lost turns)"

    indices = [t.turn_index for t in turns]
    assert len(set(indices)) == len(indices), f"Duplicate turn_index values: {indices}"
    # next_turn_index starts at 1 (COALESCE(MAX, 0) + 1).
    assert sorted(indices) == list(
        range(1, n_threads + 1)
    ), f"Turn indices not sequential 1..{n_threads}: {sorted(indices)}"


# ---------------------------------------------------------------------------
# S3: Rapid-Fire Non-Streaming Requests
# ---------------------------------------------------------------------------


def test_s3_rapid_fire_sequential(
    seq_client: TestClient,
    seq_container: CoreContainer,
    project_id: str,
) -> None:
    """50 sequential requests — turn index monotonically increasing, no corruption."""
    n_requests = 50

    convo = Conversation(project_id=project_id, title="s3-convo", mode="webui")
    seq_container.storage.add_conversation(convo)

    for i in range(n_requests):
        resp = _post_chat(
            seq_client,
            f"/v1/p/{project_id}/chat/completions",
            content=f"seq-{i}",
        )
        assert resp.status_code == 200, f"Request {i} failed: {resp.status_code} {resp.text}"

    turns = _get_turns(seq_container.storage, convo.id)
    assert len(turns) == n_requests, f"Expected {n_requests} turns, got {len(turns)}"

    # next_turn_index starts at 1 (COALESCE(MAX, 0) + 1).
    indices = [t.turn_index for t in turns]
    assert indices == list(range(1, n_requests + 1)), f"Turn indices not monotonically increasing: {indices[:10]}..."


# ---------------------------------------------------------------------------
# S4: Streaming Response Turn Recording
# ---------------------------------------------------------------------------


def test_s4_streaming_turn_recording(
    stress_paths: tuple[str, str, str, str],
    project_id: str,
) -> None:
    """Concurrent streaming requests must record complete buffered text."""
    n_threads = 10

    setup = _make_container(stress_paths)
    convo = Conversation(project_id=project_id, title="s4-convo", mode="webui")
    setup.storage.add_conversation(convo)
    convo_id = convo.id
    setup.close()

    containers = [_make_container(stress_paths) for _ in range(n_threads)]
    clients = [_make_client(c) for c in containers]

    barrier = threading.Barrier(n_threads)
    errors: list[Exception] = []
    lock = threading.Lock()

    def _worker(idx: int) -> None:
        barrier.wait()
        try:
            resp = _post_chat(
                clients[idx],
                f"/v1/p/{project_id}/chat/completions",
                content=f"stream word{idx}",
                stream=True,
            )
            assert resp.status_code == 200
            events = _parse_sse(resp.text)
            assert events[-1] == "[DONE]", "Missing [DONE] in stream response"
        except Exception as exc:
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    for c in containers:
        c.close()

    assert not errors, f"Thread errors: {errors}"

    verify = _make_container(stress_paths)
    turns = _get_turns(verify.storage, convo_id)
    verify.close()

    assert len(turns) == n_threads, f"Expected {n_threads} turns, got {len(turns)}"

    # Verify assistant_text is non-empty (buffered from stream).
    for turn in turns:
        assert turn.assistant_text, f"Turn {turn.turn_index} has empty assistant_text"


# ---------------------------------------------------------------------------
# S5: Mixed Streaming + Non-Streaming Concurrent
# ---------------------------------------------------------------------------


def test_s5_mixed_streaming_nonstreaming(
    stress_paths: tuple[str, str, str, str],
    project_id: str,
) -> None:
    """Concurrent mix of streaming and non-streaming requests."""
    n_each = 5
    n_total = n_each * 2

    setup = _make_container(stress_paths)
    convo = Conversation(project_id=project_id, title="s5-convo", mode="webui")
    setup.storage.add_conversation(convo)
    convo_id = convo.id
    setup.close()

    containers = [_make_container(stress_paths) for _ in range(n_total)]
    clients = [_make_client(c) for c in containers]

    barrier = threading.Barrier(n_total)
    errors: list[Exception] = []
    lock = threading.Lock()

    def _worker(idx: int, stream: bool) -> None:
        barrier.wait()
        try:
            resp = _post_chat(
                clients[idx],
                f"/v1/p/{project_id}/chat/completions",
                content=f"mixed-{idx}-{'s' if stream else 'n'}",
                stream=stream,
            )
            assert resp.status_code == 200
        except Exception as exc:
            with lock:
                errors.append(exc)

    threads = []
    for i in range(n_each):
        threads.append(threading.Thread(target=_worker, args=(i, True)))
        threads.append(threading.Thread(target=_worker, args=(n_each + i, False)))

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    for c in containers:
        c.close()

    assert not errors, f"Thread errors: {errors}"

    verify = _make_container(stress_paths)
    turns = _get_turns(verify.storage, convo_id)
    verify.close()

    assert len(turns) == n_total, f"Expected {n_total} turns, got {len(turns)}"


# ---------------------------------------------------------------------------
# S6: Multi-Project Isolation
# ---------------------------------------------------------------------------


def test_s6_multi_project_isolation(
    stress_paths: tuple[str, str, str, str],
) -> None:
    """Concurrent requests across projects must not cross-contaminate."""
    n_projects = 5
    n_requests_per_project = 5
    n_total = n_projects * n_requests_per_project

    setup = _make_container(stress_paths)
    projects: list[tuple[str, str]] = []  # (project_id, convo_id)
    for i in range(n_projects):
        project = Project(name=f"s6-project-{i}")
        setup.storage.add_project(project)
        convo = Conversation(project_id=project.id, title=f"s6-convo-{i}", mode="webui")
        setup.storage.add_conversation(convo)
        projects.append((project.id, convo.id))
    setup.close()

    containers = [_make_container(stress_paths) for _ in range(n_total)]
    clients = [_make_client(c) for c in containers]

    barrier = threading.Barrier(n_total)
    errors: list[Exception] = []
    lock = threading.Lock()

    def _worker(worker_idx: int, proj_idx: int, req_idx: int) -> None:
        barrier.wait()
        pid = projects[proj_idx][0]
        try:
            resp = _post_chat(
                clients[worker_idx],
                f"/v1/p/{pid}/chat/completions",
                content=f"proj-{proj_idx}-req-{req_idx}",
            )
            assert resp.status_code == 200
        except Exception as exc:
            with lock:
                errors.append(exc)

    threads = []
    worker_idx = 0
    for p in range(n_projects):
        for r in range(n_requests_per_project):
            threads.append(threading.Thread(target=_worker, args=(worker_idx, p, r)))
            worker_idx += 1

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    for c in containers:
        c.close()

    assert not errors, f"Thread errors: {errors}"

    verify = _make_container(stress_paths)
    for proj_idx, (pid, cid) in enumerate(projects):
        turns = _get_turns(verify.storage, cid)
        assert (
            len(turns) == n_requests_per_project
        ), f"Project {proj_idx}: expected {n_requests_per_project} turns, got {len(turns)}"
        # Verify no cross-project user_text leakage.
        for turn in turns:
            assert (
                f"proj-{proj_idx}" in turn.user_text
            ), f"Cross-project leakage: turn in project {proj_idx} has user_text '{turn.user_text}'"
    verify.close()


# ---------------------------------------------------------------------------
# S7: Explicit Conversation vs Auto-Session Isolation
# ---------------------------------------------------------------------------


def test_s7_explicit_vs_auto_session_isolation(
    seq_client: TestClient,
    seq_container: CoreContainer,
    project_id: str,
) -> None:
    """Interleaved explicit and auto-session requests land in correct conversations."""
    n_each = 5

    webui_convo = Conversation(project_id=project_id, title="s7-webui", mode="webui")
    seq_container.storage.add_conversation(webui_convo)

    explicit_convo = Conversation(project_id=project_id, title="s7-explicit", mode="general")
    seq_container.storage.add_conversation(explicit_convo)

    # Interleave auto-session and explicit requests.
    for i in range(n_each):
        resp = _post_chat(
            seq_client,
            f"/v1/p/{project_id}/chat/completions",
            content=f"auto-{i}",
        )
        assert resp.status_code == 200

        resp = _post_chat(
            seq_client,
            f"/v1/p/{project_id}/c/{explicit_convo.id}/chat/completions",
            content=f"explicit-{i}",
        )
        assert resp.status_code == 200

    # Auto-session turns land in webui conversation.
    auto_turns = _get_turns(seq_container.storage, webui_convo.id)
    assert len(auto_turns) == n_each, f"Auto-session: expected {n_each} turns, got {len(auto_turns)}"
    for turn in auto_turns:
        assert "auto-" in turn.user_text, f"Auto-session conversation got wrong turn: '{turn.user_text}'"

    # Explicit turns land in explicit conversation.
    explicit_turns = _get_turns(seq_container.storage, explicit_convo.id)
    assert len(explicit_turns) == n_each, f"Explicit: expected {n_each} turns, got {len(explicit_turns)}"
    for turn in explicit_turns:
        assert "explicit-" in turn.user_text, f"Explicit conversation got wrong turn: '{turn.user_text}'"


# ---------------------------------------------------------------------------
# S8: Event Chain Integrity Under Load
# ---------------------------------------------------------------------------


def test_s8_event_chain_integrity(
    stress_paths: tuple[str, str, str, str],
    project_id: str,
) -> None:
    """Event hash chains must remain intact under concurrent multi-connection load."""
    n_threads = 10

    setup = _make_container(stress_paths)
    convo = Conversation(project_id=project_id, title="s8-convo", mode="webui")
    setup.storage.add_conversation(convo)
    convo_id = convo.id
    setup.close()

    containers = [_make_container(stress_paths) for _ in range(n_threads)]
    clients = [_make_client(c) for c in containers]

    barrier = threading.Barrier(n_threads)
    errors: list[Exception] = []
    lock = threading.Lock()

    def _worker(idx: int) -> None:
        barrier.wait()
        try:
            resp = _post_chat(
                clients[idx],
                f"/v1/p/{project_id}/chat/completions",
                content=f"event-{idx}",
            )
            assert resp.status_code == 200
        except Exception as exc:
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    for c in containers:
        c.close()

    assert not errors, f"Thread errors: {errors}"

    # Verify event chain for the conversation's task_id (convo.id).
    verify = _make_container(stress_paths)
    events = verify.storage.list_events(task_id=convo_id)
    if events:
        verifier = VerificationService(verify.storage)
        result = verifier.verify_task_chain(task_id=convo_id)
        verify.close()
        assert (
            result.success
        ), f"Event chain broken: {result.error_message} ({result.verified_events}/{result.total_events} verified)"
    else:
        verify.close()


# ---------------------------------------------------------------------------
# S9: Memory Injection Consistency
# ---------------------------------------------------------------------------


def test_s9_memory_injection_consistency(
    seq_client: TestClient,
    seq_container: CoreContainer,
    project_id: str,
) -> None:
    """Context assembly with pre-seeded memories must not corrupt memory state."""
    n_memories = 20
    n_requests = 10

    convo = Conversation(project_id=project_id, title="s9-convo", mode="webui")
    seq_container.storage.add_conversation(convo)

    # Pre-seed memories.
    for i in range(n_memories):
        mem = MemoryItem(
            content=f"Memory item {i} for stress test context assembly.",
            tags=["stress", f"mem-{i}"],
            project_id=project_id,
        )
        seq_container.storage.add_memory(mem)

    for i in range(n_requests):
        resp = _post_chat(
            seq_client,
            f"/v1/p/{project_id}/chat/completions",
            content=f"recall memory {i}",
        )
        assert resp.status_code == 200, f"Request {i} failed: {resp.status_code}"

    # Verify memory count unchanged (no accidental deletions or duplications).
    # list_memory doesn't filter by project; use search_memory with broad query.
    all_memories = seq_container.storage.search_memory(
        "stress test", top_k=n_memories + 10, project_id=project_id, include_pinned=True
    )
    assert len(all_memories) == n_memories, f"Memory count changed: expected {n_memories}, got {len(all_memories)}"


# ---------------------------------------------------------------------------
# S10: V1 Passthrough vs V2 Persistent
# ---------------------------------------------------------------------------


def test_s10_v1_v2_isolation(
    seq_client: TestClient,
    seq_container: CoreContainer,
    project_id: str,
) -> None:
    """V1 requests must not record turns.  V2 requests must.  No cross-interference."""
    n_each = 5

    convo = Conversation(project_id=project_id, title="s10-convo", mode="webui")
    seq_container.storage.add_conversation(convo)

    # Interleave V1 and V2 requests.
    for i in range(n_each):
        resp = _post_chat(seq_client, "/v1/chat/completions", content=f"v1-{i}")
        assert resp.status_code == 200

        resp = _post_chat(
            seq_client,
            f"/v1/p/{project_id}/chat/completions",
            content=f"v2-{i}",
        )
        assert resp.status_code == 200

    turns = _get_turns(seq_container.storage, convo.id)
    v2_turn_count = sum(1 for t in turns if "v2-" in t.user_text)
    v1_leak = sum(1 for t in turns if "v1-" in t.user_text)

    assert v2_turn_count == n_each, f"Expected {n_each} V2 turns, got {v2_turn_count}"
    assert v1_leak == 0, f"V1 requests leaked {v1_leak} turns into V2 conversation"


# ---------------------------------------------------------------------------
# S11: Invalid Input Flood
# ---------------------------------------------------------------------------


def test_s11_invalid_input_flood(
    seq_client: TestClient,
    seq_container: CoreContainer,
    project_id: str,
) -> None:
    """Error paths must not corrupt state.  Valid requests succeed alongside invalid ones."""

    convo = Conversation(project_id=project_id, title="s11-convo", mode="webui")
    seq_container.storage.add_conversation(convo)

    # Mix of valid and invalid requests.
    cases: list[tuple[str, dict[str, Any], int]] = [
        # Valid
        (
            f"/v1/p/{project_id}/chat/completions",
            {"model": "auto", "messages": [{"role": "user", "content": f"valid-{i}"}]},
            200,
        )
        for i in range(10)
    ]
    cases.extend(
        [
            # Invalid: non-existent project
            (
                "/v1/p/nonexistent-project-id/chat/completions",
                {"model": "auto", "messages": [{"role": "user", "content": "bad-proj"}]},
                404,
            ),
            (
                "/v1/p/another-nonexistent/chat/completions",
                {"model": "auto", "messages": [{"role": "user", "content": "bad-proj"}]},
                404,
            ),
            (
                "/v1/p/yet-another-nonexistent/chat/completions",
                {"model": "auto", "messages": [{"role": "user", "content": "bad-proj"}]},
                404,
            ),
            # Invalid: empty messages
            (
                f"/v1/p/{project_id}/chat/completions",
                {"model": "auto", "messages": []},
                422,
            ),
            (
                f"/v1/p/{project_id}/chat/completions",
                {"model": "auto", "messages": []},
                422,
            ),
            (
                f"/v1/p/{project_id}/chat/completions",
                {"model": "auto", "messages": []},
                422,
            ),
            # Invalid: non-existent conversation
            (
                f"/v1/p/{project_id}/c/nonexistent-convo/chat/completions",
                {"model": "auto", "messages": [{"role": "user", "content": "bad-convo"}]},
                404,
            ),
            (
                f"/v1/p/{project_id}/c/another-nonexistent/chat/completions",
                {"model": "auto", "messages": [{"role": "user", "content": "bad-convo"}]},
                404,
            ),
            # Invalid: bad model format
            (
                f"/v1/p/{project_id}/chat/completions",
                {"model": "badformat", "messages": [{"role": "user", "content": "bad-model"}]},
                404,
            ),
            (
                f"/v1/p/{project_id}/chat/completions",
                {"model": "another-bad", "messages": [{"role": "user", "content": "bad-model"}]},
                404,
            ),
        ]
    )

    for path, body, expected_status in cases:
        resp = seq_client.post(path, json=body)
        assert (
            resp.status_code == expected_status
        ), f"Path={path}, expected {expected_status}, got {resp.status_code}: {resp.text}"

    # Valid requests should have recorded turns; invalid ones should not.
    turns = _get_turns(seq_container.storage, convo.id)
    valid_count = sum(1 for t in turns if "valid-" in t.user_text)
    assert valid_count == 10, f"Expected 10 valid turns, got {valid_count}"

    # Database integrity check.
    integrity = seq_container.storage._conn.execute("PRAGMA integrity_check").fetchone()
    assert integrity[0] == "ok", f"SQLite integrity failed: {integrity[0]}"


# ---------------------------------------------------------------------------
# S12: Conversation Growth — Large Turn History
# ---------------------------------------------------------------------------


def test_s12_conversation_growth(
    seq_client: TestClient,
    seq_container: CoreContainer,
    project_id: str,
) -> None:
    """Correctness and stability as conversation grows to 100 turns."""
    n_turns = 100

    convo = Conversation(project_id=project_id, title="s12-convo", mode="webui")
    seq_container.storage.add_conversation(convo)

    for i in range(n_turns):
        resp = _post_chat(
            seq_client,
            f"/v1/p/{project_id}/chat/completions",
            content=f"growth-{i}",
        )
        assert resp.status_code == 200, f"Turn {i} failed: {resp.status_code}"

    turns = _get_turns(seq_container.storage, convo.id)
    assert len(turns) == n_turns, f"Expected {n_turns} turns, got {len(turns)}"

    # Turn indices must be sequential (starting at 1).
    indices = [t.turn_index for t in turns]
    assert indices == list(range(1, n_turns + 1)), "Turn indices not sequential"

    # The last turn should have user_text containing the last message.
    last_turn = turns[-1]
    assert f"growth-{n_turns - 1}" in last_turn.user_text

    # Context assembly should still work at turn 100.
    resp = _post_chat(
        seq_client,
        f"/v1/p/{project_id}/chat/completions",
        content="final-query-after-growth",
    )
    assert resp.status_code == 200, f"Post-growth request failed: {resp.status_code}"

    # Verify final turn count.
    turns = _get_turns(seq_container.storage, convo.id)
    assert len(turns) == n_turns + 1
