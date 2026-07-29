"""Compact projection on the shared serializers.

`compact` exists so a caller browsing a listing doesn't pay for content it
won't read. The invariant that matters most: compact must never hand back
a `content` key holding a shortened string. Renaming the key is what makes
the truncation impossible to consume by accident.
"""

from __future__ import annotations

from datetime import UTC, datetime

from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.interfaces.serializers import (
    content_preview,
    memory_to_dict,
    project_to_dict,
)

_FIXED_DT = datetime(2026, 1, 1, tzinfo=UTC)


def _memory(content: str = "remember this") -> MemoryItem:
    return MemoryItem(
        id="mem-1",
        content=content,
        tags=["a", "b"],
        pinned=False,
        project_id="proj-1",
        source="manual",
        created_at=_FIXED_DT,
    )


def _project(metadata: dict[str, object] | None = None) -> Project:
    return Project(
        id="proj-1",
        name="proj",
        metadata={"scope": "x" * 500, "repo": "y"} if metadata is None else metadata,
        created_at=_FIXED_DT,
    )


class TestContentPreview:
    def test_short_text_is_returned_verbatim(self) -> None:
        assert content_preview("short") == "short"

    def test_long_text_is_cut_and_marked(self) -> None:
        result = content_preview("x" * 500)
        assert result == "x" * 120 + "..."

    def test_boundary_length_is_not_marked(self) -> None:
        exact = "x" * 120
        assert content_preview(exact) == exact


class TestMemoryCompact:
    def test_replaces_content_with_preview(self) -> None:
        result = memory_to_dict(_memory("x" * 500), compact=True)
        assert "content" not in result
        assert result["content_preview"] == "x" * 120 + "..."

    def test_reports_content_length(self) -> None:
        result = memory_to_dict(_memory("x" * 500), compact=True)
        assert result["content_length"] == 500

    def test_omits_ellipsis_when_content_is_short(self) -> None:
        result = memory_to_dict(_memory("tiny"), compact=True)
        assert result["content_preview"] == "tiny"
        assert result["content_length"] == 4

    def test_keeps_identifying_fields(self) -> None:
        result = memory_to_dict(_memory(), compact=True)
        assert result["id"] == "mem-1"
        assert result["project_id"] == "proj-1"
        assert result["tags"] == ["a", "b"]
        assert result["source"] == "manual"


class TestProjectCompact:
    def test_replaces_metadata_with_keys_and_size(self) -> None:
        result = project_to_dict(_project(), compact=True)
        assert "metadata" not in result
        assert result["metadata_keys"] == ["repo", "scope"]
        assert result["metadata_size"] > 500

    def test_empty_metadata_is_distinguishable_from_hidden(self) -> None:
        result = project_to_dict(_project({}), compact=True)
        assert result["metadata_keys"] == []
        assert result["metadata_size"] == len("{}")


class TestDefaultShapesAreUnchanged:
    """`compact` is opt-in and must not leak into the default path.

    These pin the exact key sets every existing consumer relies on. If a
    field is added deliberately, update these; if one of them fails after
    an unrelated change, the projection leaked.
    """

    def test_memory_default_keys(self) -> None:
        assert set(memory_to_dict(_memory())) == {
            "id",
            "content",
            "tags",
            "pinned",
            "project_id",
            "source",
            "created_at",
            "updated_at",
        }

    def test_memory_default_content_is_full(self) -> None:
        assert memory_to_dict(_memory("x" * 500))["content"] == "x" * 500

    def test_project_default_keys(self) -> None:
        assert set(project_to_dict(_project())) == {"id", "name", "metadata", "created_at"}

    def test_project_default_metadata_is_full(self) -> None:
        assert project_to_dict(_project())["metadata"]["scope"] == "x" * 500
