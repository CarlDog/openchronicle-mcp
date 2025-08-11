from __future__ import annotations

import argparse
import sys

from openchronicle import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="openchronicle", description="OpenChronicle CLI"
    )
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    parser.add_argument(
        "--legacy-cli",
        action="store_true",
        help="Run legacy CLI entry (may import heavy modules)",
    )
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    if args.legacy_cli:
        # Import lazily so normal version printing doesn't pull heavy deps
        from openchronicle.interfaces.cli.main import main as legacy_main

        return legacy_main([])

    print("OpenChronicle installed. Use '--version' or '--legacy-cli' for the old CLI.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
