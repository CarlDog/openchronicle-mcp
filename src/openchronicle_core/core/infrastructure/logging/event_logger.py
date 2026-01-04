from __future__ import annotations

from openchronicle_core.core.domain.models.project import Event
from openchronicle_core.core.domain.ports.storage_port import StoragePort


class EventLogger:
    def __init__(self, storage: StoragePort) -> None:
        self.storage = storage

    def append(self, event: Event) -> None:
        existing = self.storage.list_events(event.task_id) if event.task_id else []
        if existing:
            event.prev_hash = existing[-1].hash
        event.compute_hash()
        self.storage.append_event(event)
