class StoryMemoryAdapter:
    """In-memory adapter satisfying MemoryPortContract for tests."""

    def __init__(self, backing_store=None):
        self._mem = {}

    def get_session_memory(self, session_id):
        return self._mem.get(session_id, {"facts": []})

    def save_memory(self, session_id, state):
        self._mem[session_id] = state
        return True
