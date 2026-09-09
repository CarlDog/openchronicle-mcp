"""Fresh Prometheus text exposition with bounded, per-recorder prefix caching.

Only immutable sample names, labels and their formatted prefixes are retained;
values, timestamps, families and response bodies are collected afresh. Cache
limits cover entries and retained UTF-8 text, not total Python heap or RSS.
Unsupported families/names/escaping use the installed standard exporter.

The owning recorder's scrape slot serializes calls, including after caller
cancellation. This exporter has no independent concurrency or response cache.
Import it only on the enabled metrics path.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from prometheus_client import generate_latest
from prometheus_client.metrics_core import Metric
from prometheus_client.registry import Collector
from prometheus_client.samples import Sample
from prometheus_client.utils import floatToGoString

_METRIC_NAME = re.compile(r"[a-zA-Z_:][a-zA-Z0-9_:]*\Z")
_LABEL_NAME = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*\Z")
type PrefixKey = tuple[str, tuple[tuple[str, str], ...]]


@dataclass
class _CollectedFamily:
    metric: Metric

    def collect(self) -> Iterator[Metric]:
        yield self.metric


class _UseStandard(Exception):
    pass


class CachedPrefixExporter:
    """One cache per enabled recorder; full caches still emit every sample."""

    def __init__(self, *, max_entries: int = 4096, max_payload_bytes: int = 1_048_576) -> None:
        if max_entries < 0 or max_payload_bytes < 0:
            raise ValueError("cache limits must be nonnegative")
        self._max_entries = max_entries
        self._max_payload_bytes = max_payload_bytes
        self._prefixes: dict[PrefixKey, str] = {}
        self._payload_bytes = 0

    @staticmethod
    def _make_prefix(key: PrefixKey) -> str:
        name, labels = key
        if not _METRIC_NAME.fullmatch(name):
            raise _UseStandard
        escaped = []
        for label, value in labels:
            if not _LABEL_NAME.fullmatch(label):
                raise _UseStandard
            value = value.replace("\\", r"\\").replace("\n", r"\n").replace('"', r"\"")
            escaped.append(f'{label}="{value}"')
        return name + ("{" + ",".join(escaped) + "}" if escaped else "") + " "

    def _prefix(self, sample: Sample) -> str:
        try:
            labels = tuple(sorted(sample.labels.items()))
            # Validate before lookup: str subclasses can compare/hash equal to
            # cached strings while implementing different escaping behavior.
            if type(sample.name) is not str or any(type(part) is not str for pair in labels for part in pair):
                raise _UseStandard
            key = (sample.name, labels)
            prefix = self._prefixes.get(key)
        except TypeError, AttributeError:
            raise _UseStandard from None
        if prefix is not None:
            return prefix
        prefix = self._make_prefix(key)
        # Surrogate-pass is budget accounting only. Response encoding stays
        # strict and happens after collection/formatting, like generate_latest.
        if len(self._prefixes) < self._max_entries:
            strings = (sample.name, prefix, *(text for pair in labels for text in pair))
            size = sum(len(text.encode("utf-8", errors="surrogatepass")) for text in strings)
            if self._payload_bytes + size <= self._max_payload_bytes:
                self._prefixes[key] = prefix
                self._payload_bytes += size
        return prefix

    @staticmethod
    def _header(name: str, kind: str, documentation: str) -> str:
        help_text = documentation.replace("\\", r"\\").replace("\n", r"\n")
        return f"# HELP {name} {help_text}\n# TYPE {name} {kind}\n"

    def _family(self, metric: Metric) -> str:
        if (
            metric.type not in {"counter", "gauge", "histogram"}
            or type(metric.name) is not str
            or not _METRIC_NAME.fullmatch(metric.name)
        ):
            raise _UseStandard
        name = metric.name + "_total" if metric.type == "counter" else metric.name
        output = [self._header(name, metric.type, metric.documentation)]
        extra_names = {metric.name + suffix for suffix in ("_created", "_gsum", "_gcount")}
        extra: dict[str, list[str]] = {}
        for sample in metric.samples:
            prefix = self._prefix(sample)
            timestamp = "" if sample.timestamp is None else f" {int(float(sample.timestamp) * 1000)}"
            line = f"{prefix}{floatToGoString(sample.value)}{timestamp}\n"
            if sample.name in extra_names:
                extra.setdefault(sample.name, []).append(line)
            else:
                output.append(line)
        for name, lines in sorted(extra.items()):
            output.append(self._header(name, "gauge", metric.documentation))
            output.extend(lines)
        return "".join(output)

    @staticmethod
    def _standard_family(metric: Metric) -> str:
        try:
            return generate_latest(_CollectedFamily(metric)).decode("utf-8")
        except UnicodeEncodeError as exc:
            # generate_latest encodes only after formatting. Preserve that
            # whole-scrape error context and precedence over later collectors.
            # Formatting errors carry an appended Metric argument: never
            # mistake those for a deferred final-body encoding failure.
            if exc.encoding != "utf-8" or len(exc.args) != 5:
                raise
            return exc.object

    def __call__(self, registry: Collector, escaping: str = "underscores") -> bytes:
        if escaping != "underscores":
            return generate_latest(registry, escaping=escaping)
        output = []
        for metric in registry.collect():
            try:
                family = self._family(metric)
            except _UseStandard:
                # Reuse this collected family, never collect the registry twice.
                family = self._standard_family(metric)
            except Exception as exc:
                exc.args = (exc.args or ("",)) + (metric,)
                raise
            output.append(family)
        return "".join(output).encode("utf-8")
