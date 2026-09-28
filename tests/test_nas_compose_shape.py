"""The NAS compose keeps the storage and network shape design 0020 adopted.

Stack 151 is file-based: this file reaches production only through a reviewed
``portainer_update_stack_file``. These tests pin the properties whose loss
would fail silently there, for example a stack that starts on a new, empty
database volume.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from tests.helpers.nas_compose import NAS_COMPOSE, render_nas_compose


@pytest.fixture
def rendered(tmp_path: Path) -> dict[str, Any]:
    # The metrics profile is selected so the optional collector is checked too.
    return render_nas_compose(tmp_path, {"OC_TAG": "v3.3.0", "COMPOSE_PROFILES": "metrics"})


def test_database_volume_is_external_and_pinned_by_name(rendered: dict[str, Any]) -> None:
    """Compose must never create an empty substitute for the live database."""
    data = rendered["volumes"]["oc-data"]
    assert data["external"] is True
    assert data["name"] == "openchronicle-mcp_oc-data"


def test_other_volumes_have_project_independent_names(rendered: dict[str, Any]) -> None:
    volumes = rendered["volumes"]
    assert volumes["oc-output"]["name"] == "openchronicle-mcp_oc-output"
    assert volumes["oc-config"]["name"] == "openchronicle-mcp_oc-config"
    assert not volumes["oc-output"].get("external")
    assert not volumes["oc-config"].get("external")


def test_oc_mounts_the_live_volume_at_data(rendered: dict[str, Any]) -> None:
    mounts = {m["target"]: m for m in rendered["services"]["oc"]["volumes"]}
    assert mounts["/data"]["type"] == "volume"
    assert mounts["/data"]["source"] == "oc-data"
    assert rendered["services"]["oc"]["environment"]["OC_DB_PATH"] == "/data/openchronicle.db"
    # Without HOST_CONFIG_DIR, /config is the named volume, not a host bind.
    assert mounts["/config"]["type"] == "volume"
    assert mounts["/config"]["source"] == "oc-config"


def test_exports_bind_never_creates_its_host_directory(rendered: dict[str, Any]) -> None:
    mounts = {m["target"]: m for m in rendered["services"]["oc"]["volumes"]}
    exports = mounts["/exports"]
    assert exports["type"] == "bind"
    # Compose versions render this differently: v5 prints the explicit false,
    # while the v2 on CI omits a false value. A rendered true fails either way.
    assert (exports.get("bind") or {}).get("create_host_path", False) is False
    # Absence alone is ambiguous, so also pin the explicit setting in the source.
    source = NAS_COMPOSE.read_text(encoding="utf-8")
    assert re.search(r"target: /exports\n\s+bind:\n\s+create_host_path: false\n", source)
    assert rendered["services"]["oc"]["environment"]["OC_BACKUP_DIR"] == "/exports/backups"


def test_every_service_uses_the_shared_bridge(rendered: dict[str, Any]) -> None:
    """Fleet address-pool rule: no per-project network."""
    # Pin the set, so a renamed profile cannot quietly drop the collector
    # out of the loop below.
    assert set(rendered["services"]) == {"oc", "prometheus"}
    assert not rendered.get("networks")
    for name, service in rendered["services"].items():
        assert service.get("network_mode") == "bridge", name


def test_collector_reaches_the_published_port_through_the_host(rendered: dict[str, Any]) -> None:
    """On the shared bridge the collector scrapes host.docker.internal:18000,
    which does not resolve on Linux without the host-gateway entry."""
    assert "host.docker.internal=host-gateway" in rendered["services"]["prometheus"]["extra_hosts"]


def test_container_name_and_no_auto_updater(rendered: dict[str, Any]) -> None:
    assert rendered["services"]["oc"]["container_name"] == "openchronicle-mcp"
    # Code goes live only when OC_TAG moves; an image watcher must not
    # recreate any service behind that rule.
    for name, service in rendered["services"].items():
        labels = service.get("labels") or {}
        assert not any("watchtower" in key for key in labels), name
