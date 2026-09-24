"""Offline, same-volume activation and rollback for a staged SQLite snapshot.

Run only as PID 1 of a disposable helper container after every writer using
the named data volume has stopped. This module never constructs CoreContainer:
doing so would open and possibly migrate the database before the swap.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
from pathlib import Path
from secrets import token_hex
from typing import Any, TypedDict

from openchronicle.core.domain.time_utils import utc_now

_ID = re.compile(r"[a-z0-9][a-z0-9-]{3,63}\Z")
_CANDIDATE = re.compile(r"candidate-[0-9a-f]{24}\.db\Z")
_MARGIN = 16 * 1024 * 1024


class RestoreError(RuntimeError):
    """A safety precondition failed; leave the service stopped."""


class BackupInfo(TypedDict):
    sha256: str
    schema_version: int
    project_identity_sha256: str
    project_count: int
    memory_count: int
    embedding_count: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fsync_dir(path: Path) -> None:
    if os.name == "nt":  # Linux is the deployment target; Windows runs tests.
        return
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _regular(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise RestoreError(f"Missing or non-regular file: {path}")


def _inspect(path: Path) -> BackupInfo:
    _regular(path)
    if any(Path(f"{path}{suffix}").exists() for suffix in ("-wal", "-shm")):
        raise RestoreError(f"Expected a standalone SQLite file without sidecars: {path}")
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro&immutable=1", uri=True)
        try:
            if conn.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise RestoreError(f"SQLite integrity_check failed: {path}")
            if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise RestoreError(f"SQLite foreign_key_check failed: {path}")
            schema = int(conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0])
            project_ids = [str(row[0]) for row in conn.execute("SELECT id FROM projects ORDER BY id")]
            memories = int(conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0])
            embeddings = int(conn.execute("SELECT COUNT(*) FROM memory_embeddings").fetchone()[0])
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise RestoreError(f"Cannot inspect OpenChronicle database: {path}") from exc
    return {
        "sha256": _sha256(path),
        "schema_version": schema,
        "project_identity_sha256": hashlib.sha256("\n".join(project_ids).encode()).hexdigest(),
        "project_count": len(project_ids),
        "memory_count": memories,
        "embedding_count": embeddings,
    }


def _copy_durable(source: Path, target: Path) -> None:
    _regular(source)
    with source.open("rb") as src, target.open("xb") as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)
        dst.flush()
        os.fsync(dst.fileno())
    shutil.copymode(source, target)
    with target.open("r+b") as copied:
        os.fsync(copied.fileno())
    _fsync_dir(target.parent)


def _state_path(recovery: Path) -> Path:
    return recovery / "state.json"


def _save_state(recovery: Path, state: dict[str, Any]) -> None:
    path = _state_path(recovery)
    temp = recovery / f"state-{token_hex(8)}.tmp"
    try:
        with temp.open("x", encoding="utf-8") as output:
            json.dump(state, output, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    _fsync_dir(recovery)


def _load_state(recovery: Path) -> dict[str, Any]:
    try:
        state = json.loads(_state_path(recovery).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RestoreError("Recovery state is missing or unreadable") from exc
    if not isinstance(state, dict):
        raise RestoreError("Recovery state is malformed")
    return state


def _family(db: Path) -> list[Path]:
    return [path for path in (db, Path(f"{db}-wal"), Path(f"{db}-shm")) if path.exists() or path.is_symlink()]


def _recovery_dir(db: Path, operation_id: str) -> Path:
    if _ID.fullmatch(operation_id) is None:
        raise RestoreError("Invalid operation ID")
    root = db.parent / ".recovery"
    if root.is_symlink():
        raise RestoreError("Recovery root cannot be a symlink")
    return root / operation_id


def _preflight(db: Path, candidate: Path, expected: dict[str, Any]) -> BackupInfo:
    if not db.is_absolute() or not candidate.is_absolute() or db.name != "openchronicle.db":
        raise RestoreError("Use absolute paths and the expected openchronicle.db name")
    _regular(db)
    if db.parent.is_symlink() or candidate.parent.is_symlink():
        raise RestoreError("Database and stage directories cannot be symlinks")
    if candidate.parent != db.parent / ".restore-stage" or _CANDIDATE.fullmatch(candidate.name) is None:
        raise RestoreError("Candidate must be a generated file in the database's .restore-stage directory")
    _regular(candidate)
    if db.stat().st_dev != candidate.stat().st_dev:
        raise RestoreError("Candidate must be on the database filesystem")
    if any(Path(f"{candidate}{suffix}").exists() for suffix in ("-wal", "-shm")):
        raise RestoreError("Candidate has SQLite sidecars; stage a standalone snapshot")
    actual = _inspect(candidate)
    if (
        actual["sha256"] != expected["sha256"]
        or actual["schema_version"] != expected["schema_version"]
        or actual["project_identity_sha256"] != expected["project_identity_sha256"]
    ):
        raise RestoreError("Candidate hash, schema or project identity differs from expected")
    return actual


def _consolidate(source: Path, target: Path) -> None:
    # mode=ro cannot silently create a new database if the live path is wrong.
    _regular(source)
    origin = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    try:
        destination = sqlite3.connect(target)
        try:
            origin.backup(destination)
        finally:
            destination.close()
    finally:
        origin.close()
    with target.open("r+b") as output:
        os.fsync(output.fileno())
    _fsync_dir(target.parent)


def activate(
    db: Path,
    candidate: Path,
    operation_id: str,
    expected_sha256: str,
    expected_schema: int,
    expected_project_sha256: str,
    *,
    apply: bool = False,
) -> dict[str, Any]:
    """Archive old state, then replace a stopped database with a staged copy."""
    expected = {
        "sha256": expected_sha256,
        "schema_version": expected_schema,
        "project_identity_sha256": expected_project_sha256,
    }
    candidate_info = _preflight(db, candidate, expected)
    recovery = _recovery_dir(db, operation_id)
    if recovery.exists():
        raise RestoreError("Operation ID already has recovery state; inspect or rollback it")
    live_files = _family(db)
    if any(path.is_symlink() or not path.is_file() for path in live_files):
        raise RestoreError("Live database family contains a non-regular file")
    # Include forward-state and the old-state incoming copy needed by rollback.
    # Recheck free space at rollback: serving writes can grow either DB meanwhile.
    old_size = sum(path.stat().st_size for path in live_files)
    needed = 3 * old_size + 2 * candidate.stat().st_size + _MARGIN
    if shutil.disk_usage(db.parent).free < needed:
        raise RestoreError("Insufficient space for raw and consolidated rollback copies plus incoming candidate")
    if not apply:
        return {"action": "activate", "applied": False, "recovery_dir": str(recovery), "candidate": candidate_info}

    recovery.parent.mkdir(mode=0o700, exist_ok=True)
    recovery.mkdir(mode=0o700)
    _fsync_dir(recovery.parent)
    state: dict[str, Any] = {
        "operation_id": operation_id,
        "created_at": utc_now().isoformat(),
        "phase": "archiving",
        "db": str(db),
        "candidate": str(candidate),
        "candidate_info": candidate_info,
        "raw_files": {},
    }
    _save_state(recovery, state)
    try:
        raw = recovery / "raw-old"
        raw.mkdir(mode=0o700)
        for source in live_files:
            target = raw / source.name
            before = _sha256(source)
            _copy_durable(source, target)
            if _sha256(target) != before or _sha256(source) != before:
                raise RestoreError("Live database changed while archiving; keep the service stopped")
            state["raw_files"][source.name] = before
        _save_state(recovery, state)

        old_consistent = recovery / "old-consistent.db"
        _consolidate(db, old_consistent)
        old_info = _inspect(old_consistent)
        state["old_info"] = old_info
        incoming = db.parent / f".incoming-{operation_id}.db"
        _copy_durable(candidate, incoming)
        if _sha256(incoming) != candidate_info["sha256"]:
            raise RestoreError("Incoming copy differs from the staged candidate")
        state["phase"] = "prepared"
        _save_state(recovery, state)

        for sidecar in (Path(f"{db}-wal"), Path(f"{db}-shm")):
            if sidecar.exists():
                os.replace(sidecar, recovery / f"displaced-{sidecar.name}")
        _fsync_dir(recovery)
        _fsync_dir(db.parent)
        os.replace(incoming, db)
        _fsync_dir(db.parent)
        state["phase"] = "activated"
        _save_state(recovery, state)
    except BaseException:
        # Never restart the service after an incomplete phase. The raw family
        # and consolidated old snapshot remain in recovery for rollback.
        raise
    return {"action": "activate", "applied": True, "recovery_dir": str(recovery), "state": state}


def rollback(db: Path, operation_id: str, *, apply: bool = False) -> dict[str, Any]:
    """Restore the verified old-state snapshot after a failed cutover."""
    _regular(db)
    recovery = _recovery_dir(db, operation_id)
    state = _load_state(recovery)
    if state.get("db") != str(db) or state.get("operation_id") != operation_id:
        raise RestoreError("Recovery state belongs to a different database or operation")
    if state.get("phase") not in ("prepared", "activated", "rolling_back"):
        raise RestoreError("No verified old-state snapshot is ready for rollback")
    old = recovery / "old-consistent.db"
    old_info = _inspect(old)
    if old_info != state.get("old_info"):
        raise RestoreError("Consolidated rollback snapshot differs from its recorded identity")
    if not apply:
        return {"action": "rollback", "applied": False, "recovery_dir": str(recovery), "old": old_info}

    forward = recovery / "forward-state"
    if state["phase"] != "rolling_back":
        if forward.exists():
            raise RestoreError("Incomplete forward archive exists; inspect it before retrying rollback")
        live_files = _family(db)
        if any(path.is_symlink() or not path.is_file() for path in live_files):
            raise RestoreError("Current database family contains a non-regular file")
        required = sum(path.stat().st_size for path in live_files) + old.stat().st_size + _MARGIN
        if shutil.disk_usage(db.parent).free < required:
            raise RestoreError("Insufficient space to retain forward state and install rollback copy")
        forward.mkdir(mode=0o700)
        forward_files: dict[str, str] = {}
        for source in live_files:
            _copy_durable(source, forward / source.name)
            digest = _sha256(source)
            if _sha256(forward / source.name) != digest:
                raise RestoreError("Forward archive differs from current database")
            forward_files[source.name] = digest
        state["forward_files"] = forward_files
        state["phase"] = "rolling_back"
        _save_state(recovery, state)
    else:
        if not forward.is_dir() or forward.is_symlink():
            raise RestoreError("Verified forward archive is missing")
        recorded = state.get("forward_files")
        if not isinstance(recorded, dict) or not recorded:
            raise RestoreError("Forward archive has no recorded checksums")
        for name, digest in recorded.items():
            if name not in {db.name, f"{db.name}-wal", f"{db.name}-shm"}:
                raise RestoreError("Forward archive contains an unexpected member")
            archived = forward / name
            _regular(archived)
            if _sha256(archived) != digest:
                raise RestoreError("Forward archive differs from recorded checksum")
        current_digest = _sha256(db)
        old_digest = old_info["sha256"]
        if current_digest not in (recorded.get(db.name), old_digest):
            raise RestoreError("Current database changed during rollback; keep the service stopped")
        for sidecar in (Path(f"{db}-wal"), Path(f"{db}-shm")):
            displaced = forward / f"displaced-{sidecar.name}"
            expected_sidecar = recorded.get(sidecar.name)
            if current_digest == old_digest and sidecar.exists():
                raise RestoreError("Unexpected sidecars appeared after rollback installation")
            if sidecar.is_symlink() or displaced.is_symlink():
                raise RestoreError("Rollback sidecar path cannot be a symlink")
            if expected_sidecar is None:
                if sidecar.exists() or displaced.exists():
                    raise RestoreError("Unexpected sidecar appeared during rollback")
            elif sidecar.exists():
                if displaced.exists() or _sha256(sidecar) != expected_sidecar:
                    raise RestoreError("Current sidecar changed during rollback; keep the service stopped")
            elif not displaced.is_file() or _sha256(displaced) != expected_sidecar:
                raise RestoreError("Displaced sidecar is missing or changed; keep the service stopped")
    incoming = db.parent / f".rollback-{operation_id}.db"
    incoming.unlink(missing_ok=True)
    _copy_durable(old, incoming)
    if _sha256(incoming) != old_info["sha256"]:
        raise RestoreError("Rollback copy differs from archived old state")
    for sidecar in (Path(f"{db}-wal"), Path(f"{db}-shm")):
        if sidecar.exists():
            displaced = forward / f"displaced-{sidecar.name}"
            if displaced.exists():
                raise RestoreError("A sidecar reappeared after being displaced; keep the service stopped")
            os.replace(sidecar, displaced)
    _fsync_dir(forward)
    _fsync_dir(db.parent)
    os.replace(incoming, db)
    _fsync_dir(db.parent)
    state["phase"] = "rolled_back"
    _save_state(recovery, state)
    return {"action": "rollback", "applied": True, "recovery_dir": str(recovery), "state": state}


def retire_stage(db: Path, operation_id: str, *, apply: bool = False) -> dict[str, Any]:
    """Release a verified staged file only after activation or rollback."""
    recovery = _recovery_dir(db, operation_id)
    state = _load_state(recovery)
    if state.get("db") != str(db) or state.get("operation_id") != operation_id:
        raise RestoreError("Recovery state belongs to a different database or operation")
    if state.get("phase") not in ("activated", "rolled_back"):
        raise RestoreError("Cannot retire a stage before activation or rollback completes")
    candidate = Path(str(state.get("candidate", "")))
    if (
        candidate.parent != db.parent / ".restore-stage"
        or candidate.parent.is_symlink()
        or _CANDIDATE.fullmatch(candidate.name) is None
    ):
        raise RestoreError("Recorded staged path is invalid")
    recorded = state.get("candidate_info")
    if not isinstance(recorded, dict) or not isinstance(recorded.get("sha256"), str):
        raise RestoreError("Recorded candidate identity is invalid")
    retirement = state.get("stage_retirement")
    if retirement == "done":
        if candidate.exists():
            raise RestoreError("Retired staged file unexpectedly reappeared")
        return {"action": "retire-stage", "applied": False, "stage_retired": True}
    if retirement not in (None, "in_progress"):
        raise RestoreError("Unrecognized stage retirement state")
    if candidate.exists():
        if _inspect(candidate) != recorded:
            raise RestoreError("Staged candidate changed before retirement")
    elif retirement != "in_progress":
        raise RestoreError("Staged candidate is missing without a recorded retirement")
    if not apply:
        return {"action": "retire-stage", "applied": False, "candidate": str(candidate)}
    state["stage_retirement"] = "in_progress"
    _save_state(recovery, state)
    candidate.unlink(missing_ok=True)
    _fsync_dir(candidate.parent)
    state["stage_retirement"] = "done"
    _save_state(recovery, state)
    return {"action": "retire-stage", "applied": True, "stage_retired": True}


def _require_helper() -> None:
    if os.environ.get("OC_OFFLINE_RESTORE") != "1":
        raise RestoreError("Set OC_OFFLINE_RESTORE=1 only in the stopped-volume helper container")
    if sys.platform == "linux" and b"offline_restore.py" not in Path("/proc/1/cmdline").read_bytes():
        raise RestoreError("Run as PID 1 of a disposable helper, not docker exec in the live service")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("activate", "rollback", "retire-stage", "status"))
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--expected-schema", type=int)
    parser.add_argument("--expected-project-sha256")
    parser.add_argument("--apply", action="store_true", help="Perform the offline file change; omit for dry run")
    args = parser.parse_args(argv)
    try:
        _require_helper()
        if args.db != Path("/data/openchronicle.db"):
            raise RestoreError("Helper commands require --db /data/openchronicle.db")
        if args.action == "activate":
            if not all((args.candidate, args.expected_sha256, args.expected_schema, args.expected_project_sha256)):
                raise RestoreError("Activation requires candidate, digest, schema and project identity")
            result = activate(
                args.db,
                args.candidate,
                args.operation_id,
                args.expected_sha256,
                args.expected_schema,
                args.expected_project_sha256,
                apply=args.apply,
            )
        elif args.action == "rollback":
            result = rollback(args.db, args.operation_id, apply=args.apply)
        elif args.action == "retire-stage":
            result = retire_stage(args.db, args.operation_id, apply=args.apply)
        else:
            if args.apply:
                raise RestoreError("Status is read-only")
            result = {"action": "status", "state": _load_state(_recovery_dir(args.db, args.operation_id))}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, sqlite3.Error, RestoreError) as exc:
        print(json.dumps({"error": str(exc), "service_must_remain_stopped": True}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
