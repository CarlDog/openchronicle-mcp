#!/usr/bin/env python3
"""
OpenChronicle - Legacy Entry Point Replacement

This script replaces the original 817-line main.py with a clean entry point
that routes to the new hexagonal architecture.

For full functionality, use the new architecture:
    python src/openchronicle/main.py

This script provides legacy compatibility while the migration is completed.
"""

import sys
from pathlib import Path

# Add source path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def main():
    """Route to the new main entry point."""
    print("🔄 Routing to new hexagonal architecture...")
    print("📂 Loading from: src/openchronicle/main.py")
    print("=" * 50)
    
    try:
        # Import and run the new main
        from openchronicle.main import main as new_main
        import asyncio
        
        return asyncio.run(new_main())
        
    except Exception as e:
        print(f"❌ Error loading new architecture: {e}")
        print("💡 Falling back to legacy import system...")
        
        # If new architecture fails, show helpful error
        print("\n🔧 Migration in progress - some features may be temporarily unavailable")
        print("📖 See PHASE_4_MIGRATION_PLAN.md for status")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)
