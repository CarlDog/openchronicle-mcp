"""
Testing commands for OpenChronicle CLI.

Provides comprehensive test execution capabilities with the four-tier testing strategy:
1. Production tests with real adapters
2. Production tests with mock adapters  
3. Smoke tests for major functionality
4. Stress tests (isolated execution)
"""

import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from rich.progress import SpinnerColumn
from rich.progress import TextColumn
from rich.table import Table


console = Console()

# Test application
test_app = typer.Typer(
    name="test",
    help="Test execution and validation commands",
    no_args_is_help=True
)


def run_pytest_command(command: list, description: str, show_progress: bool = True) -> bool:
    """Execute a pytest command and return success status."""
    console.print()
    console.print(Panel(
        f"🧪 {description}",
        title="OpenChronicle Test Execution",
        style="bold blue"
    ))
    console.print(f"Command: {' '.join(command)}")
    console.print()

    start_time = time.time()

    if show_progress:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task(description="Running tests...", total=None)
            result = subprocess.run(command, check=False, capture_output=False)
    else:
        result = subprocess.run(command, check=False, capture_output=False)

    duration = time.time() - start_time

    console.print(f"\n⏱️  Duration: {duration:.2f} seconds")

    if result.returncode == 0:
        console.print(f"✅ {description} - [green]PASSED[/green]")
        return True
    console.print(f"❌ {description} - [red]FAILED[/red]")
    return False


@test_app.command("production-real")
def test_production_real():
    """Run production tests with real adapters and content (Tier 1)."""
    command = [
        sys.executable, "-m", "pytest",
        "-m", "production_real",
        "-v",
        "--tb=short",
        "--maxfail=10",
        "tests/"
    ]
    success = run_pytest_command(command, "TIER 1: Production Tests (Real Adapters)")
    if not success:
        raise typer.Exit(1)


@test_app.command("production-mock")
def test_production_mock():
    """Run production tests with mock adapters and content (Tier 2)."""
    command = [
        sys.executable, "-m", "pytest",
        "-m", "(production_mock or mock_only)",
        "-v",
        "--tb=short",
        "--maxfail=10",
        "tests/"
    ]
    success = run_pytest_command(command, "TIER 2: Production Tests (Mock Adapters)")
    if not success:
        raise typer.Exit(1)


@test_app.command("smoke")
def test_smoke():
    """Run abbreviated smoke tests for major functionality (Tier 3)."""
    command = [
        sys.executable, "-m", "pytest",
        "-m", "(smoke or core)",
        "-v",
        "--tb=short",
        "--maxfail=5",
        "tests/"
    ]
    success = run_pytest_command(command, "TIER 3: Smoke Tests (Major Functionality)")
    if not success:
        raise typer.Exit(1)


@test_app.command("stress")
def test_stress():
    """Run standalone stress testing (Tier 4) - NEVER mixed with other tiers."""
    console.print(Panel(
        "⚠️  [yellow]Warning:[/yellow] Stress tests are resource intensive and may take significant time.\n"
        "These tests are isolated and should not be run with other test tiers.",
        title="Stress Testing Notice",
        style="yellow"
    ))

    confirm = typer.confirm("Are you sure you want to run stress tests?")
    if not confirm:
        console.print("Stress tests cancelled.")
        raise typer.Exit(0)

    command = [
        sys.executable, "-m", "pytest",
        "-m", "(stress or chaos)",
        "-v",
        "--tb=short",
        "--maxfail=3",
        "--timeout=600",  # 10 minute timeout for stress tests
        "tests/"
    ]
    success = run_pytest_command(command, "TIER 4: Stress Testing (Standalone)", show_progress=False)
    if not success:
        raise typer.Exit(1)


@test_app.command("standard")
def test_standard():
    """Run all tests except stress tests (most common usage)."""
    command = [
        sys.executable, "-m", "pytest",
        "-m", "(not stress and not chaos)",
        "-v",
        "--tb=short",
        "--maxfail=10",
        "tests/"
    ]
    success = run_pytest_command(command, "STANDARD: All Tests (Excluding Stress)")
    if not success:
        raise typer.Exit(1)


@test_app.command("all-tiers")
def test_all_production_tiers():
    """Run all production tiers (1-3, excludes stress testing)."""
    console.print(Panel(
        "🚀 Running All Production Tiers (1-3, excluding stress)",
        title="Comprehensive Test Execution",
        style="bold green"
    ))

    # Define test functions and their names
    test_functions = [
        (test_production_real, "Production Real"),
        (test_production_mock, "Production Mock"),
        (test_smoke, "Smoke Tests")
    ]

    results = []

    for i, (test_func, test_name) in enumerate(test_functions, 1):
        console.print(f"\n📋 [bold]Running Tier {i}: {test_name}[/bold]")
        try:
            test_func()
            results.append((test_name, True))
        except typer.Exit as e:
            results.append((test_name, e.exit_code == 0))

    # Summary table
    console.print("\n" + "="*60)
    console.print(Panel(
        "📊 SUMMARY OF ALL PRODUCTION TIERS",
        style="bold blue"
    ))

    table = Table(title="Test Results Summary")
    table.add_column("Tier", style="cyan", no_wrap=True)
    table.add_column("Test Name", style="magenta")
    table.add_column("Status", justify="center")

    for i, (name, success) in enumerate(results, 1):
        status = "✅ PASSED" if success else "❌ FAILED"
        status_style = "green" if success else "red"
        table.add_row(f"Tier {i}", name, f"[{status_style}]{status}[/{status_style}]")

    console.print(table)

    overall_success = all(result[1] for result in results)
    overall_status = "✅ ALL TIERS PASSED" if overall_success else "❌ SOME TIERS FAILED"
    overall_style = "green" if overall_success else "red"

    console.print(f"\n🎯 Overall Result: [{overall_style}]{overall_status}[/{overall_style}]")

    if not overall_success:
        raise typer.Exit(1)


@test_app.command("status")
def test_status():
    """Show testing configuration and available test markers."""
    console.print(Panel(
        "🧪 OpenChronicle Four-Tier Testing Strategy Status",
        style="bold blue"
    ))

    # Check pytest configuration
    pytest_config = Path("tests/pytest.ini")
    if pytest_config.exists():
        console.print("✅ pytest.ini configuration found")
    else:
        console.print("❌ pytest.ini configuration missing")

    # Test configuration status
    table = Table(title="Test Tier Configuration")
    table.add_column("Tier", style="cyan", no_wrap=True)
    table.add_column("Markers", style="magenta")
    table.add_column("Purpose", style="white")

    table.add_row(
        "Tier 1",
        "production_real",
        "Production tests with real adapters and content"
    )
    table.add_row(
        "Tier 2",
        "production_mock, mock_only",
        "Production tests with mock adapters and test content"
    )
    table.add_row(
        "Tier 3",
        "smoke, core",
        "Abbreviated tests for major functionality validation"
    )
    table.add_row(
        "Tier 4",
        "stress, chaos",
        "High-load stress testing (isolated execution only)"
    )

    console.print(table)

    # Usage examples
    console.print("\n📋 [bold]Usage Examples:[/bold]")
    examples = [
        ("openchronicle test production-mock", "Most common - Development testing"),
        ("openchronicle test smoke", "Quick validation - Essential functionality"),
        ("openchronicle test all-tiers", "Comprehensive validation - All production tiers"),
        ("openchronicle test stress", "Performance testing - Isolated stress testing")
    ]

    for command, description in examples:
        console.print(f"  [cyan]{command}[/cyan] - {description}")


if __name__ == "__main__":
    test_app()

