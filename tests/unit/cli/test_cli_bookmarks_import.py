def test_cli_bookmarks_import():
    # Ensure module imports without side effects or errors
    import importlib

    mod = importlib.import_module(
        "src.openchronicle.interfaces.cli.commands.bookmarks"
    )
    assert hasattr(mod, "bookmarks_app")
