from __future__ import annotations

import io
import json
from pathlib import Path

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.use_cases import create_conversation
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.interfaces.cli import stdio as cli_stdio


def _prepare_conversation(db_path: Path) -> str:
    storage = SqliteStore(str(db_path))
    storage.init_schema()
    event_logger = EventLogger(storage)
    conversation = create_conversation.execute(
        storage=storage,
        convo_store=storage,
        emit_event=event_logger.append,
        title="Serve",
    )
    return conversation.id


def test_serve_stdio_ping_export_shutdown(tmp_path: Path) -> None:
    db_path = tmp_path / "serve.db"
    convo_id = _prepare_conversation(db_path)

    container = CoreContainer(
        db_path=str(db_path),
        config_dir=str(tmp_path / "config"),
        plugin_dir=str(tmp_path / "plugins"),
        output_dir=str(tmp_path / "output"),
    )

    requests = [
        {"command": "system.ping", "args": {}},
        {"command": "convo.export", "args": {"conversation_id": convo_id, "explain": False, "verify": False}},
        {"command": "system.shutdown", "args": {}},
    ]
    input_stream = io.StringIO("\n".join(json.dumps(req) for req in requests) + "\n")
    output_stream = io.StringIO()

    exit_code = cli_stdio.serve_stdio(
        container=container,
        input_stream=input_stream,
        output_stream=output_stream,
    )

    assert exit_code == 0

    lines = [line for line in output_stream.getvalue().splitlines() if line.strip()]
    assert len(lines) == 3

    ping_payload = json.loads(lines[0])
    assert ping_payload["command"] == "system.ping"
    assert ping_payload["ok"] is True
    assert ping_payload["result"] == {"pong": True}

    export_payload = json.loads(lines[1])
    assert export_payload["command"] == "convo.export"
    assert export_payload["ok"] is True
    export_result = export_payload["result"]
    assert export_result["format_version"] == "1"
    assert export_result["conversation"]["id"] == convo_id

    shutdown_payload = json.loads(lines[2])
    assert shutdown_payload["command"] == "system.shutdown"
    assert shutdown_payload["ok"] is True
