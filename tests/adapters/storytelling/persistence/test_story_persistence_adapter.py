# 🚫 DO NOT EDIT: guardrail test. Changes require CODEOWNERS approval.

import pytest

from tests.contracts.ports.test_persistence_port_contract import PersistencePortContract


@pytest.mark.contract
class TestStoryPersistenceAdapter(PersistencePortContract):
    def make_port(self):
        try:
            from openchronicle_old.plugins.storytelling.infrastructure.adapters.story_persistence_adapter import (
                StoryPersistenceAdapter,
            )
        except Exception:
            pytest.skip("story_persistence_adapter not present")
        return StoryPersistenceAdapter(backing_store=":memory:")
