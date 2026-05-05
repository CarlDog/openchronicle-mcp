#!/bin/sh
set -eu

# v3 entrypoint: single ASGI process serving HTTP REST at /api/v1/*
# and the MCP streamable-HTTP transport at /mcp on the same port.
# v2's plugin / asset / discord paths are gone.

# Derive per-path defaults from OC_DATA_DIR when set (per-path env
# vars still win). Two paths land here in v3:
#   - OC_DB_PATH (the SQLite store)
#   - OC_CONFIG_DIR (core.json + model configs)
#   - OC_OUTPUT_DIR (any operator-export artifacts; optional)
if [ -n "${OC_DATA_DIR:-}" ]; then
  : "${OC_DB_PATH:=$OC_DATA_DIR/openchronicle.db}"
  : "${OC_CONFIG_DIR:=$OC_DATA_DIR/config}"
  : "${OC_OUTPUT_DIR:=$OC_DATA_DIR/output}"
fi

OC_DB_PATH="${OC_DB_PATH:-/app/data/openchronicle.db}"
OC_CONFIG_DIR="${OC_CONFIG_DIR:-/app/config}"
OC_OUTPUT_DIR="${OC_OUTPUT_DIR:-/app/output}"

export OC_DB_PATH OC_CONFIG_DIR OC_OUTPUT_DIR

mkdir -p "$(dirname "$OC_DB_PATH")" "$OC_CONFIG_DIR" "$OC_OUTPUT_DIR"

# Bootstrap config defaults into $OC_CONFIG_DIR on first run.
#
# /config-defaults is baked into the image. When the container starts
# with $OC_CONFIG_DIR bind-mounted to an empty host directory, this
# populates the bind mount with example configs so operators don't
# start with an empty /config.
#
# Marker file at $OC_CONFIG_DIR/.bootstrapped prevents re-running on
# subsequent restarts. To force a re-bootstrap: rm the marker and
# restart. cp -n (no-clobber) preserves any operator changes that
# may exist alongside an absent marker.
if [ -d /config-defaults ] && [ ! -f "$OC_CONFIG_DIR/.bootstrapped" ]; then
  echo "entrypoint: bootstrapping $OC_CONFIG_DIR from /config-defaults/ (first run)"
  cp -rn /config-defaults/. "$OC_CONFIG_DIR"/
  touch "$OC_CONFIG_DIR/.bootstrapped"
fi

if [ "$#" -eq 0 ]; then
  exec oc serve
fi

exec oc "$@"
