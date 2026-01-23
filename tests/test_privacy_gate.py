from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from openchronicle.core.application.use_cases import create_conversation
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.core.infrastructure.privacy.rule_privacy import RulePrivacyGate
from tests.helpers.subprocess_env import build_env, run_oc_module


def test_privacy_gate_detects_email_and_phone() -> None:
    gate = RulePrivacyGate()
    text = "Contact me at user@example.com or +1-415-555-1212."
    redacted, report = gate.analyze_and_apply(
        text=text,
        mode="warn",
        redact_style="mask",
        categories=["email", "phone"],
    )

    assert redacted == text
    assert report.action == "warn"
    assert report.counts == {"email": 1, "phone": 1}
    assert report.categories == ["email", "phone"]


def test_privacy_gate_redacts() -> None:
    gate = RulePrivacyGate()
    text = "Email me at person@example.com."
    redacted, report = gate.analyze_and_apply(
        text=text,
        mode="redact",
        redact_style="mask",
        categories=["email"],
    )

    assert "[REDACTED_EMAIL]" in redacted
    assert report.redactions_applied is True


def _prepare_conversation(db_path: Path) -> str:
    storage = SqliteStore(str(db_path))
    storage.init_schema()
    event_logger = EventLogger(storage)
    conversation = create_conversation.execute(
        storage=storage,
        convo_store=storage,
        emit_event=event_logger.append,
        title="Privacy",
    )
    return conversation.id


def test_privacy_gate_blocks_rpc(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        db_name="privacy.db",
        extra_env={
            "OC_LLM_PROVIDER": "openai",
            "OC_PRIVACY_OUTBOUND_MODE": "block",
            "OC_PRIVACY_OUTBOUND_EXTERNAL_ONLY": "1",
        },
    )
    conversation_id = _prepare_conversation(Path(env["OC_DB_PATH"]))

    request = json.dumps(
        {
            "command": "convo.ask",
            "args": {
                "conversation_id": conversation_id,
                "prompt": "email me at user@example.com",
            },
        }
    )
    result = run_oc_module(["rpc", "--request", request], env=env)
    assert result.returncode == 0

    payload = cast(dict[str, Any], json.loads(result.stdout.strip()))
    assert payload["ok"] is False
    error = cast(dict[str, Any], payload["error"])
    assert error["error_code"] == "OUTBOUND_PII_BLOCKED"
    details = cast(dict[str, Any], error["details"])
    assert details["categories"] == ["email"]
