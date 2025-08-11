"""
Pytest marks configuration for stress testing.

This file defines custom pytest marks used in the stress testing module.
"""

import pytest


def pytest_configure(config):
    """Configure custom pytest marks."""
    config.addinivalue_line("markers", "stress: Stress testing scenarios")
    config.addinivalue_line("markers", "performance: Performance regression tests")
    config.addinivalue_line("markers", "chaos: Chaos engineering tests")
    config.addinivalue_line("markers", "production: Production readiness tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to handle stress test marks."""
    # Add slow marker to all stress tests
    for item in items:
        if "stress" in [marker.name for marker in item.iter_markers()]:
            item.add_marker(pytest.mark.slow)

        # Skip chaos tests by default unless explicitly requested
        if "chaos" in [marker.name for marker in item.iter_markers()]:
            if not config.getoption("-m") or "chaos" not in config.getoption("-m"):
                item.add_marker(pytest.mark.skip(reason="Chaos tests require explicit mark selection"))

        # Skip production tests in quick runs
        if "production" in [marker.name for marker in item.iter_markers()]:
            if config.getoption("--tb") == "short" and not config.getoption("-m"):
                item.add_marker(pytest.mark.skip(reason="Production tests skipped in quick runs"))


def pytest_runtest_setup(item):
    """Setup for stress test runs."""
    # Ensure stress tests have proper environment
    if "stress" in [marker.name for marker in item.iter_markers()]:
        # Could add environment validation here
        pass


def pytest_runtest_teardown(item, nextitem):
    """Cleanup after stress test runs."""
    if "stress" in [marker.name for marker in item.iter_markers()]:
        # Could add cleanup logic here
        pass
