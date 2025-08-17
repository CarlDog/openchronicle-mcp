# 🚫 DO NOT EDIT: guardrail test. Changes require CODEOWNERS approval.

import pytest

from tests.contracts.ports.test_content_analysis_port_contract import (
    ContentAnalysisPortContract,
)


@pytest.mark.contract
class TestStoryContentAdapter(ContentAnalysisPortContract):
    def make_port(self):
        try:
            from openchronicle_old.plugins.storytelling.infrastructure.content.adapters.story_content_adapter import (
                StoryContentAdapter,
            )
        except Exception:
            pytest.skip("story_content_adapter not present")
        return StoryContentAdapter(model="dummy")
