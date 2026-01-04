from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Project:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class Agent:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = ""
    role: str = "worker"
    name: str = ""
    provider: str = ""
    model: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = ""
    agent_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)


@dataclass
class Event:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = ""
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)
    prev_hash: str | None = None
    hash: str | None = None

    def compute_hash(self) -> str:
        body = {
            "id": self.id,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "type": self.type,
            "payload": self.payload,
            "created_at": self.created_at.isoformat(),
            "prev_hash": self.prev_hash,
        }
        digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()
        self.hash = digest
        return digest


@dataclass
class Resource:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = ""
    kind: str = ""
    path: str = ""
    content_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)
