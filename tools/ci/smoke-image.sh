#!/usr/bin/env bash
# Smoke-test a built OpenChronicle image before anything pushes it.
#
# Usage: tools/ci/smoke-image.sh <image> <expected-build-revision>
#
# CI runs this between building the image and pushing it (test.yml,
# build-and-push), so an image that cannot start never reaches :latest.
# Unit tests run against a source checkout and cannot catch a broken
# image: a dependency missing from the install, a bad entrypoint, or a
# build revision that was never baked in.
set -euo pipefail

image="$1"
expected="$2"

echo "1/3 oc version reports build revision $expected"
# --entrypoint oc skips the entrypoint script, which echoes a bootstrap
# line to stdout on a fresh container and would corrupt the JSON.
version_json="$(docker run --rm --entrypoint oc "$image" version --json)"
python3 - "$expected" "$version_json" <<'PY'
import json
import sys

expected, raw = sys.argv[1], sys.argv[2]
result = json.loads(raw)["result"]
assert result["build_revision"] == expected, f"build_revision {result['build_revision']!r} != {expected!r}"
print("    ok:", result)
PY

echo "2/3 the runtime dependencies import"
docker run --rm --entrypoint python "$image" -c \
  "import openchronicle, fastapi, uvicorn, httpx, numpy, openai, prometheus_client; from mcp.server.fastmcp import FastMCP"
echo "    ok"

echo "3/3 the server starts and answers /health"
cid="$(docker run -d "$image")"
trap 'docker rm -f "$cid" >/dev/null 2>&1 || true' EXIT
for _ in $(seq 1 30); do
  if docker exec -i "$cid" python - "$expected" <<'PY'
import json
import sys
import urllib.request

base = "http://127.0.0.1:8000"
try:
    with urllib.request.urlopen(base + "/health", timeout=3) as response:
        assert response.status == 200, response.status
    with urllib.request.urlopen(base + "/api/v1/health", timeout=3) as response:
        body = json.load(response)
except OSError:
    sys.exit(1)  # not listening yet
assert body["build_revision"] == sys.argv[1], body.get("build_revision")
print("    ok:", body["package_version"], body["build_revision"])
PY
  then
    exit 0
  fi
  sleep 2
done
echo "the server did not become healthy after 30 attempts (about 90 s); container logs:" >&2
docker logs "$cid" >&2 || true
exit 1
