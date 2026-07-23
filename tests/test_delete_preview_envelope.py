"""Every delete surface announces itself in the same shape.

The preview/confirm envelope is three lines of dict literal per use case —
too little to justify a shared constructor, since the helper would be
barely shorter than its call sites. But the invariant is load-bearing: a
preview that doesn't say `deleted: false` reads as a completed delete to
any caller that doesn't inspect `status`, which is precisely how
mnemosyne-mcp shipped a delete that silently did nothing.

A test enforces this better than a helper would. A helper only protects
code that remembers to call it; this catches a fourth delete surface that
forgets the convention entirely.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest

from openchronicle.core.application.use_cases import (
    delete_memory,
    delete_project,
    delete_projects,
)
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project

Invoker = Callable[[bool], dict[str, Any]]


def _invoke_delete_memory(confirm: bool) -> dict[str, Any]:
    store = MagicMock()
    store.get_memory.return_value = MemoryItem(
        content="remember this",
        tags=["t"],
        pinned=False,
        project_id="proj-1",
        source="manual",
    )
    return delete_memory.execute(store=store, memory_id="mem-1", confirm=confirm)


def _invoke_delete_project(confirm: bool) -> dict[str, Any]:
    store = MagicMock()
    store.get_project.return_value = Project(id="proj-1", name="proj", metadata={})
    store.count_memory.return_value = 3
    store.delete_project.return_value = 3
    return delete_project.execute(
        store=store,
        memory_store=store,
        project_id="proj-1",
        confirm=confirm,
    )


def _invoke_delete_projects(confirm: bool) -> dict[str, Any]:
    store = MagicMock()
    store.get_project.return_value = Project(id="proj-1", name="proj", metadata={})
    store.count_memory.return_value = 3
    store.delete_project.return_value = 3
    return delete_projects.execute(
        store=store,
        memory_store=store,
        project_ids=["proj-1"],
        confirm=confirm,
    )


INVOKERS: list[tuple[str, Invoker]] = [
    ("delete_memory", _invoke_delete_memory),
    ("delete_project", _invoke_delete_project),
    ("delete_projects", _invoke_delete_projects),
]

_USE_CASES = {
    "delete_memory": delete_memory,
    "delete_project": delete_project,
    "delete_projects": delete_projects,
}


@pytest.mark.parametrize(("name", "invoke"), INVOKERS, ids=[n for n, _ in INVOKERS])
class TestDeletePreviewEnvelope:
    def test_preview_announces_that_nothing_was_deleted(self, name: str, invoke: Invoker) -> None:
        result = invoke(False)
        assert result["status"] == "preview"
        assert result["deleted"] is False
        assert result["next_step"].strip(), f"{name} preview must tell the caller what to do next"
        assert "confirm=true" in result["next_step"]

    def test_confirm_announces_that_it_deleted(self, name: str, invoke: Invoker) -> None:
        result = invoke(True)
        assert result["status"] == "ok"
        assert result["deleted"] is True

    def test_confirm_is_required(self, name: str, invoke: Invoker) -> None:
        """Neither use case may reintroduce a `confirm` default.

        A default makes an omission indistinguishable from a deliberate
        preview request, which is the failure this batch exists to remove.
        """
        import inspect

        param = inspect.signature(_USE_CASES[name].execute).parameters["confirm"]
        assert param.default is inspect.Parameter.empty
