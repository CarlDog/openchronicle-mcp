from __future__ import annotations

import argparse
import sys

from openchronicle import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="openchronicle", description="OpenChronicle CLI"
    )
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    # Run modern CLI app directly when no simple flag used
    from openchronicle.interfaces.cli.main import app as cli_app
    cli_app()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
