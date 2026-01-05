class StoryPersistenceAdapter:
    """In-memory persistence adapter satisfying PersistencePortContract."""

    def __init__(self, backing_store=None):
        self._store = {}
        self._seq = 0

    def create_story(self, doc: dict) -> str:
        self._seq += 1
        sid = f"s{self._seq}"
        self._store[sid] = dict(doc)
        return sid

    def get_story(self, story_id: str) -> dict:
        return dict(self._store.get(story_id, {}))

    def update_story(self, story_id: str, patch: dict):
        if story_id in self._store:
            self._store[story_id].update(patch)
        return True
