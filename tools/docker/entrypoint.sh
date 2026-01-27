#!/bin/sh
set -eu

if [ -n "${OC_DATA_DIR:-}" ] && [ -z "${OC_DB_PATH:-}" ]; then
  OC_DB_PATH="$OC_DATA_DIR/openchronicle.db"
  export OC_DB_PATH
fi

OC_DB_PATH="${OC_DB_PATH:-/app/data/openchronicle.db}"
OC_CONFIG_DIR="${OC_CONFIG_DIR:-/app/config}"
OC_PLUGIN_DIR="${OC_PLUGIN_DIR:-/app/plugins}"
OC_OUTPUT_DIR="${OC_OUTPUT_DIR:-/app/output}"

export OC_DB_PATH OC_CONFIG_DIR OC_PLUGIN_DIR OC_OUTPUT_DIR

mkdir -p "$(dirname "$OC_DB_PATH")" "$OC_CONFIG_DIR" "$OC_PLUGIN_DIR" "$OC_OUTPUT_DIR"

if [ "$#" -eq 0 ]; then
  exec oc serve --idle-timeout-seconds 0
fi

exec oc "$@"
