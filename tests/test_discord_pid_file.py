"""Tests for Discord bot PID file management."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from openchronicle.interfaces.discord.pid_file import PidFile


@pytest.fixture()
def pid_file(tmp_path: Path) -> PidFile:
    return PidFile(path=str(tmp_path / "bot.pid"))


class TestReadPid:
    def test_returns_none_when_missing(self, pid_file: PidFile) -> None:
        assert pid_file.read_pid() is None

    def test_returns_pid_after_acquire(self, pid_file: PidFile) -> None:
        pid_file.acquire()
        assert pid_file.read_pid() == os.getpid()

    def test_returns_none_on_corrupt_file(self, pid_file: PidFile) -> None:
        Path(pid_file._path).parent.mkdir(parents=True, exist_ok=True)
        Path(pid_file._path).write_text("not-a-number", encoding="utf-8")
        assert pid_file.read_pid() is None


class TestIsAlive:
    def test_false_when_no_file(self, pid_file: PidFile) -> None:
        assert pid_file.is_alive() is False

    def test_true_for_current_process(self, pid_file: PidFile) -> None:
        pid_file.acquire()
        assert pid_file.is_alive() is True

    def test_false_for_nonexistent_pid(self, pid_file: PidFile) -> None:
        # Write a PID that almost certainly doesn't exist.
        Path(pid_file._path).parent.mkdir(parents=True, exist_ok=True)
        Path(pid_file._path).write_text("4999999", encoding="utf-8")
        assert pid_file.is_alive() is False

    def test_false_on_corrupt_file(self, pid_file: PidFile) -> None:
        Path(pid_file._path).parent.mkdir(parents=True, exist_ok=True)
        Path(pid_file._path).write_text("garbage", encoding="utf-8")
        assert pid_file.is_alive() is False


class TestAcquire:
    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b" / "c" / "bot.pid"
        pf = PidFile(path=str(deep))
        pf.acquire()
        assert deep.exists()
        assert int(deep.read_text(encoding="utf-8").strip()) == os.getpid()

    def test_overwrites_stale_pid(self, pid_file: PidFile) -> None:
        Path(pid_file._path).parent.mkdir(parents=True, exist_ok=True)
        Path(pid_file._path).write_text("4999999", encoding="utf-8")
        pid_file.acquire()
        assert pid_file.read_pid() == os.getpid()


class TestRelease:
    def test_removes_file(self, pid_file: PidFile) -> None:
        pid_file.acquire()
        assert Path(pid_file._path).exists()
        pid_file.release()
        assert not Path(pid_file._path).exists()

    def test_idempotent_when_missing(self, pid_file: PidFile) -> None:
        # Should not raise even if file never existed.
        pid_file.release()
        pid_file.release()
