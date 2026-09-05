# OpenChronicle PromQL query catalog

This is the versioned query catalog for the optional local Prometheus
collector. Run queries in the Prometheus expression browser or copy them into
a compatible Grafana panel. The queries intentionally use reset-aware
`rate()`/`increase()` functions and preserve empty results: no samples is not
the same as zero activity.

The default scrape job is `job="openchronicle"`. If the collector uses a
different job name, change that selector consistently.

## Request volume, errors, and latency

Request rate by REST route and method:

```promql
sum by (route, method) (
  rate(oc_http_requests_total{job="openchronicle"}[5m])
)
```

HTTP error rate by route and method:

```promql
sum by (route, method) (
  rate(oc_http_requests_total{job="openchronicle",status_class=~"4xx|5xx"}[5m])
)
```

Request p50 and p95 latency by route and method:

```promql
histogram_quantile(
  0.50,
  sum by (le, route, method) (
    rate(oc_http_request_duration_seconds_bucket{job="openchronicle"}[15m])
  )
)
```

```promql
histogram_quantile(
  0.95,
  sum by (le, route, method) (
    rate(oc_http_request_duration_seconds_bucket{job="openchronicle"}[15m])
  )
)
```

Request sample count for the same window:

```promql
sum by (route, method) (
  increase(oc_http_request_duration_seconds_count{job="openchronicle"}[15m])
)
```

MCP tool volume and outcomes:

```promql
sum by (tool, outcome) (
  rate(oc_mcp_executions_total{job="openchronicle"}[5m])
)
```

MCP p95 execution latency:

```promql
histogram_quantile(
  0.95,
  sum by (le, tool) (
    rate(oc_mcp_execution_duration_seconds_bucket{job="openchronicle"}[15m])
  )
)
```

## Provider, search, and SQLite contention

Embedding provider p95 latency:

```promql
histogram_quantile(
  0.95,
  sum by (le, provider, operation) (
    rate(oc_embedding_operation_duration_seconds_bucket{job="openchronicle"}[15m])
  )
)
```

Embedding failures by provider and outcome:

```promql
sum by (provider, outcome) (
  rate(oc_embedding_operations_total{job="openchronicle",outcome!="success"}[15m])
)
```

Search-stage p95 latency:

```promql
histogram_quantile(
  0.95,
  sum by (le, stage) (
    rate(oc_search_stage_duration_seconds_bucket{job="openchronicle"}[15m])
  )
)
```

Search fallbacks:

```promql
sum by (reason) (
  increase(oc_search_fallbacks_total{job="openchronicle"}[1h])
)
```

SQLite lock wait and hold p95:

```promql
histogram_quantile(
  0.95,
  sum by (le, kind) (
    rate(oc_store_lock_wait_seconds_bucket{job="openchronicle"}[15m])
  )
)
```

```promql
histogram_quantile(
  0.95,
  sum by (le, kind) (
    rate(oc_store_lock_hold_seconds_bucket{job="openchronicle"}[15m])
  )
)
```

## Jobs and backfill

Job outcomes over one hour:

```promql
sum by (job, outcome) (
  increase(oc_job_runs_total{job="openchronicle"}[1h])
)
```

Age of the last successful job completion:

```promql
time() - oc_job_last_success_timestamp_seconds{job="openchronicle"}
```

Backfill item outcomes over one hour:

```promql
sum by (outcome) (
  increase(oc_backfill_items_total{job="openchronicle"}[1h])
)
```

## Process and collector health

Current process RSS, where the platform process collector supplies it:

```promql
process_resident_memory_bytes{job="openchronicle"}
```

Process CPU rate, where supported:

```promql
rate(process_cpu_seconds_total{job="openchronicle"}[15m])
```

Process restarts observed in the last day, where process start time is
available:

```promql
changes(process_start_time_seconds{job="openchronicle"}[24h])
```

Collector reachability and scrape duration:

```promql
up{job="openchronicle"}
```

```promql
scrape_duration_seconds{job="openchronicle"}
```

Build identity:

```promql
oc_build_info{job="openchronicle"}
```

Metrics recorder health and internal errors:

```promql
oc_metrics_recorder_healthy{job="openchronicle"}
```

```promql
increase(oc_metrics_recorder_errors_total{job="openchronicle"}[1h])
```

## Seven-day comparison

Compare the current request rate with the equivalent seven-day-old window:

```promql
sum by (route, method) (
  rate(oc_http_requests_total{job="openchronicle"}[1h])
)
```

```promql
sum by (route, method) (
  rate(oc_http_requests_total{job="openchronicle"}[1h] offset 7d)
)
```

Use the same pattern for latency buckets, errors, and provider stages. Do not
interpret the comparison until the older window is populated and the workload
mix, corpus size, provider, build identity, and scrape health are known to be
comparable. A missing or down target is not zero latency or zero errors.
