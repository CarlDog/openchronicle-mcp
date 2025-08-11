#!/usr/bin/env python3
"""
Development Environment Validation Script

This script validates that the development environment is properly configured
for OpenChronicle development, including all required tools, dependencies,
and configurations.

Usage:
    python scripts/validate_environment.py
"""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path


def run_command(command: str) -> tuple[bool, str]:
    """Run a shell command and return success status and output."""
    try:
        result = subprocess.run(
            command.split(),
            check=False, capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def check_python_version() -> bool:
    """Check if Python version is 3.11+."""
    version_info = sys.version_info
    if version_info >= (3, 11):
        print(f"✅ Python {version_info.major}.{version_info.minor}.{version_info.micro}")
        return True
    print(f"❌ Python {version_info.major}.{version_info.minor}.{version_info.micro} - Need 3.11+")
    return False


def check_tool_installed(tool_name: str, command: str = None) -> bool:
    """Check if a development tool is installed."""
    command = command or tool_name
    if shutil.which(command):
        # Try to get version if possible
        success, output = run_command(f"{command} --version")
        if success:
            version = output.strip().split('\n')[0]
            print(f"✅ {tool_name}: {version}")
        else:
            print(f"✅ {tool_name}: Installed")
        return True
    print(f"❌ {tool_name}: Not found")
    return False


def check_python_package(package_name: str, import_name: str = None) -> bool:
    """Check if a Python package is installed."""
    import_name = import_name or package_name
    try:
        spec = importlib.util.find_spec(import_name)
        if spec is not None:
            print(f"✅ {package_name}: Installed")
            return True
        print(f"❌ {package_name}: Not found")
        return False
    except Exception:
        print(f"❌ {package_name}: Error checking")
        return False


def check_project_structure() -> bool:
    """Check if project structure is correct."""
    required_paths = [
        "src/openchronicle",
        "src/openchronicle/__init__.py",
        "src/openchronicle/py.typed",
        "tests",
        "pyproject.toml",
        ".pre-commit-config.yaml"
    ]

    all_exist = True
    for path in required_paths:
        path_obj = Path(path)
        if path_obj.exists():
            print(f"✅ {path}: Exists")
        else:
            print(f"❌ {path}: Missing")
            all_exist = False

    return all_exist


def check_git_hooks() -> bool:
    """Check if pre-commit hooks are installed."""
    git_hooks_dir = Path(".git/hooks")
    pre_commit_hook = git_hooks_dir / "pre-commit"

    if pre_commit_hook.exists():
        print("✅ Pre-commit hooks: Installed")
        return True
    print("❌ Pre-commit hooks: Not installed (run 'pre-commit install')")
    return False


def check_quality_tools() -> bool:
    """Check if code quality tools work correctly."""
    tools_and_commands = [
        ("Ruff", "ruff --version"),
        ("Black", "black --version"),
        ("MyPy", "mypy --version"),
        ("Pytest", "pytest --version"),
    ]

    all_working = True
    for tool_name, command in tools_and_commands:
        success, output = run_command(command)
        if success:
            version = output.strip().split('\n')[0]
            print(f"✅ {tool_name}: {version}")
        else:
            print(f"❌ {tool_name}: Not working - {output}")
            all_working = False

    return all_working


def check_development_dependencies() -> bool:
    """Check if development dependencies are installed."""
    dev_packages = [
        ("pytest", "pytest"),
        ("pytest-cov", "pytest_cov"),
        ("ruff", "ruff"),
        ("black", "black"),
        ("mypy", "mypy"),
        ("pre-commit", "pre_commit"),
        ("pydantic", "pydantic"),
        ("pydantic-settings", "pydantic_settings"),
    ]

    all_installed = True
    for package_name, import_name in dev_packages:
        if not check_python_package(package_name, import_name):
            all_installed = False

    return all_installed


def check_configuration_files() -> bool:
    """Check if configuration files are properly set up."""
    config_files = [
        "pyproject.toml",
        ".pre-commit-config.yaml",
        ".editorconfig",
        "src/openchronicle/py.typed"
    ]

    all_valid = True
    for config_file in config_files:
        path = Path(config_file)
        if path.exists():
            print(f"✅ {config_file}: Exists")
        else:
            print(f"❌ {config_file}: Missing")
            all_valid = False

    return all_valid


def run_basic_quality_checks() -> bool:
    """Run basic quality checks to ensure tools work."""
    checks = [
        ("Ruff check", "ruff check src/openchronicle/__init__.py"),
        ("Black check", "black --check src/openchronicle/__init__.py"),
        ("MyPy check", "mypy src/openchronicle/__init__.py"),
    ]

    all_passed = True
    for check_name, command in checks:
        success, output = run_command(command)
        if success:
            print(f"✅ {check_name}: Passed")
        else:
            print(f"❌ {check_name}: Failed - {output}")
            all_passed = False

    return all_passed


def check_import_paths() -> bool:
    """Check if OpenChronicle can be imported correctly."""
    try:
        sys.path.insert(0, str(Path("src")))
        import openchronicle
        print(f"✅ Import check: openchronicle v{getattr(openchronicle, '__version__', 'dev')}")
        return True
    except ImportError as e:
        print(f"❌ Import check: Failed - {e}")
        return False


def main() -> int:
    """Main validation function."""
    print("OpenChronicle Development Environment Validation")
    print("=" * 50)

    checks = [
        ("Python Version", check_python_version),
        ("Project Structure", check_project_structure),
        ("Configuration Files", check_configuration_files),
        ("Development Dependencies", check_development_dependencies),
        ("Quality Tools", check_quality_tools),
        ("Git Hooks", check_git_hooks),
        ("Import Paths", check_import_paths),
        ("Basic Quality Checks", run_basic_quality_checks),
    ]

    results = {}
    for check_name, check_func in checks:
        print(f"\n📋 {check_name}")
        print("-" * 30)
        results[check_name] = check_func()

    # Summary
    print("\n" + "=" * 50)
    print("📊 VALIDATION SUMMARY")
    print("=" * 50)

    passed = sum(results.values())
    total = len(results)

    for check_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {check_name}")

    print(f"\nOverall: {passed}/{total} checks passed")

    if passed == total:
        print("\n🎉 Development environment is ready!")
        print("You can start developing with:")
        print("  make check    # Run all quality checks")
        print("  make test     # Run test suite")
        print("  make run      # Run the application")
        return 0
    print(f"\n⚠️  {total - passed} issues need to be resolved.")
    print("Run the following to fix common issues:")
    print("  make dev-install     # Install development dependencies")
    print("  pre-commit install  # Install git hooks")
    return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
