"""CLI entry point for OpenChronicle.

Lightweight wrapper that exposes a stable `main()` for console_scripts.
Avoids importing heavy subsystems at import-time.
"""

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

    # Placeholder: provide a minimal helpful message for now
    print(
        "OpenChronicle CLI is installed. Use your project scripts or run 'python -m openchronicle'."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
