import pytest
from typer.testing import CliRunner

from openchronicle.interfaces.cli.main import app


runner = CliRunner()


def test_bookmarks_help():
    result = runner.invoke(app, ["bookmarks", "--help"])
    assert result.exit_code == 0
    assert "Manage story bookmarks" in result.stdout
    assert "list" in result.stdout and "add" in result.stdout


def test_bookmarks_list_empty(tmp_path):
    # Use a unique story id so the in-memory persistence is isolated
    story_id = "cli-story-empty"
    result = runner.invoke(app, ["bookmarks", "list", story_id])
    # Should not crash; exit code 0 and show warning text
    assert result.exit_code == 0
    assert "No bookmarks" in result.stdout


def test_bookmarks_add_and_list(tmp_path):
    story_id = "cli-story-add"
    # Add bookmark
    add_result = runner.invoke(app, ["bookmarks", "add", story_id, "scene-1", "-d", "from-cli-test"])
    assert add_result.exit_code == 0
    # List and check
    list_result = runner.invoke(app, ["bookmarks", "list", story_id])
    assert list_result.exit_code == 0
    # It should display the description
    assert "from-cli-test" in list_result.stdout
