#!/usr/bin/env bash
# End-to-end check of the cloud_backup job inside a built image (design 0001,
# plan review A8). Runs as uid 1000 with a throwaway rclone.conf whose remote is
# rclone's local backend, so no network or token is involved:
#   db_backup -> cloud_backup -> the remote holds exactly .db.age + .json.age
#   -> each decrypts with a DIFFERENT throwaway identity (both recipients are
#      on every artifact) and reproduces the manifest SHA-256
#   -> a second push adds nothing and rewrites nothing (append-only).
# Then the real entrypoint, as root, must leave a 0644 rclone.conf at 600.
#
# Usage: tools/ci/smoke-cloud-backup.sh <image>
set -euo pipefail

image="$1"

echo "1/2 push, decrypt with each recipient, and re-push append-only (uid 1000)"
docker run --rm --user 1000:1000 --entrypoint sh "$image" -euc '
w=/tmp/oc
mkdir -p "$w/data" "$w/config" "$w/exports/backups" "$w/output" "$w/remote"
export OC_DB_PATH="$w/data/openchronicle.db" OC_CONFIG_DIR="$w/config" OC_OUTPUT_DIR="$w/output"
export OC_BACKUP_DIR="$w/exports/backups" OC_MAINTENANCE_DISABLED=1
age-keygen -o "$w/primary.txt" 2>/dev/null
age-keygen -o "$w/recovery.txt" 2>/dev/null
pub1="$(age-keygen -y "$w/primary.txt")"
pub2="$(age-keygen -y "$w/recovery.txt")"
test "$pub1" != "$pub2"
printf "[testlocal]\ntype = local\n" > "$w/config/rclone.conf"
export RCLONE_CONFIG="$w/config/rclone.conf"
export OC_CLOUD_REMOTE="testlocal:$w/remote" OC_CLOUD_AGE_RECIPIENTS="$pub1,$pub2"

oc maintenance run-once db_backup
oc maintenance run-once cloud_backup

snapshot="$(basename "$(ls "$w"/exports/backups/auto/*.db)" .db)"
test "$(ls "$w/remote" | sort | tr "\n" " ")" = "$snapshot.db.age $snapshot.json.age "
# The recovery identity alone opens the database; the primary alone opens the manifest.
age -d -i "$w/recovery.txt" -o "$w/restored.db" "$w/remote/$snapshot.db.age"
age -d -i "$w/primary.txt" -o "$w/manifest.json" "$w/remote/$snapshot.json.age"
python - "$w/restored.db" "$w/manifest.json" <<PY
import hashlib, json, sqlite3, sys
db, manifest = sys.argv[1], json.load(open(sys.argv[2]))
digest = hashlib.sha256(open(db, "rb").read()).hexdigest()
assert digest == manifest["sha256"], (digest, manifest["sha256"])
conn = sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True)
assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
print("    ok: each recipient decrypts; the snapshot matches its manifest", digest[:12])
PY

before="$(cd "$w/remote" && sha256sum *)"
oc maintenance run-once cloud_backup
test "$(cd "$w/remote" && sha256sum *)" = "$before"
echo "    ok: a second push added and rewrote nothing"
# No push temp dirs left behind under the backup root.
test -z "$(ls -d "$w"/exports/backups/cloud-push-* 2>/dev/null)"
'

echo "2/2 the entrypoint leaves rclone.conf at 600, owned by oc"
docker run --rm --entrypoint sh "$image" -euc '
mkdir -p /app/config
printf "[x]\ntype = local\n" > /app/config/rclone.conf
chmod 644 /app/config/rclone.conf
/app/entrypoint.sh version >/dev/null
test "$(stat -c "%a %U" /app/config/rclone.conf)" = "600 oc"
echo "    ok"
'
