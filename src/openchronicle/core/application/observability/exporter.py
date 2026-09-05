"""Transport-neutral contract for the optional metrics scrape endpoint."""

from __future__ import annotations

from typing import Protocol


class MetricsScrapeBusyError(RuntimeError):
    """The one active scrape slot is already owned by another request."""


class MetricsScrapeError(RuntimeError):
    """The exporter could not serialize its bounded snapshot."""


class MetricsExporter(Protocol):
    """Expose metrics without making the domain depend on Prometheus."""

    content_type: str

    async def render(self) -> bytes: ...
