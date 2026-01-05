class StoryContentAdapter:
    """Minimal content analysis adapter used by contract tests."""

    def __init__(self, model=None):
        self.model = model or "dummy"

    def analyze_text(self, text: str) -> dict:
        # minimal deterministic structure
        return {"entities": [], "summary": text[:32]}
