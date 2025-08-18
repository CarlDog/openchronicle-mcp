"""Command line interface for the new core."""

from __future__ import annotations

import argparse

from ... import __version__
from ...kernel import bootstrap


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openchronicle-new")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("version", help="Show core version")
    sub.add_parser("health", help="Health check")
    sub.add_parser("plugins", help="List registered plugins")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    bootstrap.create_core()

    if args.command == "version":
        print(__version__)
    elif args.command == "health":
        print("ok")
    elif args.command == "plugins":
        registry = bootstrap.get_plugin_registry()
        ids = registry.list_all()
        if not ids:
            print("(none)")
        else:
            for pid in ids:
                print(pid)
    else:
        parser.print_help()


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
