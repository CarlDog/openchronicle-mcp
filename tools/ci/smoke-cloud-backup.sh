#!/usr/bin/env bash
# End-to-end check of the cloud_backup job inside a built image (design 0001,
# plan review A8). Runs as uid 1000 with a throwaway rclone.conf whose remote is
# rclone's local backend, so no network or token is involved:
#   db_backup -> cloud_backup -> the remote holds .db.age + .json.age
#   -> decrypting with a throwaway age identity reproduces the manifest SHA-256.
#
# Usage: tools/ci/smoke-cloud-backup.sh <image>
set -euo pipefail

image="$1"

docker run --rm --user 1000:1000 --entrypoint sh "$image" -euc '
w=/tmp/oc
mkdir -p "$w/data" "$w/config" "$w/exports/backups" "$w/output" "$w/remote"
export OC_DB_PATH="$w/data/openchronicle.db" OC_CONFIG_DIR="$w/config" OC_OUTPUT_DIR="$w/output"
export OC_BACKUP_DIR="$w/exports/backups" OC_MAINTENANCE_DISABLED=1
age-keygen -o "$w/identity.txt" 2>/dev/null
pub="$(age-keygen -y "$w/identity.txt")"
printf "[testlocal]\ntype = local\n" > "$w/config/rclone.conf"
export RCLONE_CONFIG="$w/config/rclone.conf"
export OC_CLOUD_REMOTE="testlocal:$w/remote" OC_CLOUD_AGE_RECIPIENTS="$pub,$pub"

oc maintenance run-once db_backup
oc maintenance run-once cloud_backup

db_age="$(ls "$w"/remote/*.db.age)"
json_age="$(ls "$w"/remote/*.json.age)"
test "$(ls "$w/remote" | wc -l)" -eq 2
age -d -i "$w/identity.txt" -o "$w/restored.db" "$db_age"
age -d -i "$w/identity.txt" -o "$w/manifest.json" "$json_age"
python - "$w/restored.db" "$w/manifest.json" <<PY
import hashlib, json, sqlite3, sys
db, manifest = sys.argv[1], json.load(open(sys.argv[2]))
digest = hashlib.sha256(open(db, "rb").read()).hexdigest()
assert digest == manifest["sha256"], (digest, manifest["sha256"])
conn = sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True)
assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
print("    ok: decrypted snapshot matches its manifest", digest[:12])
PY
# No push temp dirs left behind, and nothing cached outside the temp dir.
test -z "$(ls -d "$w"/exports/backups/cloud-push-* 2>/dev/null)"
test ! -e /.cache
'
