from __future__ import annotations

import json
from pathlib import Path

import pytest

from openchronicle.core.application.use_cases import create_conversation
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.interfaces.cli import main as cli_main


def _prepare_conversation(db_path: Path) -> str:
    storage = SqliteStore(str(db_path))
    storage.init_schema()
    event_logger = EventLogger(storage)
    conversation = create_conversation.execute(
        storage=storage,
        convo_store=storage,
        emit_event=event_logger.append,
        title="CLI JSON",
    )
    return conversation.id


def _set_cli_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, db_path: Path) -> None:
    monkeypatch.setenv("OC_DB_PATH", str(db_path))
    monkeypatch.setenv("OC_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("OC_PLUGIN_DIR", str(tmp_path / "plugins"))
    monkeypatch.setenv("OC_OUTPUT_DIR", str(tmp_path / "output"))


def _set_stub_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OC_LLM_PROVIDER", "stub")
    monkeypatch.setenv("OC_LLM_FAST_POOL", "")
    monkeypatch.setenv("OC_LLM_QUALITY_POOL", "")
    monkeypatch.setenv("OC_LLM_POOL_NSFW", "")


def test_convo_export_json_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "cli.db"
    convo_id = _prepare_conversation(db_path)
    _set_cli_env(monkeypatch, tmp_path, db_path)

    exit_code = cli_main.main(["convo", "export", convo_id, "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip())
    assert payload["command"] == "convo.export"
    assert payload["ok"] is True
    assert payload["error"] is None
    assert isinstance(payload["result"], dict)
    assert payload["result"].get("conversation", {}).get("id") == convo_id


def test_convo_verify_json_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "cli.db"
    convo_id = _prepare_conversation(db_path)
    _set_cli_env(monkeypatch, tmp_path, db_path)

    exit_code = cli_main.main(["convo", "verify", convo_id, "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip())
    assert payload["command"] == "convo.verify"
    assert payload["ok"] is True
    assert payload["error"] is None
    result = payload["result"]
    assert isinstance(result, dict)
    verification = result.get("verification", {})
    assert set(verification.keys()) == {"ok", "failure_event_id", "expected_hash", "actual_hash"}


def test_cli_json_mode_set_and_get(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "cli.db"
    convo_id = _prepare_conversation(db_path)
    _set_cli_env(monkeypatch, tmp_path, db_path)

    exit_code = cli_main.main(["convo", "mode", convo_id, "--set", "persona", "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip())
    assert payload["command"] == "convo.mode"
    assert payload["ok"] is True
    assert payload["result"]["mode"] == "persona"

    exit_code = cli_main.main(["convo", "mode", convo_id, "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip())
    assert payload["command"] == "convo.mode"
    assert payload["ok"] is True
    assert payload["result"]["mode"] == "persona"


def test_cli_json_ask(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = tmp_path / "cli.db"
    convo_id = _prepare_conversation(db_path)
    _set_cli_env(monkeypatch, tmp_path, db_path)
    _set_stub_llm_env(monkeypatch)

    exit_code = cli_main.main(["convo", "ask", convo_id, "hello", "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip())
    assert payload["command"] == "convo.ask"
    assert payload["ok"] is True
    result = payload["result"]
    assert result["conversation_id"] == convo_id
    assert result["turn_id"]
    assert isinstance(result["assistant_text"], str)
    assert result.get("explain") is None


def test_cli_json_error_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "cli.db"
    _set_cli_env(monkeypatch, tmp_path, db_path)

    exit_code = cli_main.main(["convo", "show", "missing-convo", "--json"])
    assert exit_code == 1

    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip())
    assert payload["command"] == "convo.show"
    assert payload["ok"] is False
    assert payload["result"] is None
    error = payload["error"]
    assert set(error.keys()) == {"error_code", "message", "hint"}
    assert error["error_code"] is None
    assert "Conversation not found" in error["message"]
