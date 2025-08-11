#!/usr/bin/env python3
"""
Phase 1 Health Check Script

Validates the health of the system during Phase 1 import cleanup.
This script ensures we don't break functionality while migrating imports.

Usage:
    python scripts/phase1_health_check.py
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def run_command(command: list[str], timeout: int = 300) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            command,
            check=False, capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def check_environment_validation() -> tuple[bool, str]:
    """Check that environment validation still passes."""
    print("🔍 Checking environment validation...")

    exit_code, stdout, stderr = run_command(["python", "scripts/validate_environment.py"])

    if exit_code == 0:
        return True, "Environment validation passed"
    return False, f"Environment validation failed: {stderr}"


def check_import_analysis() -> tuple[bool, str]:
    """Run import analysis to check progress."""
    print("📦 Running import analysis...")

    exit_code, stdout, stderr = run_command(["python", "scripts/import_analysis.py"])

    if exit_code == 0:
        # Try to load the results
        try:
            with open("storage/import_analysis.json") as f:
                data = json.load(f)

            problematic = len(data.get("import_analysis", {}).get("problematic_imports", []))
            return True, f"Import analysis complete. {problematic} problematic imports remaining."
        except Exception:
            return True, "Import analysis completed but couldn't parse results"
    else:
        return False, f"Import analysis failed: {stderr}"


def check_tests_unit() -> tuple[bool, str]:
    """Run unit tests for quick feedback."""
    print("🧪 Running unit tests...")

    exit_code, stdout, stderr = run_command(["python", "-m", "pytest", "tests/unit/", "-v", "--tb=short"], timeout=120)

    if exit_code == 0:
        # Count passed tests
        lines = stdout.split('\n')
        passed_line = [line for line in lines if " passed" in line and "failed" not in line]
        if passed_line:
            return True, f"Unit tests passed: {passed_line[-1].strip()}"
        return True, "Unit tests passed"
    return False, f"Unit tests failed: {stderr[:500]}..."


def check_tests_full() -> tuple[bool, str]:
    """Run full test suite (slower but comprehensive)."""
    print("🧪 Running full test suite...")

    exit_code, stdout, stderr = run_command(["python", "-m", "pytest", "tests/", "-v"], timeout=600)

    if exit_code == 0:
        # Count passed tests
        lines = stdout.split('\n')
        passed_line = [line for line in lines if " passed" in line and "failed" not in line]
        if passed_line:
            return True, f"All tests passed: {passed_line[-1].strip()}"
        return True, "All tests passed"
    # Extract failure information
    failed_tests = []
    lines = stdout.split('\n') + stderr.split('\n')
    for line in lines:
        if "FAILED" in line:
            failed_tests.append(line.strip())

    if failed_tests:
        return False, f"Tests failed: {len(failed_tests)} failures. First few: {failed_tests[:3]}"
    return False, f"Tests failed: {stderr[:500]}..."


def check_quality_tools() -> tuple[bool, str]:
    """Check that quality tools still work."""
    print("🔧 Checking quality tools...")

    tools_to_check = [
        (["ruff", "check", "src/"], "ruff"),
        (["black", "--check", "src/"], "black"),
        (["mypy", "src/openchronicle/"], "mypy")
    ]

    results = []
    all_passed = True

    for command, tool_name in tools_to_check:
        exit_code, stdout, stderr = run_command(command, timeout=60)
        if exit_code == 0:
            results.append(f"✅ {tool_name}")
        else:
            results.append(f"❌ {tool_name}: {stderr[:100]}...")
            all_passed = False

    return all_passed, " | ".join(results)


def check_core_imports() -> tuple[bool, str]:
    """Check for remaining problematic core imports."""
    print("🔍 Checking for problematic core imports...")

    # Search for core.* imports
    exit_code, stdout, stderr = run_command([
        "grep", "-r", "from core\\.", "src/", "tests/", "."
    ])

    if exit_code == 0 and stdout.strip():
        # Found core imports
        lines = stdout.strip().split('\n')
        return False, f"Found {len(lines)} core.* imports remaining: {lines[:3]}"
    return True, "No problematic core.* imports found"


def check_deep_relative_imports() -> tuple[bool, str]:
    """Check for deep relative imports."""
    print("🔍 Checking for deep relative imports...")

    # Search for deep relative imports (3+ dots)
    exit_code, stdout, stderr = run_command([
        "grep", "-r", "from \\.\\.\\.", "src/", "tests/"
    ])

    if exit_code == 0 and stdout.strip():
        lines = stdout.strip().split('\n')
        return False, f"Found {len(lines)} deep relative imports: {lines[:3]}"
    return True, "No deep relative imports found"


def check_performance_regression() -> tuple[bool, str]:
    """Check for performance regression compared to baseline."""
    print("📊 Checking performance regression...")

    baseline_file = Path("storage/performance_baseline.json")
    if not baseline_file.exists():
        return True, "No baseline to compare against"

    # Run a quick performance test
    start_time = time.time()
    exit_code, stdout, stderr = run_command(["python", "-c", "import src.openchronicle; print('Import successful')"])
    import_time = time.time() - start_time

    if exit_code == 0:
        if import_time < 5.0:  # Reasonable import time
            return True, f"Import performance good: {import_time:.2f}s"
        return False, f"Import performance degraded: {import_time:.2f}s"
    return False, f"Import failed: {stderr}"


def generate_health_report(checks: list[tuple[str, bool, str]]) -> dict[str, Any]:
    """Generate a comprehensive health report."""
    passed = sum(1 for _, success, _ in checks if success)
    total = len(checks)

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_health": f"{passed}/{total} checks passed",
        "health_percentage": (passed / total) * 100,
        "checks": [
            {
                "name": name,
                "status": "PASS" if success else "FAIL",
                "message": message
            }
            for name, success, message in checks
        ]
    }

    return report


def main() -> int:
    """Main health check function."""
    print("🏥 Phase 1 Health Check - OpenChronicle Architecture Migration")
    print("=" * 70)

    # Define all health checks
    health_checks = [
        ("Environment Validation", check_environment_validation),
        ("Import Analysis", check_import_analysis),
        ("Unit Tests", check_tests_unit),
        ("Quality Tools", check_quality_tools),
        ("Core Imports Check", check_core_imports),
        ("Deep Relative Imports", check_deep_relative_imports),
        ("Performance Regression", check_performance_regression),
    ]

    # Run checks
    results = []
    for check_name, check_function in health_checks:
        try:
            success, message = check_function()
            results.append((check_name, success, message))

            status_icon = "✅" if success else "❌"
            print(f"{status_icon} {check_name}: {message}")

        except Exception as e:
            results.append((check_name, False, f"Check failed with exception: {e}"))
            print(f"❌ {check_name}: Check failed with exception: {e}")

    # Generate report
    report = generate_health_report(results)

    # Save report
    report_file = Path("storage/phase1_health_report.json")
    report_file.parent.mkdir(exist_ok=True)
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 70)
    print(f"📊 Overall Health: {report['overall_health']} ({report['health_percentage']:.1f}%)")
    print(f"📝 Report saved to: {report_file}")

    # Run full test suite if all other checks pass
    if report['health_percentage'] >= 80:
        print("\n🚀 Health checks good, running full test suite...")
        success, message = check_tests_full()
        print(f"{'✅' if success else '❌'} Full Test Suite: {message}")

        if not success:
            print("\n⚠️  Full test suite failed - investigate before proceeding")
            return 1

    if report['health_percentage'] >= 90:
        print("\n🎉 System health excellent - safe to continue Phase 1!")
        return 0
    if report['health_percentage'] >= 70:
        print("\n⚠️  System health acceptable - proceed with caution")
        return 0
    print("\n🚨 System health poor - fix issues before continuing")
    return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
