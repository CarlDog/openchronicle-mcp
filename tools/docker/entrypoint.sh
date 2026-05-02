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

# Bootstrap config defaults into $OC_CONFIG_DIR on first run.
#
# /config-defaults is baked into the image (Dockerfile COPY config
# /config-defaults). When the container starts with $OC_CONFIG_DIR
# bind-mounted to an empty host directory, this populates the bind
# mount with the example model configs so operators don't start with
# an empty /config.
#
# Marker file at $OC_CONFIG_DIR/.bootstrapped prevents re-running on
# subsequent restarts. To force a re-bootstrap: rm the marker and
# restart. cp -n (no-clobber) preserves any operator changes if they
# exist alongside the marker absence.
#
# To opt out of bootstrap entirely on first deploy: touch
# $HOST_CONFIG_DIR/.bootstrapped on the host before starting the
# container.
if [ -d /config-defaults ] && [ ! -f "$OC_CONFIG_DIR/.bootstrapped" ]; then
  echo "entrypoint: bootstrapping $OC_CONFIG_DIR from /config-defaults/ (first run)"
  cp -rn /config-defaults/. "$OC_CONFIG_DIR"/
  touch "$OC_CONFIG_DIR/.bootstrapped"
fi

if [ "$#" -eq 0 ]; then
  exec oc serve --http-only
fi

exec oc "$@"
