# 🚫 DO NOT EDIT: guardrail test. Changes require CODEOWNERS approval.

import pytest

from tests.contracts.ports.test_memory_port_contract import MemoryPortContract


@pytest.mark.contract
class TestStoryMemoryAdapter(MemoryPortContract):
    def make_port(self):
        try:
            from openchronicle_old.plugins.storytelling.infrastructure.adapters.story_memory_adapter import (
                StoryMemoryAdapter,
            )
        except Exception:
            pytest.skip("story_memory_adapter not present")
        return StoryMemoryAdapter(backing_store=":memory:")
