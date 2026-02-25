from __future__ import annotations

from openchronicle.core.domain.models.project import Event
from openchronicle.core.domain.ports.storage_port import StoragePort
from openchronicle.core.domain.time_utils import utc_now


class EventLogger:
    def __init__(self, storage: StoragePort) -> None:
        self.storage = storage

    def append(self, event: Event) -> None:
        with self.storage.transaction():
            existing = self.storage.list_events(task_id=event.task_id) if event.task_id else []
            if existing:
                event.prev_hash = existing[-1].hash
            # Refresh timestamp under lock so created_at ordering matches
            # the serialization order (prevents out-of-order chain links
            # when events are constructed before the lock is acquired).
            event.created_at = utc_now()
            event.compute_hash()
            self.storage.append_event(event)
