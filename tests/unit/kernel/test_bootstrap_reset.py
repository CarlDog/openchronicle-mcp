"""Tests for core bootstrap reset capabilities."""

from openchronicle_new.kernel import bootstrap


def test_reset_core_reinitializes_container_and_registry() -> None:
    bootstrap.reset_core()
    bootstrap.create_core()
    container1 = bootstrap.get_container()
    registry1 = bootstrap.get_plugin_registry()

    bootstrap.reset_core()
    bootstrap.create_core()
    container2 = bootstrap.get_container()
    registry2 = bootstrap.get_plugin_registry()

    assert container1 is not container2
    assert registry1 is not registry2
    bootstrap.reset_core()
