"""
OpenChronicle Test Suite - Unified Test Runner

Professional test execution system providing comprehensive testing capabilities
with discovery, filtering, performance monitoring, and detailed reporting.

Usage:
    python tests/main.py                    # Run all tests
    python tests/main.py unit              # Run only unit tests
    python tests/main.py integration       # Run only integration tests
    python tests/main.py performance       # Run only performance tests
    python tests/main.py stress            # Run only stress tests
    python tests/main.py --module memory   # Run specific module tests
    python tests/main.py --verbose         # Detailed output
    python tests/main.py --coverage        # Include coverage report
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import pytest

    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False
    print("Warning: pytest not available. Install with: pip install pytest")

try:
    import coverage

    COVERAGE_AVAILABLE = True
except ImportError:
    COVERAGE_AVAILABLE = False


class TestRunner:
    """Professional test runner for OpenChronicle test suite."""

    def __init__(self):
        self.test_dir = Path(__file__).parent
        self.project_root = self.test_dir.parent

    def discover_tests(
        self, test_type: str | None = None, module: str | None = None
    ) -> list[str]:
        """Discover test files based on criteria."""
        test_files = []

        if module:
            # Search for tests in module directory or with module name
            patterns = [
                f"tests/unit/{module}/**/*.py",
                f"tests/integration/*{module}*.py",
                f"tests/performance/*{module}*.py",
                f"tests/**/*{module}*.py",
            ]
            for pattern in patterns:
                for test_file in self.project_root.glob(pattern):
                    if test_file.name.startswith("test_") and test_file.suffix == ".py":
                        rel_path = str(test_file.relative_to(self.project_root))
                        if rel_path not in test_files:
                            test_files.append(rel_path)
        else:
            if test_type == "unit":
                pattern = "tests/unit/**/*.py"
            elif test_type == "integration":
                pattern = "tests/integration/**/*.py"
            elif test_type == "performance":
                pattern = "tests/performance/**/*.py"
            elif test_type == "stress":
                pattern = "tests/stress/**/*.py"
            else:
                pattern = "tests/**/*.py"

            for test_file in self.project_root.glob(pattern):
                if test_file.name.startswith("test_") and test_file.suffix == ".py":
                    test_files.append(str(test_file.relative_to(self.project_root)))

        return sorted(test_files)

    def run_tests(
        self,
        test_type: str | None = None,
        module: str | None = None,
        verbose: bool = False,
        coverage: bool = False,
        parallel: bool = False,
    ) -> dict[str, Any]:
        """Run tests with specified options."""

        if not PYTEST_AVAILABLE:
            return {
                "success": False,
                "error": "pytest not available",
                "suggestion": "Install with: pip install pytest pytest-xdist pytest-cov",
            }

        start_time = time.time()

        # Build pytest command
        cmd = ["python", "-m", "pytest"]

        # Add test discovery
        test_files = self.discover_tests(test_type, module)
        if test_files:
            cmd.extend(test_files)
        else:
            cmd.append("tests/")

        # Add options
        if verbose:
            cmd.append("-v")
        else:
            cmd.append("-q")

        if coverage and COVERAGE_AVAILABLE:
            # Correct package path for src layout
            cmd.extend([
                "--cov=src/openchronicle",
                "--cov-report=term-missing",
                "--cov-report=html",
            ])

        if parallel:
            cmd.extend(["-n", "auto"])

        # Add output formatting
        cmd.extend(["--tb=short", "--disable-warnings"])

        try:
            print("🧪 Running OpenChronicle Test Suite")
            print(f"📁 Test Type: {test_type or 'all'}")
            if module:
                print(f"🎯 Module: {module}")
            print(f"📊 Files: {len(test_files)} test files discovered")
            print("=" * 60)

            result = subprocess.run(
                cmd, check=False, capture_output=True, text=True, cwd=self.project_root
            )

            duration = time.time() - start_time

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration": duration,
                "files_tested": len(test_files),
                "command": " ".join(cmd),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "duration": time.time() - start_time,
            }

    def generate_report(self, result: dict[str, Any]):
        """Generate comprehensive test report."""
        print("\n" + "=" * 60)
        print("🏁 TEST EXECUTION COMPLETE")
        print("=" * 60)

        if result["success"]:
            print("✅ Status: PASSED")
        else:
            print("❌ Status: FAILED")

        print(f"⏱️  Duration: {result['duration']:.2f} seconds")
        print(f"📁 Files: {result.get('files_tested', 0)} test files")

        if result.get("stdout"):
            print("\n📋 Test Output:")
            print(result["stdout"])

        if result.get("stderr"):
            print("\n⚠️  Warnings/Errors:")
            print(result["stderr"])

        print("=" * 60)

        return result["success"]


def main():
    """Main test runner entry point."""
    parser = argparse.ArgumentParser(
        description="OpenChronicle Professional Test Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tests/main.py                     # Run all tests
  python tests/main.py unit               # Unit tests only
  python tests/main.py integration        # Integration tests only
  python tests/main.py performance        # Performance tests only
  python tests/main.py --module memory    # Memory module tests
  python tests/main.py --coverage         # With coverage report
  python tests/main.py --parallel         # Parallel execution
        """,
    )

    parser.add_argument(
        "test_type",
        nargs="?",
        choices=["unit", "integration", "performance", "stress", "all"],
        default="all",
        help="Type of tests to run (default: all)",
    )

    parser.add_argument(
        "--module",
        help="Run tests for specific module (e.g., memory, models, narrative)",
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    parser.add_argument(
        "--coverage", "-c", action="store_true", help="Include coverage report"
    )

    parser.add_argument(
        "--parallel", "-p", action="store_true", help="Run tests in parallel"
    )

    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List discovered tests without running",
    )

    args = parser.parse_args()

    runner = TestRunner()

    if args.list:
        tests = runner.discover_tests(args.test_type, args.module)
        print(f"📋 Discovered {len(tests)} test files:")
        for test in tests:
            print(f"  • {test}")
        return 0

    result = runner.run_tests(
        test_type=args.test_type if args.test_type != "all" else None,
        module=args.module,
        verbose=args.verbose,
        coverage=args.coverage,
        parallel=args.parallel,
    )

    success = runner.generate_report(result)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
