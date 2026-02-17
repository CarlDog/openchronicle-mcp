"""Tests for Discord session manager (user → conversation mapping)."""

from __future__ import annotations

import json
from pathlib import Path

from openchronicle.interfaces.discord.session import SessionManager


class TestSessionManager:
    def test_get_returns_none_when_no_file(self, tmp_path: Path) -> None:
        sm = SessionManager(str(tmp_path / "sessions.json"))
        assert sm.get_conversation_id("user1") is None

    def test_set_and_get(self, tmp_path: Path) -> None:
        sm = SessionManager(str(tmp_path / "sessions.json"))
        sm.set_conversation_id("user1", "convo-abc")
        assert sm.get_conversation_id("user1") == "convo-abc"

    def test_set_overwrites(self, tmp_path: Path) -> None:
        sm = SessionManager(str(tmp_path / "sessions.json"))
        sm.set_conversation_id("user1", "convo-abc")
        sm.set_conversation_id("user1", "convo-def")
        assert sm.get_conversation_id("user1") == "convo-def"

    def test_clear(self, tmp_path: Path) -> None:
        sm = SessionManager(str(tmp_path / "sessions.json"))
        sm.set_conversation_id("user1", "convo-abc")
        sm.clear("user1")
        assert sm.get_conversation_id("user1") is None

    def test_clear_nonexistent_user(self, tmp_path: Path) -> None:
        sm = SessionManager(str(tmp_path / "sessions.json"))
        sm.clear("user-never-existed")  # should not raise

    def test_multiple_users(self, tmp_path: Path) -> None:
        sm = SessionManager(str(tmp_path / "sessions.json"))
        sm.set_conversation_id("user1", "convo-1")
        sm.set_conversation_id("user2", "convo-2")
        assert sm.get_conversation_id("user1") == "convo-1"
        assert sm.get_conversation_id("user2") == "convo-2"

    def test_persistence_across_instances(self, tmp_path: Path) -> None:
        path = str(tmp_path / "sessions.json")
        sm1 = SessionManager(path)
        sm1.set_conversation_id("user1", "convo-abc")

        sm2 = SessionManager(path)
        assert sm2.get_conversation_id("user1") == "convo-abc"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = str(tmp_path / "nested" / "dir" / "sessions.json")
        sm = SessionManager(path)
        sm.set_conversation_id("user1", "convo-abc")
        assert sm.get_conversation_id("user1") == "convo-abc"

    def test_corrupted_file_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "sessions.json"
        path.write_text("not valid json{{{", encoding="utf-8")
        sm = SessionManager(str(path))
        assert sm.get_conversation_id("user1") is None

    def test_non_dict_file_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "sessions.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        sm = SessionManager(str(path))
        assert sm.get_conversation_id("user1") is None

    def test_json_format(self, tmp_path: Path) -> None:
        path = tmp_path / "sessions.json"
        sm = SessionManager(str(path))
        sm.set_conversation_id("user1", "convo-abc")
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data == {"user1": "convo-abc"}
