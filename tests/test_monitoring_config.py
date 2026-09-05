"""Contract tests for the optional local Prometheus collector configuration."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]
PROMETHEUS_CONFIG = ROOT / "monitoring" / "prometheus" / "prometheus.yml"
PROMETHEUS_AUTH_CONFIG = ROOT / "monitoring" / "prometheus" / "prometheus-auth.yml"
PROMQL_CATALOG = ROOT / "docs" / "monitoring" / "promql.md"
RUNBOOK = ROOT / "docs" / "monitoring" / "runbook.md"


def test_default_collector_config_is_local_and_bounded() -> None:
    config = PROMETHEUS_CONFIG.read_text(encoding="utf-8")

    assert "scrape_interval: 30s" in config
    assert "scrape_timeout: 5s" in config
    assert "job_name: openchronicle" in config
    assert "metrics_path: /metrics" in config
    assert "- oc:8000" in config
    assert "remote_write:" not in config
    assert "http://" not in config


def test_authenticated_config_uses_a_file_not_a_tracked_secret() -> None:
    config = PROMETHEUS_AUTH_CONFIG.read_text(encoding="utf-8")

    assert "credentials_file: /etc/prometheus/secrets/oc-api-key" in config
    assert "credentials:" not in config
    assert "job_name: openchronicle" in config
    assert "- oc:8000" in config


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
