# OpenChronicle metrics history runbook

## When to use this

Use this runbook to start the optional local Prometheus collector for the
OpenChronicle NAS compose stack, validate that it is retaining samples, or
disable collection without touching the OpenChronicle memory database.

This is Phase 3 configuration only. It does not authorize a release, Portainer
redeploy, public exposure, alert routing, or a change to the OC runtime
default. `OC_METRICS_ENABLED` remains `false` unless the operator explicitly
enables the metrics profile.

## Prerequisites

- Docker Compose or Portainer Git-stack access to the repository.
- The OpenChronicle image already selected by `OC_TAG`.
- A local filesystem with at least 2 GiB available for Prometheus data. Do not
  use NFS for the data directory.
- If `OC_API_KEY` is set, a host-side file containing only that bearer token.
  Do not commit it or put it in a compose file.

The repository has no configured collector discovery or cloud remote-write
destination. The checked-in collector image is pinned to
`prom/prometheus:v3.14.0`; review the tag before a future collector upgrade.

## Start the opt-in collector

1. Choose a local data directory. The default named volume is
   `prometheus-data`; set `HOST_PROMETHEUS_DATA_DIR` to a bind-mounted local
   path when you need an explicit storage location.
2. Ensure the OC stack environment contains `OC_TAG` and set
   `OC_METRICS_ENABLED=true`.
3. Leave `PROMETHEUS_CONFIG_FILE` unset when `OC_API_KEY` is empty. The
   default config scrapes `oc:8000/metrics` every 30 seconds with a 5-second
   timeout.
4. Start the profile from the repository directory:

   ```powershell
   $env:OC_TAG = "<release-tag>"
   $env:OC_METRICS_ENABLED = "true"
   docker compose -f docker-compose.nas.yml --profile metrics up -d oc prometheus
   ```

   Portainer operators should activate the equivalent `metrics` profile in
   the stack configuration and use the same environment values. A green
   compose operation is not proof of a healthy scrape.
5. Open the Prometheus UI through the loopback-only binding, normally
   `http://127.0.0.1:19090`, or use an SSH tunnel to the NAS. The UI is not
   published on the LAN by this compose file.

## Authenticated scrape

When `OC_API_KEY` is non-empty, create `oc-api-key` in the directory named by
`HOST_PROMETHEUS_SECRETS_DIR` and keep the file local. It must contain the raw
token with no `Bearer` prefix or trailing whitespace. Select the checked-in authenticated config:

```powershell
$env:PROMETHEUS_CONFIG_FILE = "/etc/prometheus/openchronicle-auth.yml"
docker compose -f docker-compose.nas.yml --profile metrics up -d oc prometheus
```

The compose service mounts the configured secrets directory read-only. If the
file is missing or unreadable, Prometheus should show a down target rather than
silently recording a clean zero.

If `OC_API_ALLOWED_HOSTS` is overridden, retain `oc:*` so the collector's
private-network request passes the REST Host allowlist. The metrics endpoint is
not an authentication exemption.

## Verify collection and retention

Run these checks in the Prometheus expression browser:

```promql
up{job="openchronicle"}
```

Expected value is `1`. Then check that the target is returning the expected
families:

```promql
count({job="openchronicle"})
```

Check the collector's own sample and scrape timing:

```promql
scrape_samples_scraped{job="openchronicle"}
```

```promql
scrape_duration_seconds{job="openchronicle"}
```

Confirm the OC process identity and runtime state:

```promql
oc_build_info{job="openchronicle"}
```

```promql
oc_metrics_recorder_healthy{job="openchronicle"}
```

To verify persistence across an OC restart, record the current timestamp and
build identity, restart only `oc`, wait for its healthcheck, and confirm that
Prometheus still returns a sample older than the restart time. Requests after
the last completed scrape and before a crash may be absent; that is an expected
collection gap. A down `up` target is also distinct from zero application
traffic.

Use [promql.md](promql.md) for the saved query catalog. At low traffic, prefer
15-minute or one-hour windows and show sample counts before interpreting
percentiles.

## Stop or roll back collection

To stop collection while leaving OC data intact:

```powershell
docker compose -f docker-compose.nas.yml --profile metrics stop prometheus
```

To disable the OC exporter, set `OC_METRICS_ENABLED=false`, recreate only the
tagged OC service, and stop the collector. The Prometheus volume may be kept
for diagnosis; it is separate from the OC data, config, and output volumes.

If the application remains unhealthy with metrics disabled, stop and follow the
release rollback procedure in the deployment documentation. Phase 3 does not
perform that deployment mutation.

## Known limits

- Retention is configured as 14 days or 1 GiB of blocks, whichever threshold
  is reached first. WAL, head, and compaction overhead mean this is not a hard
  filesystem cap or a guarantee of 14 days.
- The collector is in the same NAS failure domain as OC and cannot prove that
  the whole NAS is unavailable.
- Prometheus history is disposable operational evidence, not an OC memory
  backup. No OC SQLite migration or business-state write is involved.
- Week-over-week comparisons require at least seven populated days and a
  comparable workload; the first day cannot provide that evidence.
