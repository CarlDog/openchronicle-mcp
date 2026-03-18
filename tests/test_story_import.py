"""Tests for storytelling plugin import pipeline."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from plugins.storytelling.importer import import_project

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "storytelling"


@pytest.fixture()
def memory_save_mock() -> MagicMock:
    """Mock memory_save that tracks calls."""
    return MagicMock()


@pytest.fixture()
def sample_project(tmp_path: Path) -> Path:
    """Create a sample project directory with fixture files."""
    # Copy fixture files into tmp_path
    for src in FIXTURES_DIR.iterdir():
        if src.is_file():
            (tmp_path / src.name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


class TestImportProject:
    def test_creates_memory_items(self, sample_project: Path, memory_save_mock: MagicMock) -> None:
        result = import_project(
            source_dir=str(sample_project),
            project_name="TestProject",
            memory_save=memory_save_mock,
        )
        # Should have called memory_save for each parsed entity + 1 project-meta
        assert memory_save_mock.call_count > 0
        assert sum(result.imported.values()) > 0

    def test_tags_correctly(self, sample_project: Path, memory_save_mock: MagicMock) -> None:
        import_project(
            source_dir=str(sample_project),
            project_name="TestProject",
            memory_save=memory_save_mock,
        )
        # All calls should have tags starting with "story"
        for call in memory_save_mock.call_args_list:
            tags = call.kwargs.get("tags", [])
            assert "story" in tags, f"Missing 'story' tag in {tags}"

    def test_does_not_pin_anything(self, sample_project: Path, memory_save_mock: MagicMock) -> None:
        import_project(
            source_dir=str(sample_project),
            project_name="TestProject",
            memory_save=memory_save_mock,
        )
        for call in memory_save_mock.call_args_list:
            pinned = call.kwargs.get("pinned", False)
            assert pinned is False, f"Unexpected pinned=True for content: {call.kwargs.get('content', '')[:50]}"

    def test_dry_run_creates_nothing(self, sample_project: Path, memory_save_mock: MagicMock) -> None:
        result = import_project(
            source_dir=str(sample_project),
            project_name="TestProject",
            memory_save=memory_save_mock,
            dry_run=True,
        )
        assert memory_save_mock.call_count == 0
        # But counts should still be populated
        assert sum(result.imported.values()) > 0

    def test_returns_correct_counts(self, sample_project: Path, memory_save_mock: MagicMock) -> None:
        result = import_project(
            source_dir=str(sample_project),
            project_name="TestProject",
            memory_save=memory_save_mock,
        )
        assert "character" in result.imported
        assert "location" in result.imported
        assert "style-guide" in result.imported
        assert "instructions" in result.imported
        assert "project-meta" in result.imported

    def test_handles_empty_directory(self, tmp_path: Path, memory_save_mock: MagicMock) -> None:
        result = import_project(
            source_dir=str(tmp_path),
            project_name="EmptyProject",
            memory_save=memory_save_mock,
        )
        assert sum(result.imported.values()) == 0
        assert len(result.warnings) > 0

    def test_skips_non_text_files(self, tmp_path: Path, memory_save_mock: MagicMock) -> None:
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n")
        (tmp_path / "notes.txt").write_text("Some notes.", encoding="utf-8")
        result = import_project(
            source_dir=str(tmp_path),
            project_name="TestProject",
            memory_save=memory_save_mock,
        )
        # Only notes.txt should be processed (+ project-meta)
        total = sum(result.imported.values())
        assert total == 2  # notes.txt as worldbuilding + project-meta

    def test_creates_project_meta(self, sample_project: Path, memory_save_mock: MagicMock) -> None:
        result = import_project(
            source_dir=str(sample_project),
            project_name="TestProject",
            memory_save=memory_save_mock,
        )
        assert "project-meta" in result.imported
        assert result.imported["project-meta"] == 1
        # Last call should be project-meta
        last_call = memory_save_mock.call_args_list[-1]
        assert "project-meta" in last_call.kwargs.get("tags", [])
        assert "[Project] TestProject" in last_call.kwargs.get("content", "")

    def test_skips_non_canon_firepit(self, tmp_path: Path, memory_save_mock: MagicMock) -> None:
        (tmp_path / "Non-Canon Firepit.txt").write_text("junk content", encoding="utf-8")
        (tmp_path / "Characters.txt").write_text(
            "Name: Test\nOccupation: Tester\nDescription: A tester.", encoding="utf-8"
        )
        result = import_project(
            source_dir=str(tmp_path),
            project_name="TestProject",
            memory_save=memory_save_mock,
        )
        assert "Non-Canon Firepit.txt" in result.skipped

    def test_raises_on_missing_directory(self, memory_save_mock: MagicMock) -> None:
        with pytest.raises(FileNotFoundError):
            import_project(
                source_dir="/nonexistent/path",
                project_name="TestProject",
                memory_save=memory_save_mock,
            )

    def test_asset_upload_called(self, sample_project: Path, memory_save_mock: MagicMock) -> None:
        asset_mock = MagicMock()
        result = import_project(
            source_dir=str(sample_project),
            project_name="TestProject",
            memory_save=memory_save_mock,
            asset_upload=asset_mock,
        )
        assert asset_mock.call_count > 0
        assert result.assets_uploaded > 0
