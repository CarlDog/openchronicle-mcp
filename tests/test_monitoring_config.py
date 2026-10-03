"""Contract tests for the optional local Prometheus collector configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.helpers.nas_compose import NAS_COMPOSE, render_nas_compose

ROOT = Path(__file__).parents[1]
PROMQL_CATALOG = ROOT / "docs" / "monitoring" / "promql.md"
RUNBOOK = ROOT / "docs" / "monitoring" / "runbook.md"


@pytest.fixture
def rendered(tmp_path: Path) -> dict[str, Any]:
    return render_nas_compose(tmp_path, {"OC_TAG": "v3.8.0", "COMPOSE_PROFILES": "metrics", "OC_API_KEY": "test-key"})


def _config(rendered: dict[str, Any], name: str) -> str:
    content: str = rendered["configs"][name]["content"]
    return content


def test_default_collector_config_is_local_and_bounded(rendered: dict[str, Any]) -> None:
    config = _config(rendered, "prometheus-config")

    assert "scrape_interval: 30s" in config
    assert "scrape_timeout: 5s" in config
    assert "job_name: openchronicle" in config
    assert "metrics_path: /metrics" in config
    assert "- host.docker.internal:18000" in config
    assert "remote_write:" not in config
    assert "http://" not in config
    assert "authorization:" not in config


def test_authenticated_config_uses_a_file_not_a_tracked_secret(rendered: dict[str, Any]) -> None:
    config = _config(rendered, "prometheus-auth-config")

    assert "credentials_file: /etc/prometheus/secrets/oc-api-key" in config
    assert "credentials:" not in config
    assert "job_name: openchronicle" in config
    assert "- host.docker.internal:18000" in config
    assert "remote_write:" not in config
    # The token comes from the stack's OC_API_KEY at start, never from the file.
    assert rendered["secrets"]["oc-api-key"]["environment"] == "OC_API_KEY"
    assert "test-key" not in NAS_COMPOSE.read_text(encoding="utf-8")
    assert "test-key" not in config


def test_collector_needs_no_file_beside_the_compose(rendered: dict[str, Any]) -> None:
    """Stack 151 is a file-based Portainer stack: a relative bind would mount
    an empty directory, so everything the collector reads must be inline."""
    prometheus = rendered["services"]["prometheus"]
    targets = {c["target"]: c["source"] for c in prometheus["configs"]}
    assert targets == {
        "/etc/prometheus/openchronicle.yml": "prometheus-config",
        "/etc/prometheus/openchronicle-auth.yml": "prometheus-auth-config",
    }
    assert [(s["source"], s["target"]) for s in prometheus["secrets"]] == [
        ("oc-api-key", "/etc/prometheus/secrets/oc-api-key")
    ]
    binds = [m for m in prometheus.get("volumes", []) if m["type"] == "bind"]
    assert not binds, binds
    for service in rendered["services"].values():
        for mount in service.get("volumes", []):
            assert not str(mount.get("source", "")).startswith(str(NAS_COMPOSE.parent / "monitoring")), mount


def test_collector_settings_follow_the_stack_env(tmp_path: Path) -> None:
    rendered = render_nas_compose(
        tmp_path,
        {
            "OC_TAG": "v3.8.0",
            "COMPOSE_PROFILES": "metrics",
            "HOST_HTTP_PORT": "18080",
            "PROMETHEUS_RETENTION_TIME": "30d",
            "PROMETHEUS_RETENTION_SIZE": "2GB",
            "PROMETHEUS_CONFIG_FILE": "/etc/prometheus/openchronicle-auth.yml",
        },
    )
    command = rendered["services"]["prometheus"]["command"]
    assert "--storage.tsdb.retention.time=30d" in command
    assert "--storage.tsdb.retention.size=2GB" in command
    assert "--config.file=/etc/prometheus/openchronicle-auth.yml" in command
    for name in ("prometheus-config", "prometheus-auth-config"):
        assert "- host.docker.internal:18080" in _config(rendered, name)


def test_metrics_stay_off_by_default(tmp_path: Path) -> None:
    rendered = render_nas_compose(tmp_path, {"OC_TAG": "v3.8.0"})
    assert set(rendered["services"]) == {"oc"}
    assert rendered["services"]["oc"]["environment"]["OC_METRICS_ENABLED"] == "false"
    with_profile = render_nas_compose(tmp_path, {"OC_TAG": "v3.8.0", "COMPOSE_PROFILES": "metrics"})
    command = with_profile["services"]["prometheus"]["command"]
    assert "--config.file=/etc/prometheus/openchronicle.yml" in command
    assert "--storage.tsdb.retention.time=14d" in command
    assert "--storage.tsdb.retention.size=1GB" in command


def test_query_catalog_and_runbook_cover_history_boundaries() -> None:
    queries = PROMQL_CATALOG.read_text(encoding="utf-8")
    runbook = RUNBOOK.read_text(encoding="utf-8")

    for fragment in (
        "histogram_quantile",
        "rate(oc_http_requests_total",
        "increase(oc_job_runs_total",
        "offset 7d",
        'up{job="openchronicle"}',
    ):
        assert fragment in queries or fragment in runbook

    assert "OC_METRICS_ENABLED=true" in runbook
    assert "2 GiB" in runbook
    assert "NFS" in runbook
    assert "OC_API_KEY" in runbook
    assert "No OC SQLite migration" in runbook
