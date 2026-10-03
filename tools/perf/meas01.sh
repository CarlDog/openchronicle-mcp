#!/usr/bin/env bash
# MEAS-01 direct-cost run (design 0010). Runs tools/perf/meas01.py inside the
# image production runs, with no network, on copies of the newest catalogued
# snapshot. Production is touched once: `docker inspect`. About 5 minutes.
#   sudo bash meas01.sh 2>&1 | tee meas01.log      (meas01.py beside it)
# Writes meas01-<UTC time>.json in the current directory.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
IMG=$(docker inspect -f '{{.Config.Image}}' openchronicle-mcp)
EXPORTS=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/exports"}}{{.Source}}{{end}}{{end}}' openchronicle-mcp)
SNAP=$(ls -1t "$EXPORTS"/backups/auto/openchronicle-*.db | head -n 1)
OUT="meas01-$(date -u +%Y%m%dT%H%M%SZ).json"
echo "image: $IMG ($(docker run --rm --network none --entrypoint cat "$IMG" /app/build-revision))"
echo "snapshot: $SNAP"
echo "host before: $(cut -d' ' -f1-3 /proc/loadavg)"
docker stats --no-stream --format '{{.CPUPerc}}\t{{.Name}}' | sort -rn | head -n 5
docker run --rm --network none --read-only --user 1000:1000 \
  --tmpfs /tmp:rw,nosuid,nodev,size=1g,uid=1000,gid=1000 \
  --mount "type=bind,source=$SNAP,target=/s.db,readonly" \
  --mount "type=bind,source=$HERE/meas01.py,target=/meas01.py,readonly" \
  --entrypoint python "$IMG" /meas01.py --snapshot /s.db > "$OUT"
echo "host after: $(cut -d' ' -f1-3 /proc/loadavg)"
docker stats --no-stream --format '{{.CPUPerc}}\t{{.Name}}' | sort -rn | head -n 5
echo "report: $OUT"
