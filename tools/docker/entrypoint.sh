#!/bin/sh
set -eu

# Derive per-path defaults from OC_DATA_DIR when set (per-path env vars still win)
if [ -n "${OC_DATA_DIR:-}" ]; then
  : "${OC_DB_PATH:=$OC_DATA_DIR/openchronicle.db}"
  : "${OC_CONFIG_DIR:=$OC_DATA_DIR/config}"
  : "${OC_PLUGIN_DIR:=$OC_DATA_DIR/plugins}"
  : "${OC_OUTPUT_DIR:=$OC_DATA_DIR/output}"
  : "${OC_ASSETS_DIR:=$OC_DATA_DIR/assets}"
  : "${OC_DISCORD_SESSION_STORE_PATH:=$OC_DATA_DIR/discord_sessions.json}"
  : "${OC_DISCORD_PID_PATH:=$OC_DATA_DIR/discord_bot.pid}"
fi

OC_DB_PATH="${OC_DB_PATH:-/app/data/openchronicle.db}"
OC_CONFIG_DIR="${OC_CONFIG_DIR:-/app/config}"
OC_PLUGIN_DIR="${OC_PLUGIN_DIR:-/app/plugins}"
OC_OUTPUT_DIR="${OC_OUTPUT_DIR:-/app/output}"
OC_ASSETS_DIR="${OC_ASSETS_DIR:-/app/assets}"
OC_DISCORD_SESSION_STORE_PATH="${OC_DISCORD_SESSION_STORE_PATH:-/app/data/discord_sessions.json}"
OC_DISCORD_PID_PATH="${OC_DISCORD_PID_PATH:-/app/data/discord_bot.pid}"

export OC_DB_PATH OC_CONFIG_DIR OC_PLUGIN_DIR OC_OUTPUT_DIR OC_ASSETS_DIR
export OC_DISCORD_SESSION_STORE_PATH OC_DISCORD_PID_PATH

mkdir -p "$(dirname "$OC_DB_PATH")" "$OC_CONFIG_DIR" "$OC_PLUGIN_DIR" "$OC_OUTPUT_DIR" "$OC_ASSETS_DIR"
mkdir -p "$(dirname "$OC_DISCORD_SESSION_STORE_PATH")" "$(dirname "$OC_DISCORD_PID_PATH")"

if [ "$#" -eq 0 ]; then
  exec oc serve --idle-timeout-seconds 0
fi

exec oc "$@"
