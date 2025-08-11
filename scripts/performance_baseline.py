#!/usr/bin/env python3
"""
Performance Baseline Capture Script

This script captures current performance metrics for OpenChronicle
to establish baselines before the architecture migration.

Usage:
    python scripts/performance_baseline.py
"""

import json
import subprocess
import sys
import time
import tracemalloc
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil


def measure_import_time(module_name: str) -> float:
    """Measure time to import a module."""
    start_time = time.perf_counter()
    try:
        __import__(module_name)
        end_time = time.perf_counter()
        return end_time - start_time
    except ImportError:
        return -1.0  # Module not available


def measure_test_execution_time() -> dict[str, float]:
    """Measure test suite execution times."""
    metrics = {}

    # Measure different test categories
    test_commands = [
        ("unit_tests", ["python", "-m", "pytest", "tests/unit/", "-q", "--tb=no"]),
        ("integration_tests", ["python", "-m", "pytest", "tests/integration/", "-q", "--tb=no"]),
        ("all_tests", ["python", "-m", "pytest", "tests/", "-q", "--tb=no"]),
    ]

    for test_name, command in test_commands:
        try:
            start_time = time.perf_counter()
            result = subprocess.run(
                command,
                check=False, capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            end_time = time.perf_counter()

            metrics[test_name] = {
                "execution_time": end_time - start_time,
                "success": result.returncode == 0,
                "test_count": _extract_test_count(result.stdout)
            }
        except subprocess.TimeoutExpired:
            metrics[test_name] = {
                "execution_time": 300.0,
                "success": False,
                "test_count": 0,
                "error": "timeout"
            }
        except Exception as e:
            metrics[test_name] = {
                "execution_time": 0.0,
                "success": False,
                "test_count": 0,
                "error": str(e)
            }

    return metrics


def _extract_test_count(pytest_output: str) -> int:
    """Extract test count from pytest output."""
    try:
        # Look for pattern like "347 passed"
        import re
        match = re.search(r'(\d+) passed', pytest_output)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return 0


def measure_memory_usage() -> dict[str, Any]:
    """Measure current memory usage patterns."""
    tracemalloc.start()

    try:
        # Import main modules to measure memory impact
        sys.path.insert(0, str(Path("src")))

        # Get current memory snapshot
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Get system memory info
        memory_info = psutil.virtual_memory()

        return {
            "import_memory_current": current,
            "import_memory_peak": peak,
            "system_memory_total": memory_info.total,
            "system_memory_available": memory_info.available,
            "system_memory_percent": memory_info.percent
        }
    except Exception as e:
        tracemalloc.stop()
        return {
            "error": str(e),
            "system_memory_info": dict(psutil.virtual_memory()._asdict())
        }


def measure_file_system_metrics() -> dict[str, Any]:
    """Measure file system related metrics."""
    project_root = Path()

    metrics = {
        "file_counts": {},
        "directory_sizes": {},
        "line_counts": {}
    }

    # Count files by type
    file_types = {
        "python_files": "**/*.py",
        "test_files": "tests/**/*.py",
        "config_files": "*.{toml,yaml,yml,json,ini}",
        "doc_files": "**/*.{md,rst,txt}"
    }

    for file_type, pattern in file_types.items():
        try:
            files = list(project_root.glob(pattern))
            metrics["file_counts"][file_type] = len(files)

            # Calculate total lines for Python files
            if file_type in ["python_files", "test_files"]:
                total_lines = 0
                for file_path in files:
                    try:
                        with open(file_path, encoding='utf-8') as f:
                            total_lines += len(f.readlines())
                    except Exception:
                        pass
                metrics["line_counts"][file_type] = total_lines
        except Exception as e:
            metrics["file_counts"][file_type] = f"error: {e}"

    # Directory sizes
    important_dirs = ["src", "tests", "docs", "core", "utilities"]
    for dir_name in important_dirs:
        dir_path = project_root / dir_name
        if dir_path.exists():
            try:
                size = sum(f.stat().st_size for f in dir_path.rglob('*') if f.is_file())
                metrics["directory_sizes"][dir_name] = size
            except Exception as e:
                metrics["directory_sizes"][dir_name] = f"error: {e}"

    return metrics


def measure_quality_tool_performance() -> dict[str, Any]:
    """Measure performance of quality tools."""
    tools = {
        "ruff_check": ["ruff", "check", "src/openchronicle/__init__.py"],
        "black_check": ["black", "--check", "src/openchronicle/__init__.py"],
        "mypy_check": ["mypy", "src/openchronicle/__init__.py"],
    }

    metrics = {}
    for tool_name, command in tools.items():
        try:
            start_time = time.perf_counter()
            result = subprocess.run(
                command,
                check=False, capture_output=True,
                text=True,
                timeout=30
            )
            end_time = time.perf_counter()

            metrics[tool_name] = {
                "execution_time": end_time - start_time,
                "success": result.returncode == 0
            }
        except Exception as e:
            metrics[tool_name] = {
                "execution_time": 0.0,
                "success": False,
                "error": str(e)
            }

    return metrics


def capture_baseline() -> dict[str, Any]:
    """Capture complete performance baseline."""
    print("🔍 Capturing OpenChronicle Performance Baseline")
    print("=" * 50)

    baseline = {
        "timestamp": datetime.now().isoformat(),
        "python_version": sys.version,
        "platform": sys.platform,
        "metrics": {}
    }

    # Import timing
    print("📦 Measuring import times...")
    important_imports = [
        "openchronicle",
        "src.openchronicle.main",
        "src.openchronicle.domain",
        "src.openchronicle.infrastructure"
    ]

    import_times = {}
    for module in important_imports:
        import_time = measure_import_time(module)
        import_times[module] = import_time
        status = "✅" if import_time >= 0 else "❌"
        if import_time >= 0:
            print(f"  {status} {module}: {import_time:.4f}s")
        else:
            print(f"  {status} {module}: Not available")

    baseline["metrics"]["import_times"] = import_times

    # Test execution
    print("\n🧪 Measuring test execution times...")
    test_metrics = measure_test_execution_time()
    for test_name, data in test_metrics.items():
        status = "✅" if data["success"] else "❌"
        time_str = f"{data['execution_time']:.2f}s"
        count_str = f"({data['test_count']} tests)" if data["test_count"] > 0 else ""
        print(f"  {status} {test_name}: {time_str} {count_str}")

    baseline["metrics"]["test_execution"] = test_metrics

    # Memory usage
    print("\n💾 Measuring memory usage...")
    memory_metrics = measure_memory_usage()
    if "error" not in memory_metrics:
        current_mb = memory_metrics["import_memory_current"] / 1024 / 1024
        peak_mb = memory_metrics["import_memory_peak"] / 1024 / 1024
        print(f"  ✅ Import memory: {current_mb:.2f}MB current, {peak_mb:.2f}MB peak")
        print(f"  ✅ System memory: {memory_metrics['system_memory_percent']:.1f}% used")
    else:
        print(f"  ❌ Memory measurement error: {memory_metrics['error']}")

    baseline["metrics"]["memory_usage"] = memory_metrics

    # File system
    print("\n📁 Measuring file system metrics...")
    fs_metrics = measure_file_system_metrics()
    for metric_type, data in fs_metrics.items():
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, int):
                    print(f"  ✅ {key}: {value:,}")

    baseline["metrics"]["file_system"] = fs_metrics

    # Quality tools
    print("\n🔧 Measuring quality tool performance...")
    quality_metrics = measure_quality_tool_performance()
    for tool_name, data in quality_metrics.items():
        status = "✅" if data["success"] else "❌"
        time_str = f"{data['execution_time']:.4f}s"
        print(f"  {status} {tool_name}: {time_str}")

    baseline["metrics"]["quality_tools"] = quality_metrics

    return baseline


def save_baseline(baseline: dict[str, Any]) -> None:
    """Save baseline to file."""
    output_file = Path("storage/performance_baseline.json")
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(baseline, f, indent=2)

    print(f"\n💾 Baseline saved to: {output_file}")


def main() -> int:
    """Main function."""
    try:
        baseline = capture_baseline()
        save_baseline(baseline)

        print("\n" + "=" * 50)
        print("🎉 Performance baseline capture complete!")
        print("\nKey Metrics Summary:")

        # Show summary
        if "test_execution" in baseline["metrics"]:
            all_tests = baseline["metrics"]["test_execution"].get("all_tests", {})
            if all_tests.get("success"):
                test_time = all_tests["execution_time"]
                test_count = all_tests["test_count"]
                print(f"  📊 Total tests: {test_count} in {test_time:.2f}s")

        if "file_system" in baseline["metrics"]:
            fs = baseline["metrics"]["file_system"]
            python_files = fs.get("file_counts", {}).get("python_files", 0)
            python_lines = fs.get("line_counts", {}).get("python_files", 0)
            print(f"  📊 Python files: {python_files} files, {python_lines:,} lines")

        print("\nUse this baseline to compare performance after migration!")
        return 0

    except Exception as e:
        print(f"\n❌ Error capturing baseline: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
