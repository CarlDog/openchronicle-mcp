"""Cloud backup push (design 0001 Phase 1 and its plan review amendments A1-A9)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from openchronicle.core.application.config.offsite import read_cloud_backup_config
from openchronicle.core.infrastructure.maintenance import jobs

KEYS = "age1primaryxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx,age1recoveryyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"


# --- configuration (shared by the job and health) ---------------------------


@pytest.mark.parametrize(
    "remote",
    [
        ":s3,access_key_id=AKIA,secret_access_key=abc:bucket",  # a connection string carries a credential
        "-ocdrop:nas",  # would read as an rclone flag
        "/plain/path",  # not a named remote
        "ocdrop:path with space",
        "ocdrop:'quoted'",
        "ocdrop:x;rm -rf /",
    ],
)
def test_remote_validator_rejects_unsafe_forms(monkeypatch: pytest.MonkeyPatch, remote: str) -> None:
    monkeypatch.setenv("OC_CLOUD_REMOTE", remote)
    monkeypatch.setenv("OC_CLOUD_AGE_RECIPIENTS", KEYS)
    config = read_cloud_backup_config()
    assert config.enabled and config.problem and "name:path" in config.problem


def test_config_states(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OC_CLOUD_REMOTE", raising=False)
    assert read_cloud_backup_config().enabled is False
    monkeypatch.setenv("OC_CLOUD_REMOTE", "ocdrop:openchronicle/nas")
    monkeypatch.setenv("OC_CLOUD_AGE_RECIPIENTS", " ")
    missing = read_cloud_backup_config()
    assert missing.enabled and missing.problem and "unencrypted" in missing.problem
    monkeypatch.setenv("OC_CLOUD_AGE_RECIPIENTS", KEYS)
    good = read_cloud_backup_config()
    assert good.problem is None and good.remote == "ocdrop:openchronicle/nas" and len(good.recipients) == 2


# --- handler fixtures ---------------------------------------------------------


def _publish(auto: Path, stamp: datetime, *, manifest: bool = True, suffix: str = ".db") -> Path:
    name = f"openchronicle-{stamp.strftime('%Y%m%dT%H%M%S%fZ')}-{stamp.microsecond:012x}"
    db = auto / f"{name}{suffix}"
    db.write_bytes(b"sqlite " + name.encode())
    if manifest and suffix == ".db":
        db.with_suffix(".json").write_text(json.dumps({"sha256": f"sha-{name}"}), encoding="utf-8")
    return db


class Harness:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.root = tmp_path / "exports" / "backups"
        self.auto = self.root / "auto"
        self.auto.mkdir(parents=True)
        self.config_dir = tmp_path / "config"
        self.config_dir.mkdir()
        (self.config_dir / "rclone.conf").write_text("[ocdrop]\ntype = dropbox\n", encoding="utf-8")
        self.verified: list[str] = []
        self.calls: list[tuple[list[str], dict[str, str]]] = []
        self.rclone_saw: list[str] = []
        self.rclone_rc = 0
        self.container = SimpleNamespace(
            backup_dir=self.root,
            paths=SimpleNamespace(config_dir=self.config_dir),
            backups=SimpleNamespace(verify=self._verify),
        )
        monkeypatch.setenv("OC_CLOUD_REMOTE", "ocdrop:openchronicle/nas")
        monkeypatch.setenv("OC_CLOUD_AGE_RECIPIENTS", KEYS)
        monkeypatch.delenv("RCLONE_CONFIG", raising=False)
        monkeypatch.setattr(jobs.os, "geteuid", lambda: 1000, raising=False)
        monkeypatch.setattr(jobs, "_run_captured", self._fake_run)

    def _verify(self, artifact_id: str) -> dict[str, Any]:
        self.verified.append(artifact_id)
        return {"verified": True}

    async def _fake_run(self, argv: list[str], env: dict[str, str]) -> tuple[int, bytes]:
        self.calls.append((argv, env))
        if argv[0] == "age":
            Path(argv[argv.index("-o") + 1]).write_bytes(b"ciphertext")
            return 0, b""
        source = Path(argv[argv.index("--") + 1])
        self.rclone_saw = sorted(p.name for p in source.rglob("*"))
        return self.rclone_rc, b"rclone: NOTICE something went wrong"

    def run(self) -> Any:
        return asyncio.run(jobs.cloud_backup(self.container))  # type: ignore[arg-type]

    def age_calls(self) -> list[list[str]]:
        return [argv for argv, _ in self.calls if argv[0] == "age"]

    def rclone_calls(self) -> list[tuple[list[str], dict[str, str]]]:
        return [(argv, env) for argv, env in self.calls if argv[0] == "rclone"]


@pytest.fixture
def h(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Harness:
    return Harness(tmp_path, monkeypatch)


def _now() -> datetime:
    return datetime.now(UTC)


# --- refusals: raise, never report a success that did not happen -----------------


def test_unconfigured_is_skipped_not_success(h: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OC_CLOUD_REMOTE", raising=False)
    assert h.run() == {"skipped": 1}
    assert h.calls == []


def test_malformed_remote_raises_before_any_subprocess(h: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OC_CLOUD_REMOTE", ":s3,secret_access_key=abc:bucket")
    _publish(h.auto, _now() - timedelta(hours=1))
    with pytest.raises(ValueError, match="name:path"):
        h.run()
    assert h.calls == []


def test_missing_recipients_raise_and_write_nothing(h: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OC_CLOUD_AGE_RECIPIENTS", "")
    _publish(h.auto, _now() - timedelta(hours=1))
    with pytest.raises(ValueError, match="unencrypted"):
        h.run()
    assert h.calls == []
    assert not list(h.root.glob("cloud-push-*"))


def test_refuses_to_run_as_root(h: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jobs.os, "geteuid", lambda: 0, raising=False)
    _publish(h.auto, _now() - timedelta(hours=1))
    with pytest.raises(PermissionError, match="--user 1000:1000"):
        h.run()
    assert h.calls == []


def test_missing_rclone_config_raises(h: Harness) -> None:
    (h.config_dir / "rclone.conf").unlink()
    _publish(h.auto, _now() - timedelta(hours=1))
    with pytest.raises(FileNotFoundError, match="rclone config not found"):
        h.run()


def test_nothing_published_is_a_failure_not_a_success(h: Harness) -> None:
    """A1: an empty source must not stamp success, or health says ok forever."""
    _publish(h.auto, _now() - timedelta(hours=1), manifest=False)  # unpublished
    _publish(h.auto, _now() - timedelta(hours=2), suffix=".db.failed-verify")  # quarantined
    with pytest.raises(RuntimeError, match="no published snapshot"):
        h.run()
    assert h.rclone_calls() == []


def test_stale_newest_snapshot_is_a_failure(h: Harness) -> None:
    """A1: db_backup stopped; re-pushing the same old names must not count."""
    _publish(h.auto, _now() - timedelta(hours=30))
    with pytest.raises(RuntimeError, match="stopped producing"):
        h.run()


def test_future_stamped_snapshot_is_a_failure(h: Harness) -> None:
    """A1: a clock that stepped back would otherwise hide every new snapshot."""
    _publish(h.auto, _now() + timedelta(hours=3))
    with pytest.raises(RuntimeError, match="in the future"):
        h.run()


# --- selection and verification --------------------------------------------------


def test_window_keeps_one_per_recent_day_not_only_the_newest_three(h: Harness) -> None:
    """A2: two same-day snapshots (vacuum night) must not push a whole day out."""
    now = _now()
    day0a = _publish(h.auto, now - timedelta(hours=1))
    day0b = _publish(h.auto, now - timedelta(hours=1, minutes=5))
    day0c = _publish(h.auto, now - timedelta(hours=1, minutes=10))
    day1 = _publish(h.auto, now - timedelta(days=1, hours=1))
    day2 = _publish(h.auto, now - timedelta(days=2, hours=1))
    day3 = _publish(h.auto, now - timedelta(days=3, hours=1))
    h.run()
    pushed = {Path(argv[-1]).name for argv in h.age_calls()}
    expected = {p.name for p in (day0a, day0b, day0c, day1, day2)} | {
        p.with_suffix(".json").name for p in (day0a, day0b, day0c, day1, day2)
    }
    assert pushed == expected
    assert day3.name not in pushed


def test_only_published_auto_snapshots_are_pushed(h: Harness) -> None:
    now = _now()
    good = _publish(h.auto, now - timedelta(hours=1))
    _publish(h.auto, now - timedelta(minutes=30), manifest=False)
    _publish(h.auto, now - timedelta(minutes=20), suffix=".db.failed-quick-check")
    manual = h.root / "manual"
    manual.mkdir()
    _publish(manual, now - timedelta(minutes=10))
    h.run()
    assert {Path(argv[-1]).name for argv in h.age_calls()} == {good.name, good.with_suffix(".json").name}
    assert h.verified == ["auto:" + good.stem.removeprefix("openchronicle-")]


def test_retention_and_push_share_the_published_rule(h: Harness) -> None:
    """One predicate: retention must never prune what the push relies on, or vice versa."""
    now = _now()
    published = _publish(h.auto, now - timedelta(hours=1))
    unpublished = _publish(h.auto, now - timedelta(hours=2), manifest=False)
    assert jobs._is_published(published) and not jobs._is_published(unpublished)
    assert [p for _, p in jobs._published_snapshots(h.auto)] == [published]


def test_a_snapshot_that_fails_verification_is_never_encrypted(h: Harness) -> None:
    _publish(h.auto, _now() - timedelta(hours=1))

    def bad_verify(artifact_id: str) -> dict[str, Any]:
        raise RuntimeError("Backup artifact differs from its manifest")

    h.container.backups = SimpleNamespace(verify=bad_verify)
    with pytest.raises(RuntimeError, match="differs from its manifest"):
        h.run()
    assert h.calls == []


# --- the push itself ----------------------------------------------------------


def test_rclone_argv_is_append_only_and_guarded(h: Harness) -> None:
    _publish(h.auto, _now() - timedelta(hours=1))
    h.run()
    ((argv, env),) = h.rclone_calls()
    assert argv[:2] == ["rclone", "copy"]
    assert "sync" not in argv and all("delete" not in a for a in argv)
    assert "--ignore-existing" in argv and "--ask-password=false" in argv
    # A9: the end-of-options guard sits before both positional arguments.
    guard = argv.index("--")
    assert argv[guard + 2] == "ocdrop:openchronicle/nas/" and len(argv) == guard + 3
    # The config path travels in the environment, never on argv (/proc is readable).
    assert env["RCLONE_CONFIG"] == str(h.config_dir / "rclone.conf")
    assert not any("rclone.conf" in a for a in argv)
    # The cache lives outside the uploaded directory.
    source = Path(argv[guard + 1])
    assert not Path(env["RCLONE_CACHE_DIR"]).is_relative_to(source)


def test_pushes_encrypted_database_and_manifest_only(h: Harness) -> None:
    snap = _publish(h.auto, _now() - timedelta(hours=1))
    assert h.run() == {"selected": 1}
    assert h.rclone_saw == sorted([f"{snap.name}.age", f"{snap.with_suffix('.json').name}.age"])
    for argv in h.age_calls():
        assert argv.count("-r") == 2  # both escrowed recipients, every time


def test_temp_dir_is_removed_on_success_and_on_failure(h: Harness) -> None:
    _publish(h.auto, _now() - timedelta(hours=1))
    h.run()
    assert not list(h.root.glob("cloud-push-*"))
    h.rclone_rc = 7
    with pytest.raises(RuntimeError, match="rclone exited 7: rclone: NOTICE"):
        h.run()
    assert not list(h.root.glob("cloud-push-*"))


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_temp_dir_is_private(h: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    modes: list[int] = []

    async def capture(argv: list[str], env: dict[str, str]) -> tuple[int, bytes]:
        if argv[0] == "rclone":
            modes.append(Path(argv[argv.index("--") + 1]).parent.stat().st_mode & 0o777)
        return await h._fake_run(argv, env)

    monkeypatch.setattr(jobs, "_run_captured", capture)
    _publish(h.auto, _now() - timedelta(hours=1))
    h.run()
    assert modes == [0o700]


def test_stale_push_dirs_are_swept_fresh_ones_kept(h: Harness) -> None:
    stale = h.root / "cloud-push-stale"
    fresh = h.root / "cloud-push-fresh"
    for d in (stale, fresh):
        d.mkdir()
        (d / "x.age").write_bytes(b"c")
    old = time.time() - jobs._CLOUD_TIMEOUT_SECONDS - 60
    os.utime(stale, (old, old))
    jobs._sweep_stale_push_dirs(h.root)
    assert not stale.exists() and fresh.exists()


def test_sweep_never_raises(tmp_path: Path) -> None:
    jobs._sweep_stale_push_dirs(tmp_path / "does-not-exist")


def test_timeout_bounds_the_whole_handler(h: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """The bound is the global lock's only release guarantee: it must cover
    verification and encryption, not just the upload."""
    assert jobs._CLOUD_TIMEOUT_SECONDS == 900.0
    monkeypatch.setattr(jobs, "_CLOUD_TIMEOUT_SECONDS", 0.2)
    _publish(h.auto, _now() - timedelta(hours=1))

    def slow_verify(artifact_id: str) -> dict[str, Any]:
        time.sleep(1.0)
        return {}

    h.container.backups = SimpleNamespace(verify=slow_verify)
    with pytest.raises(TimeoutError):
        h.run()


def test_cancelled_child_is_killed() -> None:
    """The shared finally kills the child; otherwise proc.wait() would block ~30 s."""

    async def go() -> None:
        async with asyncio.timeout(0.5):
            await jobs._run_captured([sys.executable, "-c", "import time; time.sleep(30)"], dict(os.environ))

    started = time.monotonic()
    with pytest.raises(TimeoutError):
        asyncio.run(go())
    assert time.monotonic() - started < 10


# --- health -------------------------------------------------------------------


def _state(db_dir: Path, stamp: datetime | None) -> None:
    raw: dict[str, Any] = {"last_run_at": {}, "last_success_at": {}}
    if stamp is not None:
        raw["last_success_at"]["cloud_backup"] = stamp.isoformat()
        raw["last_run_at"]["cloud_backup"] = stamp.isoformat()
    (db_dir / "maintenance_state.json").write_text(json.dumps(raw), encoding="utf-8")


@pytest.fixture
def db_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    monkeypatch.setenv("OC_DB_PATH", str(d / "db.db"))
    monkeypatch.setenv("OC_CLOUD_AGE_RECIPIENTS", KEYS)
    return d


def _status() -> dict[str, Any]:
    from openchronicle.core.application.use_cases.diagnose_runtime import _cloud_backup_status

    return _cloud_backup_status()


def test_health_disabled(db_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OC_CLOUD_REMOTE", raising=False)
    _state(db_dir, _now())
    assert _status()["status"] == "disabled"


def test_health_enabled_never_pushed_is_stale(db_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OC_CLOUD_REMOTE", "ocdrop:openchronicle/nas")
    assert _status() == {"status": "stale", "last_success_at": None, "hours_since_last_success": None}
    (db_dir / "maintenance_state.json").write_text("{not json", encoding="utf-8")
    assert _status()["status"] == "stale"


def test_health_ok_then_stale_after_48h(db_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OC_CLOUD_REMOTE", "ocdrop:openchronicle/nas")
    _state(db_dir, _now() - timedelta(hours=13))
    ok = _status()
    assert ok["status"] == "ok" and 12.9 <= ok["hours_since_last_success"] <= 13.1
    _state(db_dir, _now() - timedelta(hours=49))
    assert _status()["status"] == "stale"


def test_health_misconfigured_wins_over_ok(db_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A5: a recent success must not hide a remote that was just broken."""
    monkeypatch.setenv("OC_CLOUD_REMOTE", "-broken")
    _state(db_dir, _now() - timedelta(hours=1))
    assert _status()["status"] == "misconfigured"


def test_disabled_runs_never_stamp_success_through_the_loop(
    db_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Enabling the feature must start from 'stale', not an old skipped run's 'ok'."""
    from openchronicle.core.application.services.maintenance_loop import JobState, MaintenanceLoop

    monkeypatch.delenv("OC_CLOUD_REMOTE", raising=False)
    state_path = db_dir / "maintenance_state.json"
    job = JobState(name="cloud_backup", interval_seconds=86400, enabled=True)
    loop = MaintenanceLoop(
        container=SimpleNamespace(),  # type: ignore[arg-type]
        jobs=[job],
        handlers={"cloud_backup": jobs.cloud_backup},
        state_path=state_path,
    )
    asyncio.run(loop.run_once("cloud_backup"))
    assert job.last_success_at is None
    monkeypatch.setenv("OC_CLOUD_REMOTE", "ocdrop:openchronicle/nas")
    assert _status()["status"] == "stale"
