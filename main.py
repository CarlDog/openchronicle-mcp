#!/usr/bin/env python3
"""
OpenChronicle - Main Entry Point

Professional Narrative AI Engine with comprehensive CLI and core orchestration.
This entry point routes users to the modern Typer-based CLI while maintaining
backward compatibility and clean architecture separation.

Usage:
    python main.py [CLI_COMMANDS]

Architecture:
    main.py → src/openchronicle/interfaces/cli/main.py → src/openchronicle/ (core business logic)
"""

import subprocess
import sys
from pathlib import Path

from openchronicle_old.shared.logging_system import log_error
from openchronicle_old.shared.logging_system import log_info


def main():
    """Route to the modern CLI interface."""
    # Add the src directory to the path for imports
    src_path = Path(__file__).parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    # Lightweight pre-parser for a quick system test run
    # Usage: python main.py --test [optional args ignored]
    if "--test" in sys.argv:
        # Remove our flag and any unrelated args we don't support here
        # Advanced tests are intentionally excluded (stress/perf/chaos/production)
        log_info(
            "Running OpenChronicle system tests (unit only)…",
            context_tags=["startup", "test"]
        )
        pytest_cmd = [
            sys.executable,
            "-m",
            "pytest",
            "tests/unit",
            "-q",
            "--maxfail=1",
            "--tb=short",
            "-m",
            "not stress and not chaos and not performance and not production and not production_real",
        ]
        try:
            result = subprocess.run(pytest_cmd, check=False)
            return result.returncode
        except (OSError, ValueError) as e:  # subprocess.run(check=False) won't raise CalledProcessError
            log_error(
                f"Failed to run system tests: {e}",
                context_tags=["startup", "test", "error"],
            )
            return 1

    try:
        # Import and run the modern CLI from its new location
        from openchronicle_old.interfaces.cli.main import app

        # Pass all command line arguments to the CLI
        app()

    except ImportError as e:
        log_error(
            f"Error loading OpenChronicle CLI: {e}",
            context_tags=["startup","cli","import_error"],
        )
        log_info(
            "Please ensure all dependencies are installed: pip install -e .",
            context_tags=["startup","cli","hint"],
        )
        return 1
    except (RuntimeError, ValueError, OSError) as e:  # narrowed from broad Exception
        log_error(
            f"Unexpected error: {e}", context_tags=["startup", "cli", "error"]
        )
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log_info("Interrupted by user", context_tags=["shutdown","keyboard_interrupt"])
        sys.exit(0)
