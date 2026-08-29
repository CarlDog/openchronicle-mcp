"""Import a previously-exported memory JSON envelope into a store.

Modes:
- ``merge`` (default): insert items whose IDs are not already present;
  skip items whose IDs collide. Project rows behave the same way.
- ``replace``: refuse if the destination is non-empty (prevents
  silently overwriting). Caller is expected to back up first and
  start with a fresh store.

``merge`` is a **union by id, not a sync**. There is no update branch, so
a collision keeps the destination's copy and discards the envelope's —
and an item deleted here since the export is simply absent, so it gets
re-inserted. Neither is detectable after the fact (no tombstones, no
per-item version), which is why both counts are returned to the caller
*and* warned about: silence was the failure mode, not the semantics.
Use a fresh DB plus ``mode="replace"`` to restore an envelope exactly.

Git-onboard watermark rows are dropped in **both** modes. ``export_memory``
no longer emits them, but every envelope written before that landed still
carries one, and those are exactly the envelopes a first cross-device
restore uses — so filtering only on the write side would leave the
existing artifacts poisoned.

Embeddings are not part of the export format (see ``export_memory``); run
``oc memory embed`` after import to regenerate them.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from openchronicle.core.application.services.git_onboard import WATERMARK_SOURCE
from openchronicle.core.application.use_cases.export_memory import EXPORT_FORMAT_VERSION
from openchronicle.core.domain.exceptions import ValidationError
from openchronicle.core.domain.models.memory_item import MAX_CONTENT_CHARS, MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort
from openchronicle.core.domain.ports.storage_port import StoragePort
from openchronicle.core.domain.time_utils import utc_now

logger = logging.getLogger(__name__)

VALID_MODES = ("merge", "replace")


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _row_error(collection: str, index: int, row: Any, reason: str) -> ValidationError:
    """Build the one error shape every row rejection uses.

    Names the collection, the zero-based index, and the row's id when one
    is present — enough to find the offending row in a large envelope
    without dumping its content (which may be sensitive) into the message.
    """
    row_id = row.get("id") if isinstance(row, dict) else None
    where = f"{collection}[{index}]" + (f" (id={row_id!r})" if isinstance(row_id, str) else "")
    return ValidationError(f"invalid {where}: {reason}")


def _require_str(collection: str, index: int, row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise _row_error(collection, index, row, f"{key!r} must be a non-empty string, got {type(value).__name__}")
    return value


def _require_dt_str(collection: str, index: int, row: dict[str, Any], key: str, *, optional: bool = False) -> None:
    value = row.get(key)
    if value is None and optional:
        return
    if not isinstance(value, str):
        raise _row_error(collection, index, row, f"{key!r} must be an ISO-8601 string, got {type(value).__name__}")
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise _row_error(collection, index, row, f"{key!r} is not ISO-8601: {exc}") from exc


def _validate_envelope(
    payload: dict[str, Any],
    *,
    existing_project_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate the whole envelope before any write. Returns (projects, memory_items).

    Version dispatch first, then structure, then every row — so a bad
    envelope is rejected with one actionable error naming the failing
    collection/index/id, and the transaction below never opens for it.
    The old shape validated per-row *during* insertion, which cost
    nothing in atomicity (the transaction rolled back) but leaked
    ``KeyError`` for rows missing ``id`` and ``IntegrityError`` for
    unknown project references or duplicate in-envelope ids — raw
    tracebacks on the disaster-recovery path.

    Deliberately NOT validated: id/UUID *shape* (the store accepts any
    string id and a restore must not fail on data it already held — the
    same stance the oversized-content path takes) and unknown extra keys
    (an envelope from a newer build must import into this one).
    """
    version = payload.get("format_version")
    if not isinstance(version, int) or isinstance(version, bool) or version != EXPORT_FORMAT_VERSION:
        raise ValidationError(
            f"unsupported format_version {version!r}; this build reads version {EXPORT_FORMAT_VERSION}",
        )

    for key in ("projects", "memory_items"):
        if key not in payload:
            raise ValidationError(f"payload missing required {key!r} array")
        if not isinstance(payload[key], list):
            raise ValidationError(f"{key!r} must be an array, got {type(payload[key]).__name__}")

    projects: list[dict[str, Any]] = payload["projects"]
    memory_items: list[dict[str, Any]] = payload["memory_items"]

    envelope_project_ids: set[str] = set()
    for i, row in enumerate(projects):
        if not isinstance(row, dict):
            raise _row_error("projects", i, row, f"expected an object, got {type(row).__name__}")
        row_id = _require_str("projects", i, row, "id")
        _require_str("projects", i, row, "name")
        _require_dt_str("projects", i, row, "created_at")
        if row.get("metadata") is not None and not isinstance(row["metadata"], dict):
            raise _row_error("projects", i, row, "'metadata' must be an object or null")
        if row_id in envelope_project_ids:
            raise _row_error("projects", i, row, "duplicate project id within the envelope")
        envelope_project_ids.add(row_id)

    known_project_ids = existing_project_ids | envelope_project_ids
    seen_memory_ids: set[str] = set()
    for i, row in enumerate(memory_items):
        if not isinstance(row, dict):
            raise _row_error("memory_items", i, row, f"expected an object, got {type(row).__name__}")
        row_id = _require_str("memory_items", i, row, "id")
        if not isinstance(row.get("content"), str):
            raise _row_error(
                "memory_items", i, row, f"'content' must be a string, got {type(row.get('content')).__name__}"
            )
        _require_dt_str("memory_items", i, row, "created_at")
        _require_dt_str("memory_items", i, row, "updated_at", optional=True)
        tags = row.get("tags")
        if tags is not None and not (isinstance(tags, list) and all(isinstance(t, str) for t in tags)):
            raise _row_error("memory_items", i, row, "'tags' must be an array of strings or null")
        if row.get("source") is not None and not isinstance(row["source"], str):
            raise _row_error("memory_items", i, row, "'source' must be a string or null")
        project_id = row.get("project_id")
        if project_id is not None and not isinstance(project_id, str):
            raise _row_error("memory_items", i, row, "'project_id' must be a string or null")
        if isinstance(project_id, str) and project_id not in known_project_ids:
            # Caught here rather than left to the FK constraint: the
            # constraint fires as IntegrityError mid-transaction, which
            # nothing translated — the operator got a traceback instead
            # of the row that caused it.
            raise _row_error(
                "memory_items", i, row, f"references project {project_id!r} not in this store or this envelope"
            )
        if row_id in seen_memory_ids:
            raise _row_error("memory_items", i, row, "duplicate memory id within the envelope")
        seen_memory_ids.add(row_id)

    return projects, memory_items


def _aware_exported_at(value: Any) -> datetime | None:
    """Parse an envelope's ``exported_at`` to an aware datetime, or ``None``.

    Anything absent, non-string, unparseable, or naive yields ``None``
    rather than raising: the only consumer is a best-effort warning, and
    a malformed ``exported_at`` must never fail an import. Naive values
    are dropped instead of assumed-UTC — they can only arrive via a
    hand-edited envelope, and guessing the zone would fire or suppress a
    warning on an invention.
    """
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _newest_edit(items: Iterable[MemoryItem]) -> datetime | None:
    """Newest timezone-aware ``updated_at`` across ``items``, if any.

    Deliberately NOT ``max(created_at)``: ``onboard_git`` sets cluster
    ``created_at`` from the commit author date, and a rebased or
    future-dated commit would then make every legitimate envelope read
    as stale forever. ``updated_at`` is a local wall-clock edit marker,
    which is the question being asked. It is ``None`` on an item nobody
    has edited (and ``set_pinned`` does not bump it), so an unedited
    store yields ``None`` and the staleness check is skipped rather than
    guessed. Naive values are excluded for the reason above.
    """
    stamps = [m.updated_at for m in items if m.updated_at is not None and m.updated_at.tzinfo is not None]
    return max(stamps) if stamps else None


def _warn_merge_hazards(
    *,
    payload: dict[str, Any],
    existing_items: list[MemoryItem],
    counts: dict[str, int],
) -> None:
    """Log what a merge silently did. Two independent warnings.

    The first is unconditional because both hazards are real at any
    count: a skip discarded the envelope's copy, and an add may have
    resurrected a local deletion. The second fires only when the
    envelope demonstrably predates local edits.

    Both project and memory counts appear in the first — a project
    collision discards a rename or a metadata edit exactly the way a
    memory collision discards content. The second is memory-only and
    cannot be otherwise: `projects` has no `updated_at` column, so a
    project edit carries no version to compare. It is a signal, not a
    guarantee, which is why it never replaces the unconditional one.
    """
    logger.warning(
        "merge is a union by id, not a sync: an existing row is kept as-is "
        "(any newer copy in the envelope is discarded) and an absent row is inserted "
        "(including anything deleted here since the export). "
        "This import kept %d project(s) + %d memory item(s) and inserted %d project(s) + %d memory item(s). "
        "To restore an envelope exactly, import it into a fresh DB with --mode replace.",
        counts["projects_skipped"],
        counts["memory_skipped"],
        counts["projects_added"],
        counts["memory_added"],
    )

    exported_at = _aware_exported_at(payload.get("exported_at"))
    newest_edit = _newest_edit(existing_items)
    if exported_at is not None and newest_edit is not None and exported_at < newest_edit:
        logger.warning(
            "this envelope was exported %s, which predates this store's newest edit (%s) — "
            "it cannot contain any change made here since then.",
            exported_at.isoformat(),
            newest_edit.isoformat(),
        )


def execute(
    storage: StoragePort,
    memory_store: MemoryStorePort,
    payload: dict[str, Any],
    *,
    mode: str = "merge",
) -> dict[str, int]:
    """Apply ``payload`` to the store. Returns per-kind added/skipped counts.

    The skipped counts are the point, not bookkeeping: without them a
    caller cannot tell "0 added, the envelope was empty" from "0 added,
    every item collided and its envelope copy was discarded" — the exact
    ambiguity that made ``merge``'s union-by-id semantics dangerous.
    ``watermark_dropped`` is tracked separately from ``memory_skipped``
    for the same reason: a dropped watermark is not a collision, and
    inflating the collision count would undo what it exists to report.

    Raises ``ValidationError`` for unknown modes, an unsupported or
    non-integer ``format_version``, a structurally invalid envelope
    (missing/malformed arrays, bad rows, unknown project references,
    duplicate ids), or non-empty destinations in ``replace`` mode. The
    whole envelope is validated before the write transaction opens, so a
    rejection never mutates the store and always names the failing
    collection, index, and row id.
    """
    if mode not in VALID_MODES:
        raise ValidationError(
            f"mode must be one of {VALID_MODES}, got {mode!r}",
        )
    if not isinstance(payload, dict):
        raise ValidationError(f"payload must be a JSON object, got {type(payload).__name__}")

    if mode == "replace":
        existing_projects = storage.list_projects()
        existing_memory = memory_store.list_memory(limit=1)
        if existing_projects or existing_memory:
            raise ValidationError(
                "destination is non-empty; refuse to replace. Start with a fresh DB or use mode='merge'.",
            )

    existing_project_ids = {p.id for p in storage.list_projects()}
    # Held whole (not reduced to an id set) so the staleness warning can
    # read updated_at off the same snapshot rather than re-querying.
    existing_items = memory_store.list_memory(limit=None)
    existing_memory_ids = {m.id for m in existing_items}

    raw_projects, raw_memory_items = _validate_envelope(
        payload,
        existing_project_ids=existing_project_ids,
    )

    projects_added = 0
    projects_skipped = 0
    memory_added = 0
    memory_skipped = 0
    watermark_dropped = 0
    oversized_content = 0
    oversized_ids: list[str] = []

    # One transaction: this is the disaster-recovery path, where a
    # failure mid-loop must roll back everything rather than commit a
    # half-applied import (each insert used to auto-commit). Every row
    # was validated above, so nothing in here is expected to raise on
    # envelope content. utc_now() (not naive datetime.now()) — a naive
    # created_at mixed into aware ones poisons Python-side datetime
    # sorts later.
    with storage.transaction():
        for raw_project in raw_projects:
            if raw_project["id"] in existing_project_ids:
                projects_skipped += 1
                continue
            storage.add_project(
                Project(
                    id=raw_project["id"],
                    name=raw_project["name"],
                    metadata=raw_project.get("metadata") or {},
                    created_at=_parse_dt(raw_project["created_at"]) or utc_now(),
                )
            )
            projects_added += 1

        for raw_memory in raw_memory_items:
            # Never insert another device's git resume point, whatever
            # mode we are in. Export stopped emitting these, but every
            # envelope written before that fix still carries one, and
            # those are exactly the envelopes a first cross-device
            # restore uses. Counted separately: this is not a collision,
            # and folding it into memory_skipped would corrupt the one
            # number a caller relies on to detect discarded edits.
            if raw_memory.get("source") == WATERMARK_SOURCE:
                watermark_dropped += 1
                continue
            if raw_memory["id"] in existing_memory_ids:
                memory_skipped += 1
                continue
            # Import is a RESTORE, not new input, so the content cap is
            # reported rather than enforced: a store can already hold an
            # over-cap row (the CLI accepted them before the cap moved
            # into the use cases), and refusing it here would turn the
            # disaster-recovery path into a failure on data the operator
            # already owns. Counted and warned so it is never silent.
            if len(raw_memory.get("content") or "") > MAX_CONTENT_CHARS:
                oversized_content += 1
                oversized_ids.append(str(raw_memory["id"]))
            memory_store.add_memory(
                MemoryItem(
                    id=raw_memory["id"],
                    content=raw_memory["content"],
                    tags=raw_memory.get("tags") or [],
                    pinned=bool(raw_memory.get("pinned", False)),
                    project_id=raw_memory.get("project_id"),
                    source=raw_memory.get("source") or "import",
                    created_at=_parse_dt(raw_memory["created_at"]) or utc_now(),
                    updated_at=_parse_dt(raw_memory.get("updated_at")),
                )
            )
            memory_added += 1

    counts = {
        "projects_added": projects_added,
        "projects_skipped": projects_skipped,
        "memory_added": memory_added,
        "memory_skipped": memory_skipped,
        "watermark_dropped": watermark_dropped,
        "oversized_content": oversized_content,
    }

    if oversized_content:
        # Accepted deliberately (see the loop), but an operator restoring
        # rows no current surface would let them create should know.
        logger.warning(
            "imported %d memory item(s) whose content exceeds the %d-character cap: %s. "
            "Accepted for round-trip fidelity — a restore must not fail on data the store "
            "already held — but no current surface would accept this content as new input.",
            oversized_content,
            MAX_CONTENT_CHARS,
            ", ".join(oversized_ids[:10]) + (" ..." if len(oversized_ids) > 10 else ""),
        )

    # Warn after the commit, never inside it: a rolled-back import must
    # not leave a log line claiming it did anything.
    if mode == "merge":
        _warn_merge_hazards(payload=payload, existing_items=existing_items, counts=counts)

    return counts
