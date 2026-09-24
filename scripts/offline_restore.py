"""Offline, same-volume staging, activation and rollback of a SQLite snapshot.

Run only as PID 1 of a disposable helper container. `stage` only reads a
verified snapshot and writes the stage directory, so it may run while the
service is up; activation, rollback and stage retirement need every writer
using the named data volume stopped. This module never constructs
CoreContainer: doing so would open and possibly migrate the database before
the swap.
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
from contextlib import closing
from pathlib import Path
from secrets import token_hex
from typing import Any, TypedDict

from openchronicle.core.domain.time_utils import utc_now

_ID = re.compile(r"[a-z0-9][a-z0-9-]{3,63}\Z")
_CANDIDATE = re.compile(r"candidate-[0-9a-f]{24}\.db\Z")
_MARGIN = 16 * 1024 * 1024
# Primary SQLite result codes that mean "this file is not a readable
# database", as opposed to an environmental failure (disk, lock, I/O).
_SQLITE_CORRUPT = 11
_SQLITE_NOTADB = 26
_ARCHIVING_NOTE = (
    "Activation stopped before the main database file was replaced; there is nothing to roll back. "
    "The helper reads the live family only by byte copy, so it is unchanged; raw-old holds a copy. "
    "Start the service, or activate again under a new operation ID."
)


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


def _sqlite_error_name(exc: sqlite3.Error) -> str:
    return str(getattr(exc, "sqlite_errorname", None) or type(exc).__name__)


def _describe(path: Path) -> dict[str, Any]:
    """Assess an old-state copy without requiring it to pass.

    A damaged live store must not block activation (operator decision,
    2026-09-24), so every check and query is recorded separately, and an
    SQLite error from one of them is a verdict rather than a failure.
    """
    info: dict[str, Any] = {"sha256": _sha256(path), "size_bytes": path.stat().st_size}
    checks: dict[str, str] = {}
    with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro&immutable=1", uri=True)) as conn:
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            checks["integrity"] = "ok" if row == ("ok",) else str(row[0] if row else "no result")
        except sqlite3.Error as exc:
            checks["integrity"] = f"raised {_sqlite_error_name(exc)}"
        try:
            violation = conn.execute("PRAGMA foreign_key_check").fetchone()
            checks["foreign_keys"] = "ok" if violation is None else "violations"
        except sqlite3.Error as exc:
            checks["foreign_keys"] = f"raised {_sqlite_error_name(exc)}"
        try:
            schema = int(conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0])
            project_ids = [str(row[0]) for row in conn.execute("SELECT id FROM projects ORDER BY id")]
            memories = int(conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0])
            embeddings = int(conn.execute("SELECT COUNT(*) FROM memory_embeddings").fetchone()[0])
        except sqlite3.Error as exc:
            info["identity_error"] = f"{_sqlite_error_name(exc)}: {exc}"
        else:
            info.update(
                schema_version=schema,
                project_identity_sha256=hashlib.sha256("\n".join(project_ids).encode()).hexdigest(),
                project_count=len(project_ids),
                memory_count=memories,
                embedding_count=embeddings,
            )
    # Rollback may reinstall a faithfully damaged copy, but never something
    # that is not recognisably an OpenChronicle database (for example the
    # empty result of consolidating a zero-length main file).
    identity_ok = "identity_error" not in info and int(info.get("schema_version", 0)) > 0
    info["checks"] = checks
    info["rollback_available"] = identity_ok
    info["verified"] = identity_ok and all(value == "ok" for value in checks.values())
    return info


def _assess_old_state(recovery: Path, raw: Path, db_name: str) -> dict[str, Any]:
    """Consolidate the archived old family into old-consistent.db and assess it.

    SQLite never opens the live files: even a read-only open can create or
    delete sidecars. It opens a disposable copy of raw-old instead, so both
    the live family and the forensic archive stay byte-exact.
    """
    scratch = recovery / "consolidate-source"
    scratch.mkdir(mode=0o700)
    target = recovery / "old-consistent.db"
    try:
        for member in raw.iterdir():
            _copy_durable(member, scratch / member.name)
        try:
            _consolidate(scratch / db_name, target)
        except sqlite3.DatabaseError as exc:
            code = getattr(exc, "sqlite_errorcode", None)
            if code is None or code & 0xFF not in (_SQLITE_CORRUPT, _SQLITE_NOTADB):
                raise
            target.unlink(missing_ok=True)
            return {
                "readable": False,
                "rollback_available": False,
                "verified": False,
                "error": f"{_sqlite_error_name(exc)}: {exc}",
            }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return {"readable": True, **_describe(target)}


def _remove_incoming(db: Path, operation_id: str, candidate_sha256: str) -> str | None:
    """Remove a leftover activation copy that is byte-identical to the candidate."""
    incoming = db.parent / f".incoming-{operation_id}.db"
    if not incoming.exists() and not incoming.is_symlink():
        return None
    if incoming.is_symlink() or not incoming.is_file() or _sha256(incoming) != candidate_sha256:
        return f"left {incoming.name}: it does not match the staged candidate"
    incoming.unlink()
    _fsync_dir(db.parent)
    return f"removed {incoming.name}"


def stage(db: Path, source: Path, expected_sha256: str, *, apply: bool = False) -> dict[str, Any]:
    """Stage a verified snapshot for activation without the MCP tools.

    This is the production staging path while auth stays disabled. The
    expected digest must come from an independent record (the artifact's
    manifest or verify output, or the off-NAS copy's recorded hash). A hash
    computed from the file at staging time would pass for any file,
    including a fresh copy of the live database.
    """
    if not db.is_absolute() or db.name != "openchronicle.db" or not source.is_absolute():
        raise RestoreError("Use absolute paths and the expected openchronicle.db name")
    if re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        raise RestoreError("--expected-sha256 must be 64 lowercase hex characters from an independent record")
    stage_dir = db.parent / ".restore-stage"
    resolved = source.resolve()
    forbidden = {path.resolve() for path in (db, Path(f"{db}-wal"), Path(f"{db}-shm"))}
    for protected in (stage_dir, db.parent / ".recovery"):
        if resolved.is_relative_to(protected.resolve()):
            raise RestoreError("Stage a snapshot, not a file from .restore-stage or .recovery")
    if resolved in forbidden or source.name.startswith((".incoming-", ".rollback-")):
        raise RestoreError("The live database family cannot be staged; stage a verified snapshot")
    info = _inspect(source)
    if info["sha256"] != expected_sha256:
        raise RestoreError("Snapshot digest differs from the independently recorded SHA-256")
    if stage_dir.is_symlink():
        raise RestoreError("Stage directory cannot be a symlink")
    if stage_dir.exists() and any(stage_dir.glob("*.db")):
        raise RestoreError("A restore candidate is already staged; activate it or retire it first")
    if shutil.disk_usage(db.parent).free < source.stat().st_size + _MARGIN:
        raise RestoreError("Insufficient space to stage the snapshot")
    if not apply:
        return {"action": "stage", "applied": False, "source": str(source), "candidate": info}
    stage_dir.mkdir(mode=0o700, exist_ok=True)
    name = f"candidate-{token_hex(12)}"
    temp = stage_dir / f"{name}.tmp"
    final = stage_dir / f"{name}.db"
    try:
        _copy_durable(source, temp)
        if _sha256(temp) != expected_sha256:
            raise RestoreError("Staged copy differs from the verified snapshot")
        os.replace(temp, final)
        _fsync_dir(stage_dir)
    finally:
        temp.unlink(missing_ok=True)
    staged = _inspect(final)
    if staged != info:
        final.unlink(missing_ok=True)
        raise RestoreError("Staged candidate failed re-verification")
    return {"action": "stage", "applied": True, "stage_path": str(final), "candidate": staged}


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
    # raw-old, its disposable consolidation copy and old-consistent coexist.
    needed = 4 * old_size + 2 * candidate.stat().st_size + _MARGIN
    if shutil.disk_usage(db.parent).free < needed:
        raise RestoreError("Insufficient space for raw and consolidated rollback copies plus incoming candidate")
    if not apply:
        return {
            "action": "activate",
            "applied": False,
            "recovery_dir": str(recovery),
            "candidate": candidate_info,
            "old_state": "assessed during apply; a damaged old state does not block activation",
        }

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

        state["old_state"] = _assess_old_state(recovery, raw, db.name)
        _save_state(recovery, state)
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
    phase = state.get("phase")
    candidate_sha = str((state.get("candidate_info") or {}).get("sha256", ""))
    if phase == "archiving":
        if not apply:
            return {"action": "rollback", "applied": False, "phase": phase, "note": _ARCHIVING_NOTE}
        cleanup = _remove_incoming(db, operation_id, candidate_sha)
        state["phase"] = "abandoned"
        _save_state(recovery, state)
        return {
            "action": "rollback",
            "applied": True,
            "phase": "abandoned",
            "note": _ARCHIVING_NOTE,
            "cleanup": cleanup,
        }
    if phase not in ("prepared", "activated", "rolling_back"):
        raise RestoreError(f"Nothing to roll back in phase {phase!r}")
    old_state = state.get("old_state")
    if not isinstance(old_state, dict) or not old_state.get("rollback_available"):
        raise RestoreError(
            "The old state was not a readable OpenChronicle database, so there is no automated rollback target. "
            "It is preserved byte-exact in raw-old. To leave this state, activate another verified artifact "
            "under a new operation ID."
        )
    old = recovery / "old-consistent.db"
    _regular(old)
    old_digest = str(old_state["sha256"])
    if _sha256(old) != old_digest:
        raise RestoreError("Consolidated rollback snapshot differs from its recorded identity")
    if not apply:
        return {"action": "rollback", "applied": False, "recovery_dir": str(recovery), "old": old_state}

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
        if current_digest not in (recorded.get(db.name), old_digest):
            raise RestoreError("Current database changed during rollback; keep the service stopped")
        for sidecar in (Path(f"{db}-wal"), Path(f"{db}-shm")):
            displaced = forward / f"displaced-{sidecar.name}"
            expected_sidecar = recorded.get(sidecar.name)
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
    if _sha256(incoming) != old_digest:
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
    cleanup = _remove_incoming(db, operation_id, candidate_sha)
    return {"action": "rollback", "applied": True, "recovery_dir": str(recovery), "state": state, "cleanup": cleanup}


def retire_stage(db: Path, operation_id: str, *, apply: bool = False) -> dict[str, Any]:
    """Release a verified staged file only after activation or rollback."""
    recovery = _recovery_dir(db, operation_id)
    state = _load_state(recovery)
    if state.get("db") != str(db) or state.get("operation_id") != operation_id:
        raise RestoreError("Recovery state belongs to a different database or operation")
    if state.get("phase") not in ("activated", "rolled_back", "abandoned"):
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
    cleanup = _remove_incoming(db, operation_id, str(recorded["sha256"]))
    return {"action": "retire-stage", "applied": True, "stage_retired": True, "cleanup": cleanup}


def _require_helper() -> None:
    if os.environ.get("OC_OFFLINE_RESTORE") != "1":
        raise RestoreError("Set OC_OFFLINE_RESTORE=1 only in the stopped-volume helper container")
    if sys.platform == "linux" and b"offline_restore.py" not in Path("/proc/1/cmdline").read_bytes():
        raise RestoreError("Run as PID 1 of a disposable helper, not docker exec in the live service")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("stage", "activate", "rollback", "retire-stage", "status"))
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--operation-id")
    parser.add_argument("--source", type=Path, help="stage: absolute path of a verified snapshot")
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
        if args.action == "stage":
            if args.source is None or not args.expected_sha256:
                raise RestoreError("Staging requires --source and --expected-sha256 from an independent record")
            result = stage(args.db, args.source, args.expected_sha256, apply=args.apply)
            print(json.dumps(result, sort_keys=True))
            return 0
        if not args.operation_id:
            raise RestoreError(f"{args.action} requires --operation-id")
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
        payload: dict[str, Any] = {"error": str(exc)}
        if args.action != "stage":  # staging never touches the live family
            payload["service_must_remain_stopped"] = True
        print(json.dumps(payload), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
