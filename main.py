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

import sys
from pathlib import Path


def main():
    """Route to the modern CLI interface."""
    # Add the src directory to the path for imports
    src_path = Path(__file__).parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    try:
        # Import and run the modern CLI from its new location
        from openchronicle.interfaces.cli.main import app
        
        # Pass all command line arguments to the CLI
        app()
        
    except ImportError as e:
        print(f"❌ Error loading OpenChronicle CLI: {e}")
        print("💡 Please ensure all dependencies are installed:")
        print("   pip install -e .")
        return 1
    except Exception as e:
        print(f"� Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
